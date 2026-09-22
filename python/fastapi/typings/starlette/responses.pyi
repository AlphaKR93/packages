import os
from collections.abc import AsyncIterable, Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from .background import BackgroundTask
from .datastructures import URL, MutableHeaders
from .types import Receive, Scope, Send

class Response:
    media_type = ...
    charset = ...
    def __init__(
        self,
        content: Any = ...,
        status_code: int = ...,
        headers: Mapping[str, str] | None = ...,
        media_type: str | None = ...,
        background: BackgroundTask | None = ...,
    ) -> None: ...
    def render(self, content: Any) -> bytes | memoryview: ...
    def init_headers(self, headers: Mapping[str, str] | None = ...) -> None: ...
    @property
    def headers(self) -> MutableHeaders: ...
    def set_cookie(
        self,
        key: str,
        value: str = ...,
        max_age: int | None = ...,
        expires: datetime | str | int | None = ...,
        path: str | None = ...,
        domain: str | None = ...,
        secure: bool = ...,
        httponly: bool = ...,
        samesite: Literal["lax", "strict", "none"] | None = ...,
        partitioned: bool = ...,
    ) -> None: ...
    def delete_cookie(
        self,
        key: str,
        path: str = ...,
        domain: str | None = ...,
        secure: bool = ...,
        httponly: bool = ...,
        samesite: Literal["lax", "strict", "none"] | None = ...,
        partitioned: bool = ...,
    ) -> None: ...
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...

class HTMLResponse(Response):
    media_type = ...

class PlainTextResponse(Response):
    media_type = ...

class JSONResponse(Response):
    media_type = ...
    def __init__(
        self,
        content: Any,
        status_code: int = ...,
        headers: Mapping[str, str] | None = ...,
        media_type: str | None = ...,
        background: BackgroundTask | None = ...,
    ) -> None: ...
    def render(self, content: Any) -> bytes: ...

class RedirectResponse(Response):
    def __init__(
        self,
        url: str | URL,
        status_code: int = ...,
        headers: Mapping[str, str] | None = ...,
        background: BackgroundTask | None = ...,
    ) -> None: ...

type Content = str | bytes | memoryview
type SyncContentStream = Iterable[Content]
type AsyncContentStream = AsyncIterable[Content]
type ContentStream = AsyncContentStream | SyncContentStream

class StreamingResponse(Response):
    body_iterator: AsyncContentStream
    def __init__(
        self,
        content: ContentStream,
        status_code: int = ...,
        headers: Mapping[str, str] | None = ...,
        media_type: str | None = ...,
        background: BackgroundTask | None = ...,
    ) -> None: ...
    async def listen_for_disconnect(self, receive: Receive) -> None: ...
    async def stream_response(self, send: Send) -> None: ...
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...

class MalformedRangeHeader(Exception):
    def __init__(self, content: str = ...) -> None: ...

class RangeNotSatisfiable(Exception):
    def __init__(self, max_size: int) -> None: ...

class FileResponse(Response):
    chunk_size = ...
    max_ranges = ...
    def __init__(
        self,
        path: str | os.PathLike[str],
        status_code: int = ...,
        headers: Mapping[str, str] | None = ...,
        media_type: str | None = ...,
        background: BackgroundTask | None = ...,
        filename: str | None = ...,
        stat_result: os.stat_result | None = ...,
        content_disposition_type: str = ...,
    ) -> None: ...
    def set_stat_headers(self, stat_result: os.stat_result) -> None: ...
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...
    def generate_multipart(
        self,
        ranges: Sequence[tuple[int, int]],
        boundary: str,
        max_size: int,
        content_type: str,
    ) -> tuple[int, Callable[[int, int], bytes]]:
        r"""
        Multipart response headers generator.

        ```
        --{boundary}\r\n
        Content-Type: {content_type}\r\n
        Content-Range: bytes {start}-{end-1}/{max_size}\r\n
        \r\n
        ..........content...........\r\n
        --{boundary}\r\n
        Content-Type: {content_type}\r\n
        Content-Range: bytes {start}-{end-1}/{max_size}\r\n
        \r\n
        ..........content...........\r\n
        --{boundary}--
        ```
        """
