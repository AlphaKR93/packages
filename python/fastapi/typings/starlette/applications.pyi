from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Self

from .datastructures import URLPath
from .middleware import Middleware, _MiddlewareFactory
from .requests import Request
from .responses import Response
from .routing import BaseRoute
from .types import ASGIApp, ExceptionHandler, Lifespan, Receive, Scope, Send

class Starlette:
    """Creates a Starlette application."""
    def __init__(
        self: Self,
        debug: bool = ...,
        routes: Sequence[BaseRoute] | None = ...,
        middleware: Sequence[Middleware] | None = ...,
        exception_handlers: Mapping[Any, ExceptionHandler] | None = ...,
        lifespan: Lifespan[Self] | None = ...,
        *,
        max_body_size: int | None = ...,
    ) -> None:
        """Initializes the application.

        Parameters:
            debug: Boolean indicating if debug tracebacks should be returned on errors.
            routes: A list of routes to serve incoming HTTP and WebSocket requests.
            middleware: A list of middleware to run for every request. A starlette
                application will always automatically include two middleware classes.
                `ServerErrorMiddleware` is added as the very outermost middleware, to handle
                any uncaught errors occurring anywhere in the entire stack.
                `ExceptionMiddleware` is added as the very innermost middleware, to deal
                with handled exception cases occurring in the routing or endpoints.
            exception_handlers: A mapping of either integer status codes,
                or exception class types onto callables which handle the exceptions.
                Exception handler callables should be of the form
                `handler(request, exc) -> response` and may be either standard functions, or
                async functions.
            lifespan: A lifespan context function, which can be used to perform
                startup and shutdown tasks. This is a newer style that replaces the
                `on_startup` and `on_shutdown` handlers. Use one or the other, not both.
            max_body_size: Non-negative maximum total size in bytes of an HTTP request
                body. The default, `None`, does not limit request body size.
        """

    def build_middleware_stack(self) -> ASGIApp: ...
    @property
    def routes(self) -> list[BaseRoute]: ...
    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath: ...
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...
    def mount(self, path: str, app: ASGIApp, name: str | None = ...) -> None: ...
    def host(self, host: str, app: ASGIApp, name: str | None = ...) -> None: ...
    def add_middleware[**P](
        self, middleware_class: _MiddlewareFactory[P], *args: P.args, **kwargs: P.kwargs
    ) -> None: ...
    def add_exception_handler(
        self, exc_class_or_status_code: int | type[Exception], handler: ExceptionHandler
    ) -> None: ...
    def add_route(
        self,
        path: str,
        route: Callable[[Request], Awaitable[Response] | Response],
        methods: list[str] | None = ...,
        name: str | None = ...,
        include_in_schema: bool = ...,
    ) -> None: ...
