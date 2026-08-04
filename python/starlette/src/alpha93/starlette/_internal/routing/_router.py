from ._match import Match, NoMatchFound
from ._utils import get_route_path

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any, Self

    from starlette.datastructures import URLPath
    from starlette.types import ASGIApp, Receive, Scope, Send


class _DefaultLifespan:
    def __init__(self, router: Router):
        self._router = router

    async def __aenter__(self) -> None:
        pass

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    def __call__(self: Self, app: object) -> Self:
        return self


class Router:
    def __init__(
        self,
        routes = None,
        redirect_slashes = True,
        default = None,
        # the generic to Lifespan[AppType] is the type of the top level application
        # which the router cannot know statically, so we use Any
        lifespan = None,
        *,
        middleware = None,
    ) -> None:
        self.routes = [] if routes is None else list(routes)
        self.redirect_slashes = redirect_slashes
        self.default = self.not_found if default is None else default
        self.lifespan_context = lifespan or _DefaultLifespan(self)

        self.middleware_stack = self.app
        if middleware:
            for cls, args, kwargs in reversed(middleware):
                self.middleware_stack = cls(self.middleware_stack, *args, **kwargs)

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        for route in self.routes:
            try:
                return route.url_path_for(name, **path_params)
            except NoMatchFound:
                pass
        raise NoMatchFound(name, path_params)

    def mount(self, path: str, /, app: ASGIApp, name: str | None = None) -> None:
        from ._routes.mount import Mount

        route = Mount(path, app=app, name=name)
        self.routes.append(route)

    def host(self, host: str, /, app: ASGIApp, name: str | None = None) -> None:
        from ._routes.host import Host

        route = Host(host, app=app, name=name)
        self.routes.append(route)

    def add_route(self, path: str, endpoint, /, **kwargs) -> None:  # pragma: no cover
        from ._routes import Route

        route = Route(path, endpoint, **kwargs)
        self.routes.append(route)

    def __eq__(self, other: Any, /) -> bool:
        return isinstance(other, Router) and self.routes == other.routes

    async def __call__(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        """
        The main entry point to the Router class.
        """
        await self.middleware_stack(scope, receive, send)

    @staticmethod
    async def not_found(scope: Scope, receive: Receive, send: Send, /) -> None:
        # If we're running inside a starlette application then raise an
        # exception, so that the configurable exception handler can deal with
        # returning the response. For plain ASGI apps, just return the response.
        if "app" in scope:
            from starlette.exceptions import HTTPException

            raise HTTPException(status_code=404)

        from starlette.responses import PlainTextResponse

        response = PlainTextResponse("Not Found", status_code=404)
        await response(scope, receive, send)

    async def lifespan(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        """
        Handle ASGI lifespan messages, which allows us to manage application
        startup and shutdown events.
        """
        started = False
        app: Any = scope.get("app")
        await receive()
        try:
            async with self.lifespan_context(app) as maybe_state:
                if maybe_state is not None:
                    if "state" not in scope:
                        raise RuntimeError('The server does not support "state" in the lifespan scope.')
                    scope["state"].update(maybe_state)
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except BaseException:
            import traceback

            exc_text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": exc_text})
            else:
                await send({"type": "lifespan.startup.failed", "message": exc_text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})

    async def app(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        assert scope["type"] == "http" or scope["type"] == "lifespan"

        if "router" not in scope:
            scope["router"] = self

        if scope["type"] == "lifespan":
            await self.lifespan(scope, receive, send)
            return

        partial = None

        for route in self.routes:
            # Determine if any route matches the incoming scope,
            # and hand over to the matching route if found.
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope.update(child_scope)
                await route.handle(scope, receive, send)
                return
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            # Handle partial matches. These are cases where an endpoint is
            # able to handle the request, but is not a preferred option.
            # We use this in particular to deal with "405 Method Not Allowed".
            scope.update(partial_scope)
            await partial.handle(scope, receive, send)
            return

        route_path = get_route_path(scope)
        if scope["type"] == "http" and self.redirect_slashes and route_path != "/":
            redirect_scope = dict(scope)
            if route_path.endswith("/"):
                redirect_scope["path"] = redirect_scope["path"].rstrip("/")
            else:
                redirect_scope["path"] = redirect_scope["path"] + "/"

            for route in self.routes:
                match, child_scope = route.matches(redirect_scope)
                if match != Match.NONE:
                    from starlette.datastructures import URL
                    from starlette.responses import RedirectResponse

                    redirect_url = URL(scope=redirect_scope)
                    response = RedirectResponse(url=str(redirect_url))
                    await response(scope, receive, send)
                    return

        await self.default(scope, receive, send)
