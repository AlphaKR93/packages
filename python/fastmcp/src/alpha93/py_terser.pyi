from collections.abc import Callable


type Runtime[T] = T

def keep_types[C: Callable](fn: C, /) -> C: ...
