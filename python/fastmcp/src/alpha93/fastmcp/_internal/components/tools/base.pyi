from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar, Any, Annotated, overload
from warnings import deprecated

from mcp.types import Tool as MCPTool, ToolAnnotations, ToolExecution, Icon, CreateTaskResult
from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from fastmcp.tools.base import ToolResultSerializerType, ToolResult
from fastmcp.tools.tool_transform import ArgTransform, TransformedTool
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.tasks import TaskConfig, TaskMeta
from fastmcp.utilities.types import NotSetT, NotSet

from .function_tool import FunctionTool


class Tool(ABC, FastMCPComponent):
    """Internal tools registration info."""

    KEY_PREFIX: ClassVar[str] = "tools"

    parameters: dict[str, Any]
    """JSON schema for tools parameters"""

    output_schema: dict[str, Any] | None = None
    """JSON schema for tools output"""

    annotations: ToolAnnotations | None = None
    """Additional annotations about the tools"""

    execution: ToolExecution | None = None
    """Task execution configuration (SEP-1686)"""

    serializer: Annotated[
        SkipJsonSchema[ToolResultSerializerType | None],
        Field(deprecated=deprecated("Deprecated. Return ToolResult from your tools for full control over serialization.")),
    ] = None
    """Deprecated. Return ToolResult from your tools for full control over serialization."""

    auth: Annotated[SkipJsonSchema[AuthCheck | list[AuthCheck] | None], Field(exclude=True)] = None
    """Authorization checks for this tools"""

    timeout: float | None = None
    """Execution timeout in seconds. If None, no timeout is applied."""

    @model_validator(mode="after")
    def _validate_tool_name(self, /) -> Tool:
        """Validate tools name according to MCP specification (SEP-986)."""

    def to_mcp_tool(self, /, **overrides: Any) -> MCPTool:
        """Convert the FastMCP tools to an MCP tools."""
        title = None

        if self.title:
            title = self.title
        elif self.annotations and self.annotations.title:
            title = self.annotations.title

        mcp_tool = MCPTool(
            name=overrides.get("name", self.name),
            title=overrides.get("title", title),
            description=overrides.get("description", self.description),
            inputSchema=overrides.get("inputSchema", self.parameters),
            outputSchema=overrides.get("outputSchema", self.output_schema),
            icons=overrides.get("icons", self.icons),
            annotations=overrides.get("annotations", self.annotations),
            execution=overrides.get("execution", self.execution),
            _meta=overrides.get(  # type: ignore[call-arg]  # _meta is Pydantic alias for meta field
                "_meta", self.get_meta()
            ),  # ty:ignore[unknown-argument]
        )

        if (
                self.task_config.supports_tasks()
                and "execution" not in overrides
                and not self.execution
        ):
            mcp_tool.execution = ToolExecution(taskSupport=self.task_config.mode)

        return mcp_tool

    @classmethod
    def from_function(
            cls,
            fn: Callable[..., Any],
            *,
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: list[Icon] | None = None,
            tags: set[str] | None = None,
            annotations: ToolAnnotations | None = None,
            exclude_args: list[str] | None = None,
            output_schema: dict[str, Any] | NotSetT | None = NotSet,
            serializer: ToolResultSerializerType | None = None,  # Deprecated
            meta: dict[str, Any] | None = None,
            task: bool | TaskConfig | None = None,
            timeout: float | None = None,
            auth: AuthCheck | list[AuthCheck] | None = None,
            run_in_thread: bool | None = None,
    ) -> FunctionTool:
        """Create a Tool from a function."""

        return FunctionTool.from_function(
            fn=fn,
            name=name,
            version=version,
            title=title,
            description=description,
            icons=icons,
            tags=tags,
            annotations=annotations,
            exclude_args=exclude_args,
            output_schema=output_schema,
            serializer=serializer,
            meta=meta,
            task=task,
            timeout=timeout,
            auth=auth,
            run_in_thread=run_in_thread,
        )

    @abstractmethod
    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """
        Run the tools with arguments.

        This method is not implemented in the base Tool class and must be
        implemented by subclasses.

        `run()` can EITHER return a list of ContentBlocks, or a tuple of
        (list of ContentBlocks, dict of structured output).
        """

    def convert_result(self, raw_value: Any) -> ToolResult:
        """Convert a raw result to ToolResult.

        Handles ToolResult passthrough and converts raw values using the tools's
        attributes (serializer, output_schema) for proper conversion.
        """

    @overload
    async def _run(self, arguments: dict[str, Any], /, task_meta: None = None) -> ToolResult: ...

    @overload
    async def _run(self, arguments: dict[str, Any], /, task_meta: TaskMeta) -> CreateTaskResult: ...

    async def _run(
            self, arguments: dict[str, Any], /, task_meta: TaskMeta | None = None
    ) -> ToolResult | CreateTaskResult:
        """Server entry point that handles task routing.

        This allows ANY Tool subclass to support background execution by setting
        task_config.mode to "supported" or "required". The server calls this
        method instead of run() directly.

        Args:
            arguments: Tool arguments
            task_meta: If provided, execute as background task and return
                CreateTaskResult. If None (default), execute synchronously and
                return ToolResult.

        Returns:
            ToolResult when task_meta is None.
            CreateTaskResult when task_meta is provided.

        Subclasses can override this to customize task routing behavior.
        For example, FastMCPProviderTool overrides to delegate to child
        middleware without submitting to Docket.
        """

    @classmethod
    def from_tool(
            cls,
            tool: Tool | Callable[..., Any],
            *,
            name: str | None = None,
            title: str | NotSetT | None = NotSet,
            description: str | NotSetT | None = NotSet,
            tags: set[str] | None = None,
            annotations: ToolAnnotations | NotSetT | None = NotSet,
            output_schema: dict[str, Any] | NotSetT | None = NotSet,
            serializer: ToolResultSerializerType | None = None,  # Deprecated
            meta: dict[str, Any] | NotSetT | None = NotSet,
            transform_args: dict[str, ArgTransform] | None = None,
            transform_fn: Callable[..., Any] | None = None,
    ) -> TransformedTool:
        ...

    @classmethod
    def _ensure_tool(cls, tool: Tool | Callable[..., Any], /) -> Tool:
        """Coerce a callable into a Tool, respecting @tools decorator metadata."""

    def get_span_attributes(self, /) -> dict[str, Any]:
        ...
