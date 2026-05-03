import os
from pathlib import Path
from typing import override

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

import shutil, subprocess, tomllib

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any, Final


class CustomBuildHook(BuildHookInterface):
    @property
    def __root(self):
        return Path(self.root)

    @property
    def __config(self):
        with open(self.__root / "pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)

        try:
            config = pyproject["tool"]["patcher"]
        except KeyError as e:
            raise RuntimeError("[tool.patcher] not found in pyproject.toml") from e
        return config["module-source"], frozenset(config.get("excludes", set()))

    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        module_name, exclude_globs = self.__config

        src = self.__root / "work" / "sources" / module_name
        if not src.exists(): raise RuntimeError(f"{src} not exists")
        elif not src.is_dir(): raise RuntimeError(f"{src} is not a directory")

        excludes = set()
        for glob in exclude_globs:
            excludes |= set(str(excluded.relative_to(src)) for excluded in src.rglob(glob) if str(excluded.relative_to(src)).startswith(glob.split(os.sep)[0]))

        patches = self.__root / "patches"
        if not patches.exists(): raise RuntimeError(f"{patches} not exists")
        elif not patches.is_dir(): raise RuntimeError(f"{patches} is not a directory")

        dst = self.__root / "src" / module_name
        if dst.exists():
            if not dst.is_dir(): raise RuntimeError(f"{dst} is not a directory")
            shutil.rmtree(dst)
        dst.mkdir(parents=True)

        # Copy sources, skipping excludes
        for src_file in src.rglob("*"):
            if not src_file.is_file(): continue

            rel = src_file.relative_to(src)
            if str(rel) in excludes: continue

            dst_file = dst / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

        # Apply patches
        for patch_file in sorted(patches.rglob("*.patch")):
            rel_patch = patch_file.relative_to(patches)
            # e.g. foo.py.patch → foo.py
            target_rel = rel_patch.with_suffix("")
            target = dst / target_rel

            if not target.parent.exists():
                target.parent.mkdir(parents=True, exist_ok=False)

            result = subprocess.run(
                ["patch", "--unified", str(target), str(patch_file)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to apply {rel_patch}:\n{result.stderr}")

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        module_source, _ = self.__config
        dst = self.__root / "src" / module_source
        if dst.exists():
            shutil.rmtree(dst)
