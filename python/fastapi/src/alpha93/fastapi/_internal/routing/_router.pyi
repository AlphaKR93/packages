from collections.abc import Sequence
from typing import TypedDict, Callable, Any, Unpack, override

from fastapi.params import Depends
from fastapi.types import GenerateUniqueIdFunction
from starlette.responses import Response
from starlette.routing import BaseRoute, Router, Route
from starlette.types import Lifespan, ASGIApp

from ._routable import Routable, RouteParams


class RouterParameters(TypedDict, total=False):
    name: str

    prefix: str
    """An optional path prefix for the router."""

    dependencies: Sequence[Depends]
    """
    A list of dependencies (using `Depends()`) to be applied to all the
    *path operations* in this router.

    Read more about it in the
    [FastAPI docs for Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/#include-an-apirouter-with-a-custom-prefix-tags-responses-and-dependencies).
    """

    default_response: type[Response]
    """
    The default response class to be used.

    Read more in the
    [FastAPI docs for Custom Response - HTML, Stream, File, others](https://fastapi.tiangolo.com/advanced/custom-response/#default-response-class).
    """

    callbacks: Sequence[BaseRoute]
    """
    OpenAPI callbacks that should apply to all *path operations* in this
    router.

    It will be added to the generated OpenAPI (e.g. visible at `/docs`).

    Read more about it in the
    [FastAPI docs for OpenAPI Callbacks](https://fastapi.tiangolo.com/advanced/openapi-callbacks/).
    """

    redirect_slashes: bool
    """
    Whether to detect and redirect slashes in URLs when the client doesn't
    use the same format.
    """

    lifespan: Lifespan
    """
    A `Lifespan` context manager handler. This replaces `startup` and
    `shutdown` functions with a single context manager.

    Read more in the
    [FastAPI docs for `lifespan`](https://fastapi.tiangolo.com/advanced/events/).
    """

    generate_unique_id: GenerateUniqueIdFunction
    """
    Customize the function used to generate unique IDs for the *path
    operations* shown in the generated OpenAPI.

    This is particularly useful when automatically generating clients or
    SDKs for your API.

    Read more about it in the
    [FastAPI docs about how to Generate Clients](https://fastapi.tiangolo.com/advanced/generate-clients/#custom-generate-unique-id-function).
    """

    strict_content_type: bool
    """
    Enable strict checking for request Content-Type headers.

    When `True` (the default), requests with a body that do not include
    a `Content-Type` header will **not** be parsed as JSON.

    This prevents potential cross-site request forgery (CSRF) attacks
    that exploit the browser's ability to send requests without a
    Content-Type header, bypassing CORS preflight checks. In particular
    applicable for apps that need to be run locally (in localhost).

    When `False`, requests without a `Content-Type` header will have
    their body parsed as JSON, which maintains compatibility with
    certain clients that don't send `Content-Type` headers.

    Read more about it in the
    [FastAPI docs for Strict Content-Type](https://fastapi.tiangolo.com/advanced/strict-content-type/).
    """

    deprecated: bool
    """
    Mark all *path operations* in this router as deprecated.

    It will be added to the generated OpenAPI (e.g. visible at `/docs`).

    Read more about it in the
    [FastAPI docs for Path Operation Configuration](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/).
    """

class APIRouter(Router, Routable):
    prefix: str
    name: str | None
    dependencies: list[Depends]
    callbacks: list[BaseRoute]
    dependency_overrides_provider: Any | None
    route_class: type[Route]
    default_response: type[Response]
    generate_unique_id: GenerateUniqueIdFunction
    strict_content_type: bool
    deprecated: bool

    def __init__(
        self,
        /,
        dependency_overrides_provider: Any = None,
        **kwargs: Unpack[RouterParameters]
    ): ...

    @override
    def add_api_route(self, path: str, endpoint: Callable[..., Any], /,  **kwargs: Unpack[RouteParams]): ...

    @override
    def include_router(self, router: Router, /, **kwargs: Unpack[RouterParameters]): ...
