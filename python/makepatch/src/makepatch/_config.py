import os
from collections.abc import Iterable
from pathlib import Path
from typing import final, Annotated, ClassVar

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

if __debug__ and __import__("typing").TYPE_CHECKING:

    from makepatch._types.hatch import HatchHookInterface


@final
class PatcherConfig(BaseModel):
    __INTERNAL: ClassVar[object] = object()
    __INSTANCE: ClassVar[PatcherConfig | None] = None

    module_source: Annotated[str, Field(alias="module-source")]
    excludes: Annotated[Iterable[str], Field(default_factory=frozenset)]
    dev_excludes: Annotated[Iterable[str], Field(alias="dev-excludes", default_factory=frozenset)]

    module_name: Annotated[SkipJsonSchema[str], Field(exclude=True)]
    project_root: Annotated[SkipJsonSchema[Path], Field(exclude=True)]

    def __init__(self, obj: object, /, **kwargs):
        if obj is not self.__INTERNAL:
            raise RuntimeError("Security error: External initialization is prohibited")
        if "/" in kwargs["module-source"]:
            _, kwargs["module_name"] = str(kwargs["module-source"]).rsplit(os.sep, 1)
        else:
            kwargs["module_name"] = kwargs["module-source"]
        super().__init__(**kwargs)

    @classmethod
    def from_hatch(cls, hook: HatchHookInterface, /) -> PatcherConfig:
        if PatcherConfig.__INSTANCE:
            raise RuntimeError(f"{cls.__name__} already initialized")

        config = hook.config["options"]
        config["project_root"] = Path(hook.root).resolve()
        PatcherConfig.__INSTANCE = PatcherConfig(PatcherConfig.__INTERNAL, **config)
        assert PatcherConfig.__INSTANCE
        return PatcherConfig.__INSTANCE

    @classmethod
    def from_pyproject(cls, root: Path, /):
        pyproject_toml = (root / "pyproject.toml").resolve()
        if not pyproject_toml.exists() or not pyproject_toml.is_file():
            raise FileNotFoundError(f"{pyproject_toml} does not exist or is not a file")

        import tomllib
        try:
            with open(pyproject_toml, 'rb') as f:
                config = tomllib.load(f)["tool"]["hatch"]["build"]["hooks"]["makepatch"]["options"]
                config["project_root"] = Path(root).resolve()
                return PatcherConfig(PatcherConfig.__INTERNAL, **config)
        except tomllib.TOMLDecodeError as e:
            raise RuntimeError(f"Cannot parse pyproject.toml") from e
