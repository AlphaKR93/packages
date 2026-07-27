from typing import TYPE_CHECKING, override

from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.asyncexitstack import AsyncExitStackMiddleware
from fastapi.routing import APIRouter
from starlette.applications import Starlette
from starlette.datastructures import State
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware

from .routing._routable import Routable

if __debug__ and TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from fastapi.types import IncEx
    from starlette.middleware.base import DispatchFunction
    from starlette.types import ASGIApp, ExceptionHandler


class FastAPI(Starlette, Routable):
    # noinspection PyMissingConstructor
    def __init__(
        self,
        *,
        debug = False,
        version = None,
        middleware = None,
        webhooks = None,
        exception_handlers = None,
        **kwargs
    ):
        self.debug = debug
        self.version = version
        self.webhooks = webhooks
        self.state = State()
        self.dependency_overrides = {}
        self.router: APIRouter = APIRouter(dependency_overrides_provider=self, **kwargs)
        self.exception_handlers = {} if exception_handlers is None else dict(exception_handlers)
        self.exception_handlers.setdefault(HTTPException, http_exception_handler)
        self.exception_handlers.setdefault(RequestValidationError, request_validation_exception_handler)

        self.user_middleware = [] if middleware is None else list(middleware)
        self.middleware_stack = None

    def build_middleware_stack(self, /) -> ASGIApp:
        # Duplicate/override from Starlette to add AsyncExitStackMiddleware
        # inside of ExceptionMiddleware, inside of custom user middlewares
        debug = self.debug
        error_handler = None
        exception_handlers: dict[Any, ExceptionHandler] = {}

        for key, value in self.exception_handlers.items():
            if key in (500, Exception):
                error_handler = value
            else:
                exception_handlers[key] = value

        middleware = (
            [Middleware(ServerErrorMiddleware, handler=error_handler, debug=debug)]  # ty: ignore[invalid-argument-type]
            + self.user_middleware
            + [
                Middleware(
                    ExceptionMiddleware,  # ty: ignore[invalid-argument-type]
                    handlers=exception_handlers,
                    debug=debug,
                ),
                # Add FastAPI-specific AsyncExitStackMiddleware for closing files.
                # Before this was also used for closing dependencies with yield but
                # those now have their own AsyncExitStack, to properly support
                # streaming responses while keeping compatibility with the previous
                # versions (as of writing 0.117.1) that allowed doing
                # except HTTPException inside a dependency with yield.
                # This needs to happen after user middlewares because those create a
                # new contextvars context copy by using a new AnyIO task group.
                # This AsyncExitStack preserves the context for contextvars, not
                # strictly necessary for closing files but it was one of the original
                # intentions.
                # If the AsyncExitStack lived outside of the custom middlewares and
                # contextvars were set, for example in a dependency with 'yield'
                # in that internal contextvars context, the values would not be
                # available in the outer context of the AsyncExitStack.
                # By placing the middleware and the AsyncExitStack here, inside all
                # user middlewares, the same context is used.
                # This is currently not needed, only for closing files, but used to be
                # important when dependencies with yield were closed here.
                Middleware(AsyncExitStackMiddleware),  # ty: ignore[invalid-argument-type]
            ]
        )

        app = self.router
        for cls, args, kwargs in reversed(middleware):
            app = cls(app, *args, **kwargs)
        return app

    @override
    def add_api_route(self, path: str, endpoint: Callable[..., Any], /, **kwargs):
        self.router.add_api_route(path, endpoint, **kwargs)

    def include_router(self, router, /, **kwargs):
        self.router.include_router(router, **kwargs)

    def middleware(self, /):
        def decorator(func: DispatchFunction):
            self.add_middleware(BaseHTTPMiddleware, dispatch=func)  # ty: ignore[invalid-argument-type]
            return func
        return decorator

    def exception_handler(self, status_code_or_exc_type: int | type[BaseException], /):
        def decorator(func: ExceptionHandler):
            self.add_exception_handler(status_code_or_exc_type, func)
            return func
        return decorator
