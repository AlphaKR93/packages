import os
import shutil
import subprocess
from typing import final

from makepatch._config import PatcherConfig


if __debug__ and __import__("typing").TYPE_CHECKING:
    from pathlib import Path
    from typing import Final


@final
class PatchApplier:
    __slots__ = (
        "__config",
        "__excludes",
        "__excludes_dev",
        "__patches",
        "__sources",
        "__src",
    )

    def __init__(self, config: PatcherConfig, /) -> None:
        self.__config: Final = config
        self.__excludes: Final = set[str]()
        self.__excludes_dev: Final = set[str]()

        # resolve patches
        self.__patches: Final = self.__resolve_path(config.project_root / "patches")

        # INTENDED: required for later use
        self.__src: Path | None = None
        self.__sources: Path | None = None

    def has_sdist_cache(self, /):
        return (self.__config.project_root / "src" / self.__config.module_name).resolve().exists()

    def setup_required(self, /):
        return not (self.__config.project_root / "work/patched").resolve().exists()

    @staticmethod
    def __resolve_path(path: Path, /):
        path = path.resolve()
        if not path.exists() or not path.is_dir():
            raise RuntimeError(f"{path} does not exist or is not a directory")
        return path

    def resolve_src(self, /):
        """
        Resolves `module` src root, where the codes are placed
        """
        assert not self.__src
        if not self.__sources:
            self.__sources = self.__resolve_path(self.__config.project_root / "work/sources")
        assert self.__sources
        src = self.__src = self.__resolve_path(self.__sources / self.__config.module_source)

        for glob in self.__config.excludes:
            dirname = glob.split(os.sep, 1)[0]
            for excluded in src.rglob(glob):
                if (rel_str := str(excluded.relative_to(src))).startswith(dirname):
                    self.__excludes.add(rel_str)

    def resolve_sources(self, /):
        """
        Resolves entire git sources
        """
        assert not self.__sources
        sources = self.__sources = self.__resolve_path(self.__config.project_root / "work/sources")

        for glob in self.__config.dev_excludes:
            dirname = glob.split(os.sep, 1)[0]
            for excluded in sources.rglob(glob):
                if (rel_str := str(excluded.relative_to(sources))).startswith(dirname):
                    self.__excludes_dev.add(rel_str)

    def copy(self, dst: Path, /):
        if self.__excludes_dev:
            src = self.__sources
            excludes = self.__excludes_dev
            filter_ = lambda path: path.is_relative_to(self.__src) and (str(path.relative_to(self.__src)) in self.__excludes)
        else:
            src = self.__src
            excludes = self.__excludes
            filter_ = None

        assert src and excludes
        for src_file in src.rglob("*"):
            if not src_file.is_file():
                assert src_file.exists()
                continue

            rel = src_file.relative_to(src)
            if (str(rel) in excludes) or (filter_ and filter_(src_file)):
                continue

            dst_file = dst / rel
            if dst_file.exists():
                raise RuntimeError(f"Failed to copy file {rel}: file exists")
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

    def apply(self, dst: Path, /) -> bool:
        total = []
        for patch in self.__patches.rglob("*.patch"):
            rel_patch = patch.relative_to(self.__patches)
            total.append(rel_patch)

            rel_dst = rel_patch.with_suffix("") # foo.py.patch -> foo.py
            dst_file = dst / rel_dst
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            res = subprocess.run(
                ["patch", "--unified", str(dst_file), str(patch)],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                print(f"Failed to apply {rel_patch}:\n\t"
                      + "\n\t".join(res.stdout.splitlines()))
                break
        else:
            print(f"Successfully applied {len(total)} patches")
            return True
        return False
