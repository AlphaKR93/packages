from enum import IntEnum

from alpha93.fastapi._contextlib import AsyncExitStack
from alpha93.fastapi._internal._compat.shared import lenient_issubclass
from fastapi.datastructures import Default, DefaultPlaceholder
from fastapi.exceptions import FastAPIError
from fastapi.utils import (
    generate_unique_id as _default_generate_unique_id,
    is_body_allowed_for_status_code,
    create_model_field
)
from starlette._exception_handler import wrap_app_handling_exceptions
from starlette._utils import is_async_callable
from starlette.responses import JSONResponse
from starlette.routing import Route, get_name, compile_path, Match

from ._handler import get_request_handler
from ...dependencies.utils import (
    get_dependant,
    get_typed_return_annotation,
    get_stream_item_type,
    get_parameterless_sub_dependant,
    get_flat_dependant,
    should_embed_body_fields,
    get_body_field
)


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Sequence, Coroutine, Awaitable
    from typing import Any

    from alpha93.fastapi._internal._compat.v2 import ModelField
    from commons.types import AwaitableOr
    from fastapi.params import Depends
    from fastapi.types import GenerateUniqueIdFunction
    from pydantic.main import IncEx
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import BaseRoute
    from starlette.types import Scope, ASGIApp, Receive, Send


# Copy of starlette.routing.request_response modified to include the
# dependencies' AsyncExitStack
def request_response(func: Callable[[Request], AwaitableOr[Response]], /) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """
    f: Callable[[Request], Awaitable[Response]] = (
        func  # type: ignore[assignment]  # ty: ignore[unused-ignore-comment]
        if is_async_callable(func)
        else functools.partial(run_in_threadpool, func)  # type: ignore[call-arg]  # ty: ignore[unused-ignore-comment]
    )  # ty: ignore[invalid-assignment]

    async def app(scope: Scope, receive: Receive, send: Send, /) -> None:
        request = Request(scope, receive, send)

        async def app(scope: Scope, receive: Receive, send: Send, /) -> None:
            # Starts customization
            response_awaited = False
            async with AsyncExitStack() as request_stack:
                scope["fastapi_inner_astack"] = request_stack
                async with AsyncExitStack() as function_stack:
                    scope["fastapi_function_astack"] = function_stack
                    response = await f(request)
                await response(scope, receive, send)
                # Continues customization
                response_awaited = True
            if not response_awaited:
                raise FastAPIError(
                    "Response not awaited. There's a high chance that the "
                    "application code is raising an exception and a dependency with yield "
                    "has a block with a bare except, or a block with except Exception, "
                    "and is not raising the exception again. Read more about it in the "
                    "docs: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-except"
                )

        # Same as in Starlette
        await wrap_app_handling_exceptions(app, request)(scope, receive, send)

    return app

class APIRoute(Route):
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        /,
        *,
        response_model: Any = Default(None),
        status_code: int | None = None,
        dependencies: Sequence[Depends] | None = None,
        deprecated: bool | None = None,
        name: str | None = None,
        methods: set[str] | list[str] | None = None,
        operation_id: str | None = None,
        response_model_include: IncEx | None = None,
        response_model_exclude: IncEx | None = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        response_class: type[Response] = Default(JSONResponse),
        callbacks: list[BaseRoute] | None = None,
        dependency_overrides_provider: Any | None = None,
        generate_unique_id: GenerateUniqueIdFunction = Default(_default_generate_unique_id),
        strict_content_type: bool = Default(True),
    ) -> None:
        self.path = path
        self.endpoint = endpoint
        self.stream_item_type: Any | None = None
        if isinstance(response_model, DefaultPlaceholder):
            return_annotation = get_typed_return_annotation(endpoint)
            if lenient_issubclass(return_annotation, Response):
                response_model = None
            else:
                stream_item = get_stream_item_type(return_annotation)
                if stream_item is not None:
                    # Extract item type for JSONL or SSE streaming when
                    # response_class is DefaultPlaceholder (JSONL) or
                    # EventSourceResponse (SSE).
                    # ServerSentEvent is excluded: it's a transport
                    # wrapper, not a data model, so it shouldn't feed
                    # into validation or OpenAPI schema generation.
                    if isinstance(response_class, DefaultPlaceholder):
                        self.stream_item_type = stream_item
                    response_model = None
                else:
                    response_model = return_annotation
        self.response_model = response_model
        self.deprecated = deprecated
        self.operation_id = operation_id
        self.response_model_include = response_model_include
        self.response_model_exclude = response_model_exclude
        self.response_model_by_alias = response_model_by_alias
        self.response_model_exclude_unset = response_model_exclude_unset
        self.response_model_exclude_defaults = response_model_exclude_defaults
        self.response_model_exclude_none = response_model_exclude_none
        self.include_in_schema = include_in_schema
        self.response_class = response_class.value if isinstance(response_class, DefaultPlaceholder) else response_class
        self.dependency_overrides_provider = dependency_overrides_provider
        self.callbacks = callbacks
        self.generate_unique_id_function = generate_unique_id
        self.strict_content_type = strict_content_type
        self.name = get_name(endpoint) if name is None else name
        self.path_regex, self.path_format, self.param_convertors = compile_path(path)
        if methods is None:
            methods = ["GET"]
        self.methods: set[str] = {method.upper() for method in methods}
        if operation_id:
            self.unique_id = operation_id
        else:
            self.unique_id = (generate_unique_id.value
                              if isinstance(generate_unique_id, DefaultPlaceholder)
                              else generate_unique_id)(self)
        # normalize enums e.g. http.HTTPStatus
        if isinstance(status_code, IntEnum):
            status_code = int(status_code)
        self.status_code = status_code
        if self.response_model:
            assert is_body_allowed_for_status_code(status_code), (
                f"Status code {status_code} must not have a response body"
            )
            response_name = "Response_" + self.unique_id
            self.response_field = create_model_field(
                name=response_name,
                type_=self.response_model,
                mode="serialization",
            )
        else:
            self.response_field = None  # type: ignore  # ty: ignore[unused-ignore-comment]
        if self.stream_item_type:
            stream_item_name = "StreamItem_" + self.unique_id
            self.stream_item_field: ModelField | None = create_model_field(
                name=stream_item_name,
                type_=self.stream_item_type,
                mode="serialization",
            )
        else:
            self.stream_item_field = None
        self.dependencies = list(dependencies or [])
        response_fields = {}
        for additional_status_code, response in self.responses.items():
            assert isinstance(response, dict), "An additional response must be a dict"
            model = response.get("model")
            if model:
                assert is_body_allowed_for_status_code(additional_status_code), (
                    f"Status code {additional_status_code} must not have a response body"
                )
                response_name = f"Response_{additional_status_code}_{self.unique_id}"
                response_field = create_model_field(
                    name=response_name, type_=model, mode="serialization"
                )
                response_fields[additional_status_code] = response_field
        if response_fields:
            self.response_fields: dict[int | str, ModelField] = response_fields
        else:
            self.response_fields = {}

        assert callable(endpoint), "An endpoint must be a callable"
        self.dependant = get_dependant(path=self.path_format, call=self.endpoint, scope="function")
        for depends in self.dependencies[::-1]:
            self.dependant.dependencies.insert(0, get_parameterless_sub_dependant(depends, path=self.path_format))
        self._flat_dependant = get_flat_dependant(self.dependant)
        self._embed_body_fields = should_embed_body_fields(self._flat_dependant.body_params)
        self.body_field = get_body_field(
            flat_dependant=self._flat_dependant,
            name=self.unique_id,
            embed_body_fields=self._embed_body_fields,
        )
        # Detect generator endpoints that should stream as JSONL
        is_generator = self.dependant.is_async_gen_callable or self.dependant.is_gen_callable
        self.is_json_stream = is_generator and isinstance(response_class, DefaultPlaceholder)
        self.app = request_response(self.get_route_handler())

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        return get_request_handler(
            self.dependant,
            self.body_field,
            self.status_code,
            self.response_class,
            self.response_field,
            self.response_model_include,
            self.response_model_exclude,
            self.response_model_by_alias,
            self.response_model_exclude_unset,
            self.response_model_exclude_defaults,
            self.response_model_exclude_none,
            self.dependency_overrides_provider,
            self._embed_body_fields,
            self.strict_content_type,
            self.stream_item_field,
            self.is_json_stream,
        )

    def matches(self, scope: Scope, /) -> tuple[Match, Scope]:
        match, child_scope = super().matches(scope)
        if match != Match.NONE:
            child_scope["route"] = self
        return match, child_scope
