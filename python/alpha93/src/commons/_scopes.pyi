from collections.abc import Callable


def constant[T](func: Callable[[], T]) -> T: ...
