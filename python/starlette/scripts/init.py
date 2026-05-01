#!/usr/bin/env python3
import shutil
import subprocess
import tomllib

from pathlib import Path

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Final

def main():
    root: Final = Path(__import__("os").getcwd())

    def __load_config():
        with open(root / "pyproject.toml", 'rb') as f:
            pyproject = tomllib.load(f)

        try:
            config = pyproject["tool"]["patcher"]
        except KeyError as e:
            raise RuntimeError("[tool.patcher] not found in pyproject.toml") from e
        return config["module-source"], \
            frozenset(config.get("excludes", set())), \
            frozenset(config.get("dev-excludes", set()))

    module_name, exclude_globs, src_exclude_globs = __load_config()

    src = root / "work" / "sources"
    src_module = src / module_name
    if not src_module.exists(): raise RuntimeError(f"{src} not exists")
    elif not src_module.is_dir(): raise RuntimeError(f"{src} is not a directory")

    excludes = set()
    for glob in exclude_globs:
        excludes |= set(str(excluded.relative_to(src_module)) for excluded in src_module.rglob(glob))

    src_excludes = set()
    for exclude_glob in src_exclude_globs:
        src_excludes |= set(str(excluded.relative_to(src)) for excluded in src.rglob(exclude_glob))

    dst = root / "work" / "patched"
    dst_module = dst / module_name
    if dst_module.exists():
        if not dst_module.is_dir(): raise RuntimeError(f"{dst} is not a directory")
        __import__("shutil").rmtree(dst)
    dst.mkdir(parents=True)

    for src_file in src.rglob("*"):
        if not src_file.is_file(): continue

        rel = src_file.relative_to(src)
        if str(rel) in src_excludes: continue
        if src_file.is_relative_to(src_module) and str(src_file.relative_to(src_module)) in excludes: continue

        dst_file = dst / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)

    patches = root / "patches"
    if not patches.exists(): raise RuntimeError(f"{patches} not exists")
    elif not patches.is_dir(): raise RuntimeError(f"{patches} is not a directory")

    for patch_file in sorted(patches.rglob("*.patch")):
        rel_patch = patch_file.relative_to(patches)
        # e.g. foo.py.patch → foo.py
        target_rel = rel_patch.with_suffix("")
        target = dst_module / target_rel

        if not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=False)

        result = subprocess.run(
            ["patch", "--unified", str(target), str(patch_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to apply {rel_patch}:\n{result.stderr}")

if __name__ == "__main__":
    main()
