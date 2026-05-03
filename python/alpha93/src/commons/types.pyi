from collections.abc import Awaitable, Callable, Sequence


type AwaitableOr[T] = T | Awaitable[T]
type SequenceOr[T] = T | Sequence[T]

type Decorator[F, V] = Callable[[F], V]
type Wrapper[T] = Decorator[T, T]
