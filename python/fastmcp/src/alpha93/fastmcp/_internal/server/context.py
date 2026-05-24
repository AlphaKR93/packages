import logging
import weakref
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from mcp.server.lowlevel.server import request_ctx
from uncalled_for import SharedContext

import fastmcp.server.context as _origin
from fastmcp.server.elicitation import (
    handle_elicit_accept,
    parse_elicit_response_type,
)
from fastmcp.server.server import StateValue
from fastmcp.server.transforms.visibility import disable_components as _disable_components
from fastmcp.server.transforms.visibility import enable_components as _enable_components
from fastmcp.server.transforms.visibility import get_session_transforms as _get_session_transforms
from fastmcp.server.transforms.visibility import get_visibility_rules as _get_visibility_rules
from fastmcp.server.transforms.visibility import reset_visibility as _reset_visibility


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from contextvars import ContextVar, Token
    from typing import Any, Literal

    import mcp.types
    from mcp.types import LoggingLevel
    from mcp.server.session import ServerSession
    from mcp.shared.context import RequestContext
    from pydantic.networks import AnyUrl
    from starlette.requests import Request

    from fastmcp.server.elicitation import CancelledElicitation, DeclinedElicitation
    from fastmcp.server.low_level import MiddlewareServerSession
    from fastmcp.server.server import FastMCP

    type TransportType = Literal["stdio", "streamable-http"]


_current_context: ContextVar[Context | None] = ContextVar("context", default=None)
_current_transport: ContextVar[TransportType | None] = ContextVar("transport", default=None)


set_transport = lambda transport: _current_transport.set(transport)
reset_transport = lambda token: _current_transport.reset(token)


@dataclass
class LogData:
    msg: str
    extra: Mapping[str, Any] | None = None


@contextmanager
def set_context(context: Context, /):
    token = _current_context.set(context)
    try:
        yield context
    finally:
        _current_context.reset(token)


@dataclass
class Context:
    # Default TTL for session state: 1 day in seconds
    _STATE_TTL_SECONDS: int = 86400

    def __init__(self, fastmcp, /, session = None, *, task_id = None, origin_request_id = None):
        self._fastmcp: weakref.ref[FastMCP] = weakref.ref(fastmcp)
        self._session: ServerSession | None = session  # For state ops during init
        self._tokens: list[Token] = []
        # Background task support (SEP-1686)
        self._task_id: str | None = task_id
        self._origin_request_id: str | None = origin_request_id
        # Request-scoped state for non-serializable values (serializable=False)
        self._request_state: dict[str, Any] = {}

    @property
    def is_background_task(self, /) -> bool:
        return self._task_id is not None

    @property
    def task_id(self, /) -> str | None:
        return self._task_id

    @property
    def origin_request_id(self, /) -> str | None:
        if self.request_context is not None:
            return str(self.request_context.request_id)
        return self._origin_request_id

    @property
    def fastmcp(self, /) -> FastMCP:
        fastmcp = self._fastmcp()
        if fastmcp is None:
            raise RuntimeError("FastMCP instance is no longer available")
        return fastmcp

    async def __aenter__(self: FastMCP, /):
        # Inherit request-scoped state from parent context so middleware
        # and tool contexts share the same in-memory state dict.
        parent = _current_context.get(None)
        if parent is not None:
            self._request_state = parent._request_state

        # Always set this context and save the token
        token = _current_context.set(self)
        self._tokens.append(token)

        # Without docket, the lifespan won't provide a SharedContext,
        # so create one scoped to this Context for Shared() dependencies.
        self._shared_context = SharedContext()
        await self._shared_context.__aenter__()

        return self

    async def __aexit__(self: FastMCP, exc_type, exc_val, exc_tb, /):
        if hasattr(self, "_shared_context"):
            await self._shared_context.__aexit__(exc_type, exc_val, exc_tb)
            del self._shared_context

        # Reset context token
        if self._tokens:
            token = self._tokens.pop()
            _current_context.reset(token)

    @property
    def request_context(self, /) -> RequestContext[ServerSession, Any, Request] | None:
        try:
            return request_ctx.get()
        except LookupError:
            return None

    @property
    def lifespan_context(self, /) -> dict[str, Any]:
        result = self.fastmcp._lifespan_result
        if result is not None:
            return result
        # Server's lifespan was never entered for this Context's server (or
        # yielded None). Fall back to the request context's lifespan, which
        # for a mounted child will be the parent's — preserved for parity
        # with prior behavior, but in normal operation a child's own
        # lifespan populates `_lifespan_result` and short-circuits above.
        rc = self.request_context
        if rc is None:
            return {}
        return rc.lifespan_context

    async def report_progress(self, /, *args, **kwargs):
        progress_token = (
            self.request_context.meta.progressToken
            if self.request_context and self.request_context.meta
            else None
        )

        # Foreground: Send MCP progress notification if we have a token
        if progress_token is not None:
            await self.session.send_progress_notification(progress_token, *args, **kwargs, related_request_id=self.request_id,)
            return
        return

    @staticmethod
    async def _paginate_list(
            request_factory: Callable[[str | None], Any],
            call_method: Callable[[Any], Any],
            extract_items: Callable[[Any], list[Any]],
    ):
        all_items: list[Any] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            request = request_factory(cursor)
            result = await call_method(request)
            all_items.extend(extract_items(result))
            if not result.nextCursor:
                break
            if result.nextCursor in seen_cursors:
                break
            seen_cursors.add(result.nextCursor)
            cursor = result.nextCursor
        return all_items

    async def list_resources(self, /):
        return await self._paginate_list(
            request_factory=lambda cursor: mcp.types.ListResourcesRequest(
                params=mcp.types.PaginatedRequestParams(cursor=cursor)
                if cursor
                else None
            ),
            call_method=self.fastmcp._list_resources_mcp,
            extract_items=lambda result: result.resources,
        )

    async def list_prompts(self, /):
        return await self._paginate_list(
            request_factory=lambda cursor: mcp.types.ListPromptsRequest(
                params=mcp.types.PaginatedRequestParams(cursor=cursor)
                if cursor
                else None
            ),
            call_method=self.fastmcp._list_prompts_mcp,
            extract_items=lambda result: result.prompts,
        )

    async def get_prompt(self, /, *args):
        result = await self.fastmcp.render_prompt(*args)
        if isinstance(result, mcp.types.CreateTaskResult):
            raise RuntimeError(
                "Unexpected CreateTaskResult: Context calls should not have task metadata"
            )
        return result.to_mcp_prompt_result()

    async def read_resource(self, uri: str | AnyUrl, /):
        result = await self.fastmcp.read_resource(str(uri))
        if isinstance(result, mcp.types.CreateTaskResult):
            raise RuntimeError(
                "Unexpected CreateTaskResult: Context calls should not have task metadata"
            )
        return result

    async def log(self, message, /, *, extra = None, **kwargs):
        await _log_to_server_and_client(
            data=LogData(msg=message, extra=extra),
            session=self.session,
            related_request_id=self.origin_request_id,
            **kwargs
        )

    @property
    def transport(self, /) -> TransportType | None:
        return _current_transport.get()

    def client_supports_extension(self, extension_id: str, /) -> bool:
        rc = self.request_context
        if rc is None:
            return False
        session = rc.session
        if not isinstance(session, MiddlewareServerSession):
            return False
        return session.client_supports_extension(extension_id)

    @property
    def client_id(self, /) -> str | None:
        return (
            getattr(self.request_context.meta, "client_id", None)
            if self.request_context and self.request_context.meta
            else None
        )

    @property
    def request_id(self, /) -> str:
        if self.request_context is None:
            raise RuntimeError(
                "request_id is not available because the MCP session has not been established yet. "
                "Check `context.request_context` for None before accessing this attribute."
            )
        return str(self.request_context.request_id)

    @property
    def session_id(self, /) -> str:
        from uuid import uuid4

        # Get session from request context or _session (for on_initialize)
        request_ctx = self.request_context
        if request_ctx is not None:
            session = request_ctx.session
        elif self._session is not None:
            session = self._session
        else:
            raise RuntimeError(
                "session_id is not available because no session exists. "
                "This typically means you're outside a request context."
            )

        # Check for cached session ID
        session_id = getattr(session, "_fastmcp_state_prefix", None)
        if session_id is not None:
            return session_id

        # For HTTP, try to get from header
        if request_ctx is not None:
            request = request_ctx.request
            if request:
                session_id = request.headers.get("mcp-session-id")

        # For STDIO/SSE/in-memory, generate a UUID
        if session_id is None:
            session_id = str(uuid4())

        # Cache on session for consistency
        session._fastmcp_state_prefix = session_id  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
        return session_id

    @property
    def session(self, /) -> ServerSession:
        # Background task mode: use the stored session
        if self.is_background_task and self._session is not None:
            return self._session

        # Request mode: use request context
        if self.request_context is not None:
            return self.request_context.session

        # Fallback to stored session (e.g., during on_initialize)
        if self._session is not None:
            return self._session

        raise RuntimeError(
            "session is not available because the MCP session has not been established yet. "
            "Check `context.request_context` for None before accessing this attribute."
        )

    # Convenience methods for common log levels
    async def debug(self, message, /, **kwargs):
        await self.log(message, level="debug", **kwargs)
    async def info(self, message, /, **kwargs):
        await self.log(message, level="info", **kwargs)
    async def warning(self, message, /, **kwargs):
        await self.log(message, level="warning", **kwargs)
    async def error(self, message, /, **kwargs):
        await self.log(message, level="error", **kwargs)

    async def list_roots(self, /):
        result = await self.session.list_roots()
        return result.roots

    async def send_notification(self, notification: mcp.types.ServerNotificationType, /):
        await self.session.send_notification(mcp.types.ServerNotification(notification))

    async def close_sse_stream(self, /):
        if not self.request_context or not self.request_context.close_sse_stream:
            _origin.logger.debug(
                "close_sse_stream() called but not applicable "
                "(requires StreamableHTTP transport with event_store)"
            )
            return
        await self.request_context.close_sse_stream()

    async def sample_step(self, /, *args, **kwargs):
        from fastmcp.server.sampling.run import sample_step_impl

        return await sample_step_impl(self, *args, **kwargs)

    async def sample(self, /, *args, **kwargs):
        # TODO: Add background task support similar to elicit() when is_background_task
        from fastmcp.server.sampling.run import sample_impl

        return await sample_impl(self, *args, **kwargs)

    async def elicit(self, message, /, *args, **kwargs):
        config = parse_elicit_response_type(*args, **kwargs)

        if self.is_background_task:
            # Background task mode: use task-aware elicitation
            result = await self._elicit_for_task(
                message=message,
                schema=config.schema,
            )
        else:
            # Standard request mode: use session.elicit directly
            result = await self.session.elicit(
                message=message,
                requestedSchema=config.schema,
                related_request_id=self.request_id,
            )

        if result.action == "accept":
            return handle_elicit_accept(config, result.content)
        elif result.action == "decline":
            return DeclinedElicitation()
        elif result.action == "cancel":
            return CancelledElicitation()
        else:
            raise ValueError(f"Unexpected elicitation action: {result.action}")

    async def _elicit_for_task(self, /, **kwargs):
        if not self.is_background_task:
            raise RuntimeError(
                "_elicit_for_task called but not in a background task context"
            )

        # Import here to avoid circular imports and optional dependency issues
        from fastmcp.server.tasks.elicitation import elicit_for_task

        return await elicit_for_task(
            task_id=self._task_id,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
            session=self._session,
            fastmcp=self.fastmcp,
            **kwargs
        )

    def _make_state_key(self, key, /):
        return f"{self.session_id}:{key}"

    async def set_state(self, key, value, /, *, serializable = True):
        prefixed_key = self._make_state_key(key)
        if not serializable:
            self._request_state[prefixed_key] = value
            return
        # Clear any request-scoped shadow so the session value is visible
        self._request_state.pop(prefixed_key, None)
        try:
            await self.fastmcp._state_store.put(
                key=prefixed_key,
                value=StateValue(value=value),
                ttl=Context._STATE_TTL_SECONDS,
            )
        except Exception as e:
            # Catch serialization errors from Pydantic (ValueError) or
            # the key_value library (SerializationError). Both contain
            # "serialize" in the message. Other exceptions propagate as-is.
            if "serialize" in str(e).lower():
                raise TypeError(
                    f"Value for state key {key!r} is not serializable. "
                    f"Use set_state({key!r}, value, serializable=False) to store "
                    f"non-serializable values. Note: non-serializable state is "
                    f"request-scoped and will not persist across requests."
                ) from e
            raise

    async def get_state(self, key, /):
        prefixed_key = self._make_state_key(key)
        if prefixed_key in self._request_state:
            return self._request_state[prefixed_key]
        result = await self.fastmcp._state_store.get(key=prefixed_key)
        return result.value if result is not None else None

    async def delete_state(self, key, /):
        prefixed_key = self._make_state_key(key)
        self._request_state.pop(prefixed_key, None)
        await self.fastmcp._state_store.delete(key=prefixed_key)

    # -------------------------------------------------------------------------
    # Session visibility control
    # -------------------------------------------------------------------------

    async def _get_visibility_rules(self, /):
        return await _get_visibility_rules(self)

    async def _get_session_transforms(self, /):
        return await _get_session_transforms(self)

    async def enable_components(self, /, **kwargs):
        await _enable_components(self, **kwargs)

    async def disable_components(self, /, **kwargs):
        await _disable_components(self, **kwargs)

    async def reset_visibility(self, /):
        await _reset_visibility(self)


_MCP_LEVEL_SEVERITY: dict[LoggingLevel, int] = {
    "debug": 0,
    "info": 1,
    "notice": 2,
    "warning": 3,
    "error": 4,
    "critical": 5,
    "alert": 6,
    "emergency": 7,
}

_mcp_level_to_python_level = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "notice": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "alert": logging.CRITICAL,
    "emergency": logging.CRITICAL,
}


async def _log_to_server_and_client(
        data: LogData,
        session: ServerSession,
        level: LoggingLevel = "info",
        logger_name: str | None = None,
        related_request_id: str | None = None,
):
    """Log a message to the server and client."""
    from fastmcp.server.low_level import MiddlewareServerSession

    if isinstance(session, MiddlewareServerSession):
        min_level = session._minimum_logging_level or session.fastmcp.client_log_level
        if min_level is not None:
            if _MCP_LEVEL_SEVERITY[level] < _MCP_LEVEL_SEVERITY[min_level]:
                return

    msg_prefix = f"Sending {level.upper()} to client"

    if logger_name:
        msg_prefix += f" ({logger_name})"

    _origin.to_client_logger.log(
        level=_mcp_level_to_python_level[level],
        msg=f"{msg_prefix}: {data.msg}",
        extra=data.extra,
    )

    await session.send_log_message(
        level=level,
        data=data,
        logger=logger_name,
        related_request_id=related_request_id,
    )
