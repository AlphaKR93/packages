import functools
from enum import IntEnum

from alpha93.fastapi._contextlib import AsyncExitStack
from alpha93.fastapi._internal._compat.shared import lenient_issubclass
from fastapi.datastructures import Default, DefaultPlaceholder
from fastapi.dependencies.models import _is_async_gen_callable, _is_gen_callable
from fastapi.exceptions import FastAPIError
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.utils import (
    generate_unique_id as _default_generate_unique_id,
    is_body_allowed_for_status_code,
    create_model_field
)
from starlette._exception_handler import wrap_app_handling_exceptions
from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route, get_name, compile_path, Match

from ._handler import get_request_handler
from ...dependencies.utils import (
    get_dependant,
    get_typed_return_annotation,
    get_stream_item_type,
    get_parameterless_sub_dependant,
    get_flat_dependant,
    should_embed_body_fields,
    get_body_field
)

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Sequence, Coroutine, Awaitable
    from typing import Any, Protocol

    from alpha93.commons.types import AwaitableOr
    from pydantic.main import IncEx
    from starlette.routing import BaseRoute
    from starlette.types import Scope, ASGIApp, Receive, Send

    from alpha93.fastapi._internal._compat.v2 import ModelField
    from alpha93.fastapi._internal.dependencies.utils._solve import Dependant
    from fastapi.params import Depends
    from fastapi.types import GenerateUniqueIdFunction

    class _APIRouteLike(Protocol):
        path: str
        endpoint: Callable[..., Any]
        stream_item_type: Any | None
        response_model: Any
        is_sse_stream: bool
        is_json_stream: bool
        deprecated: bool | None
        operation_id: str | None
        response_model_include: IncEx | None
        response_model_exclude: IncEx | None
        response_model_by_alias: bool
        response_model_exclude_unset: bool
        response_model_exclude_defaults: bool
        response_model_exclude_none: bool
        include_in_schema: bool
        response_class: type[Response] | DefaultPlaceholder
        dependency_overrides_provider: Any | None
        callbacks: list[BaseRoute] | None
        generate_unique_id_function: GenerateUniqueIdFunction | DefaultPlaceholder
        strict_content_type: bool | DefaultPlaceholder
        name: str
        path_regex: Any
        path_format: str
        param_convertors: dict[str, Any]
        methods: set[str]
        unique_id: str
        status_code: int | None
        response_field: ModelField | None
        stream_item_field: ModelField | None
        dependencies: list[Depends]
        dependant: Dependant
        _embed_body_fields: bool
        body_field: ModelField | None


# Copy of starlette.routing.request_response modified to include the
# dependencies' AsyncExitStack
def request_response(func: "Callable[[Request], AwaitableOr[Response]]", /) -> "ASGIApp":
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """
    f: "Callable[[Request], Awaitable[Response]]" = (
        func  # type: ignore[assignment]  # ty: ignore[unused-ignore-comment]
        if is_async_callable(func)
        else functools.partial(run_in_threadpool, func)  # type: ignore[call-arg]  # ty: ignore[unused-ignore-comment]
    )  # ty: ignore[invalid-assignment]

    async def app(scope: "Scope", receive: "Receive", send: "Send", /) -> None:
        request = Request(scope, receive, send)

        async def app(scope: "Scope", receive: "Receive", send: "Send", /) -> None:
            # Starts customization
            response_awaited = False
            async with AsyncExitStack() as request_stack:
                scope["fastapi_inner_astack"] = request_stack
                async with AsyncExitStack() as function_stack:
                    scope["fastapi_function_astack"] = function_stack
                    response = await f(request)
                await response(scope, receive, send)
                # Continues customization
                response_awaited = True
            if not response_awaited:
                raise FastAPIError(
                    "Response not awaited. There's a high chance that the "
                    "application code is raising an exception and a dependency with yield "
                    "has a block with a bare except, or a block with except Exception, "
                    "and is not raising the exception again. Read more about it in the "
                    "docs: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-except"
                )

        # Same as in Starlette
        await wrap_app_handling_exceptions(app, request)(scope, receive, send)

    return app


def _populate_api_route_state(
    route: "_APIRouteLike",
    path: str,
    endpoint: "Callable[..., Any]",
    /,
    *,
    response_model: "Any" = Default(None),
    status_code: int | None = None,
    dependencies: "Sequence[Depends] | None" = None,
    deprecated: bool | None = None,
    name: str | None = None,
    methods: set[str] | list[str] | None = None,
    operation_id: str | None = None,
    response_model_include: "IncEx | None" = None,
    response_model_exclude: "IncEx | None" = None,
    response_model_by_alias: bool = True,
    response_model_exclude_unset: bool = False,
    response_model_exclude_defaults: bool = False,
    response_model_exclude_none: bool = False,
    include_in_schema: bool = True,
    response_class: "type[Response] | DefaultPlaceholder" = Default(JSONResponse),
    callbacks: "list[BaseRoute] | None" = None,
    dependency_overrides_provider: "Any | None" = None,
    generate_unique_id_function: "GenerateUniqueIdFunction | DefaultPlaceholder" = Default(_default_generate_unique_id),
    strict_content_type: "bool | DefaultPlaceholder" = Default(True),
) -> None:
    route.endpoint = endpoint
    route.stream_item_type = None
    assert callable(endpoint), "An endpoint must be a callable"
    is_generator = _is_async_gen_callable(endpoint) or _is_gen_callable(endpoint)
    if isinstance(response_model, DefaultPlaceholder):
        return_annotation = get_typed_return_annotation(endpoint)
        if lenient_issubclass(return_annotation, Response):
            response_model = None
        else:
            stream_item = get_stream_item_type(return_annotation)
            if stream_item is not None and is_generator:
                # Extract item type for JSONL or SSE streaming when
                # response_class is DefaultPlaceholder (JSONL) or
                # EventSourceResponse (SSE).
                # ServerSentEvent is excluded: it's a transport
                # wrapper, not a data model, so it shouldn't feed
                # into validation or OpenAPI schema generation.
                if (
                    isinstance(response_class, DefaultPlaceholder)
                    or lenient_issubclass(response_class, EventSourceResponse)
                ) and not lenient_issubclass(stream_item, ServerSentEvent):
                    route.stream_item_type = stream_item
                response_model = None
            else:
                response_model = return_annotation
    route.response_model = response_model
    route.is_sse_stream = is_generator and lenient_issubclass(response_class, EventSourceResponse)
    route.deprecated = deprecated
    route.operation_id = operation_id
    route.response_model_include = response_model_include
    route.response_model_exclude = response_model_exclude
    route.response_model_by_alias = response_model_by_alias
    route.response_model_exclude_unset = response_model_exclude_unset
    route.response_model_exclude_defaults = response_model_exclude_defaults
    route.response_model_exclude_none = response_model_exclude_none
    route.include_in_schema = include_in_schema
    route.response_class = response_class
    route.dependency_overrides_provider = dependency_overrides_provider
    route.callbacks = callbacks
    route.generate_unique_id_function = generate_unique_id_function
    route.strict_content_type = strict_content_type
    route.name = name or get_name(endpoint)
    assert methods, "methods should not be empty or none"
    route.methods = {method.upper() for method in methods}
    route.path = path
    route.path_regex, route.path_format, route.param_convertors = compile_path(path)
    if operation_id:
        route.unique_id = operation_id
    else:
        current_generate_unique_id = (
            generate_unique_id_function.value
            if isinstance(generate_unique_id_function, DefaultPlaceholder)
            else generate_unique_id_function
        )
        route.unique_id = current_generate_unique_id(route)

    # normalize enums e.g. http.HTTPStatus
    if isinstance(status_code, IntEnum):
        status_code = int(status_code)
    route.status_code = status_code
    if route.response_model:
        assert is_body_allowed_for_status_code(status_code), (
            f"Status code {status_code} must not have a response body"
        )
        response_name = "Response_" + route.unique_id
        route.response_field = create_model_field(
            name=response_name,
            type_=route.response_model,
            mode="serialization",
        )
    else:
        route.response_field = None  # type: ignore  # ty: ignore[unused-ignore-comment]
    if route.stream_item_type:
        stream_item_name = "StreamItem_" + route.unique_id
        route.stream_item_field = create_model_field(
            name=stream_item_name,
            type_=route.stream_item_type,
            mode="serialization",
        )
    else:
        route.stream_item_field = None
    route.dependencies = list(dependencies or [])

    route.dependant = get_dependant(path=route.path_format, call=route.endpoint, scope="function")
    for depends in route.dependencies[::-1]:
        route.dependant.dependencies.insert(0, get_parameterless_sub_dependant(depends, path=route.path_format))
    flat_dependant = get_flat_dependant(route.dependant)
    route._embed_body_fields = should_embed_body_fields(flat_dependant.body_params)
    route.body_field = get_body_field(flat_dependant, route.unique_id, route._embed_body_fields)
    # Detect generator endpoints that should stream as JSONL
    route.is_json_stream = is_generator and isinstance(response_class, DefaultPlaceholder)


class APIRoute(Route):
    def __init__(
        self,
        path: str,
        endpoint: "Callable[..., Any]",
        /,
        *,
        response_model: "Any" = Default(None),
        status_code: int | None = None,
        dependencies: "Sequence[Depends] | None" = None,
        deprecated: bool | None = None,
        name: str | None = None,
        methods: set[str] | list[str] | None = None,
        operation_id: str | None = None,
        response_model_include: "IncEx | None" = None,
        response_model_exclude: "IncEx | None" = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        response_class: "type[Response]" = Default(JSONResponse),
        callbacks: "list[BaseRoute] | None" = None,
        dependency_overrides_provider: "Any | None" = None,
        generate_unique_id: "GenerateUniqueIdFunction" = Default(_default_generate_unique_id),
        strict_content_type: bool = Default(True),
    ) -> None:
        _populate_api_route_state(
            self,
            path,
            endpoint,
            response_model=response_model,
            status_code=status_code,
            dependencies=dependencies,
            deprecated=deprecated,
            name=name,
            methods=methods,
            operation_id=operation_id,
            response_model_include=response_model_include,
            response_model_exclude=response_model_exclude,
            response_model_by_alias=response_model_by_alias,
            response_model_exclude_unset=response_model_exclude_unset,
            response_model_exclude_defaults=response_model_exclude_defaults,
            response_model_exclude_none=response_model_exclude_none,
            include_in_schema=include_in_schema,
            response_class=response_class,
            callbacks=callbacks,
            dependency_overrides_provider=dependency_overrides_provider,
            generate_unique_id_function=generate_unique_id,
            strict_content_type=strict_content_type,
        )
        self.app = request_response(self.get_route_handler())

    def get_route_handler(self) -> "Callable[[Request], Coroutine[Any, Any, Response]]":
        from .._include import _effective_route_context_var

        route: "_APIRouteLike" = self
        effective_context = _effective_route_context_var.get()
        if effective_context is not None and effective_context.original_route is self:
            route = effective_context
        return get_request_handler(
            route.dependant,
            route.body_field,
            route.status_code,
            route.response_class,
            route.response_field,
            route.response_model_include,
            route.response_model_exclude,
            route.response_model_by_alias,
            route.response_model_exclude_unset,
            route.response_model_exclude_defaults,
            route.response_model_exclude_none,
            route.dependency_overrides_provider,
            route._embed_body_fields,
            route.strict_content_type,
            route.stream_item_field,
            route.is_json_stream,
            route.is_sse_stream,
        )

    def matches(self, scope: "Scope", /) -> "tuple[Match, Scope]":
        from .._include import _get_scope_effective_route_context

        effective_context = _get_scope_effective_route_context(scope)
        if effective_context is not None and effective_context.original_route is self:
            match, child_scope = effective_context.matches(scope)
        else:
            match, child_scope = super().matches(scope)
        if match != Match.NONE:
            child_scope["route"] = self
        return match, child_scope

    async def handle(self, scope: "Scope", receive: "Receive", send: "Send", /) -> None:
        from .._include import _effective_route_context_var, _get_scope_effective_route_context

        effective_context = _get_scope_effective_route_context(scope)
        if effective_context is not None and effective_context.original_route is self:
            methods = effective_context.methods
            if methods and scope["method"] not in methods:
                headers = {"Allow": ", ".join(methods)}
                if "app" in scope:
                    raise HTTPException(status_code=405, headers=headers)
                response = PlainTextResponse("Method Not Allowed", status_code=405, headers=headers)
                await response(scope, receive, send)
                return
            token = _effective_route_context_var.set(effective_context)
            try:
                app = request_response(self.get_route_handler())
            finally:
                _effective_route_context_var.reset(token)
            await app(scope, receive, send)
            return
        await super().handle(scope, receive, send)
