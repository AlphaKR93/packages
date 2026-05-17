from collections.abc import Callable
from typing import Any, Annotated, override, overload

from fastmcp.tools.base import ToolResultSerializerType, ToolResult
from mcp.types import Icon, ToolAnnotations
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from fastmcp.tools.function_tool import ToolMeta
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.tasks import TaskConfig
from fastmcp.utilities.types import NotSetT, NotSet
from .base import Tool


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
            *,
            metadata: ToolMeta | None = None,
            # Keep individual params for backwards compat
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: list[Icon] | None = None,
            tags: set[str] | None = None,
            annotations: ToolAnnotations | None = None,
            exclude_args: list[str] | None = None,
            output_schema: dict[str, Any] | NotSetT | None = NotSet,
            serializer: ToolResultSerializerType | None = None,
            meta: dict[str, Any] | None = None,
            task: bool | TaskConfig | None = None,
            timeout: float | None = None,
            auth: AuthCheck | list[AuthCheck] | None = None,
            run_in_thread: bool | None = None,
    ) -> FunctionTool:
        """Create a FunctionTool from a function.

        Args:
            fn: The function to wrap
            metadata: ToolMeta object with all configuration. If provided,
                individual parameters must not be passed.
            name, title, etc.: Individual parameters for backwards compatibility.
                Cannot be used together with metadata parameter.
        """

    @override
    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ...


@overload
def tool[F: Callable](fn: F) -> F: ...
@overload
def tool[F: Callable](
        name_or_fn: str,
        *,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: list[Icon] | None = None,
        tags: set[str] | None = None,
        output_schema: dict[str, Any] | NotSetT | None = NotSet,
        annotations: ToolAnnotations | dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        exclude_args: list[str] | None = None,
        serializer: Any | None = None,
        timeout: float | None = None,
        auth: AuthCheck | list[AuthCheck] | None = None,
        run_in_thread: bool = True,
) -> Callable[[F], F]: ...
@overload
def tool[F: Callable](
        name_or_fn: None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: list[Icon] | None = None,
        tags: set[str] | None = None,
        output_schema: dict[str, Any] | NotSetT | None = NotSet,
        annotations: ToolAnnotations | dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        exclude_args: list[str] | None = None,
        serializer: Any | None = None,
        timeout: float | None = None,
        auth: AuthCheck | list[AuthCheck] | None = None,
        run_in_thread: bool = True,
) -> Callable[[F], F]: ...


@overload
def tool[F: Callable](
        name_or_fn: F | str | None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: list[Icon] | None = None,
        tags: set[str] | None = None,
        output_schema: dict[str, Any] | NotSetT | None = NotSet,
        annotations: ToolAnnotations | dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        exclude_args: list[str] | None = None,
        serializer: Any | None = None,
        timeout: float | None = None,
        auth: AuthCheck | list[AuthCheck] | None = None,
        run_in_thread: bool = True,
) -> Any:
    """Standalone decorator to mark a function as an MCP tools.

    Returns the original function with metadata attached. Register with a server
    using mcp.add_tool().

    Args:
        run_in_thread: Applies to sync tools functions only. When True (default),
            the sync function is dispatched to a worker thread so it does not
            block the event loop. Set to False to run the function inline on the
            event loop thread — useful for libraries with thread affinity
            (e.g. Windows COM via `uiautomation`/`comtypes`/`pywin32`, `tkinter`,
            some GPU/driver bindings). Ignored for async functions. Cannot be
            combined with `timeout` on a sync function: inline calls have no
            cancellation checkpoints, so the timeout would be a silent no-op.
    """
