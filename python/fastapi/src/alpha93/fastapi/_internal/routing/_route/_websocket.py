from alpha93.fastapi._contextlib import AsyncExitStack
from fastapi.exceptions import EndpointContext, WebSocketRequestValidationError
from starlette._exception_handler import wrap_app_handling_exceptions
from starlette.routing import WebSocketRoute, get_name, compile_path, Match
from starlette.websockets import WebSocket

from ...dependencies.utils import (
    get_dependant,
    get_parameterless_sub_dependant,
    get_flat_dependant,
    should_embed_body_fields,
    solve_dependencies,
)

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Sequence, Coroutine, Awaitable
    from typing import Any

    from fastapi.dependencies.models import Dependant
    from fastapi.params import Depends
    from starlette.types import Scope, ASGIApp, Receive, Send


_endpoint_context_cache: dict[int, EndpointContext] = {}
def _extract_endpoint_context(func: "Any") -> EndpointContext:
    func_id = id(func)

    if func_id in _endpoint_context_cache:
        return _endpoint_context_cache[func_id]

    try:
        import inspect

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


def get_websocket_app(
    dependant: "Dependant",
    /,
    *,
    dependency_overrides_provider: "Any | None" = None,
    embed_body_fields: bool = False,
) -> "Callable[[WebSocket], Coroutine[Any, Any, Any]]":
    async def app(websocket: WebSocket, /) -> None:
        endpoint_ctx = _extract_endpoint_context(dependant.call) if dependant.call else EndpointContext()
        if dependant.path:
            mount_path = websocket.scope.get("root_path", "").rstrip("/")
            endpoint_ctx["path"] = f"WS {mount_path}{dependant.path}"

        async_exit_stack = websocket.scope.get("fastapi_inner_astack")
        assert isinstance(async_exit_stack, AsyncExitStack), "fastapi_inner_astack not found in request scope"

        solved_result = await solve_dependencies(
            request=websocket,
            dependant=dependant,
            dependency_overrides_provider=dependency_overrides_provider,
            async_exit_stack=async_exit_stack,
            embed_body_fields=embed_body_fields,
        )
        if solved_result.errors:
            raise WebSocketRequestValidationError(solved_result.errors, endpoint_ctx=endpoint_ctx)
        assert dependant.call is not None, "dependant.call must be a function"
        await dependant.call(**solved_result.values)

    return app


# Copy of starlette.routing.websocket_session modified to include the
# dependencies' AsyncExitStack
def websocket_session(func: "Callable[[WebSocket], Awaitable[None]]", /) -> "ASGIApp":
    async def app(scope: "Scope", receive: "Receive", send: "Send", /) -> None:
        session = WebSocket(scope, receive=receive, send=send)

        async def app(scope: "Scope", receive: "Receive", send: "Send", /) -> None:
            async with AsyncExitStack() as request_stack:
                scope["fastapi_inner_astack"] = request_stack
                async with AsyncExitStack() as function_stack:
                    scope["fastapi_function_astack"] = function_stack
                    await func(session)

        await wrap_app_handling_exceptions(app, session)(scope, receive, send)

    return app


class APIWebSocketRoute(WebSocketRoute):
    def __init__(
        self,
        path: str,
        endpoint: "Callable[..., Any]",
        /,
        *,
        name: str | None = None,
        dependencies: "Sequence[Depends] | None" = None,
        dependency_overrides_provider: "Any | None" = None,
    ) -> None:
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.dependencies = list(dependencies or [])
        self.setup(path)

        self.dependant = get_dependant(path=self.path_format, call=self.endpoint, scope="function")
        for depends in self.dependencies[::-1]:
            self.dependant.dependencies.insert(0, get_parameterless_sub_dependant(depends, path=self.path_format))
        flat_dependant = get_flat_dependant(self.dependant)
        self._embed_body_fields = should_embed_body_fields(flat_dependant.body_params)

        self.app = websocket_session(
            get_websocket_app(
                self.dependant,
                dependency_overrides_provider=dependency_overrides_provider,
                embed_body_fields=self._embed_body_fields,
            )
        )

    def setup(self, path: str, /) -> None:
        self.path = path
        self.path_regex, self.path_format, self.param_convertors = compile_path(path)

    def matches(self, scope: "Scope", /) -> "tuple[Match, Scope]":
        match, child_scope = super().matches(scope)
        if match != Match.NONE:
            child_scope["route"] = self
        return match, child_scope
