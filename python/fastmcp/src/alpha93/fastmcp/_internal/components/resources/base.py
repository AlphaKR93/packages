from typing import ClassVar, Annotated

import pydantic_core
from mcp.types import Annotations, Resource as SDKResource
from pydantic import ConfigDict, AnyUrl, UrlConstraints, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from fastmcp.resources.base import ResourceContent, ResourceResult


class Resource(FastMCPComponent):
    """Base class for all resources."""

    KEY_PREFIX: ClassVar[str] = "resource"

    model_config = ConfigDict(validate_default=True)

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
    def from_function(cls, fn: Callable[..., Any], uri: str | AnyUrl, /, **kwargs):
        from .function_resource import FunctionResource

        return FunctionResource.from_function(fn, uri, **kwargs)

    @field_validator("mime_type", mode="before")
    @classmethod
    def set_default_mime_type(cls, mime_type: str | None, /) -> str:
        """Set default MIME type if not provided."""
        if mime_type:
            return mime_type
        return "text/plain"

    @model_validator(mode="after")
    def set_default_name(self, /):
        """Set default name from URI if not provided."""
        if self.name:
            pass
        elif self.uri:
            self.name = str(self.uri)
        else:
            raise ValueError("Either name or uri must be provided")
        return self

    async def read(self, /):
        """Read the resource content.

        Subclasses implement this to return resource data. Supported return types:
            - str: Text content
            - bytes: Binary content
            - ResourceResult: Full control over contents and result-level meta
        """

    def convert_result(self, raw_value, /):
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
        from fastmcp.resources.base import ResourceContent, ResourceResult

        if isinstance(raw_value, ResourceResult):
            return raw_value

        # For plain str/bytes returns, wrap in ResourceContent with the
        # resource's MIME type and component meta so the wire response
        # carries the correct type and metadata (e.g. CSP for MCP Apps).
        if isinstance(raw_value, (str, bytes)):
            return ResourceResult([
                ResourceContent(raw_value, mime_type=self.mime_type, meta=self.meta)
            ])

        # For JSON-native types (dict, list, tuple, int, float, bool, None),
        # serialize and wrap in ResourceContent with the component's meta,
        # matching the str/bytes path above so CSP/permissions propagate.
        # Exclude list[ResourceContent] which should go through ResourceResult
        # normalization below.
        if (isinstance(raw_value, (dict, list, tuple, int, float, bool)) or raw_value is None) \
                and not (isinstance(raw_value, list) and raw_value and isinstance(raw_value[0], ResourceContent)):
            return ResourceResult([
                ResourceContent(
                    pydantic_core.to_json(raw_value),
                    mime_type=self.mime_type or "application/json",
                    meta=self.meta,
                )
            ])

        # All other types fall through to ResourceResult for error handling
        return ResourceResult(raw_value)

    async def _read(self, /, task_meta = None):
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

    def to_mcp_resource(self, /, **overrides):
        """Convert the resource to an SDKResource."""

        return SDKResource(
            name=overrides.get("name", self.name),
            uri=overrides.get("uri", self.uri),
            description=overrides.get("description", self.description),
            mimeType=overrides.get("mimeType", self.mime_type),
            title=overrides.get("title", self.title),
            icons=overrides.get("icons", self.icons),
            annotations=overrides.get("annotations", self.annotations),
            _meta=overrides.get(  # type: ignore[call-arg]  # _meta is Pydantic alias for meta field
                "_meta", self.get_meta()
            ),  # ty:ignore[unknown-argument]
        )

    def __repr__(self, /):
        return f"{self.__class__.__name__}(uri={self.uri!r}, name={self.name!r}, description={self.description!r}, tags={self.tags})"

    @property
    def key(self, /):
        base_key = self.make_key(str(self.uri))
        return f"{base_key}@{self.version or ''}"

    def get_span_attributes(self, /):
        return super().get_span_attributes() | {
            "fastmcp.component.type": "resource",
            "fastmcp.provider.type": "LocalProvider",
        }
