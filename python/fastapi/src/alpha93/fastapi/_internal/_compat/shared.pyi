from typing import Any, TypeGuard


def lenient_issubclass[T](cls: Any, class_or_tuple: type[T] | tuple[type[T], ...] | None, /) -> TypeGuard[type[T]]:
    ...
