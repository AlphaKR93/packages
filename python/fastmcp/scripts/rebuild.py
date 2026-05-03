#!/usr/bin/env python3

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
        return config["module-source"], frozenset(config.get("excludes", set()))

    module_name, excludes = __load_config()

    ref = root / "work" / "sources" / module_name
    if not ref.exists(): raise RuntimeError(f"{ref} not exists")
    elif not ref.is_dir(): raise RuntimeError(f"{ref} is not a directory")

    src = root / "work" / "patched" / module_name
    if not src.exists(): raise RuntimeError(f"{src} not exists")
    elif not src.is_dir(): raise RuntimeError(f"{src} is not a directory")

    patches = root / "patches"
    if patches.exists():
        if not patches.is_dir(): raise RuntimeError(f"{patches} is not a directory")
        __import__("shutil").rmtree(patches)
    patches.mkdir(parents=True)

    for target_file in sorted(src.rglob("*")):
        if not target_file.is_file(): continue

        rel_file = target_file.relative_to(src)
        if str(rel_file) in excludes: continue

        edited = target_file.relative_to(root)
        origin = (ref / rel_file).relative_to(root)

        result = subprocess.run(
            ("diff", "--unified", "--new-file", str(origin), str(edited)),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            continue
        elif result.returncode != 1:
            raise RuntimeError(f"Failed to generate a patch file for {edited} (return code {result.returncode}):"
                               f"\n{result.stderr}")
        else:
            patch = patches / rel_file.with_suffix(rel_file.suffix + ".patch")
            patch.parent.mkdir(parents=True, exist_ok=True)
            with open(patch, "x") as f:
                f.write(result.stdout)

if __name__ == "__main__":
    main()
