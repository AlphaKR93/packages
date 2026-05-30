from collections.abc import Awaitable, Sequence


type AwaitableOr[T] = T | Awaitable[T]
type SequenceOr[T] = T | Sequence[T]
