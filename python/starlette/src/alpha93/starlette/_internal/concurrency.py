import functools

import anyio.to_thread
from terser_hints import constant


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


async def run_in_threadpool(func, *args, **kwargs):
    func = functools.partial(func, *args, **kwargs)
    return await anyio.to_thread.run_sync(func)


@constant
def iterate_in_threadpool():
    class _StopIteration(Exception):
        pass

    def _next(iterator: Iterator, /):
        # We can't raise `StopIteration` from within the threadpool iterator
        # and catch it outside that context, so we coerce them into a different
        # exception type.
        try:
            return next(iterator)
        except StopIteration:
            raise _StopIteration

    async def iterate(iterable: Iterable, /):
        as_iterator = iter(iterable)
        while True:
            try:
                yield await anyio.to_thread.run_sync(_next, as_iterator)
            except _StopIteration:
                break
    return iterate
