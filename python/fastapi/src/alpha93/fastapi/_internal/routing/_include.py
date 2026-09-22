import threading
from contextvars import ContextVar
from dataclasses import dataclass, field

from fastapi.datastructures import Default, DefaultPlaceholder
from fastapi.utils import generate_unique_id as _default_generate_unique_id, get_value_or_default
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute, Match, Mount, NoMatchFound, Route, WebSocketRoute, compile_path, replace_params
from starlette.datastructures import URLPath

from ._route import APIRoute, APIWebSocketRoute
from ._route._route import _populate_api_route_state

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from typing import Any, Protocol

    from pydantic.main import IncEx
    from starlette.responses import Response
    from starlette.types import Receive, Scope, Send

    from alpha93.fastapi._internal._compat.v2 import ModelField
    from alpha93.fastapi._internal.dependencies.utils._solve import Dependant
    from fastapi.params import Depends
    from fastapi.types import GenerateUniqueIdFunction
    from ._router import APIRouter

    class _RouteWithPath(Protocol):
        path: str


# Scope keys used to thread lazy-include state through the ASGI scope, since
# BaseRoute.matches()/.handle() only take `scope`, no extra context.
_FASTAPI_SCOPE_KEY = "fastapi"
_FASTAPI_EFFECTIVE_ROUTE_CONTEXT_KEY = "effective_route_context"
_FASTAPI_INCLUDED_ROUTER_KEY = "included_router"

# Set while APIRoute.handle() is running under an effective (included) route
# context, so nested calls into get_route_handler() pick up the combined
# (router + route) state instead of the route's own standalone state.
_effective_route_context_var: "ContextVar[_EffectiveRouteContext | None]" = ContextVar(
    "fastapi_effective_route_context", default=None
)

_SCOPE_MISSING = object()


def _get_fastapi_scope(scope: "Scope") -> dict:
    fastapi_scope = scope.setdefault(_FASTAPI_SCOPE_KEY, {})
    assert isinstance(fastapi_scope, dict)
    return fastapi_scope


def _update_scope(scope: "Scope", child_scope: "Scope") -> None:
    fastapi_child_scope = child_scope.get(_FASTAPI_SCOPE_KEY)
    for key, value in child_scope.items():
        if key != _FASTAPI_SCOPE_KEY:
            scope[key] = value
    if isinstance(fastapi_child_scope, dict):
        _get_fastapi_scope(scope).update(fastapi_child_scope)


def _get_scope_effective_route_context(scope: "Scope") -> "_EffectiveRouteContext | None":
    return scope.get(_FASTAPI_SCOPE_KEY, {}).get(_FASTAPI_EFFECTIVE_ROUTE_CONTEXT_KEY)


def _get_scope_included_router(scope: "Scope") -> "_IncludedRouter | None":
    return scope.get(_FASTAPI_SCOPE_KEY, {}).get(_FASTAPI_INCLUDED_ROUTER_KEY)


def _restore_fastapi_scope_key(scope: "Scope", key: str, previous) -> None:
    fastapi_scope = scope.get(_FASTAPI_SCOPE_KEY)
    if not isinstance(fastapi_scope, dict):
        return
    if previous is _SCOPE_MISSING:
        fastapi_scope.pop(key, None)
    else:
        fastapi_scope[key] = previous


@dataclass
class _RouterIncludeContext:
    included_router: "APIRouter"
    prefix: str = ""
    dependencies: "list[Depends]" = field(default_factory=list)
    default_response_class: "type[Response] | DefaultPlaceholder" = field(
        default_factory=lambda: Default(JSONResponse)
    )
    callbacks: "list[BaseRoute]" = field(default_factory=list)
    generate_unique_id_function: "GenerateUniqueIdFunction | DefaultPlaceholder" = field(
        default_factory=lambda: Default(_default_generate_unique_id)
    )
    strict_content_type: "bool | DefaultPlaceholder" = field(default_factory=lambda: Default(True))
    dependency_overrides_provider: "Any | None" = None

    @classmethod
    def for_include(
        cls,
        *,
        parent_router: "APIRouter",
        included_router: "APIRouter",
        prefix: str = "",
        dependencies: "Sequence[Depends] | None" = None,
        default_response_class: "type[Response] | DefaultPlaceholder" = Default(JSONResponse),
        callbacks: "list[BaseRoute] | None" = None,
        generate_unique_id_function: "GenerateUniqueIdFunction | DefaultPlaceholder" = Default(_default_generate_unique_id),
        strict_content_type: "bool | DefaultPlaceholder" = True,
    ) -> "_RouterIncludeContext":
        return cls(
            included_router=included_router,
            prefix=parent_router.prefix + prefix,
            dependencies=[*parent_router.dependencies, *(dependencies or [])],
            default_response_class=get_value_or_default(default_response_class, parent_router.default_response),
            callbacks=[*parent_router.callbacks, *(callbacks or [])],
            generate_unique_id_function=get_value_or_default(
                generate_unique_id_function, parent_router.generate_unique_id
            ),
            strict_content_type=get_value_or_default(strict_content_type, parent_router.strict_content_type),
            dependency_overrides_provider=parent_router.dependency_overrides_provider,
        )

    def combine(self, child_context: "_RouterIncludeContext") -> "_RouterIncludeContext":
        return _RouterIncludeContext(
            included_router=child_context.included_router,
            prefix=self.prefix + child_context.prefix,
            dependencies=[*self.dependencies, *child_context.dependencies],
            default_response_class=get_value_or_default(
                child_context.default_response_class, self.default_response_class
            ),
            callbacks=[*self.callbacks, *child_context.callbacks],
            generate_unique_id_function=get_value_or_default(
                child_context.generate_unique_id_function, self.generate_unique_id_function
            ),
            strict_content_type=get_value_or_default(
                child_context.strict_content_type, self.strict_content_type
            ),
            dependency_overrides_provider=self.dependency_overrides_provider,
        )

    def path_for(self, route: "_RouteWithPath") -> str:
        return self.prefix + route.path


@dataclass
class _EffectiveRouteContext:
    original_route: "BaseRoute"
    starlette_route: "BaseRoute | None" = None
    path: str = ""
    endpoint: "Callable[..., Any] | None" = None
    stream_item_type: "Any | None" = None
    response_model: "Any" = None
    deprecated: bool | None = None
    operation_id: str | None = None
    response_model_include: "IncEx | None" = None
    response_model_exclude: "IncEx | None" = None
    response_model_by_alias: bool = True
    response_model_exclude_unset: bool = False
    response_model_exclude_defaults: bool = False
    response_model_exclude_none: bool = False
    include_in_schema: bool = True
    response_class: "type[Response] | DefaultPlaceholder" = field(default_factory=lambda: Default(JSONResponse))
    dependency_overrides_provider: "Any | None" = None
    callbacks: "list[BaseRoute] | None" = None
    generate_unique_id_function: "GenerateUniqueIdFunction | DefaultPlaceholder" = field(
        default_factory=lambda: Default(_default_generate_unique_id)
    )
    strict_content_type: "bool | DefaultPlaceholder" = field(default_factory=lambda: Default(True))
    name: str = ""
    path_regex: "Any" = None
    path_format: str = ""
    param_convertors: dict = field(default_factory=dict)
    methods: set = field(default_factory=set)
    unique_id: str = ""
    status_code: int | None = None
    response_field: "ModelField | None" = None
    stream_item_field: "ModelField | None" = None
    dependencies: "list[Depends]" = field(default_factory=list)
    dependant: "Dependant | None" = None
    _embed_body_fields: bool = False
    body_field: "ModelField | None" = None
    is_sse_stream: bool = False
    is_json_stream: bool = False

    @classmethod
    def from_api_route(
        cls,
        *,
        original_route: "APIRoute",
        include_context: "_RouterIncludeContext",
    ) -> "_EffectiveRouteContext":
        route = original_route
        context = cls(original_route=original_route)
        _populate_api_route_state(
            context,
            include_context.path_for(original_route),
            route.endpoint,
            response_model=route.response_model,
            status_code=route.status_code,
            dependencies=[*include_context.dependencies, *route.dependencies],
            deprecated=route.deprecated,
            methods=route.methods,
            operation_id=route.operation_id,
            response_model_include=route.response_model_include,
            response_model_exclude=route.response_model_exclude,
            response_model_by_alias=route.response_model_by_alias,
            response_model_exclude_unset=route.response_model_exclude_unset,
            response_model_exclude_defaults=route.response_model_exclude_defaults,
            response_model_exclude_none=route.response_model_exclude_none,
            include_in_schema=route.include_in_schema,
            response_class=get_value_or_default(
                route.response_class,
                include_context.included_router.default_response,
                include_context.default_response_class,
            ),
            name=route.name,
            callbacks=[*include_context.callbacks, *(route.callbacks or [])],
            dependency_overrides_provider=include_context.dependency_overrides_provider,
            generate_unique_id_function=get_value_or_default(
                route.generate_unique_id_function,
                include_context.included_router.generate_unique_id,
                include_context.generate_unique_id_function,
            ),
            strict_content_type=get_value_or_default(
                route.strict_content_type,
                include_context.included_router.strict_content_type,
                include_context.strict_content_type,
            ),
        )
        context.stream_item_type = route.stream_item_type
        return context

    def matches(self, scope: "Scope") -> "tuple[Match, Scope]":
        if not isinstance(self.original_route, APIRoute):
            assert self.starlette_route is not None
            return self.starlette_route.matches(scope)
        if scope["type"] != "http":
            return Match.NONE, {}
        from starlette._utils import get_route_path

        route_path = get_route_path(scope)
        match = self.path_regex.match(route_path)
        if not match:
            return Match.NONE, {}
        matched_params = match.groupdict()
        for key, value in matched_params.items():
            matched_params[key] = self.param_convertors[key].convert(value)
        path_params = dict(scope.get("path_params", {}))
        path_params.update(matched_params)
        child_scope = {"endpoint": self.endpoint, "path_params": path_params}
        methods = self.methods
        if methods and scope["method"] not in methods:
            return Match.PARTIAL, child_scope
        return Match.FULL, child_scope

    def url_path_for(self, name: str, /, **path_params) -> "Any":
        if not isinstance(self.original_route, APIRoute):
            assert self.starlette_route is not None
            return self.starlette_route.url_path_for(name, **path_params)
        seen_params = set(path_params.keys())
        param_convertors = self.param_convertors
        expected_params = set(param_convertors.keys())
        if name != self.name or seen_params != expected_params:
            raise NoMatchFound(name, path_params)
        path, remaining_params = replace_params(self.path_format, param_convertors, path_params)
        assert not remaining_params
        return URLPath(path=path, protocol="http")


@dataclass(frozen=True)
class RouteContext:
    route: "BaseRoute"
    _route_context: "_EffectiveRouteContext | None" = field(default=None, repr=False)

    @property
    def original_route(self) -> "BaseRoute":
        if self._route_context is not None:
            return self._route_context.original_route
        return self.route

    @property
    def _effective_route(self) -> "BaseRoute | _EffectiveRouteContext":
        if self._route_context is not None:
            return self._route_context
        return self.route

    @property
    def path(self) -> str | None:
        return getattr(self._effective_route, "path", None)

    @property
    def path_format(self) -> str | None:
        return getattr(self._effective_route, "path_format", None)

    @property
    def name(self) -> str | None:
        return getattr(self._effective_route, "name", None)

    @property
    def methods(self) -> set | None:
        return getattr(self._effective_route, "methods", None)

    @property
    def endpoint(self):
        return getattr(self._effective_route, "endpoint", None)

    def __getattr__(self, name: str):
        return getattr(self._effective_route, name)


@dataclass
class _IncludedRouter(BaseRoute):
    original_router: "APIRouter"
    include_context: "_RouterIncludeContext"
    _effective_routes_lock: "Any" = field(default_factory=threading.Lock, repr=False, compare=False)
    _effective_candidates: "list[_EffectiveRouteContext | _IncludedRouter]" = field(default_factory=list)
    _effective_candidates_version: int | None = None

    def effective_candidates(self) -> "list[_EffectiveRouteContext | _IncludedRouter]":
        routes_version = self.original_router._get_routes_version()
        if routes_version == self._effective_candidates_version:
            return self._effective_candidates
        with self._effective_routes_lock:
            routes_version = self.original_router._get_routes_version()
            if routes_version == self._effective_candidates_version:
                return self._effective_candidates
            effective_candidates: "list[_EffectiveRouteContext | _IncludedRouter]" = []
            for route in self.original_router.routes:
                if isinstance(route, _IncludedRouter):
                    child_context = self.include_context.combine(route.include_context)
                    child_branch = _IncludedRouter(
                        original_router=route.original_router,
                        include_context=child_context,
                    )
                    effective_candidates.append(child_branch)
                    continue
                route_context = self._build_effective_context(route)
                if route_context is not None:
                    effective_candidates.append(route_context)
            self._effective_candidates = effective_candidates
            self._effective_candidates_version = routes_version
            return effective_candidates

    def _build_effective_context(self, route: "BaseRoute") -> "_EffectiveRouteContext | None":
        if isinstance(route, APIRoute):
            return _EffectiveRouteContext.from_api_route(original_route=route, include_context=self.include_context)
        if isinstance(route, APIWebSocketRoute):
            starlette_route = APIWebSocketRoute(
                self.include_context.path_for(route),
                route.endpoint,
                name=route.name,
                dependencies=[*self.include_context.dependencies, *route.dependencies],
                dependency_overrides_provider=self.include_context.dependency_overrides_provider,
            )
            return _EffectiveRouteContext(original_route=route, starlette_route=starlette_route)
        if isinstance(route, WebSocketRoute):
            starlette_route = WebSocketRoute(self.include_context.path_for(route), route.endpoint, name=route.name)
            return _EffectiveRouteContext(original_route=route, starlette_route=starlette_route)
        if isinstance(route, Mount):
            import copy

            starlette_route = copy.copy(route)
            starlette_route.path = self.include_context.path_for(route).rstrip("/")
            (
                starlette_route.path_regex,
                starlette_route.path_format,
                starlette_route.param_convertors,
            ) = compile_path(starlette_route.path + "/{path:path}")
            return _EffectiveRouteContext(original_route=route, starlette_route=starlette_route)
        if isinstance(route, Route):
            starlette_route = Route(
                self.include_context.path_for(route),
                endpoint=route.endpoint,
                methods=list(route.methods or []),
                name=route.name,
                include_in_schema=route.include_in_schema,
            )
            return _EffectiveRouteContext(original_route=route, starlette_route=starlette_route)
        return None

    def _match(self, scope: "Scope") -> "tuple[Match, Scope, BaseRoute | None, _EffectiveRouteContext | None]":
        partial = None
        for candidate in self.effective_candidates():
            if isinstance(candidate, _IncludedRouter):
                match, child_scope = candidate.matches(scope)
                route: "BaseRoute" = candidate
                route_context = None
            elif isinstance(candidate.original_route, APIRoute):
                route_context = candidate
                fastapi_scope = _get_fastapi_scope(scope)
                previous_context = fastapi_scope.get(_FASTAPI_EFFECTIVE_ROUTE_CONTEXT_KEY, _SCOPE_MISSING)
                fastapi_scope[_FASTAPI_EFFECTIVE_ROUTE_CONTEXT_KEY] = route_context
                try:
                    match, child_scope = candidate.original_route.matches(scope)
                finally:
                    _restore_fastapi_scope_key(scope, _FASTAPI_EFFECTIVE_ROUTE_CONTEXT_KEY, previous_context)
                route = candidate.original_route
            else:
                route_context = candidate
                match, child_scope = candidate.matches(scope)
                route = candidate.starlette_route or candidate.original_route
            if match == Match.FULL:
                return match, child_scope, route, route_context
            if match == Match.PARTIAL and partial is None:
                partial = (child_scope, route, route_context)
        if partial is not None:
            child_scope, route, route_context = partial
            return Match.PARTIAL, child_scope, route, route_context
        return Match.NONE, {}, None, None

    def matches(self, scope: "Scope") -> "tuple[Match, Scope]":
        fastapi_scope = _get_fastapi_scope(scope)
        previous_router = fastapi_scope.get(_FASTAPI_INCLUDED_ROUTER_KEY, _SCOPE_MISSING)
        fastapi_scope[_FASTAPI_INCLUDED_ROUTER_KEY] = self
        try:
            match, _ = self.original_router.matches(scope)
            return match, {}
        finally:
            _restore_fastapi_scope_key(scope, _FASTAPI_INCLUDED_ROUTER_KEY, previous_router)

    async def handle(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        _get_fastapi_scope(scope)[_FASTAPI_INCLUDED_ROUTER_KEY] = self
        await self.original_router.handle(scope, receive, send)

    async def _handle_selected(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        match, child_scope, route, effective_context = self._match(scope)
        if match == Match.NONE or route is None:
            await self.original_router.default(scope, receive, send)
            return
        scope.update(child_scope)
        if isinstance(route, _IncludedRouter):
            await route.handle(scope, receive, send)
            return
        if effective_context is not None:
            _get_fastapi_scope(scope)[_FASTAPI_EFFECTIVE_ROUTE_CONTEXT_KEY] = effective_context
            original_route = effective_context.original_route
            if isinstance(original_route, APIRoute):
                scope["route"] = original_route
                await original_route.handle(scope, receive, send)
                return
        await route.handle(scope, receive, send)

    def effective_route_contexts(self) -> "Iterator[_EffectiveRouteContext]":
        for candidate in self.effective_candidates():
            if isinstance(candidate, _IncludedRouter):
                yield from candidate.effective_route_contexts()
            else:
                yield candidate

    def url_path_for(self, name: str, /, **path_params) -> "Any":
        for route_context in self.effective_route_contexts():
            try:
                return route_context.url_path_for(name, **path_params)
            except NoMatchFound:
                pass
        raise NoMatchFound(name, path_params)
