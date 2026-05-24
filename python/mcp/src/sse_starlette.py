"""Server-Sent Events response for Starlette / FastAPI.

Intentional divergence from ``starlette.responses.StreamingResponse``
--------------------------------------------------------------------

``EventSourceResponse`` is modelled on Starlette's ``StreamingResponse`` and
re-syncs most of its behaviour (WebSocket denial, ``collapse_excgroups()``
around the task group, ``memoryview`` chunk handling). The following points
are deliberate divergences — DO NOT "fix" them without reading the rationale:

1. ASGI ``spec_version >= 2.4`` fast path is NOT adopted.
   Upstream short-circuits to ``await stream_response(send)`` and converts
   ``OSError`` into ``ClientDisconnect``, skipping ``listen_for_disconnect``.
   We keep ``_listen_for_disconnect`` running because it
     (a) invokes ``client_close_handler_callable`` on disconnect,
     (b) flips ``self.active = False`` so ``_ping`` and the cooperative
         shutdown grace loop exit promptly.
   Adopting the upstream fast path would regress both features.

2. ``_wrap_websocket_denial_send`` is inlined in this module rather than
   inherited from ``starlette.responses.Response``. The helper landed on
   Starlette ``main`` after our minimum pin (``starlette>=0.41.3``); inline
   until the floor moves past the release that contains it.

3. ``collapse_excgroups()`` is vendored in ``sse_starlette._utils`` rather
   than imported from ``starlette._utils`` (private module).
"""
import io
import re
import logging
import threading
from collections.abc import AsyncIterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import override

import anyio
from starlette.background import BackgroundTask
from starlette.concurrency import iterate_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.responses import Response


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator, Mapping, Iterable
    from typing import Any, Literal

    from starlette.types import Receive, Scope, Send, Message

    type Content = str | bytes | Mapping | ServerSentEvent | Any
    type SyncContentStream = Iterable[Content]
    type AsyncContentStream = AsyncIterable[Content]
    type ContentStream = SyncContentStream | AsyncContentStream


logger = logging.getLogger(__name__)


@contextmanager
def collapse_excgroups() -> Generator[None, None, None]:
    try:
        yield
    except BaseException as exc:
        # `ty` does not narrow BaseExceptionGroup.exceptions; the runtime
        # contract is identical to starlette._utils.collapse_excgroups.
        while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:  # ty: ignore[unresolved-attribute]
            exc = exc.exceptions[0]  # ty: ignore[unresolved-attribute]

        raise exc


class ServerSentEvent:
    """
    Helper class to format data for Server-Sent Events (SSE).
    """

    _LINE_SEP_EXPR = re.compile(r"\r\n|\r|\n")
    DEFAULT_SEPARATOR = "\r\n"

    def __init__(
        self,
        data: Any | None = None,
        /,
        *,
        event: str | None = None,
        id: str | None = None,
        retry: str | None = None,
        comment: str | None = None,
        sep: str | None = None,
    ) -> None:
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry
        self.comment = comment
        self._sep = sep if sep is not None else self.DEFAULT_SEPARATOR

    def encode(self, /) -> bytes:
        buffer = io.StringIO()
        if self.comment is not None:
            for chunk in self._LINE_SEP_EXPR.split(str(self.comment)):
                buffer.write(f": {chunk}{self._sep}")

        if self.id is not None:
            # Clean newlines in the event id
            buffer.write("id: " + self._LINE_SEP_EXPR.sub("", self.id) + self._sep)

        if self.event is not None:
            # Clean newlines in the event name
            buffer.write(
                "event: " + self._LINE_SEP_EXPR.sub("", self.event) + self._sep
            )

        if self.data is not None:
            # Break multi-line data into multiple data: lines
            for chunk in self._LINE_SEP_EXPR.split(str(self.data)):
                buffer.write(f"data: {chunk}{self._sep}")

        if self.retry is not None:
            if not isinstance(self.retry, int):
                raise TypeError("retry argument must be int")
            buffer.write(f"retry: {self.retry}{self._sep}")

        buffer.write(self._sep)
        return buffer.getvalue().encode("utf-8")


def ensure_bytes(data: bytes | dict | ServerSentEvent | Any, /, sep: str) -> bytes:
    if isinstance(data, ServerSentEvent):
        return data.encode()
    if isinstance(data, (bytes, memoryview)):
        return bytes(data)
    if isinstance(data, dict):
        data["sep"] = sep
        return ServerSentEvent(**data).encode()
    return ServerSentEvent(str(data), sep=sep).encode()


@dataclass
class _ShutdownState:
    """Per-thread state for shutdown coordination.

    Issue #152 fix: Uses threading.local() instead of ContextVar to ensure
    one watcher per thread rather than one per async context.
    """

    events: set[anyio.Event] = field(default_factory=set)
    watcher_started: bool = False


# Each thread gets its own shutdown state (one event loop per thread typically)
_thread_state = threading.local()


def _wrap_websocket_denial_send(send: Send) -> Send:
    """Mirror of ``starlette.responses.Response._wrap_websocket_denial_send``.

    Divergence #2 (see module docstring): inlined because the helper landed
    on Starlette ``main`` (commit 9ee9519) after our minimum pin
    ``starlette>=0.41.3``. Drop this once the floor moves past the release
    that contains it.
    """

    async def wrapped(message: Message) -> None:
        message_type = message["type"]
        if message_type in {"http.response.start", "http.response.body"}:
            message = {**message, "type": "websocket." + message_type}
        await send(message)

    return wrapped


class SendTimeoutError(TimeoutError):
    pass


class EventSourceResponse(Response):
    """Streaming response implementing the SSE (Server-Sent Events) specification.

    Args:
        content: Async iterable or sync iterator yielding SSE event data.
        status_code: HTTP status code. Default: 200.
        headers: Additional HTTP headers.
        media_type: Response media type. Default: "text/event-stream".
        background: Background task to run after response completes.
        ping: Ping interval in seconds (0 to disable). Default: 15.
        sep: Line separator for SSE messages ("\\r\\n", "\\r", or "\\n").
        ping_message_factory: Callable returning custom ping ServerSentEvent.
        data_sender_callable: Async callable for push-based data sending.
        send_timeout: Timeout in seconds for individual send operations.
        client_close_handler_callable: Async callback on client disconnect.
        shutdown_event: Optional ``anyio.Event`` set by the library when server
            shutdown is detected. Generators can watch this event to send farewell
            messages and exit cooperatively instead of receiving CancelledError.
        shutdown_grace_period: Seconds to wait after setting ``shutdown_event``
            before force-cancelling the generator. Must be >= 0. Should be less
            than your ASGI server's graceful shutdown timeout. Default: 0
            (immediate cancel, identical to pre-v3.3.0 behavior).
    """

    DEFAULT_PING_INTERVAL = 15
    DEFAULT_SEPARATOR = "\r\n"

    def __init__(
        self,
        content: ContentStream,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str = "text/event-stream",
        background: BackgroundTask | None = None,
        ping: int | None = None,
        sep: Literal["\r\n", "\r", "\n"] | None = None,
        ping_message_factory: Callable[[], ServerSentEvent] | None = None,
        data_sender_callable: Callable[[], Awaitable[None]] | None = None,
        send_timeout: float | None = None,
        client_close_handler_callable: Callable[[Message], Awaitable[None]] | None = None,
        shutdown_event: anyio.Event | None = None,
        shutdown_grace_period: float = 0,
    ) -> None:
        # Validate separator
        assert sep in (None, "\r\n", "\r", "\n"), rf"sep must be one of: \r\n, \r, \n, got: {sep}"
        self.sep = sep or self.DEFAULT_SEPARATOR

        # If content is sync, wrap it for async iteration
        if isinstance(content, AsyncIterable):
            self.body_iterator: AsyncContentStream = content
        else:
            self.body_iterator = iterate_in_threadpool(content)

        self.status_code = status_code
        self.media_type = self.media_type if media_type is None else media_type
        self.background = background
        self.data_sender_callable = data_sender_callable
        self.send_timeout = send_timeout

        # Build SSE-specific headers.
        _headers = MutableHeaders()
        if headers is not None:  # pragma: no cover
            _headers.update(headers)

        # "The no-store response directive indicates that any caches of any kind (private or shared)
        # should not store this response."
        # -- https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
        # allow cache control header to be set by user to support fan out proxies
        # https://www.fastly.com/blog/server-sent-events-fastly

        _headers.setdefault("Cache-Control", "no-store")
        # mandatory for servers-sent events headers
        _headers["Connection"] = "keep-alive"
        _headers["X-Accel-Buffering"] = "no"
        self.init_headers(_headers)

        self.ping_interval = self.DEFAULT_PING_INTERVAL if ping is None else ping
        self.ping_message_factory = ping_message_factory

        self.client_close_handler_callable = client_close_handler_callable

        # Cooperative shutdown (Issue #167): Allow generators to send farewell
        # events before force-cancellation. The grace period should be less than
        # your ASGI server's graceful shutdown timeout (e.g. uvicorn's
        # --timeout-graceful-shutdown), otherwise the process is killed before
        # the grace period expires.
        if shutdown_grace_period < 0:
            raise ValueError("shutdown_grace_period must be >= 0")
        self._shutdown_event = shutdown_event
        self._shutdown_grace_period = shutdown_grace_period

        self.active = True
        # https://github.com/sysid/sse-starlette/pull/55#issuecomment-1732374113
        self._send_lock = anyio.Lock()

    @property
    def ping_interval(self) -> float:
        return self._ping_interval

    @ping_interval.setter
    def ping_interval(self, value: float, /) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("ping interval must be int")
        if value < 0:
            raise ValueError("ping interval must be greater than 0")
        self._ping_interval = value

    async def _stream_response(self, send: Send, /) -> None:
        """Send out SSE data to the client as it becomes available in the iterator."""
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )

        async for data in self.body_iterator:
            chunk = ensure_bytes(data, self.sep)
            logger.debug("chunk: %s", chunk)
            with anyio.move_on_after(self.send_timeout) as cancel_scope:
                await send(
                    {"type": "http.response.body", "body": chunk, "more_body": True}
                )

            if cancel_scope and cancel_scope.cancel_called:
                aclose = getattr(self.body_iterator, "aclose", None)
                if aclose is not None:
                    await aclose()
                raise SendTimeoutError()

        async with self._send_lock:
            self.active = False
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def _listen_for_disconnect(self, receive: Receive) -> None:
        """Watch for a disconnect message from the client.

        Divergence #1 (see module docstring): kept unconditionally instead of
        adopting Starlette's ASGI 2.4 ``OSError → ClientDisconnect`` fast path,
        because this loop drives ``client_close_handler_callable`` and flips
        ``self.active = False`` for ``_ping`` and the shutdown grace loop.
        """
        while self.active:
            message = await receive()
            if message["type"] == "http.disconnect":
                self.active = False
                logger.debug("Got event: http.disconnect. Stop streaming.")
                if self.client_close_handler_callable:
                    await self.client_close_handler_callable(message)
                break

    async def _listen_for_exit_signal_with_grace(self) -> None:
        """Wait for shutdown signal, then optionally give generator a grace period.

        Issue #167: When a shutdown_event is provided, the library sets it before
        returning, giving the generator a chance to send farewell events and exit
        cooperatively. The shutdown_grace_period controls how long to wait before
        force-cancelling via task group cancellation.
        """
        # Signal the user's generator that shutdown is happening
        if self._shutdown_event:
            self._shutdown_event.set()

        # Grace period: let generator finish naturally before force-cancel
        if self._shutdown_grace_period > 0:
            with anyio.move_on_after(self._shutdown_grace_period):
                while self.active:
                    await anyio.sleep(0.1)

    async def _ping(self, send: Send) -> None:
        """Periodically send ping messages to keep the connection alive on proxies.
        - frequenccy ca every 15 seconds.
        - Alternatively one can send periodically a comment line (one starting with a ':' character)
        """
        while self.active:
            await anyio.sleep(self._ping_interval)
            sse_ping = (
                self.ping_message_factory()
                if self.ping_message_factory
                else ServerSentEvent(
                    comment=f"ping - {datetime.now(timezone.utc)}", sep=self.sep
                )
            )
            ping_bytes = ensure_bytes(sse_ping, self.sep)
            logger.debug("ping: %s", ping_bytes)

            async with self._send_lock:
                if self.active:
                    await send(
                        {
                            "type": "http.response.body",
                            "body": ping_bytes,
                            "more_body": True,
                        }
                    )

    @override
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Entrypoint for Starlette's ASGI contract. We spin up tasks:
        - _stream_response to push events
        - _ping to keep the connection alive
        - _listen_for_exit_signal to respond to server shutdown
        - _listen_for_disconnect to respond to client disconnect
        """
        # WebSocket denial parity with Starlette's StreamingResponse: a
        # streaming response on a websocket scope must wrap send so message
        # types become ``websocket.http.response.*``.
        if scope["type"] == "websocket":
            send = _wrap_websocket_denial_send(send)

        # collapse_excgroups parity with Starlette's StreamingResponse: anyio
        # v4 wraps task-group failures in ExceptionGroup; user middleware
        # expects the bare exception.
        with collapse_excgroups():
            async with anyio.create_task_group() as task_group:
                # https://trio.readthedocs.io/en/latest/reference-core.html#custom-supervisors
                async def cancel_on_finish(coro: Callable[[], Awaitable[None]]):
                    await coro()
                    task_group.cancel_scope.cancel()

                task_group.start_soon(cancel_on_finish, lambda: self._stream_response(send))
                task_group.start_soon(cancel_on_finish, lambda: self._ping(send))
                task_group.start_soon(cancel_on_finish, self._listen_for_exit_signal_with_grace)

                if self.data_sender_callable:
                    task_group.start_soon(self.data_sender_callable)    # type: ignore

                # Wait for the client to disconnect last
                task_group.start_soon(cancel_on_finish, lambda: self._listen_for_disconnect(receive))

        if self.background is not None:
            await self.background()
