import functools
import inspect

import pydantic_core
from pydantic.json_schema import SkipJsonSchema

from fastmcp.exceptions import PromptError, FastMCPError
from fastmcp.prompts.function_prompt import logger
from fastmcp.server.dependencies import transform_context_annotations, without_injected_parameters
from fastmcp.utilities.async_utils import call_sync_fn_in_threadpool, is_coroutine_function
from fastmcp.utilities.json_schema import compress_schema
from fastmcp.utilities.tasks import TaskConfig
from fastmcp.utilities.types import get_cached_typeadapter

from .base import Prompt


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from fastmcp.prompts.base import PromptArgument, PromptResult
    from fastmcp.prompts.function_prompt import PromptMeta


class FunctionPrompt(Prompt):
    """A prompt that is a function."""

    fn: SkipJsonSchema[Callable[..., Any]]

    @classmethod
    def from_function(
            cls,
            fn: Callable[..., Any],
            /,
            metadata: PromptMeta | None = None,
            **kwargs
    ) -> FunctionPrompt:
        assert not metadata or not kwargs, \
            "Cannot pass both 'metadata' and individual parameters to from_function(). " \
            "Use metadata alone or individual parameters alone."

        # Build metadata from kwargs if not provided
        if metadata is None:
            metadata = PromptMeta(**kwargs)

        name = metadata.name or getattr(fn, "__name__", None) or getattr(fn, "__class__").__name__
        assert name != "<lambda>", "You must provide a name for lambda functions"

        # Reject functions with *args or **kwargs
        sig = inspect.signature(fn)
        for param in sig.parameters.values():
            assert param.kind != inspect.Parameter.VAR_POSITIONAL, "Positional args are not supported as prompts"
            assert param.kind != inspect.Parameter.VAR_KEYWORD, "Keyword args are not supported as prompts"

        # Parse the outer docstring (before unwrapping) to preserve the class
        # docstring as the prompt description for callable class instances.
        outer_docstring = inspect.getdoc(fn)

        # Normalize task to TaskConfig and validate
        task_value = metadata.task
        if task_value is None:
            task_config = TaskConfig(mode="forbidden")
        elif isinstance(task_value, bool):
            task_config = TaskConfig.from_bool(task_value)
        else:
            task_config = task_value
        task_config.validate_function(fn, name)

        # if the fn is a callable class, we need to get the __call__ method from here out
        if not inspect.isroutine(fn) and not isinstance(fn, functools.partial):
            fn = getattr(fn, "__call__")
        # if the fn is a staticmethod, we need to work with the underlying function
        elif isinstance(fn, staticmethod):
            fn = fn.__func__

        # For callable classes, argument descriptions must come from
        # __call__'s docstring — where the exposed parameters are actually
        # declared. The class docstring's Args section, if any, typically
        # describes __init__, so falling back to it would risk injecting
        # constructor docs into __call__'s arguments on overlapping names.
        # The description, however, comes from the class docstring (which
        # describes what the prompt IS) when present.
        description = metadata.description if metadata.description else outer_docstring or inspect.getdoc(fn)

        # Transform Context type annotations to Depends() for unified DI
        fn = transform_context_annotations(fn)

        # Wrap fn to handle dependency resolution internally
        wrapped_fn = without_injected_parameters(fn)
        parameters = compress_schema(get_cached_typeadapter(wrapped_fn).json_schema(), prune_titles=True)

        # Convert parameters to PromptArguments
        arguments: list[PromptArgument] = []
        if "properties" in parameters:
            required = parameters.get("required", [])
            for param_name, param in parameters["properties"].items():
                arg_description = param.get("description")

                # For non-string parameters, append JSON schema info to help users
                # understand the expected format when passing as strings (MCP requirement)
                if param_name in sig.parameters \
                        and (annotation := sig.parameters[param_name]) != inspect.Parameter.empty \
                        and annotation is not str:
                    # Get the JSON schema for this specific parameter type
                    try:
                        # Create compact schema representation
                        schema_str = pydantic_core.to_json(get_cached_typeadapter(annotation).json_schema())

                        # Append schema info to description
                        schema_note = f"Provide as a JSON string matching the following schema: {schema_str}"
                        arg_description = f"{arg_description}\n\n{schema_note}" if arg_description else schema_note
                    except Exception as e:
                        # If schema generation fails, skip enhancement
                        logger.debug(
                            "Failed to generate schema for prompt argument %s: %s",
                            param_name,
                            e,
                        )

                arguments.append(
                    PromptArgument(
                        name=param_name,
                        description=arg_description,
                        required=param_name in required,
                    )
                )

        return cls(
            name=name,
            version=str(metadata.version) if metadata.version else None,
            description=description,
            arguments=arguments,
            fn=wrapped_fn,
            task_config=task_config,
            title=metadata.title,
            icons=metadata.icons,
            tags=metadata.tags,
            meta=metadata.meta,
            auth=metadata.auth,
        )

    def _convert_string_arguments(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Convert string arguments to expected types based on function signature."""
        from fastmcp.server.dependencies import without_injected_parameters

        wrapper_fn = without_injected_parameters(self.fn)
        sig = inspect.signature(wrapper_fn)
        converted_kwargs = {}

        for param_name, param_value in kwargs.items():
            if param_name not in sig.parameters:
                converted_kwargs[param_name] = param_value
                continue

            annotation = sig.parameters[param_name].annotation

            # If parameter has no annotation or annotation is str, pass as-is
            if (annotation == inspect.Parameter.empty or annotation is str) or not isinstance(param_value, str):
                converted_kwargs[param_name] = param_value
                continue

            # Try to convert string argument using type adapter
            try:
                adapter = get_cached_typeadapter(annotation)
                # Try JSON parsing first for complex types
                try:
                    converted_kwargs[param_name] = adapter.validate_json(param_value)
                except (ValueError, TypeError, pydantic_core.ValidationError):
                    # Fallback to direct validation
                    converted_kwargs[param_name] = adapter.validate_python(param_value)
            except (ValueError, TypeError, pydantic_core.ValidationError) as e:
                # If conversion fails, provide informative error
                raise PromptError(
                    f"Could not convert argument '{param_name}' with value '{param_value}' "
                    f"to expected type {annotation}. Error: {e}"
                ) from e

        return converted_kwargs

    async def render(self, arguments: dict[str, Any] | None = None, /) -> PromptResult:
        # Validate required arguments
        if self.arguments:
            required = {arg.name for arg in self.arguments if arg.required}
            provided = set(arguments or {})
            missing = required - provided
            if missing:
                raise ValueError(f"Missing required arguments: {missing}")

        try:
            # Prepare arguments
            kwargs = arguments.copy() if arguments else {}

            # Convert string arguments to expected types BEFORE validation
            kwargs = self._convert_string_arguments(kwargs)

            # Filter out arguments that aren't in the function signature
            # This is important for security: dependencies should not be overridable
            # from external callers. self.fn is wrapped by without_injected_parameters,
            # so we only accept arguments that are in the wrapped function's signature.
            sig = inspect.signature(self.fn)
            valid_params = set(sig.parameters.keys())
            kwargs = {k: v for k, v in kwargs.items() if k in valid_params}

            # Use type adapter to validate arguments and handle Field() defaults
            # This matches the behavior of tools in function_tool
            type_adapter = get_cached_typeadapter(self.fn)

            # self.fn is wrapped by without_injected_parameters which handles
            # dependency resolution internally
            if is_coroutine_function(self.fn):
                result = await type_adapter.validate_python(kwargs)
            else:
                # Run sync functions in threadpool to avoid blocking the event loop
                result = await call_sync_fn_in_threadpool(type_adapter.validate_python, kwargs)
                # Handle sync wrappers that return awaitables (e.g., partial(async_fn))
                if inspect.isawaitable(result):
                    result = await result

            return self.convert_result(result)
        except FastMCPError:
            raise
        except Exception as e:
            logger.exception(f"Error rendering prompt {self.name}")
            raise PromptError(f"Error rendering prompt {self.name!r}: {e}") from e

def prompt(name_or_fn: str | Callable[..., Any] | None = None, /, *, name: str | None = None, **kwargs) -> Any:
    # INTENDED: Throw only during development; decorator errors cannot occur unexpectedly in production.
    assert not isinstance(name_or_fn, classmethod), "To decorate a classmethod, use @classmethod above @prompt. " \
                                                    "See https://gofastmcp.com/servers/prompts#using-with-methods"

    def attach_metadata(fn, prompt_name: str | None, /):
        metadata = PromptMeta(name=prompt_name, **kwargs)
        target = fn.__func__ if hasattr(fn, "__func__") else fn
        target.__fastmcp__ = metadata
        return fn

    if inspect.isroutine(name_or_fn):
        return attach_metadata(name_or_fn, name)
    elif isinstance(name_or_fn, str):
        # INTENDED: Throw only during development; decorator errors cannot occur unexpectedly in production.
        assert not name, "Cannot specify name both as first argument and keyword"
        name = name_or_fn
    else:
        raise TypeError(f"Invalid first argument: {type(name_or_fn)}")

    return lambda fn: attach_metadata(fn, name)
