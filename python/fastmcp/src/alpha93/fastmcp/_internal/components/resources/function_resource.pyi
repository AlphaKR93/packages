from collections.abc import Callable
from typing import Any, override

from mcp.types import Icon, Annotations
from pydantic import AnyUrl
from pydantic.json_schema import SkipJsonSchema

from fastmcp.resources import ResourceResult
from fastmcp.resources.function_resource import ResourceMeta
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.tasks import TaskConfig
from .base import Resource


class FunctionResource(Resource):
    """A resource that defers data loading by wrapping a function.

    The function is only called when the resource is read, allowing for lazy loading
    of potentially expensive data. This is particularly useful when listing resources,
    as the function won't be called until the resource is actually accessed.

    The function can return:
    - str for text content (default)
    - bytes for binary content
    - other types will be converted to JSON
    """

    fn: SkipJsonSchema[Callable[..., Any]]

    @classmethod
    def from_function(
            cls,
            fn: Callable[..., Any],
            uri: str | AnyUrl | None = None,
            /,
            metadata: ResourceMeta | None = None,
            *,
            # Keep individual params for backwards compat
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
        """Create a FunctionResource from a function.

        Args:
            fn: The function to wrap
            uri: The URI for the resource (required if metadata not provided)
            metadata: ResourceMeta object with all configuration. If provided,
                individual parameters must not be passed.
            name, title, etc.: Individual parameters for backwards compatibility.
                Cannot be used together with metadata parameter.
        """

    @override
    async def read(self, /) -> str | bytes | ResourceResult:
        ...


def resource[F](
        uri: str,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: list[Icon] | None = None,
        mime_type: str | None = None,
        tags: set[str] | None = None,
        annotations: Annotations | dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: AuthCheck | list[AuthCheck] | None = None,
) -> Callable[[F], F]:
    """Standalone decorator to mark a function as an MCP resource.

    Returns the original function with metadata attached. Register with a server
    using mcp.add_resource().
    """
