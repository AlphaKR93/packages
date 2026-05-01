from collections.abc import Callable
from typing import TypedDict, Any
from warnings import deprecated as _deprecated

from pydantic import AliasPath, AliasChoices, Discriminator
from pydantic.config import JsonDict
from pydantic.fields import FieldInfo


class PydanticFieldInfoParameters[T](TypedDict, total=False):
    annotation: type[T] | None
    """The type annotation of the field."""

    alias: str | None
    """The alias name of the field."""

    validation_alias: str | AliasPath | AliasChoices | None
    """The validation alias of the field."""

    serialization_alias: str | None
    """The serialization alias of the field."""

    title: str | None
    """The title of the field."""

    field_title_generator: Callable[[str, FieldInfo], str] | None
    """A callable that takes a field name and returns title for it."""

    description: str | None
    """The description of the field."""

    examples: list[T] | None
    """List of examples of the field."""

    exclude: bool | None
    """Whether to exclude the field from the model serialization."""

    exclude_if: Callable[[Any], bool] | None
    """A callable that determines whether to exclude a field during serialization based on its value."""

    discriminator: str | Discriminator | None
    """Field name or Discriminator for discriminating the type in a tagged union."""

    deprecated: _deprecated | str | bool | None
    """A deprecation message, an instance of `warnings.deprecated` or a boolean.
    If `True`, a default deprecation message will be emitted when accessing the field."""

    json_schema_extra: JsonDict | Callable[[JsonDict], None] | None
    """A dict or callable to provide extra JSON schema properties."""

    metadata: list[Any]
    """The metadata list. Contains all the data that isn't expressed as direct `FieldInfo` attributes, including:

        * Type-specific constraints, such as `gt` or `min_length` (these are converted to metadata classes such as `annotated_types.Gt`).
        * Any other arbitrary object used within [`Annotated`][typing.Annotated] metadata
          (e.g. [custom types handlers](../concepts/types.md#as-an-annotation) or any object not recognized by Pydantic)."""
