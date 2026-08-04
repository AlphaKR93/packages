from collections.abc import Callable, Sequence
from types import TracebackType
from typing import Any, Self, TypeGuard

from alpha93.commons.types import AwaitableOr

from starlette.datastructures import URLPath
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Lifespan, Receive, Scope, Send

from ._routes import BaseRoute, Route

class _DefaultLifespan[T: Router]:
    def __init__(self, router: T, /) -> None:
        ...

    def __call__(self, app: Any) -> Self:
        ...

    async def __aenter__(self) -> None:
        ...

    async def __aexit__(
        self,
        exc_type:type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None
    ):
        ...

class Router:
    routes: list[Route]
    redirect_slashes: bool
    default: ASGIApp
    lifespan_context: Lifespan[Self]
    middleware_stack: ASGIApp

    def __init__(
        self,
        routes: Sequence[BaseRoute] | None = None,
        redirect_slashes: bool = True,
        default: ASGIApp | None = None,
        # the generic to Lifespan[AppType] is the type of the top level application
        # which the router cannot know statically, so we use Any
        lifespan: Lifespan[Self] | None = None,
        *,
        middleware: Sequence[Middleware] | None = None,
    ) -> None:
        ...

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        ...

    def add_route(self, path: str, endpoint: Callable[[Request], AwaitableOr[Response]], /, **kwargs) -> None:
        ...

    def host(self, path: str, /, app: ASGIApp, name: str | None = None) -> None:
        ...

    def mount(self, path: str, /, app: ASGIApp, name: str | None = None) -> None:
        ...

    def __eq__(self, other: Any, /) -> TypeGuard[Self]:
        ...

    async def lifespan(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        ...

    async def app(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        ...

    async def not_found(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        ...
