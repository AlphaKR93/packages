from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

from alpha93.fastapi._contextlib import AsyncExitStack
from fastapi.concurrency import contextmanager_in_threadpool
from fastapi.dependencies.models import Dependant
from starlette.background import BackgroundTasks
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response

from .._base import get_dependant
from ._to_args import extract_from_body, extract_from_params

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Any

    from fastapi.types import DependencyCacheKey


@dataclass(frozen=True)
class SolvedDependency:
    values: Mapping[str, Any]
    errors: Sequence[Any]
    background_tasks: BackgroundTasks | None
    response: Response
    dependency_cache: dict[DependencyCacheKey, Any]

async def _solve_generator(
    *, dependant: Dependant, stack: AsyncExitStack, sub_values: Mapping[str, Any]
) -> Any:
    assert dependant.call
    if dependant.is_async_gen_callable:
        cm = asynccontextmanager(dependant.call)(**sub_values)
    elif dependant.is_gen_callable:
        cm = contextmanager_in_threadpool(contextmanager(dependant.call)(**sub_values))
    return await stack.enter_async_context(cm)

async def solve_dependencies(
    *,
    request: Request,
    dependant: Dependant,
    body: dict[str, Any] | bytes | None = None,
    background_tasks: BackgroundTasks | None = None,
    response: Response | None = None,
    dependency_overrides_provider: Any | None = None,
    dependency_cache: dict[DependencyCacheKey, Any] | None = None,
    # TODO: remove this parameter later, no longer used, not removing it yet as some
    # people might be monkey patching this function (although that's not supported)
    async_exit_stack: AsyncExitStack,
    embed_body_fields: bool,
) -> SolvedDependency:
    request_astack = request.scope.get("fastapi_inner_astack")
    assert isinstance(request_astack, AsyncExitStack), "fastapi_inner_astack not found in request scope"

    function_astack = request.scope.get("fastapi_function_astack")
    assert isinstance(function_astack, AsyncExitStack), "fastapi_function_astack not found in request scope"

    values: dict[str, Any] = {}
    errors: list[Any] = []
    if response is None:
        response: Response = Response()
        del response.headers["content-length"]
        response.status_code = None  # type: ignore  # ty: ignore[unused-ignore-comment]

    if dependency_cache is None:
        dependency_cache: dict[DependencyCacheKey, Any] = {}

    for sub_dependant in dependant.dependencies:
        call = sub_dependant.call
        use_sub_dependant = sub_dependant
        if dependency_overrides_provider and dependency_overrides_provider.dependency_overrides:
            original_call = sub_dependant.call
            call = getattr(dependency_overrides_provider, "dependency_overrides", {}).get(original_call, original_call)
            use_sub_dependant = get_dependant(
                path=sub_dependant.path,
                call=call,
                name=sub_dependant.name,
                parent_oauth_scopes=sub_dependant.oauth_scopes,
                scope=sub_dependant.scope,
            )

        solved_result = await solve_dependencies(
            request=request,
            dependant=use_sub_dependant,
            body=body,
            background_tasks=background_tasks,
            response=response,
            dependency_overrides_provider=dependency_overrides_provider,
            dependency_cache=dependency_cache,
            async_exit_stack=async_exit_stack,
            embed_body_fields=embed_body_fields,
        )
        background_tasks = solved_result.background_tasks
        if solved_result.errors:
            errors.extend(solved_result.errors)
            continue

        if sub_dependant.use_cache and sub_dependant.cache_key in dependency_cache:
            solved = dependency_cache[sub_dependant.cache_key]
        elif use_sub_dependant.is_gen_callable or use_sub_dependant.is_async_gen_callable:
            use_astack = request_astack
            if sub_dependant.scope == "function":
                use_astack = function_astack

            solved = await _solve_generator(dependant=use_sub_dependant, stack=use_astack, sub_values=solved_result.values)
        elif use_sub_dependant.is_coroutine_callable:
            solved = await call(**solved_result.values)
        else:
            solved = await run_in_threadpool(call, **solved_result.values)

        if sub_dependant.name is not None:
            values[sub_dependant.name] = solved
        if sub_dependant.cache_key not in dependency_cache:
            dependency_cache[sub_dependant.cache_key] = solved

    for expect, actual in (
            (request.path_params, dependant.path_params),
            (request.query_params, dependant.query_params),
            (request.headers, dependant.header_params),
            (request.cookies, dependant.cookie_params),
    ):
        v_, errors_ = extract_from_params(expect, actual)
        values.update(v_)
        errors.extend(errors_)

    if dependant.body_params:
        v_, errors_ = extract_from_body(body, dependant.body_params, embed_body_fields)
        values.update(v_)
        errors.extend(errors_)

    if dependant.http_connection_param_name:
        values[dependant.http_connection_param_name] = request
    if dependant.request_param_name and isinstance(request, Request):
        values[dependant.request_param_name] = request
    if dependant.background_tasks_param_name:
        if background_tasks is None:
            background_tasks = BackgroundTasks()
        values[dependant.background_tasks_param_name] = background_tasks
    if dependant.response_param_name:
        values[dependant.response_param_name] = response

    return SolvedDependency(
        values=values,
        errors=errors,
        background_tasks=background_tasks,
        response=response,
        dependency_cache=dependency_cache,
    )
