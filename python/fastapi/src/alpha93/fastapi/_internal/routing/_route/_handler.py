import email
import inspect
import json
from collections.abc import Callable, Coroutine, AsyncIterator, Iterator
from logging import warning
from typing import Any

import anyio
from alpha93.fastapi._contextlib import AsyncExitStack
from alpha93.fastapi._internal._compat.v2 import ModelField
from alpha93.fastapi._internal.dependencies.utils import solve_dependencies
from fastapi.datastructures import DefaultPlaceholder
from fastapi.dependencies.models import Dependant
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException, EndpointContext, RequestValidationError, ResponseValidationError
from fastapi.utils import is_body_allowed_for_status_code
from pydantic.main import IncEx
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Mapping

    from alpha93.fastapi._internal.dependencies.utils._solve import SolvedDependency


# Cache for endpoint context to avoid re-extracting on every request
_endpoint_context_cache: dict[int, EndpointContext] = {}
def _extract_endpoint_context(func: Any) -> EndpointContext:
    """Extract endpoint context with caching to avoid repeated file I/O."""
    func_id = id(func)

    if func_id in _endpoint_context_cache:
        return _endpoint_context_cache[func_id]

    try:
        ctx: EndpointContext = {}

        if (source_file := inspect.getsourcefile(func)) is not None:
            ctx["file"] = source_file
        if (line_number := inspect.getsourcelines(func)[1]) is not None:
            ctx["line"] = line_number
        if (func_name := getattr(func, "__name__", None)) is not None:
            ctx["function"] = func_name
    except Exception:
        ctx = EndpointContext()

    _endpoint_context_cache[func_id] = ctx
    return ctx

def _build_response_args(
    *, status_code: int | None, solved_result: Any
) -> dict[str, Any]:
    response_args: dict[str, Any] = {
        "background": solved_result.background_tasks,
    }
    # If status_code was set, use it, otherwise use the default from the
    # response class, in the case of redirect it's 307
    current_status_code = (
        status_code if status_code else solved_result.response.status_code
    )
    if current_status_code is not None:
        response_args["status_code"] = current_status_code
    if solved_result.response.status_code:
        response_args["status_code"] = solved_result.response.status_code
    return response_args

async def serialize_response(
    *,
    field: ModelField | None = None,
    response_content: Any,
    include: IncEx | None = None,
    exclude: IncEx | None = None,
    by_alias: bool = True,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    is_coroutine: bool = True,
    endpoint_ctx: EndpointContext | None = None,
    dump_json: bool = False,
) -> Any:
    if field:
        if is_coroutine:
            value, errors = field.validate(response_content, {}, loc=("response",))
        else:
            value, errors = await run_in_threadpool(
                field.validate, response_content, {}, loc=("response",)
            )
        if errors:
            ctx = endpoint_ctx or EndpointContext()
            raise ResponseValidationError(
                errors=errors,
                body=response_content,
                endpoint_ctx=ctx,
            )
        serializer = field.serialize_json if dump_json else field.serialize
        return serializer(
            value,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    else:
        return jsonable_encoder(response_content)

async def _extract_body(request: Request, endpoint_ctx: EndpointContext, strict_content_type: bool, /):
    try:
        body_bytes = await request.body()
        if not body_bytes:
            return None

        content_type = request.headers.get("content-type")
        if not content_type and not strict_content_type:
            return await request.json()

        message = email.message.Message()
        message["content-type"] = content_type
        if message.get_content_maintype() == "application":
            subtype = message.get_content_subtype()
            if subtype == "json" or subtype.endswith("+json"):
                return await request.json()

        return body_bytes
    except HTTPException:
        # If a middleware raises an HTTPException, it should be raised again
        raise
    except json.JSONDecodeError as e:
        errors = [{
            "type": "json_invalid",
            "loc": ("body", e.pos),
            "msg": "JSON decode error",
            "input": {},
            "ctx": {"error": e.msg},
        }]
        raise RequestValidationError(errors, body=e.doc, endpoint_ctx=endpoint_ctx) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail="There was an error parsing the body") from e

def get_request_handler(
    dependant: Dependant,
    body_field: ModelField | None,
    status_code: int | None,
    response_class: type[Response] | DefaultPlaceholder[type[Response]],
    response_field: ModelField | None,
    response_model_include: IncEx | None,
    response_model_exclude: IncEx | None,
    response_model_by_alias: bool,
    response_model_exclude_unset: bool,
    response_model_exclude_defaults: bool,
    response_model_exclude_none: bool,
    dependency_overrides_provider: Any | None,
    embed_body_fields: bool,
    strict_content_type: bool,
    stream_item_field: ModelField | None,
    is_json_stream: bool,
) -> Callable[[Request], Coroutine[Any, Any, Response]]:
    assert dependant.call is not None, "dependant.call must be a function"
    response_class: type[Response] = response_class.value if isinstance(response_class, DefaultPlaceholder) \
        else response_class

    async def solve(request: Request, endpoint_ctx: EndpointContext, /):
        # Solve dependencies and run path operation function, auto-closing dependencies
        async_exit_stack = request.scope.get("fastapi_inner_astack")
        assert isinstance(async_exit_stack, AsyncExitStack), "fastapi_inner_astack not found in request scope"

        body = await _extract_body(request, endpoint_ctx, strict_content_type) if body_field else None

        solved_result = await solve_dependencies(
            dependant=dependant,
            dependency_overrides_provider=dependency_overrides_provider,
            embed_body_fields=embed_body_fields,

            request=request,
            async_exit_stack=async_exit_stack,
            body=body,
        )

        if errors := solved_result.errors:
            raise RequestValidationError(errors, body=body, endpoint_ctx=endpoint_ctx)
        return solved_result

    if is_json_stream:
        # Shared serializer for stream items.
        # Validates against stream_item_field when set, then
        # serializes to JSON bytes.
        if stream_item_field:
            def _serialize_data(ctx: EndpointContext, data: Any, /) -> bytes:
                v_, errors_ = stream_item_field.validate(data, {}, loc=("response",))
                if errors_:
                    raise ResponseValidationError(errors_, body=data, endpoint_ctx=ctx)

                return stream_item_field.serialize_json(
                    v_,
                    include=response_model_include,
                    exclude=response_model_exclude,
                    by_alias=response_model_by_alias,
                    exclude_unset=response_model_exclude_unset,
                    exclude_defaults=response_model_exclude_defaults,
                    exclude_none=response_model_exclude_none,
                )
        else:
            def _serialize_data(_, data: Any, /) -> bytes:
                # TODO: Customizable JSON provider
                return json.dumps(data).encode("utf-8")

        if dependant.is_async_gen_callable:
            async def _jsonl_stream(ctx: EndpointContext, generator) -> AsyncIterator[bytes]:
                async for item in generator:
                    # noinspection PyTypeChecker
                    yield _serialize_data(ctx, item) + b'\n'
                    # To allow for cancellation to trigger
                    # Ref: https://github.com/fastapi/fastapi/issues/14680
                    await anyio.sleep(0)
        else:
            def _jsonl_stream(ctx: EndpointContext, generator) -> Iterator[bytes]:
                for item in generator:
                    # noinspection PyTypeChecker
                    yield _serialize_data(ctx, item) + b'\n'

        async def produce_response(ctx: EndpointContext, solved_result: SolvedDependency, /):
            # Generator endpoint: stream as JSONL
            generator = dependant.call(**solved_result.values)

            response = StreamingResponse(
                _jsonl_stream(ctx, generator),
                media_type="application/jsonl",
                background=solved_result.background_tasks,
            )
            response.headers.raw.extend(solved_result.response.headers.raw)
            return response
    elif dependant.is_gen_callable or dependant.is_async_gen_callable:
        if dependant.is_async_gen_callable:
            async def _raw_stream(**kwargs):
                async for chunk in dependant.call(**kwargs):
                    yield chunk
                    # To allow for cancellation to trigger
                    # Ref: https://github.com/fastapi/fastapi/issues/14680
                    await anyio.sleep(0)
            call = _raw_stream
        else:
            call = dependant.call

        async def produce_response(_: EndpointContext, solved_result: SolvedDependency, /):
            gen = call(**solved_result.values)

            response_args = _build_response_args(status_code=status_code, solved_result=solved_result)
            response = response_class(content=gen, **response_args)
            response.headers.raw.extend(solved_result.response.headers.raw)
            return response
    else:
        use_dump_json = response_field is not None and isinstance(response_class, DefaultPlaceholder)
        if use_dump_json:
            _response = lambda content, args: Response(content, media_type="application/json", **args)
        else:
            _response = lambda content, args: response_class(content, **args)

        async def produce_response(endpoint_ctx: EndpointContext, solved_result: SolvedDependency, /):
            if dependant.is_coroutine_callable:
                raw_response = await dependant.call(**solved_result.values)
            else:
                raw_response = await run_in_threadpool(dependant.call, **solved_result.values)
            if isinstance(raw_response, Response):
                if not raw_response.background:
                    raw_response.background = solved_result.background_tasks
                return raw_response

            response_args = _build_response_args(status_code=status_code, solved_result=solved_result)

            # Use the fast path (dump_json) when no custom response
            # class was set and a response field with a TypeAdapter
            # exists. Serializes directly to JSON bytes via Pydantic's
            # Rust core, skipping the intermediate Python dict +
            # json.dumps() step.
            content = await serialize_response(
                field=response_field,
                response_content=raw_response,
                include=response_model_include,
                exclude=response_model_exclude,
                by_alias=response_model_by_alias,
                exclude_unset=response_model_exclude_unset,
                exclude_defaults=response_model_exclude_defaults,
                exclude_none=response_model_exclude_none,
                is_coroutine=dependant.is_coroutine_callable,
                endpoint_ctx=endpoint_ctx,
                dump_json=use_dump_json,
            )
            response = _response(content, response_args)
            if __debug__ and not is_body_allowed_for_status_code(response.status_code):
                # TODO: Add warning
                response.body = b""
            response.headers.raw.extend(solved_result.response.headers.raw)
            return response

    async def app(request: Request, /) -> Response:
        # Extract endpoint context for error messages
        endpoint_ctx = _extract_endpoint_context(dependant.call) if dependant.call else EndpointContext()

        if dependant.path:
            # For mounted sub-apps, include the mount path prefix
            endpoint_ctx["path"] = f"{request.method} {request.scope.get("root_path", "").rstrip("/")}{dependant.path}"

        solved_result = await solve(request, endpoint_ctx)
        return await produce_response(endpoint_ctx, solved_result)

    return app
