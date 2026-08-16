from ._concurrent import GuardedValue
from ._mapping import MappingAccessor, MutableMappingAccessor, accessor
from ._singleton import (
    MetaSingleton,
    MutableSingletonSequence,
    Singleton,
    SingletonList,
    SingletonSequence,
    SingletonTuple,
)
from ._weakref import Reference
from .utils import flatmap

if __debug__ and __import__("typing").TYPE_CHECKING:
    from ._mapping import MappingLike, MutableMappingLike

__all__ = (
    "GuardedValue",
    "MappingAccessor",
    "MappingLike",
    "MetaSingleton",
    "MutableMappingAccessor",
    "MutableMappingLike",
    "MutableSingletonSequence",
    "Reference",
    "Singleton",
    "SingletonList",
    "SingletonSequence",
    "SingletonTuple",
    "accessor",
    "flatmap",
)
