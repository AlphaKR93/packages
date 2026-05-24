import functools
import inspect
import re
from collections.abc import Callable
from typing import Any

from pydantic import validate_call
from pydantic.json_schema import SkipJsonSchema

from fastmcp.resources.template import extract_query_params
from fastmcp.server.dependencies import transform_context_annotations, without_injected_parameters
from fastmcp.utilities.json_schema import compress_schema
from fastmcp.utilities.tasks import TaskMeta, TaskConfig
from fastmcp.utilities.types import get_cached_typeadapter
from .base import ResourceTemplate
from ..base import Resource


if __debug__ and __import__("typing").TYPE_CHECKING:
    from mcp.types import CreateTaskResult

    from fastmcp.resources.base import ResourceResult


# noinspection RegExpUnnecessaryNonCapturingGroup
PATTERN = re.compile(r"{([\w-]+)(?:\*)?}")

class FunctionResourceTemplate(ResourceTemplate):
    """A template for dynamically creating resources."""

    fn: SkipJsonSchema[Callable[..., Any]]

    async def _read(
            self, uri: str, params: dict[str, Any], task_meta: TaskMeta | None = None, /
    ) -> ResourceResult | CreateTaskResult:
        from fastmcp.server.tasks.routing import check_background_task

        task_result = await check_background_task(
            component=self, task_type="template", arguments=params, task_meta=task_meta
        )
        if task_result:
            return task_result

        # Synchronous execution - call read() directly, skip resource creation
        result = await self.read(params)
        return self.convert_result(result)

    async def create_resource(self, uri: str, params: dict[str, Any], /) -> Resource:
        """Create a resource from the template with the given parameters."""

        async def resource_read_fn() -> str | bytes | ResourceResult:
            # Call function and check if result is a coroutine
            return await self.read(arguments=params)

        return Resource.from_function(
            resource_read_fn,
            uri,
            name=self.name,
            description=self.description,
            mime_type=self.mime_type,
            tags=self.tags,
            task=self.task_config,
            auth=self.auth,
        )

    async def read(self, arguments: dict[str, Any], /) -> str | bytes | ResourceResult:
        """Read the resource content."""
        # Type coercion for query parameters (which arrive as strings)
        kwargs = arguments.copy()
        sig = inspect.signature(self.fn)
        for param_name, param_value in list(kwargs.items()):
            if param_name not in sig.parameters or not isinstance(param_value, str):
                continue

            param = sig.parameters[param_name]
            annotation = param.annotation

            if annotation is inspect.Parameter.empty or annotation is str:
                continue

            try:
                if annotation is int:
                    kwargs[param_name] = int(param_value)
                elif annotation is float:
                    kwargs[param_name] = float(param_value)
                elif annotation is not bool:
                    continue

                lower = param_value.lower()
                if lower in ("true", "1", "yes"):
                    kwargs[param_name] = True
                elif lower in ("false", "0", "no"):
                    kwargs[param_name] = False
                else:
                    raise ValueError(f"Invalid boolean value for {param_name}: {param_value!r}")
            except (ValueError, AttributeError):
                raise

        # self.fn is wrapped by without_injected_parameters which handles
        # dependency resolution internally, so we call it directly
        result = self.fn(**kwargs)
        if inspect.isawaitable(result):
            result = await result

        return result

    @classmethod
    def from_function(
        cls,
        fn: Callable[..., Any],
        uri_template: str,
        /,
        *,
        version: str | int | None = None,
        task: bool | TaskConfig | None = None,
        **kwargs
    ) -> FunctionResourceTemplate:
        """Create a template from a function."""

        if not kwargs.get("name"):
            kwargs["name"] = getattr(fn, "__name__", None) or getattr(fn, "__class__").__name__
            assert kwargs["name"] != "<lambda>", "You must provide a name for lambda functions"

        # Reject functions with *args
        # (**kwargs is allowed because the URI will define the parameter names)
        sig = inspect.signature(fn)
        for param in sig.parameters.values():
            assert param.kind != inspect.Parameter.VAR_POSITIONAL, "Positional args are not supported as templates"

        # Extract path and query parameters from URI template.
        # Allow hyphens in names and normalize to underscores so they
        # match Python function parameter names.
        raw_path_params = set(re.findall(PATTERN, uri_template))
        raw_query_params = extract_query_params(uri_template)

        # Detect collisions: two raw param names that normalize to the
        # same Python identifier (e.g. {user-id} and {user_id}).
        all_raw = raw_path_params | raw_query_params
        seen: dict[str, str] = {}
        for raw_name in sorted(all_raw):
            normalized = raw_name.replace("-", "_")
            assert normalized not in seen, \
                f"URI template parameters '{seen[normalized]}' and " \
                f"'{raw_name}' both normalize to '{normalized}'. " \
                f"Use one or the other, not both."
            seen[normalized] = raw_name

        path_params = {p.replace("-", "_") for p in raw_path_params}
        query_params = {p.replace("-", "_") for p in raw_query_params}
        all_uri_params = path_params | query_params
        assert all_uri_params, "URI template must contain at least one parameter"

        # Use wrapper to get user-facing parameters (excludes injected params)

        wrapper_fn = without_injected_parameters(fn)
        user_sig = inspect.signature(wrapper_fn)
        func_params = set(user_sig.parameters.keys())

        # Get required and optional function parameters
        required_params = {
            p
            for p in func_params
            if user_sig.parameters[p].default is inspect.Parameter.empty
               and user_sig.parameters[p].kind != inspect.Parameter.VAR_KEYWORD
        }
        optional_params = {
            p
            for p in func_params
            if user_sig.parameters[p].default is not inspect.Parameter.empty
               and user_sig.parameters[p].kind != inspect.Parameter.VAR_KEYWORD
        }

        # Validate RFC 6570 query parameters
        # Query params must be optional (have defaults)
        if query_params:
            invalid_query_params = query_params - optional_params
            assert not invalid_query_params, f"Query parameters {invalid_query_params} must be " \
                                             f"optional function parameters with default values"

        # Check if required parameters are a subset of the path parameters
        assert required_params.issubset(path_params), f"Required function arguments {required_params} must be " \
                                                      "a subset of the URI path parameters {path_params}"

        # Check if all URI parameters are valid function parameters (skip if **kwargs present)
        assert any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()) \
               or all_uri_params.issubset(func_params), \
            f"URI parameters {all_uri_params} must be a subset of the function arguments: {func_params}"

        if not kwargs.get("description"):
            kwargs["description"] = inspect.getdoc(fn)
        if not kwargs.get("mime_type"):
            kwargs["mime_type"] = "text/plain"

        # Normalize task to TaskConfig and validate
        if task is None:
            task_config = TaskConfig(mode="forbidden")
        elif isinstance(task, bool):
            task_config = TaskConfig.from_bool(task)
        else:
            task_config = task
        task_config.validate_function(fn, kwargs["name"])
        kwargs["task_config"] = task_config

        # if the fn is a callable class, we need to get the __call__ method from here out
        if not inspect.isroutine(fn) and not isinstance(fn, functools.partial):
            fn = getattr(fn, "__call__")
        # if the fn is a staticmethod, we need to work with the underlying function
        if isinstance(fn, staticmethod):
            fn = fn.__func__

        # Transform Context type annotations to Depends() for unified DI
        fn = transform_context_annotations(fn)

        wrapper_fn = without_injected_parameters(fn)
        parameters = compress_schema(get_cached_typeadapter(wrapper_fn).json_schema(), prune_titles=True)

        # Use validate_call on wrapper for runtime type coercion
        fn = validate_call(wrapper_fn)

        return cls(fn=fn, uri_template=uri_template, parameters=parameters, version=str(version) if version else None, **kwargs)
