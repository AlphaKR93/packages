from collections.abc import Callable
from typing import ClassVar, Annotated, Any
from warnings import deprecated

import pydantic_core
from mcp.shared.tool_name_validation import validate_and_warn_tool_name
from mcp.types import ContentBlock, Tool as MCPTool, ToolAnnotations, ToolExecution
from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from fastmcp.tools.base import ToolResult, ToolResultSerializerType, _convert_to_content
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.types import File, Image, Audio, validate

if __debug__ and __import__("typing").TYPE_CHECKING:
    from mcp.types import CreateTaskResult

    from fastmcp.tools.tool_transform import TransformedTool
    from fastmcp.utilities.tasks import TaskMeta


@validate
class Tool(FastMCPComponent):
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
        validate_and_warn_tool_name(self.name)
        return self

    def to_mcp_tool(self, /, **overrides) -> MCPTool:
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
    def from_function(cls, fn, /, **kwargs):
        """Create a Tool from a function."""
        from .function_tool import FunctionTool

        return FunctionTool.from_function(fn, **kwargs)

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """
        Run the tools with arguments.

        This method is not implemented in the base Tool class and must be
        implemented by subclasses.

        `run()` can EITHER return a list of ContentBlocks, or a tuple of
        (list of ContentBlocks, dict of structured output).
        """

    def convert_result(self, raw_value, /) -> ToolResult:
        """Convert a raw result to ToolResult.

        Handles ToolResult passthrough and converts raw values using the tools's
        attributes (serializer, output_schema) for proper conversion.
        """
        if isinstance(raw_value, ToolResult):
            return raw_value

        content = _convert_to_content(raw_value, serializer=self.serializer)

        # Bytes can't be represented as structured JSON content
        if isinstance(raw_value, bytes):
            return ToolResult(content=content)

        # Skip structured content for ContentBlock types only if no output_schema
        # (if output_schema exists, MCP SDK requires structured_content)
        if self.output_schema is None and (
                isinstance(raw_value, (ContentBlock, Audio, Image, File))
                or (
                        isinstance(raw_value, list | tuple)
                        and any(isinstance(item, ContentBlock) for item in raw_value)
                )
        ):
            return ToolResult(content=content)

        try:
            structured = pydantic_core.to_jsonable_python(raw_value)
        except (pydantic_core.PydanticSerializationError, UnicodeDecodeError):
            return ToolResult(content=content)

        if self.output_schema is None:
            # No schema - only use structured_content for dicts
            if isinstance(structured, dict):
                return ToolResult(content=content, structured_content=structured)
            return ToolResult(content=content)

        # Has output_schema - wrap if x-fastmcp-wrap-result is set
        wrap_result = self.output_schema.get("x-fastmcp-wrap-result")
        return ToolResult(
            content=content,
            structured_content={"result": structured} if wrap_result else structured,
            meta={"fastmcp": {"wrap_result": True}} if wrap_result else None,
        )

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
        from fastmcp.server.tasks.routing import check_background_task

        task_result = await check_background_task(
            component=self,
            task_type="tool",
            arguments=arguments,
            task_meta=task_meta,
        )
        if task_result:
            return task_result

        return await self.run(arguments)

    @classmethod
    def from_tool(cls, tool: Tool | Callable[..., Any], /, **kwargs) -> TransformedTool:
        from fastmcp.tools.tool_transform import TransformedTool

        tool = cls._ensure_tool(tool)
        return TransformedTool.from_tool(tool, **kwargs)

    @classmethod
    def _ensure_tool(cls, tool: Tool | Callable[..., Any], /) -> Tool:
        """Coerce a callable into a Tool, respecting @tools decorator metadata."""
        if isinstance(tool, Tool):
            return tool

        from fastmcp.decorators import get_fastmcp_meta
        from fastmcp.tools.function_tool import ToolMeta
        from .function_tool import FunctionTool

        fmeta = get_fastmcp_meta(tool)
        if isinstance(fmeta, ToolMeta):
            return FunctionTool.from_function(tool, metadata=fmeta)

        return cls.from_function(tool)

    def get_span_attributes(self) -> dict[str, Any]:
        return super().get_span_attributes() | {
            "fastmcp.component.type": "tools",
            "fastmcp.provider.type": "LocalProvider",
        }
