from typing import override

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

import shutil

from makepatch._config import PatcherConfig
from makepatch.core import PatchApplier

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any, Final


class PatcherBuildHook(BuildHookInterface):
    PLUGIN_NAME = "makepatch"

    def __init__(self, /, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__config: Final = PatcherConfig.from_hatch(self)
        self.__patcher: Final = PatchApplier(self.__config)

    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        config = self.__config
        patcher = self.__patcher

        if patcher.setup_required():
            patcher.resolve_sources()
            patcher.resolve_src()

            dst = config.project_root / "work/patched"
            if dst.exists():
                if not dst.is_dir(): raise RuntimeError(f"{dst} is not a directory")
                shutil.rmtree(dst)
            dst.mkdir(parents=True)

            patcher.copy(dst)
            patcher.apply(dst / config.module_source)
            self.__success = False
            return

        patcher.resolve_src()

        dst = self.__dst = config.project_root / "src" / config.module_name
        if dst.exists():
            if not dst.is_dir(): raise RuntimeError(f"{dst} is not a directory")
            shutil.rmtree(dst)
        dst.mkdir(parents=True)

        patcher.copy(dst)
        self.__success = patcher.apply(dst)
        build_data["force_include"][str(dst.relative_to(config.project_root))] = dst.name

    @override
    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        if not self.__success:
            return

        if not self.__dst.exists() or not self.__dst.is_dir():
            raise RuntimeError(f"{self.__dst} does not exists or is not a directory")
        shutil.rmtree(self.__dst)
