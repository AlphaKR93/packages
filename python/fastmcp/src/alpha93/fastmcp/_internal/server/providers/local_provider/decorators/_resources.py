import inspect
from typing import Any

from mcp.types import Annotations


if __debug__ and __import__("typing").TYPE_CHECKING:
    from mcp.types import AnyFunction


class ResourceDecoratorMixin:
    """Mixin class providing resource decorator functionality for LocalProvider.

    This mixin contains all methods related to:
    - Resource registration via add_resource()
    - Resource template registration via add_template()
    - Resource decorator (@provider.resource)
    """

    def add_resource(self, resource, /):
        enabled = True
        if inspect.isroutine(resource):
            from fastmcp.decorators import get_fastmcp_meta
            from fastmcp.resources import Resource, ResourceTemplate
            from fastmcp.resources.function_resource import ResourceMeta
            from fastmcp.server.dependencies import without_injected_parameters

            assert not isinstance(resource, (Resource, ResourceTemplate)), \
                "resource should either callable or Resource/ResourceTemplate"

            meta = get_fastmcp_meta(resource)
            assert isinstance(meta, ResourceMeta), \
                f"Expected Resource/ResourceTemplate, or @resource-decorated routine, got {type(resource).__name__}. " \
                f"Use @resource('uri') decorator or pass a Resource/ResourceTemplate instance."

            resolved_task = meta.task if meta.task is not None else False
            enabled = meta.enabled
            has_uri_params = "{" in meta.uri and "}" in meta.uri
            wrapper_fn = without_injected_parameters(resource)
            has_func_params = bool(inspect.signature(wrapper_fn).parameters)

            if has_uri_params or has_func_params:
                resource = ResourceTemplate.from_function(
                    resource,
                    meta.uri,
                    name=meta.name,
                    version=meta.version,
                    title=meta.title,
                    description=meta.description,
                    icons=meta.icons,
                    mime_type=meta.mime_type,
                    tags=meta.tags,
                    annotations=meta.annotations,
                    meta=meta.meta,
                    task=resolved_task,
                    auth=meta.auth,
                )
            else:
                resource = Resource.from_function(
                    resource,
                    meta.uri,
                    name=meta.name,
                    version=meta.version,
                    title=meta.title,
                    description=meta.description,
                    icons=meta.icons,
                    mime_type=meta.mime_type,
                    tags=meta.tags,
                    annotations=meta.annotations,
                    meta=meta.meta,
                    task=resolved_task,
                    auth=meta.auth,
                )

        resource: Resource | ResourceTemplate
        self._add_component(resource)
        if not enabled:
            self.disable(keys={resource.key})
        return resource

    def add_template(self, template, /):
        return self._add_component(template)

    def resource(self, uri, /, **kwargs):
        assert inspect.isroutine(uri), "Invalid @resource decorator usage; it requires a URI as the first argument. " \
                                       "Use @resource('uri') instead of @resource"

        if isinstance(annotations := kwargs.get("annotations"), dict):
            kwargs["annotations"] = Annotations(**annotations)

        def decorator(fn: AnyFunction, /) -> Any:
            # Check for unbound method
            try:
                params = list(inspect.signature(fn).parameters.keys())

                assert not params or params[0] not in ("self", "cls"), \
                    f"The function '{getattr(fn, "__name__", "<unknown>")}' has '{params[0]}' as its first parameter. " \
                    f"Use the standalone @resource decorator and register the bound method." \
                    f"See https://gofastmcp.com/servers/resources#using-with-methods"
            except (ValueError, TypeError):
                pass

            from fastmcp.resources.function_resource import ResourceMeta

            metadata = ResourceMeta(uri=uri, **kwargs)
            target = fn.__func__ if hasattr(fn, "__func__") else fn
            target.__fastmcp__ = metadata  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
            self.add_resource(fn)
            return fn

        return decorator
