from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from contextlib import AbstractAsyncContextManager
from typing import Any

from .requests import Request
from .responses import Response
from .websockets import WebSocket

type Scope = MutableMapping[str, Any]
type Message = MutableMapping[str, Any]
type Receive = Callable[[], Awaitable[Message]]
type Send = Callable[[Message], Awaitable[None]]
type ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]
type StatelessLifespan[T] = Callable[[T], AbstractAsyncContextManager[None]]
type StatefulLifespan[T] = Callable[
    [T], AbstractAsyncContextManager[Mapping[str, Any]]
]
type Lifespan[T] = StatelessLifespan[T] | StatefulLifespan[T]
type HTTPExceptionHandler = Callable[
    [Request, Exception], Response | Awaitable[Response]
]
type WebSocketExceptionHandler = Callable[[WebSocket, Exception], Awaitable[None]]
type ExceptionHandler = HTTPExceptionHandler | WebSocketExceptionHandler
