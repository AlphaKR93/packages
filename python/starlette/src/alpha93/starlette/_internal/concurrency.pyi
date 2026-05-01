from collections.abc import Callable
from typing import ParamSpec, TypeVar, Iterable, AsyncIterator


_P = ParamSpec("_P")
_T = TypeVar("_T")

async def run_in_threadpool(func: Callable[_P, _T], *args: _P.args, **kwargs: _P.kwargs) -> _T: ...
async def iterate_in_threadpool[T](iterator: Iterable[T], /) -> AsyncIterator[T]: ...
