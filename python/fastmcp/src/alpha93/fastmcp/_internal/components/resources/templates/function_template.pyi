from collections.abc import Callable
from typing import Any

from mcp.types import Icon, Annotations, Resource
from pydantic.json_schema import SkipJsonSchema

from fastmcp.resources import ResourceResult
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.tasks import TaskConfig
from .base import ResourceTemplate


class FunctionResourceTemplate(ResourceTemplate):
    """A template for dynamically creating resources."""

    fn: SkipJsonSchema[Callable[..., Any]]

    async def create_resource(self, uri: str, params: dict[str, Any]) -> Resource:
        """Create a resource from the template with the given parameters."""

    async def read(self, arguments: dict[str, Any]) -> str | bytes | ResourceResult:
        """Read the resource content."""

    @classmethod
    def from_function(
            cls,
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
        """Create a template from a function."""
