from collections.abc import Iterable
from functools import reduce

__all__ = (
    "flatmap",
)

def flatmap[K, V](mappings: Iterable[dict[K, V]]) -> dict[K, V]:
    return reduce(dict.__or__, mappings)
