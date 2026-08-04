from terser_hints import constant

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from .types import Coroutine


# noinspection shadowing-builtins
@constant
def enumerate():
    import builtins

    async def __aenumerate(iterable, start: int, /):
        async for k in iterable:
            yield start, k
            start += 1

    def __func(iterable, /, start = 0):
        return (__aenumerate if hasattr(iterable, "__aiter__") else builtins.enumerate)(iterable, start)
    return __func


def throw(cls, /, *args, caused_by = None, **kwargs):
    try:
        if caused_by: raise cls(*args) from caused_by
        raise cls(*args)
    except cls as exc:
        for k, v in kwargs.items(): setattr(exc, k, v)
        return exc


def catch(*types: type, coro: bool | None = None):
    if coro is None or coro:
        def acall[**P](fn: Coroutine[P, Any], /):
            async def __func(*args: P.args, **kwargs: P.kwargs):
                try: return await fn(*args, **kwargs), None
                except types as e: return None, e
            return __func
    if coro is None or not coro:
        def call[**P](fn: Callable[P, Any], /):
            def __func(*args: P.args, **kwargs: P.kwargs):
                try: return fn(*args, **kwargs), None
                except types as e: return None, e
            return __func

    if coro is not None:
        # noinspection PyUnboundLocalVariable
        return acall if coro else call

    import inspect

    def __determine[**P](fn: Callable[P, Any] | Coroutine[P, Any], /):
        return acall(fn) \
            if inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn) or inspect.isawaitable(fn) \
            else call(fn)
    return __determine
