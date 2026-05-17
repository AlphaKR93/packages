from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar, Annotated, Self, overload

from mcp.types import Annotations, Icon, CreateTaskResult
from mcp.types import Resource as SDKResource
from pydantic import ConfigDict, UrlConstraints, Field, AnyUrl, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from fastmcp.resources import ResourceResult
from fastmcp.resources.function_resource import FunctionResource
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.tasks import TaskConfig, TaskMeta


class Resource(ABC, FastMCPComponent):
    """Base class for all resources."""

    KEY_PREFIX: ClassVar[str] = "resource"

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_default=True)

    uri: Annotated[AnyUrl, UrlConstraints(host_required=False), Field(default=...)]
    """URI of the resource"""

    name: Annotated[str, Field(default="")]
    """Name of the resource"""

    mime_type: Annotated[str, Field(default="text/plain")]
    """MIME type of the resource content"""

    annotations: Annotated[Annotations | None, Field(description="")] = None
    """Optional annotations about the resource's behavior"""

    auth: Annotated[SkipJsonSchema[AuthCheck | list[AuthCheck] | None], Field(exclude=True)]
    """Authorization checks for this resource"""

    @classmethod
    def from_function(
            cls,
            fn: Callable[..., Any],
            uri: str | AnyUrl,
            /,
            *,
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
    ) -> FunctionResource:
        ...

    @field_validator("mime_type", mode="before")
    @classmethod
    def set_default_mime_type(cls, mime_type: str | None, /) -> str:
        """Set default MIME type if not provided."""

    @model_validator(mode="after")
    def set_default_name(self, /) -> Self:
        """Set default name from URI if not provided."""

    @abstractmethod
    async def read(self, /) -> str | bytes | ResourceResult:
        """Read the resource content.

        Subclasses implement this to return resource data. Supported return types:
            - str: Text content
            - bytes: Binary content
            - ResourceResult: Full control over contents and result-level meta
        """

    def convert_result(self, raw_value: Any, /) -> ResourceResult:
        """Convert a raw result to ResourceResult.

        This is used in two contexts:
        1. In _read() to convert user function return values to ResourceResult
        2. In tasks_result_handler() to convert Docket task results to ResourceResult

        Handles ResourceResult passthrough and converts raw values using
        ResourceResult's normalization.  When the raw value is a plain
        string or bytes, the resource's own ``mime_type`` is forwarded so
        that ``ui://`` resources (and others with non-default MIME types)
        don't fall back to ``text/plain``.

        The resource's component-level ``meta`` (e.g. ``ui`` metadata for
        MCP Apps CSP/permissions) is propagated to each content item so
        that hosts can read it from the ``resources/read`` response.
        """

    @overload
    async def _read(self, /, task_meta: None = None) -> ResourceResult: ...

    @overload
    async def _read(self, /, task_meta: TaskMeta) -> CreateTaskResult: ...

    async def _read(self, /, task_meta: TaskMeta | None = None) -> ResourceResult | CreateTaskResult:
        """Server entry point that handles task routing.

        This allows ANY Resource subclass to support background execution by setting
        task_config.mode to "supported" or "required". The server calls this
        method instead of read() directly.

        Args:
            task_meta: If provided, execute as a background task and return
                CreateTaskResult. If None (default), execute synchronously and
                return ResourceResult.

        Returns:
            ResourceResult when task_meta is None.
            CreateTaskResult when task_meta is provided.

        Subclasses can override this to customize task routing behavior.
        For example, FastMCPProviderResource overrides to delegate to child
        middleware without submitting to Docket.
        """
        from fastmcp.server.tasks.routing import check_background_task

        task_result = await check_background_task(
            component=self, task_type="resource", arguments=None, task_meta=task_meta
        )
        if task_result:
            return task_result

        # Synchronous execution - convert result to ResourceResult
        result = await self.read()
        return self.convert_result(result)

    def to_mcp_resource(self, /, **overrides: Any) -> SDKResource:
        """Convert the resource to an SDKResource."""

    def __repr__(self) -> str:
        ...

    @property
    def key(self) -> str:
        ...

    def get_span_attributes(self) -> dict[str, Any]:
        ...
