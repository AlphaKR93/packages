from contextlib import asynccontextmanager

from fastapi.datastructures import Default
from fastapi.params import Depends
from fastapi.utils import generate_unique_id as _default_generate_unique_id, get_value_or_default
from starlette._utils import get_route_path
from starlette.datastructures import URL
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Match, Router, _DefaultLifespan

from ._include import _IncludedRouter, _RouterIncludeContext, _get_scope_included_router
from ._route import APIRoute, APIWebSocketRoute
from ._routable import Routable

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Sequence, AsyncIterator, Mapping
    from typing import Any

    from starlette.responses import Response
    from starlette.routing import BaseRoute
    from starlette.types import ASGIApp, Lifespan, Receive, Scope, Send

    from fastapi.types import GenerateUniqueIdFunction


def _merge_lifespan_context(original_context: Lifespan[Any], nested_context: Lifespan[Any]) -> Lifespan[Any]:
    @asynccontextmanager
    async def merged_lifespan(app: ASGIApp, /) -> AsyncIterator[Mapping[str, Any] | None]:
        async with original_context(app) as maybe_original_state:
            async with nested_context(app) as maybe_nested_state:
                if maybe_nested_state is None and maybe_original_state is None:
                    yield None  # old ASGI compatibility
                else:
                    yield {**(maybe_nested_state or {}), **(maybe_original_state or {})}

    return merged_lifespan  # type: ignore[return-value]

class APIRouter(Router, Routable):
    """
    `APIRouter` class, used to group *path operations*, for example to structure
    an app in multiple files. It would then be included in the `FastAPI` app, or
    in another `APIRouter` (ultimately included in the app).

    Read more about it in the
    [FastAPI docs for Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/).

    ## Example

    ```python
    from fastapi import APIRouter, FastAPI

    app = FastAPI()
    router = APIRouter()


    @router.get("/users/", tags=["users"])
    async def read_users():
        return [{"username": "Rick"}, {"username": "Morty"}]


    app.include_router(router)
    ```
    """

    def __init__(
        self,
        *,
        prefix = "",
        name = None,
        dependencies = None,
        default_response = Default(JSONResponse),
        callbacks = None,
        redirect_slashes = True,
        default = None,
        route_class = APIRoute,
        lifespan = None,
        deprecated = None,
        dependency_overrides_provider = None,
        generate_unique_id = Default(_default_generate_unique_id),
        strict_content_type = Default(True),
    ) -> None:
        self.lifespan_context = lifespan or _DefaultLifespan(self)

        super().__init__(
            None,
            redirect_slashes=redirect_slashes,
            default=default,
            lifespan=self.lifespan_context,
        )
        if prefix:
            assert prefix.startswith("/"), "A path prefix must start with '/'"
            assert not prefix.endswith("/"), "A path prefix must not end with '/', as the routes will start with '/'"

        self.name = name
        self.prefix = prefix
        self.dependencies = list(dependencies or [])
        self.deprecated = deprecated
        self.callbacks = callbacks or []
        self.dependency_overrides_provider = dependency_overrides_provider
        self.route_class = route_class
        self.default_response = default_response
        self.generate_unique_id = generate_unique_id
        self.strict_content_type = strict_content_type
        self._routes_version = 0

    def _mark_routes_changed(self, /) -> None:
        self._routes_version += 1

    def _get_routes_version(self, /, seen: set[int] | None = None) -> int:
        if seen is None:
            seen = set()
        router_id = id(self)
        if router_id in seen:
            return self._routes_version
        seen.add(router_id)
        version = self._routes_version
        for route in self.routes:
            if isinstance(route, _IncludedRouter):
                version += route.original_router._get_routes_version(seen)
        return version

    def _contains_router(self, router: "APIRouter", /, seen: set[int] | None = None) -> bool:
        if seen is None:
            seen = set()
        router_id = id(self)
        if router_id in seen:
            return False
        seen.add(router_id)
        for route in self.routes:
            if not isinstance(route, _IncludedRouter):
                continue
            if route.original_router is router:
                return True
            if route.original_router._contains_router(router, seen):
                return True
        return False

    def route(self, path: str, /, **kwargs):
        def decorator(func):
            self.add_route(path, func, **kwargs)
            self._mark_routes_changed()
            return func
        return decorator

    # noinspection PyMethodOverriding
    def add_api_route(
        self,
        path: str,
        endpoint: Callable[..., Any],
        /,
        *,
        route_class: type[APIRoute] | None = None,
        response_model_by_alias = True,
        response_model_exclude_unset = False,
        response_model_exclude_defaults = False,
        response_model_exclude_none = False,
        response_class: type[Response] = Default(JSONResponse),
        dependencies: Sequence[Depends] | None = None,
        callbacks: list[BaseRoute] | None = None,
        generate_unique_id: GenerateUniqueIdFunction = Default(_default_generate_unique_id),
        strict_content_type: bool = Default(True),
        **kwargs,
    ) -> None:
        kwargs.update({
            "response_model_by_alias": response_model_by_alias,
            "response_model_exclude_unset": response_model_exclude_unset,
            "response_model_exclude_defaults": response_model_exclude_defaults,
            "response_model_exclude_none": response_model_exclude_none,
        })

        cls = route_class or self.route_class
        kwargs["response_class"] = get_value_or_default(response_class, self.default_response)
        kwargs["generate_unique_id"] = get_value_or_default(generate_unique_id, self.generate_unique_id)
        kwargs["strict_content_type"] = get_value_or_default(strict_content_type, self.strict_content_type)

        current_dependencies = self.dependencies.copy()
        if dependencies:
            current_dependencies.extend(dependencies)
        kwargs["dependencies"] = current_dependencies

        current_callbacks = self.callbacks.copy()
        if callbacks:
            current_callbacks.extend(callbacks)
        kwargs["callbacks"] = current_callbacks

        route = cls(self.prefix + path, endpoint, **kwargs)
        self.routes.append(route)
        self._mark_routes_changed()

    def add_api_websocket_route(
        self,
        path: str,
        endpoint: Callable[..., Any],
        /,
        *,
        name: str | None = None,
        dependencies: Sequence[Depends] | None = None,
    ) -> None:
        current_dependencies = self.dependencies.copy()
        if dependencies:
            current_dependencies.extend(dependencies)

        route = APIWebSocketRoute(
            self.prefix + path,
            endpoint,
            name=name,
            dependencies=current_dependencies,
            dependency_overrides_provider=self.dependency_overrides_provider,
        )
        self.routes.append(route)
        self._mark_routes_changed()

    def include_router(
        self,
        router: "APIRouter",
        /,
        prefix = "",
        dependencies = None,
        callbacks = None,
        default_response = Default(JSONResponse),
        generate_unique_id = Default(_default_generate_unique_id),
        strict_content_type = True,
        **kwargs,
    ) -> None:
        """
        Include another `APIRouter` in the same current `APIRouter`.

        This is lazy: routes contributed by `router` are resolved on demand
        (and re-resolved whenever `router`'s own routes change), instead of
        being eagerly cloned into `self.routes` at include time.

        Read more about it in the
        [FastAPI docs for Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/).

        ## Example

        ```python
        from fastapi import APIRouter, FastAPI

        app = FastAPI()
        internal_router = APIRouter()
        users_router = APIRouter()

        @users_router.get("/users/")
        def read_users():
            return [{"name": "Rick"}, {"name": "Morty"}]

        internal_router.include_router(users_router)
        app.include_router(internal_router)
        ```
        """
        assert self is not router, "Cannot include the same APIRouter instance into itself"
        assert not router._contains_router(self), (
            "Cannot include an APIRouter instance that already includes this router"
        )
        if prefix:
            assert prefix.startswith("/"), "A path prefix must start with '/'"
            assert not prefix.endswith("/"), "A path prefix must not end with '/'"
        else:
            for r in router.routes:
                path = getattr(r, "path")  # noqa: B009
                assert path, f"Prefix and path cannot be both empty (path operation: {getattr(r, "name", "unknown")})"

        include_context = _RouterIncludeContext.for_include(
            parent_router=self,
            included_router=router,
            prefix=prefix,
            dependencies=dependencies,
            default_response_class=default_response,
            callbacks=callbacks,
            generate_unique_id_function=generate_unique_id,
            strict_content_type=strict_content_type,
        )
        self.routes.append(_IncludedRouter(original_router=router, include_context=include_context))
        self._mark_routes_changed()
        self.lifespan_context = _merge_lifespan_context(self.lifespan_context, router.lifespan_context)

    async def app(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        # Same as starlette.routing.Router.app, but without the redirect_slashes
        # low-priority pass that upstream added for frontend fallback routes
        # (not supported by this fork).
        assert scope["type"] in ("http", "websocket", "lifespan")

        if "router" not in scope:
            scope["router"] = self

        if scope["type"] == "lifespan":
            await self.lifespan(scope, receive, send)
            return

        partial = None
        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope.update(child_scope)
                await route.handle(scope, receive, send)
                return
            if match == Match.PARTIAL and partial is None:
                partial = (route, child_scope)

        if partial is not None:
            route, child_scope = partial
            scope.update(child_scope)
            await route.handle(scope, receive, send)
            return

        route_path = get_route_path(scope)
        if scope["type"] == "http" and self.redirect_slashes and route_path != "/":
            redirect_scope = dict(scope)
            if route_path.endswith("/"):
                redirect_scope["path"] = redirect_scope["path"].rstrip("/")
            else:
                redirect_scope["path"] = redirect_scope["path"] + "/"

            for route in self.routes:
                match, _ = route.matches(redirect_scope)
                if match != Match.NONE:
                    redirect_url = URL(scope=redirect_scope)
                    response = RedirectResponse(url=str(redirect_url))
                    await response(scope, receive, send)
                    return

        await self.default(scope, receive, send)

    async def handle(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        included_router = _get_scope_included_router(scope)
        if isinstance(included_router, _IncludedRouter) and included_router.original_router is self:
            await included_router._handle_selected(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def matches(self, scope: Scope, /) -> tuple[Match, Scope]:
        included_router = _get_scope_included_router(scope)
        if isinstance(included_router, _IncludedRouter) and included_router.original_router is self:
            match, child_scope, _, _ = included_router._match(scope)
            return match, child_scope
        return Match.NONE, {}
