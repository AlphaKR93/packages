from collections.abc import Mapping

class HTTPException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str | None = ...,
        headers: Mapping[str, str] | None = ...,
    ) -> None: ...

class WebSocketException(Exception):
    def __init__(self, code: int, reason: str | None = ...) -> None: ...
