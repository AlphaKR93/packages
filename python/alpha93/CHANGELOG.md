# Changelogs

## 1.2.x

### 1.2.5

- Implemented real fix of 1.2.4

### 1.2.4

- Fixed `alpha93.commons.types.typed` failed to initialize object

### 1.2.3

- Refactored `alpha93.commons.types`
  - `constructor[T].__call__(T.__init__)` is now `typed[T](T.__init__)`
  - Deprecated `constructor[T]`, will be removed in 1.3.0
  - Added `type_is[T](object) -> TypeGuard[T]`

### 1.2.2

- PyCharm doesn't recognize `i` is the alias of `__call__`

### 1.2.1

- Forgot to add `alpha93.commons.types.constructor#i`

### 1.2.0

- Added `alpha93.commons.types.constructor` for PyCharm (it handles `__call__` incorrectly)<br>
  Usage: `constructor[Foo].i(Foo.__init__)(*args, **kwargs)` (`i` is alias of `__call__`)

## 1.1.x

### 1.1.0

- Merged versioning system (previously the version of `alpha93-stubs` was `1.0.1`)
- Added `alpha93.commons.types.type_is`<br>
  Example: `type_is[Iterable].hasattr(obj, "__iter__")`

## 0.6.x

### 0.6.0

- Added `Singleton`, `Reference`, `GuardedValue` in `alpha93.collections`
- Added `alpha93.commons.utils.exceptions`

## 0.5.x

### 0.5.3

- Fixed incorrectly set `alpha93.commons.futures.__all__`

### 0.5.2

- Fixed incorrectly built `alpha93-stubs`

### 0.5.1

- Fixed `AttributeError` when attempting to access after `del MutableSingletonSequence.value` (now returns `None`
  properly)

### 0.5.0

- Bumped minor version to 0.5.0
- Migrated `alpha93.commons.collections` to `alpha93.collections`
- Moved constructor of `SingletonSequence` and `MutableSingletonSequence` to `SingletonTuple` and `SingletonList`
- Added `alpha93.collections.utils`

## 0.4.x

### 0.4.2

- Renamed `alpha93.commons.utils` into `alpha93.commons.collections`
- Added `SingletonSequence` and `MutableSingletonSequence` in `alpha93.commons.collections`

### 0.4.1

- Removed `alpha93.commons.types.AnyObject` and added `alpha93.commons.types.any_object()`<br/>
  (I wanted to create something that acts as both a type alias of `Any` and a callable function that returns `Any`,
  but I can't figure out how to do that.)

### 0.4.0

- Initial publish
