"""Tool decorator mixin for LocalProvider.

This module provides the ToolDecoratorMixin class that adds tool
registration functionality to LocalProvider.
"""
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import partial
from typing import Any, overload

from commons.types import SequenceOr
from mcp.types import Icon, ToolAnnotations, AnyFunction

from fastmcp.tools import FunctionTool, Tool
from fastmcp.server.providers import LocalProvider
from fastmcp.tools.base import ToolResultSerializerType
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.tasks import TaskConfig
from fastmcp.utilities.types import NotSetT, NotSet


class ToolDecoratorMixin:
    """Mixin class providing tool decorator functionality for LocalProvider.

    This mixin contains all methods related to:
    - Tool registration via add_tool()
    - Tool decorator (@provider.tool)
    """

    def add_tool(self: LocalProvider, tool: Tool | Callable[..., Any], /):
        """Add a tool to this provider's storage.

        Accepts either a Tool object or a decorated function with __fastmcp__ metadata.
        """

    @overload
    def tool[F: Callable](
        self: LocalProvider,
        name_or_fn: F,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: Sequence[Icon] | None = None,
        tags: Iterable[str] | None = None,
        output_schema: Mapping[str, Any] | NotSetT | None = NotSet,
        annotations: ToolAnnotations | Mapping[str, Any] | None = None,
        exclude_args: Sequence[str] | None = None,
        meta: Mapping[str, Any] | None = None,
        enabled: bool = True,
        task: bool | TaskConfig | None = None,
        timeout: float | None = None,
        auth: SequenceOr[AuthCheck] | None = None,
        run_in_thread: bool = True,
    ) -> F: ...

    @overload
    def tool[F: Callable](
        self: LocalProvider,
        name_or_fn: str | None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: Sequence[Icon] | None = None,
        tags: Iterable[str] | None = None,
        output_schema: Mapping[str, Any] | NotSetT | None = NotSet,
        annotations: ToolAnnotations | Mapping[str, Any] | None = None,
        exclude_args: Sequence[str] | None = None,
        meta: Mapping[str, Any] | None = None,
        enabled: bool = True,
        task: bool | TaskConfig | None = None,
        timeout: float | None = None,
        auth: SequenceOr[AuthCheck] | None = None,
        run_in_thread: bool = True,
    ) -> Callable[[F], F]: ...

    # NOTE: This method mirrors fastmcp.tools.tool() but adds registration,
    # the `enabled` param, and supports deprecated params (serializer, exclude_args).
    # When deprecated params are removed, this should delegate to the standalone
    # decorator to reduce duplication.
    def tool(
        self: LocalProvider,
        name_or_fn: str | AnyFunction | None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: Sequence[Icon] | None = None,
        tags: Iterable[str] | None = None,
        output_schema: Mapping[str, Any] | NotSetT | None = NotSet,
        annotations: ToolAnnotations | Mapping[str, Any] | None = None,
        exclude_args: Sequence[str] | None = None,
        meta: Mapping[str, Any] | None = None,
        enabled: bool = True,
        task: bool | TaskConfig | None = None,
        timeout: float | None = None,
        auth: SequenceOr[AuthCheck] | None = None,
        run_in_thread: bool = True,
    ) -> (
        Callable[[AnyFunction], FunctionTool]
        | FunctionTool
        | partial[Callable[[AnyFunction], FunctionTool] | FunctionTool]
    ):
        """Decorator to register a tool.

        This decorator supports multiple calling patterns:
        - @provider.tool (without parentheses)
        - @provider.tool() (with empty parentheses)
        - @provider.tool("custom_name") (with name as first argument)
        - @provider.tool(name="custom_name") (with name as keyword argument)
        - provider.tool(function, name="custom_name") (direct function call)

        Args:
            name_or_fn: Either a function (when used as @tool), a string name, or None
            name: Optional name for the tool (keyword-only, alternative to name_or_fn)
            title: Optional title for the tool
            description: Optional description of what the tool does
            icons: Optional icons for the tool
            tags: Optional set of tags for categorizing the tool
            output_schema: Optional JSON schema for the tool's output
            annotations: Optional annotations about the tool's behavior
            exclude_args: Optional list of argument names to exclude from the tool schema
            meta: Optional meta information about the tool
            enabled: Whether the tool is enabled (default True). If False, adds to blocklist.
            task: Optional task configuration for background execution
            serializer: Deprecated. Return ToolResult from your tools for full control over serialization.

        Returns:
            The registered FunctionTool or a decorator function.

        Example:
            ```python
            provider = LocalProvider()

            @provider.tool
            def greet(name: str) -> str:
                return f"Hello, {name}!"

            @provider.tool("custom_name")
            def my_tool(x: int) -> str:
                return str(x)
            ```
        """
