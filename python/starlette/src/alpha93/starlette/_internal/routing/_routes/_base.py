import functools
import inspect

from alpha93.commons import typed

from starlette._exception_handler import wrap_app_handling_exceptions
from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import URLPath
from starlette.requests import Request

from .._match import Match, NoMatchFound
from .._utils import get_route_path
from ._abc import BaseRoute

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection, Sequence
    from typing import Any, Final

    from alpha93.commons.types import AwaitableOr

    from starlette.middleware import Middleware
    from starlette.responses import Response
    from starlette.types import ASGIApp, Receive, Scope, Send


get_name: Final[Callable[[Callable[..., Any]], str]] = \
    lambda endpoint, /: typed[str].getattr(endpoint, "__name__", type(endpoint).__name__)

def request_response(func: Callable[[Request], AwaitableOr[Response]], /) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """
    f: Callable[[Request], Awaitable[Response]] = (
        func if is_async_callable(func) else functools.partial(run_in_threadpool, func)
    )

    async def app(scope: Scope, receive: Receive, send: Send, /) -> None:
        request = Request(scope, receive, send)

        async def catcher(scope: Scope, receive: Receive, send: Send, /) -> None:
            response = await f(request)
            await response(scope, receive, send)

        await wrap_app_handling_exceptions(catcher, request)(scope, receive, send)

    return app


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        /,
        endpoint: Callable[..., Any],
        *,
        methods: Collection[str] | None = None,
        name: str | None = None,
        middleware: Sequence[Middleware] | None = None,
    ) -> None:
        assert path.startswith("/"), "Routed paths must start with '/'"
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func
        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            # Endpoint is function or method. Treat it as `func(request) -> response`.
            self.app = request_response(endpoint)
            if methods is None:
                methods = ["GET"]
        else:
            # Endpoint is a class. Treat it as ASGI.
            self.app = endpoint

        if middleware is not None:
            for cls, args, kwargs in reversed(middleware):
                self.app = cls(self.app, *args, **kwargs)

        if methods is None:
            self.methods = None
        else:
            self.methods = {method.upper() for method in methods}
            if "GET" in self.methods:
                self.methods.add("HEAD")

        self.path_regex, self.path_format, self.param_convertors = self.compile_path(path)

    def matches(self, scope: Scope, /) -> tuple[Match, Scope]:
        path_params: dict[str, Any]
        if scope["type"] == "http":
            route_path = get_route_path(scope)
            match = self.path_regex.match(route_path)
            if match:
                matched_params = match.groupdict()
                for key, value in matched_params.items():
                    matched_params[key] = self.param_convertors[key].convert(value)
                path_params = dict(scope.get("path_params", {}))
                path_params.update(matched_params)
                child_scope = {"endpoint": self.endpoint, "path_params": path_params}
                if self.methods and scope["method"] not in self.methods:
                    return Match.PARTIAL, child_scope
                else:
                    return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        seen_params = set(path_params.keys())
        expected_params = set(self.param_convertors.keys())

        if name != self.name or seen_params != expected_params:
            raise NoMatchFound(name, path_params)

        path, remaining_params = self.replace_params(self.path_format, self.param_convertors, path_params)
        assert not remaining_params
        return URLPath(path=path, protocol="http")

    async def handle(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        if self.methods and scope["method"] not in self.methods:
            headers = {"Allow": ", ".join(self.methods)}
            if "app" in scope:
                from starlette.exceptions import HTTPException

                raise HTTPException(status_code=405, headers=headers)
            else:
                from starlette.responses import PlainTextResponse

                response = PlainTextResponse("Method Not Allowed", status_code=405, headers=headers)
            await response(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    def __eq__(self, other: Any, /) -> bool:
        return (
            isinstance(other, Route)
            and self.path == other.path
            and self.endpoint == other.endpoint
            and self.methods == other.methods
        )

    def __repr__(self, /) -> str:
        class_name = self.__class__.__name__
        methods = sorted(self.methods or [])
        path, name = self.path, self.name
        return f"{class_name}(path={path!r}, name={name!r}, methods={methods!r})"
