from ._mapping import MappingAccessor, MutableMappingAccessor, accessor

if __debug__ and __import__("typing").TYPE_CHECKING:
    from ._mapping import MappingLike, MutableMappingLike

__all__ = (
    "MappingAccessor",
    "MappingLike",
    "MutableMappingAccessor",
    "MutableMappingLike",
    "accessor",
)
