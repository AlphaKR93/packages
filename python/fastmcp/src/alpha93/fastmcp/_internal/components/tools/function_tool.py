import inspect
from collections.abc import Callable
from typing import Any, Annotated

import anyio
from mcp.types import ErrorData, ToolAnnotations
from mcp.shared.exceptions import McpError
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from fastmcp.decorators import get_fastmcp_meta
from fastmcp.tools.function_tool import ToolMeta, logger
from fastmcp.utilities.async_utils import is_coroutine_function, call_sync_fn_in_threadpool
from fastmcp.utilities.tasks import TaskConfig
from fastmcp.utilities.types import NotSetT, get_cached_typeadapter, validate
from .base import Tool

if __debug__ and __import__("typing").TYPE_CHECKING:
    from fastmcp.tools.base import ToolResult


@validate
class FunctionTool(Tool):
    fn: SkipJsonSchema[Callable[..., Any]]
    return_type: Annotated[SkipJsonSchema[Any], Field(exclude=True)] = None
    run_in_thread: bool = True
    """
    Applies to sync tools functions only. When True (default), sync 
    functions are dispatched to a worker thread so they don't block 
    the event loop. Set to False to run the sync function inline on 
    the event loop thread — useful for libraries with thread 
    affinity (e.g. Windows COM, tkinter). Ignored for async functions, 
    which always run on the event loop. Cannot be combined with 
    `timeout` on a sync function: inline calls have no cancellation 
    checkpoints, so the timeout would be a silent no-op.
    """

    @classmethod
    def from_function(
            cls,
            fn: Callable[..., Any],
            /,
            metadata: ToolMeta | None = None,
            **kwargs,
    ) -> FunctionTool:
        """Create a FunctionTool from a function.

        Args:
            fn: The function to wrap
            metadata: ToolMeta object with all configuration. If provided,
                individual parameters must not be passed.
            name, title, etc.: Individual parameters for backwards compatibility.
                Cannot be used together with metadata parameter.
        """
        # Check mutual exclusion
        assert not metadata or not kwargs, "Cannot pass both 'metadata' and individual parameters to from_function(). " \
                                           "Use metadata alone or individual parameters alone."
        if not metadata and not kwargs:
            fmeta = get_fastmcp_meta(fn)
            if isinstance(fmeta, ToolMeta):
                metadata = fmeta

        # Build metadata from kwargs if not provided
        if metadata is None:
            metadata = ToolMeta(**kwargs)

        # if metadata.serializer is not None and fastmcp.settings.deprecation_warnings:
        #     warnings.warn(
        #         "The `serializer` parameter is deprecated. "
        #         "Return ToolResult from your tools for full control over serialization. "
        #         "See https://gofastmcp.com/servers/tools#custom-serialization for migration examples.",
        #         FastMCPDeprecationWarning,
        #         stacklevel=2,
        #     )
        # if metadata.exclude_args and fastmcp.settings.deprecation_warnings:
        #     warnings.warn(
        #         "The `exclude_args` parameter is deprecated as of FastMCP 2.14. "
        #         "Use dependency injection with `Depends()` instead for better lifecycle management. "
        #         "See https://gofastmcp.com/servers/dependency-injection#using-depends for examples.",
        #         FastMCPDeprecationWarning,
        #         stacklevel=2,
        #     )

        from fastmcp.tools.function_parsing import _is_object_schema, ParsedFunction

        parsed_fn = ParsedFunction.from_function(fn, exclude_args=metadata.exclude_args)
        func_name = metadata.name or parsed_fn.name
        assert func_name != "<lambda>", "You must provide a name for lambda functions"

        # Inline sync execution has no cancellation checkpoints, so
        # anyio.fail_after cannot preempt the call — the timeout would be
        # silently ignored. Reject the combination so users make an
        # explicit choice. Async generators are async even though
        # is_coroutine_function returns False for them; the generator's
        # iteration has checkpoints, so timeout enforcement still works.
        if (
                metadata.timeout is not None
                and not metadata.run_in_thread
                and not is_coroutine_function(fn)
                and not inspect.isasyncgenfunction(fn)
        ):
            raise ValueError(
                f"Tool {func_name!r}: timeout cannot be enforced when "
                "run_in_thread=False on a sync function. Inline execution has "
                "no cancellation checkpoints, so the timeout would be a no-op. "
                "Either drop the timeout or remove run_in_thread=False and "
                "accept worker-thread dispatch."
            )

        # Normalize task to TaskConfig
        task_value = metadata.task
        if task_value is None:
            task_config = TaskConfig(mode="forbidden")
        elif isinstance(task_value, bool):
            task_config = TaskConfig.from_bool(task_value)
        else:
            task_config = task_value
        task_config.validate_function(fn, func_name)

        # Handle output_schema
        if isinstance(metadata.output_schema, NotSetT):
            final_output_schema = parsed_fn.output_schema
        else:
            final_output_schema = metadata.output_schema

        if final_output_schema is not None and isinstance(final_output_schema, dict):
            if not _is_object_schema(final_output_schema):
                raise ValueError(
                    f"Output schemas must represent object types due to MCP spec limitations. "
                    f"Received: {final_output_schema!r}"
                )

        return cls(
            fn=parsed_fn.fn,
            return_type=parsed_fn.return_type,
            name=metadata.name or parsed_fn.name,
            version=str(metadata.version) if metadata.version is not None else None,
            title=metadata.title,
            description=metadata.description
            if metadata.description is not None
            else parsed_fn.description,
            icons=metadata.icons,
            parameters=parsed_fn.input_schema,
            output_schema=final_output_schema,
            annotations=metadata.annotations,
            tags=metadata.tags or set(),
            serializer=metadata.serializer,
            meta=metadata.meta,
            task_config=task_config,
            timeout=metadata.timeout,
            auth=metadata.auth,
            run_in_thread=metadata.run_in_thread,
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """Run the tools with arguments."""
        from fastmcp.server.dependencies import without_injected_parameters

        wrapper_fn = without_injected_parameters(
            self.fn, run_in_thread=self.run_in_thread
        )
        type_adapter = get_cached_typeadapter(wrapper_fn)

        # Apply timeout if configured. Combining timeout with
        # run_in_thread=False on a sync function is rejected at
        # registration (see FunctionTool.from_function), so the timeout
        # path here only needs to handle async and threadpool-sync.
        if self.timeout is not None:
            try:
                with anyio.fail_after(self.timeout):
                    # Thread pool execution for sync functions, direct await for async
                    if is_coroutine_function(wrapper_fn):
                        result = await type_adapter.validate_python(arguments)
                    else:
                        # Sync function: run in threadpool to avoid blocking
                        result = await call_sync_fn_in_threadpool(type_adapter.validate_python, arguments)
                        # Handle sync wrappers that return awaitables
                        if inspect.isawaitable(result):
                            result = await result
                    # Materialize generators inside timeout scope so slow
                    # generators don't run past the configured timeout
                    result = await self._materialize_generator(result)
            except TimeoutError:
                logger.warning(
                    f"Tool '{self.name}' timed out after {self.timeout}s. "
                    f"Consider using task=True for long-running operations. "
                    f"See https://gofastmcp.com/servers/tasks"
                )
                raise McpError(
                    ErrorData(
                        code=-32000,
                        message=f"Tool '{self.name}' execution timed out after {self.timeout}s",
                    )
                ) from None
        else:
            # No timeout: use existing execution path
            if is_coroutine_function(wrapper_fn):
                result = await type_adapter.validate_python(arguments)
            elif self.run_in_thread:
                result = await call_sync_fn_in_threadpool(
                    type_adapter.validate_python, arguments
                )
                if inspect.isawaitable(result):
                    result = await result
            else:
                result = type_adapter.validate_python(arguments)
                if inspect.isawaitable(result):
                    result = await result
            result = await self._materialize_generator(result)

        return self.convert_result(result)

    @staticmethod
    async def _materialize_generator(result: Any) -> Any:
        """Consume generators/async generators into lists.

        Without this, async generators pass through as objects (repr string),
        and sync generators get consumed during text serialization but are
        exhausted by the time structured content is built.
        """
        if inspect.isasyncgen(result):
            return [item async for item in result]
        if inspect.isgenerator(result):
            return list(result)
        return result


def tool(name_or_fn = None, /, *, name: str | None = None, **kwargs):
    assert not isinstance(name_or_fn, classmethod), "To decorate a classmethod, use @classmethod above @tools. "\
                                                    "See https://gofastmcp.com/servers/tools#using-with-methods"

    if isinstance(kwargs.get("annotations"), dict):
        kwargs["annotations"] = ToolAnnotations(**kwargs["annotations"])

    def attach_metadata(fn, tool_name):
        metadata = ToolMeta(name=tool_name, **kwargs)
        target = fn.__func__ if hasattr(fn, "__func__") else fn
        target.__fastmcp__ = metadata
        return fn

    if inspect.isroutine(name_or_fn):
        return attach_metadata(name_or_fn, name)
    elif isinstance(name_or_fn, str):
        if name is not None:
            raise TypeError("Cannot specify name both as first argument and keyword")
        name = name_or_fn
    else:
        raise TypeError(f"Invalid first argument: {type(name_or_fn)}")

    return lambda fn: attach_metadata(fn, name)
