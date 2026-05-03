from collections.abc import Callable
from typing import TypedDict, Any
from warnings import deprecated as _deprecated

from pydantic import AliasPath, AliasChoices, Discriminator
from pydantic.config import JsonDict
from pydantic.fields import FieldInfo


class PydanticFieldInfoParameters[T](TypedDict, total=False):
    annotation: type[T]
    """The type annotation of the field."""

    alias: str
    """The alias name of the field."""

    validation_alias: str | AliasPath | AliasChoices
    """The validation alias of the field."""

    serialization_alias: str
    """The serialization alias of the field."""

    title: str
    """The title of the field."""

    field_title_generator: Callable[[str, FieldInfo], str]
    """A callable that takes a field name and returns title for it."""

    description: str
    """The description of the field."""

    examples: list[T]
    """List of examples of the field."""

    exclude: bool
    """Whether to exclude the field from the model serialization."""

    exclude_if: Callable[[Any], bool]
    """A callable that determines whether to exclude a field during serialization based on its value."""

    discriminator: str | Discriminator
    """Field name or Discriminator for discriminating the type in a tagged union."""

    deprecated: _deprecated | str | bool
    """A deprecation message, an instance of `warnings.deprecated` or a boolean.
    If `True`, a default deprecation message will be emitted when accessing the field."""

    json_schema_extra: JsonDict | Callable[[JsonDict], None]
    """A dict or callable to provide extra JSON schema properties."""

    metadata: list[Any]
    """The metadata list. Contains all the data that isn't expressed as direct `FieldInfo` attributes, including:

        * Type-specific constraints, such as `gt` or `min_length` (these are converted to metadata classes such as `annotated_types.Gt`).
        * Any other arbitrary object used within [`Annotated`][typing.Annotated] metadata
          (e.g. [custom types handlers](../concepts/types.md#as-an-annotation) or any object not recognized by Pydantic)."""
