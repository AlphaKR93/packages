from ._mapping import MappingAccessor, MutableMappingAccessor, accessor
from ._singleton import (
    MutableSingletonSequence,
    SingletonList,
    SingletonSequence,
    SingletonTuple,
)
from .utils import flatmap

if __debug__ and __import__("typing").TYPE_CHECKING:
    from ._mapping import MappingLike, MutableMappingLike

__all__ = (
    "MappingAccessor",
    "MappingLike",
    "MutableMappingAccessor",
    "MutableMappingLike",
    "MutableSingletonSequence",
    "SingletonList",
    "SingletonSequence",
    "SingletonTuple",
    "accessor",
    "flatmap",
)
