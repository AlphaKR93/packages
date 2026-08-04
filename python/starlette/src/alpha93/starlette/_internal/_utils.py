import functools
from contextlib import contextmanager
from inspect import iscoroutinefunction

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any


class AwaitableOrContextManagerWrapper:
    __slots__ = ("aw", "entered")

    def __init__(self, aw, /) -> None:
        self.aw = aw

    def __await__(self, /):
        return self.aw.__await__()

    async def __aenter__(self, /):
        self.entered = await self.aw
        return self.entered

    async def __aexit__(self, *args: Any):
        await self.entered.close()
        return None

def is_async_callable(obj, /):
    while isinstance(obj, functools.partial):
        obj = obj.func

    return iscoroutinefunction(obj) or (callable(obj) and iscoroutinefunction(obj.__call__))

@contextmanager
def collapse_excgroups() -> Generator[None]:
    try:
        yield
    except BaseException as exc:
        while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
            exc = exc.exceptions[0]

        raise
