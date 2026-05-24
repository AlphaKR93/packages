import functools
import inspect
from collections.abc import Callable
from typing import Any

from mcp.types import Annotations
from pydantic.json_schema import SkipJsonSchema

from fastmcp.resources.function_resource import ResourceMeta
from fastmcp.utilities.async_utils import is_coroutine_function, call_sync_fn_in_threadpool
from fastmcp.utilities.tasks import TaskConfig

from .base import Resource


if __debug__ and __import__("typing").TYPE_CHECKING:
    from pydantic import AnyUrl

    from fastmcp.resources.base import ResourceResult


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
            **kwargs,
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
        # Check mutual exclusion
        assert not metadata or not kwargs, "Cannot pass both 'metadata' and individual parameters to from_function(). " \
                                           "Use metadata alone or individual parameters alone."

        # Build metadata from kwargs if not provided
        if metadata is None:
            if uri is None:
                raise TypeError("uri is required when metadata is not provided")
            metadata = ResourceMeta(uri=str(uri), **kwargs)

        uri_obj = AnyUrl(metadata.uri)

        # Get function name - use class name for callable objects
        func_name = metadata.name or getattr(fn, "__name__", None) or getattr(fn, "__class__").__name__

        # Normalize task to TaskConfig and validate
        task_value = metadata.task
        if task_value is None:
            task_config = TaskConfig(mode="forbidden")
        elif isinstance(task_value, bool):
            task_config = TaskConfig.from_bool(task_value)
        else:
            task_config = task_value
        task_config.validate_function(fn, func_name)

        # if the fn is a callable class, we need to get the __call__ method from here out
        if not inspect.isroutine(fn) and not isinstance(fn, functools.partial):
            fn = getattr(fn, "__call__")
        # if the fn is a staticmethod, we need to work with the underlying function
        if isinstance(fn, staticmethod):
            fn = fn.__func__

        # Transform Context type annotations to Depends() for unified DI
        from fastmcp.server.dependencies import (
            transform_context_annotations,
            without_injected_parameters,
        )

        fn = transform_context_annotations(fn)

        # Wrap fn to handle dependency resolution internally
        wrapped_fn = without_injected_parameters(fn)

        return cls(
            fn=wrapped_fn,
            uri=uri_obj,
            name=func_name,
            version=str(metadata.version) if metadata.version is not None else None,
            title=metadata.title,
            description=metadata.description
            if metadata.description is not None
            else inspect.getdoc(fn),
            icons=metadata.icons,
            mime_type=metadata.mime_type or "text/plain",
            tags=metadata.tags or set(),
            annotations=metadata.annotations,
            meta=metadata.meta,
            task_config=task_config,
            auth=metadata.auth,
        )

    async def read(self, /) -> str | bytes | ResourceResult:
        """Read the resource by calling the wrapped function."""
        # self.fn is wrapped by without_injected_parameters which handles
        # dependency resolution internally
        if is_coroutine_function(self.fn):
            result = await self.fn()
        else:
            # Run sync functions in threadpool to avoid blocking the event loop
            result = await call_sync_fn_in_threadpool(self.fn)
            # Handle sync wrappers that return awaitables (e.g., partial(async_fn))
            if inspect.isawaitable(result):
                result = await result

        # If user returned another Resource, read it recursively
        if isinstance(result, Resource):
            return await result.read()

        return result


def resource(uri: str, /, **kwargs):
    """Standalone decorator to mark a function as an MCP resource.

    Returns the original function with metadata attached. Register with a server
    using mcp.add_resource().
    """
    assert inspect.isroutine(uri), "The @resource decorator requires a URI. Use @resource('uri') instead of @resource"

    if isinstance(kwargs["annotations"], dict):
        kwargs["annotations"] = Annotations(**kwargs["annotations"])

    def attach_metadata(fn, /):
        metadata = ResourceMeta(uri=uri, **kwargs)
        target = fn.__func__ if hasattr(fn, "__func__") else fn
        target.__fastmcp__ = metadata
        return fn

    return attach_metadata
