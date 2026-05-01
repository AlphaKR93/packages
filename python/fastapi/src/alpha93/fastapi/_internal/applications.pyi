from collections.abc import Sequence, MutableMapping, Callable
from typing import Unpack, Self, Any, override, final, overload

from commons.types import Wrapper
from fastapi.routing import APIRouter
from fastapi.types import GenerateUniqueIdFunction
from starlette._exception_handler import ExceptionHandlers
from starlette.applications import Starlette
from starlette.datastructures import State
from starlette.middleware import Middleware
from starlette.middleware.base import DispatchFunction
from starlette.requests import Request
from starlette.types import Lifespan, ASGIApp

from .routing._routable import Routable, RouteParams
from .routing._router import RouterParameters


@final
class InitializeParameters[T : FastAPI](RouterParameters, total=False):
    debug: bool
    """
    Boolean indicating if debug tracebacks should be returned on server
    errors.

    Read more in the
    [Starlette docs for Applications](https://www.starlette.dev/applications/#instantiating-the-application).
    """

    version: str
    """
    The version of the API.

    **Note** This is the version of your application, not the version of
    the OpenAPI specification nor the version of FastAPI being used.

    It will be added to the generated OpenAPI (e.g. visible at `/docs`).

    Read more in the
    [FastAPI docs for Metadata and Docs URLs](https://fastapi.tiangolo.com/tutorial/metadata/#metadata-for-api).

    **Example**

    ```python
    from fastapi import FastAPI

    app = FastAPI(version="0.0.1")
    ```
    """

    middleware: Sequence[Middleware]
    """
    List of middleware to be added when creating the application.

    In FastAPI you would normally do this with `app.add_middleware()`
    instead.

    Read more in the
    [FastAPI docs for Middleware](https://fastapi.tiangolo.com/tutorial/middleware/).
    """

    exception_handlers: ExceptionHandlers
    """
    A dictionary with handlers for exceptions.

    In FastAPI, you would normally use the decorator
    `@app.exception_handler()`.

    Read more in the
    [FastAPI docs for Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/).
    """

    lifespan: Lifespan[T]
    """
    A `Lifespan` context manager handler. This replaces `startup` and
    `shutdown` functions with a single context manager.

    Read more in the
    [FastAPI docs for `lifespan`](https://fastapi.tiangolo.com/advanced/events/).
    """

    webhooks: APIRouter
    """
    Add OpenAPI webhooks. This is similar to `callbacks` but it doesn't
    depend on specific *path operations*.

    It will be added to the generated OpenAPI (e.g. visible at `/docs`).

    **Note**: This is available since OpenAPI 3.1.0, FastAPI 0.99.0.

    Read more about it in the
    [FastAPI docs for OpenAPI Webhooks](https://fastapi.tiangolo.com/advanced/openapi-webhooks/).
    """

class FastAPI(Starlette, Routable):
    """
    `FastAPI` app class, the main entrypoint to use FastAPI.

    Read more in the
    [FastAPI docs for First Steps](https://fastapi.tiangolo.com/tutorial/first-steps/).

    ## Example

    ```python
    from fastapi import FastAPI

    app = FastAPI()
    ```
    """

    version: str | None
    """
    The version of the API.

    Read more in the
    [FastAPI docs for Metadata and Docs URLs](https://fastapi.tiangolo.com/tutorial/metadata/#metadata-for-api).
    """

    webhooks: APIRouter | None
    """
    The `app.webhooks` attribute is an `APIRouter` with the *path
    operations* that will be used just for documentation of webhooks.

    Read more about it in the
    [FastAPI docs for OpenAPI Webhooks](https://fastapi.tiangolo.com/advanced/openapi-webhooks/).
    """

    #override
    state: State
    """
    A state object for the application. This is the same object for the
    entire application, it doesn't change from request to request.

    You normally wouldn't use this in FastAPI, for most of the cases you
    would instead use FastAPI dependencies.

    This is simply inherited from Starlette.

    Read more about it in the
    [Starlette docs for Applications](https://www.starlette.dev/applications/#storing-state-on-the-app-instance).
    """

    dependency_overrides: MutableMapping[Callable[..., Any], Callable[..., Any]]
    """
    A dictionary with overrides for the dependencies.

    Each key is the original dependency callable, and the value is the
    actual dependency that should be called.

    This is for testing, to replace expensive dependencies with testing
    versions.

    Read more about it in the
    [FastAPI docs for Testing Dependencies with Overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/).
    """

    def __init__(self, /, **kwargs: Unpack[InitializeParameters[Self]]): ...

    @override
    def build_middleware_stack(self, /) -> ASGIApp: ...

    @override
    def add_api_route(self, path: str, endpoint: Callable[..., Any], /, **kwargs: Unpack[RouteParams]): ...

    def include_router(self, router: APIRouter, /, prefix: str, **kwargs: Unpack[RouterParameters]): ...
    def attach(self, router: APIRouter, /, prefix: str, **kwargs: Unpack[RouterParameters]):
        """
        Attach an `APIRouter` in the same app.

        Read more about it in the
        [FastAPI docs for Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
        """

    def middleware[T: DispatchFunction](self, /) -> Wrapper[T]:
        """
        Add a middleware to the application.

        Read more about it in the
        [FastAPI docs for Middleware](https://fastapi.tiangolo.com/tutorial/middleware/).

        ## Example

        ```python
        import time
        from typing import Awaitable, Callable

        from fastapi import FastAPI, Request, Response

        app = FastAPI()


        @app.middleware("http")
        async def add_process_time_header(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response
        ```
        """

    @overload
    def exception_handler(self, status_code: int, /) -> Wrapper[Callable[[Request, int], Any]]: ...
    @overload
    def exception_handler[T: BaseException](self, exc_type: type[T], /) -> Wrapper[Callable[[Request, T], Any]]: ...
    @overload
    def exception_handler(
        self,
        status_code_or_exc_type: int | type[BaseException],
        /
    ) -> Wrapper[Callable[[Request, int | type[BaseException]], Any]]:
        """
        Add an exception handler to the app.

        Read more about it in the
        [FastAPI docs for Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/).

        ## Example

        ```python
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse


        class UnicornException(Exception):
            def __init__(self, name: str):
                self.name = name


        app = FastAPI()


        @app.exception_handler(UnicornException)
        async def unicorn_exception_handler(request: Request, exc: UnicornException):
            return JSONResponse(
                status_code=418,
                content={"message": f"Oops! {exc.name} did something. There goes a rainbow..."},
            )
        ```
        """
