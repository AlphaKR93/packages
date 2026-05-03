import email
import inspect
import json
from collections.abc import Callable, Coroutine, AsyncIterator, Iterator
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
from pydantic_core import PydanticUndefined as Undefined
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse


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

async def run_endpoint_function(
    *, dependant: Dependant, values: dict[str, Any], is_coroutine: bool
) -> Any:
    # Only called by get_request_handler. Has been split into its own function to
    # facilitate profiling endpoints, since inner functions are harder to profile.
    assert dependant.call is not None, "dependant.call must be a function"

    if is_coroutine:
        return await dependant.call(**values)
    else:
        return await run_in_threadpool(dependant.call, **values)

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

def get_request_handler(
    dependant: Dependant,
    body_field: ModelField | None,
    status_code: int | None,
    response_class: type[Response],
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
    is_coroutine = dependant.is_coroutine_callable

    async def app(request: Request) -> Response:
        file_stack = request.scope.get("fastapi_middleware_astack")
        assert isinstance(file_stack, AsyncExitStack), "fastapi_middleware_astack not found in request scope"

        # Extract endpoint context for error messages
        endpoint_ctx = (
            _extract_endpoint_context(dependant.call)
            if dependant.call
            else EndpointContext()
        )

        if dependant.path:
            # For mounted sub-apps, include the mount path prefix
            mount_path = request.scope.get("root_path", "").rstrip("/")
            endpoint_ctx["path"] = f"{request.method} {mount_path}{dependant.path}"

        # Read body and auto-close files
        try:
            body: Any = None
            if body_field:
                body_bytes = await request.body()
                if body_bytes:
                    json_body: Any = Undefined
                    content_type_value = request.headers.get("content-type")
                    if not content_type_value:
                        if not strict_content_type:
                            json_body = await request.json()
                    else:
                        message = email.message.Message()
                        message["content-type"] = content_type_value
                        if message.get_content_maintype() == "application":
                            subtype = message.get_content_subtype()
                            if subtype == "json" or subtype.endswith("+json"):
                                json_body = await request.json()
                    if json_body != Undefined:
                        body = json_body
                    else:
                        body = body_bytes
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

        # Solve dependencies and run path operation function, auto-closing dependencies
        async_exit_stack = request.scope.get("fastapi_inner_astack")
        assert isinstance(async_exit_stack, AsyncExitStack), "fastapi_inner_astack not found in request scope"
        solved_result = await solve_dependencies(
            request=request,
            dependant=dependant,
            body=body,
            dependency_overrides_provider=dependency_overrides_provider,
            async_exit_stack=async_exit_stack,
            embed_body_fields=embed_body_fields,
        )
        if errors := solved_result.errors:
            raise RequestValidationError(errors, body=body, endpoint_ctx=endpoint_ctx)

        # Shared serializer for stream items.
        # Validates against stream_item_field when set, then
        # serializes to JSON bytes.
        def _serialize_data(data: Any) -> bytes:
            if stream_item_field:
                value, errors_ = stream_item_field.validate(
                    data, {}, loc=("response",)
                )
                if errors_:
                    ctx = endpoint_ctx or EndpointContext()
                    raise ResponseValidationError(errors_, body=data, endpoint_ctx=ctx)
                return stream_item_field.serialize_json(
                    value,
                    include=response_model_include,
                    exclude=response_model_exclude,
                    by_alias=response_model_by_alias,
                    exclude_unset=response_model_exclude_unset,
                    exclude_defaults=response_model_exclude_defaults,
                    exclude_none=response_model_exclude_none,
                )
            else:
                data = jsonable_encoder(data)
                return json.dumps(data).encode("utf-8")

        if is_json_stream:
            # Generator endpoint: stream as JSONL
            gen = dependant.call(**solved_result.values)

            def _serialize_item(item: Any) -> bytes:
                return _serialize_data(item) + b"\n"

            if dependant.is_async_gen_callable:

                async def _async_stream_jsonl() -> AsyncIterator[bytes]:
                    async for item in gen:
                        yield _serialize_item(item)
                        # To allow for cancellation to trigger
                        # Ref: https://github.com/fastapi/fastapi/issues/14680
                        await anyio.sleep(0)

                jsonl_stream_content: AsyncIterator[bytes] | Iterator[bytes] = _async_stream_jsonl()
            else:
                def _sync_stream_jsonl() -> Iterator[bytes]:
                    for item in gen:  # ty: ignore[not-iterable]
                        yield _serialize_item(item)

                jsonl_stream_content = _sync_stream_jsonl()

            response = StreamingResponse(
                jsonl_stream_content,
                media_type="application/jsonl",
                background=solved_result.background_tasks,
            )
            response.headers.raw.extend(solved_result.response.headers.raw)
        elif dependant.is_async_gen_callable or dependant.is_gen_callable:
            # Raw streaming with explicit response_class (e.g. StreamingResponse)
            gen = dependant.call(**solved_result.values)
            if dependant.is_async_gen_callable:

                async def _async_stream_raw(
                    async_gen: AsyncIterator[Any],
                ) -> AsyncIterator[Any]:
                    async for chunk in async_gen:
                        yield chunk
                        # To allow for cancellation to trigger
                        # Ref: https://github.com/fastapi/fastapi/issues/14680
                        await anyio.sleep(0)

                gen = _async_stream_raw(gen)
            response_args = _build_response_args(
                status_code=status_code, solved_result=solved_result
            )
            response = response_class(content=gen, **response_args)
            response.headers.raw.extend(solved_result.response.headers.raw)
        else:
            raw_response = await run_endpoint_function(
                dependant=dependant,
                values=solved_result.values,
                is_coroutine=is_coroutine,
            )
            if isinstance(raw_response, Response):
                if raw_response.background is None:
                    raw_response.background = solved_result.background_tasks
                response = raw_response
            else:
                response_args = _build_response_args(
                    status_code=status_code, solved_result=solved_result
                )
                # Use the fast path (dump_json) when no custom response
                # class was set and a response field with a TypeAdapter
                # exists. Serializes directly to JSON bytes via Pydantic's
                # Rust core, skipping the intermediate Python dict +
                # json.dumps() step.
                use_dump_json = response_field is not None and isinstance(
                    response_class, DefaultPlaceholder
                )
                content = await serialize_response(
                    field=response_field,
                    response_content=raw_response,
                    include=response_model_include,
                    exclude=response_model_exclude,
                    by_alias=response_model_by_alias,
                    exclude_unset=response_model_exclude_unset,
                    exclude_defaults=response_model_exclude_defaults,
                    exclude_none=response_model_exclude_none,
                    is_coroutine=is_coroutine,
                    endpoint_ctx=endpoint_ctx,
                    dump_json=use_dump_json,
                )
                if use_dump_json:
                    response = Response(
                        content=content,
                        media_type="application/json",
                        **response_args,
                    )
                else:
                    response = response_class(content, **response_args)
                if not is_body_allowed_for_status_code(response.status_code):
                    response.body = b""
                response.headers.raw.extend(solved_result.response.headers.raw)

        # Return response
        assert response
        return response

    return app
