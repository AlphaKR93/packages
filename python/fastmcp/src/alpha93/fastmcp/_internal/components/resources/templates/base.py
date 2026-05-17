from abc import ABC, abstractmethod
from typing import ClassVar, Annotated, Any

from mcp.types import Annotations
from pydantic import Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from fastmcp.resources import ResourceResult
from fastmcp.resources.template import match_uri_template
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent

from .function_template import FunctionResourceTemplate


class ResourceTemplate(ABC, FastMCPComponent):
    """A template for dynamically creating resources."""

    KEY_PREFIX: ClassVar[str] = "template"

    uri_template: str
    """URI template with parameters (e.g. weather://{city}/current)"""

    mime_type: str = "text/plain"
    """MIME type of the resource content"""

    parameters: dict[str, Any]
    """JSON schema for function parameters"""

    annotations: Annotations | None = None
    """Optional annotations about the resource's behavior"""

    auth: Annotated[SkipJsonSchema[AuthCheck | list[AuthCheck] | None], Field(exclude=True)] = None
    """Authorization checks for this resource template"""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(uri_template={self.uri_template!r}, name={self.name!r}, description={self.description!r}, tags={self.tags})"

    @staticmethod
    def from_function(**kwargs) -> FunctionResourceTemplate:
        return FunctionResourceTemplate.from_function(**kwargs)

    @field_validator("mime_type", mode="before")
    @classmethod
    def set_default_mime_type(cls, mime_type: str | None) -> str:
        """Set default MIME type if not provided."""
        if mime_type:
            return mime_type
        return "text/plain"

    def matches(self, uri: str) -> dict[str, Any] | None:
        """Check if URI matches template and extract parameters."""
        return match_uri_template(uri, self.uri_template)

    async def read(self, arguments: dict[str, Any]) -> str | bytes | ResourceResult:
        """Read the resource content."""
        raise NotImplementedError(
            "Subclasses must implement read() or override create_resource()"
        )

    def convert_result(self, raw_value: Any) -> ResourceResult:
        """Convert a raw result to ResourceResult.

        This is used in two contexts:
        1. In _read() to convert user function return values to ResourceResult
        2. In tasks_result_handler() to convert Docket task results to ResourceResult

        Handles ResourceResult passthrough and converts raw values using
        ResourceResult's normalization.
        """
        if isinstance(raw_value, ResourceResult):
            return raw_value

        # ResourceResult.__init__ handles all normalization
        return ResourceResult(raw_value)

    async def _read(
            self, uri: str, params: dict[str, Any], /, task_meta: TaskMeta | None = None
    ) -> ResourceResult | mcp.types.CreateTaskResult:
        """Server entry point that handles task routing.

        This allows ANY ResourceTemplate subclass to support background execution
        by setting task_config.mode to "supported" or "required". The server calls
        this method instead of create_resource()/read() directly.

        Args:
            uri: The concrete URI being read
            params: Template parameters extracted from the URI
            task_meta: If provided, execute as a background task and return
                CreateTaskResult. If None (default), execute synchronously and
                return ResourceResult.

        Returns:
            ResourceResult when task_meta is None.
            CreateTaskResult when task_meta is provided.

        Subclasses can override this to customize task routing behavior.
        For example, FastMCPProviderResourceTemplate overrides to delegate to child
        middleware without submitting to Docket.
        """
        from fastmcp.server.tasks.routing import check_background_task

        task_result = await check_background_task(
            component=self, task_type="template", arguments=params, task_meta=task_meta
        )
        if task_result:
            return task_result

        # Synchronous execution - create resource and read directly
        # Call resource.read() not resource._read() to avoid task routing on ephemeral resource
        resource = await self.create_resource(uri, params)
        result = await resource.read()
        return self.convert_result(result)

    @abstractmethod
    async def create_resource(self, uri: str, params: dict[str, Any]) -> Resource:
        """Create a resource from the template with the given parameters.

        The base implementation does not support background tasks.
        Use FunctionResourceTemplate for task support.
        """

    def to_mcp_template(
            self,
            **overrides: Any,
    ) -> SDKResourceTemplate:
        """Convert the resource template to an SDKResourceTemplate."""

        return SDKResourceTemplate(
            name=overrides.get("name", self.name),
            uriTemplate=overrides.get("uriTemplate", self.uri_template),
            description=overrides.get("description", self.description),
            mimeType=overrides.get("mimeType", self.mime_type),
            title=overrides.get("title", self.title),
            icons=overrides.get("icons", self.icons),
            annotations=overrides.get("annotations", self.annotations),
            _meta=overrides.get(  # type: ignore[call-arg]  # _meta is Pydantic alias for meta field
                "_meta", self.get_meta()
            ),  # ty:ignore[unknown-argument]
        )

    @classmethod
    def from_mcp_template(cls, mcp_template: SDKResourceTemplate) -> ResourceTemplate:
        """Creates a FastMCP ResourceTemplate from a raw MCP ResourceTemplate object."""
        # Note: This creates a simple ResourceTemplate instance. For function-based templates,
        # the original function is lost, which is expected for remote templates.
        return cls(
            uri_template=mcp_template.uriTemplate,
            name=mcp_template.name,
            description=mcp_template.description,
            mime_type=mcp_template.mimeType or "text/plain",
            parameters={},  # Remote templates don't have local parameters
        )

    @property
    def key(self) -> str:
        """The globally unique lookup key for this template."""
        base_key = self.make_key(self.uri_template)
        return f"{base_key}@{self.version or ''}"

    def get_span_attributes(self) -> dict[str, Any]:
        return super().get_span_attributes() | {
            "fastmcp.component.type": "resource_template",
            "fastmcp.provider.type": "LocalProvider",
        }
