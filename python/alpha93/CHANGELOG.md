# Changelogs

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
