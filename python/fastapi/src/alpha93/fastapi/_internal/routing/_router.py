from contextlib import asynccontextmanager

from fastapi.datastructures import Default
from fastapi.params import Depends
from fastapi.utils import generate_unique_id as _default_generate_unique_id, get_value_or_default
from starlette.responses import Response, JSONResponse
from starlette.routing import Router, _DefaultLifespan, BaseRoute, Route

from ._route import APIRoute
from ._routable import Routable

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Sequence, AsyncIterator, Mapping
    from typing import Any

    from fastapi.types import GenerateUniqueIdFunction
    from starlette.types import ASGIApp, Lifespan


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

    def route(self, path: str, /, **kwargs):
        def decorator(func):
            self.add_route(path, func, **kwargs)
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
        response_class: type[Response] = Default(JSONResponse),
        dependencies: Sequence[Depends] | None = None,
        callbacks: list[BaseRoute] | None = None,
        generate_unique_id: GenerateUniqueIdFunction = Default(_default_generate_unique_id),
        strict_content_type: bool = Default(True),
        **kwargs,
    ) -> None:
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

    def include_router(
        self,
        router,
        /,
        prefix = "",
        dependencies = None,
        default_response = Default(JSONResponse),
        callbacks = None,
        generate_unique_id = Default(_default_generate_unique_id),
        deprecated = None,
        **kwargs,
    ) -> None:
        """
        Include another `APIRouter` in the same current `APIRouter`.

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
        if prefix:
            assert prefix.startswith("/"), "A path prefix must start with '/'"
            assert not prefix.endswith("/"), "A path prefix must not end with '/'"
        else:
            for r in router.routes:
                path = getattr(r, "path")  # noqa: B009
                assert path, f"Prefix and path cannot be both empty (path operation: {getattr(r, "name", "unknown")})"

        for route in router.routes:
            if isinstance(route, Route):
                methods = list(route.methods or [])
                self.add_route(prefix + route.path, route.endpoint, methods=methods, name=route.name)
            elif isinstance(route, APIRoute):
                router: APIRouter
                current_dependencies: list[Depends] = []
                if dependencies:
                    current_dependencies.extend(dependencies)
                if route.dependencies:
                    current_dependencies.extend(route.dependencies)

                current_callbacks = []
                if callbacks:
                    current_callbacks.extend(callbacks)
                if route.callbacks:
                    current_callbacks.extend(route.callbacks)

                response_cls = get_value_or_default(
                    route.response_class,
                    router.default_response,
                    default_response,
                    self.default_response,
                )

                current_generate_unique_id = get_value_or_default(
                    route.generate_unique_id_function,
                    router.generate_unique_id,
                    generate_unique_id,
                    self.generate_unique_id,
                )

                current_strict_content_type = get_value_or_default(
                    route.strict_content_type,
                    router.strict_content_type,
                    self.strict_content_type
                )

                self.add_api_route(
                    prefix + route.path,
                    route.endpoint,
                    response_model=route.response_model,
                    status_code=route.status_code,
                    dependencies=current_dependencies,
                    deprecated=route.deprecated or deprecated or self.deprecated,
                    methods=route.methods,
                    operation_id=route.operation_id,
                    response_model_include=route.response_model_include,
                    response_model_exclude=route.response_model_exclude,
                    response_model_by_alias=route.response_model_by_alias,
                    response_model_exclude_unset=route.response_model_exclude_unset,
                    response_model_exclude_defaults=route.response_model_exclude_defaults,
                    response_model_exclude_none=route.response_model_exclude_none,
                    response_class=response_cls,
                    name=route.name,
                    route_class=type(route),
                    callbacks=current_callbacks,
                    generate_unique_id=current_generate_unique_id,
                    strict_content_type=current_strict_content_type,
                )
        self.lifespan_context = _merge_lifespan_context(self.lifespan_context, router.lifespan_context)
