from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar, Any, Annotated, overload

from mcp.types import Annotations, Icon, CreateTaskResult, Resource
from pydantic import Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from fastmcp.resources import ResourceResult
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.tasks import TaskConfig, TaskMeta


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
    def from_function(
            fn: Callable[..., Any],
            uri_template: str,
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: list[Icon] | None = None,
            mime_type: str | None = None,
            tags: set[str] | None = None,
            annotations: Annotations | None = None,
            meta: dict[str, Any] | None = None,
            task: bool | TaskConfig | None = None,
            auth: AuthCheck | list[AuthCheck] | None = None,
    ) -> FunctionResourceTemplate:
        ...

    @field_validator("mime_type", mode="before")
    @classmethod
    def set_default_mime_type(cls, mime_type: str | None) -> str:
        """Set default MIME type if not provided."""

    def matches(self, uri: str) -> dict[str, Any] | None:
        """Check if URI matches template and extract parameters."""

    @abstractmethod
    async def read(self, arguments: dict[str, Any]) -> str | bytes | ResourceResult:
        """Read the resource content."""

    def convert_result(self, raw_value: Any) -> ResourceResult:
        """Convert a raw result to ResourceResult.

        This is used in two contexts:
        1. In _read() to convert user function return values to ResourceResult
        2. In tasks_result_handler() to convert Docket task results to ResourceResult

        Handles ResourceResult passthrough and converts raw values using
        ResourceResult's normalization.
        """

    @overload
    async def _read(
            self, uri: str, params: dict[str, Any], task_meta: None = None
    ) -> ResourceResult: ...

    @overload
    async def _read(
            self, uri: str, params: dict[str, Any], task_meta: TaskMeta
    ) -> CreateTaskResult: ...

    async def _read(
            self, uri: str, params: dict[str, Any], task_meta: TaskMeta | None = None
    ) -> ResourceResult | CreateTaskResult:
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

    @abstractmethod
    async def create_resource(self, uri: str, params: dict[str, Any]) -> Resource:
        """Create a resource from the template with the given parameters.

        The base implementation does not support background tasks.
        Use FunctionResourceTemplate for task support.
        """

    def to_mcp_template(self, /, **overrides: Any) -> SDKResourceTemplate:
        """Convert the resource template to an SDKResourceTemplate."""

    @classmethod
    def from_mcp_template(cls, mcp_template: SDKResourceTemplate) -> ResourceTemplate:
        """Creates a FastMCP ResourceTemplate from a raw MCP ResourceTemplate object."""

    @property
    def key(self) -> str: ...

    def get_span_attributes(self) -> dict[str, Any]: ...
