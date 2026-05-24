"""Resource decorator mixin for LocalProvider.

This module provides the ResourceDecoratorMixin class that adds resource
and template registration functionality to LocalProvider.
"""
from collections.abc import Callable, Sequence, Mapping, Iterable
from typing import Any

from commons.types import SequenceOr
from mcp.types import Icon, Annotations

from fastmcp.resources import Resource, ResourceTemplate
from fastmcp.server.providers import LocalProvider
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.tasks import TaskConfig


class ResourceDecoratorMixin:
    """Mixin class providing resource decorator functionality for LocalProvider.

    This mixin contains all methods related to:
    - Resource registration via add_resource()
    - Resource template registration via add_template()
    - Resource decorator (@provider.resource)
    """

    def add_resource(
        self: LocalProvider, resource: Resource | ResourceTemplate | Callable[..., Any]
    ) -> Resource | ResourceTemplate:
        """
        Add a resource to this provider's storage.

        Accepts either a Resource/ResourceTemplate object or a decorated function with __fastmcp__ metadata.
        """

    def add_template(self: LocalProvider, template: ResourceTemplate) -> ResourceTemplate:
        """Add a resource template to this provider's storage."""

    def resource[F: Callable](
        self: LocalProvider,
        uri: str,
        /,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: Sequence[Icon] | None = None,
        mime_type: str | None = None,
        tags: Iterable[str] | None = None,
        enabled: bool = True,
        annotations: Annotations | Mapping[str, Any] | None = None,
        meta: Mapping[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: SequenceOr[AuthCheck] | None = None,
    ) -> Callable[[F], F]:
        """Decorator to register a function as a resource.

        If the URI contains parameters (e.g. "resource://{param}") or the function
        has parameters, it will be registered as a template resource.

        Args:
            uri: URI for the resource (e.g. "resource://my-resource" or "resource://{param}")
            name: Optional name for the resource
            title: Optional title for the resource
            description: Optional description of the resource
            icons: Optional icons for the resource
            mime_type: Optional MIME type for the resource
            tags: Optional set of tags for categorizing the resource
            enabled: Whether the resource is enabled (default True). If False, adds to blocklist.
            annotations: Optional annotations about the resource's behavior
            meta: Optional meta information about the resource
            task: Optional task configuration for background execution
            auth: Optional authorization checks for the resource

        Returns:
            A decorator function.

        Example:
            ```python
            provider = LocalProvider()

            @provider.resource("data://config")
            def get_config() -> str:
                return '{"setting": "value"}'

            @provider.resource("data://{city}/weather")
            def get_weather(city: str) -> str:
                return f"Weather for {city}"
            ```
        """
