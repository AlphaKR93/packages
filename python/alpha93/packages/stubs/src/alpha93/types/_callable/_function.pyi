import sys
import types
from collections.abc import Callable
from typing import Any, ParamSpec, Self, TypeVar, TypeVarTuple, overload

from _typeshed import AnnotateFunc, AnnotationForm
from alpha93.types import Method

class Function[**P, T](Callable[P, T]):
    __code__: types.CodeType
    __defaults__: tuple[Any, ...] | None
    __dict__: dict[str, Any]
    __name__: str
    __qualname__: str
    __annotations__: dict[str, AnnotationForm]
    __module__: str
    __kwdefaults__: dict[str, Any] | None

    if sys.version_info >= (3, 12):
        __type_params__: tuple[TypeVar | ParamSpec | TypeVarTuple, ...]
    if sys.version_info >= (3, 14):
        __annotate__: AnnotateFunc | None

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        ...

    if sys.version_info >= (3, 13):
        def __new__(
            cls,
            code: types.CodeType,
            globals: dict[str, Any],
            name: str | None = None,
            argdefs: tuple[object, ...] | None = None,
            closure: tuple[types.CellType, ...] | None = None,
            kwdefaults: dict[str, object] | None = None,
        ) -> Self: ...
    else:
        def __new__(
            cls,
            code: types.CodeType,
            globals: dict[str, Any],
            name: str | None = None,
            argdefs: tuple[object, ...] | None = None,
            closure: tuple[types.CellType, ...] | None = None,
        ) -> Self: ...

    @overload
    def __get__(self, instance: None, owner: types.NoneType, /) -> Self: ...
    @overload
    def __get__[C](self, instance: C, owner: type[C] | None = None, /) -> Method[C, P, T]: ...

    @property
    def __closure__(self) -> tuple[types.CellType, ...] | None:
        ...

    @property
    def __globals__(self) -> dict[str, Any]:
        ...

    @property
    def __builtins__(self) -> dict[str, Any]:
        ...
