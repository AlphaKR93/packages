import os
import re
import subprocess

from pathlib import Path

from makepatch._config import PatcherConfig

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Final


def rebuild_patches():
    TIMESTAMP = re.compile(r"\t\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{9} \+\d{4}")
    ARGS = (
        "--ignore-trailing-space",
        "--strip-trailing-cr",
    )

    root: Final = Path(os.getcwd())
    config: Final = PatcherConfig.from_pyproject(root)

    ref = root / "work/sources" / config.module_source
    if not ref.exists() or not ref.is_dir():
        raise RuntimeError(f"{ref} does not exists or is not a directory")

    src = root / "work/patched" / config.module_source
    if not ref.exists() or not ref.is_dir():
        raise RuntimeError(f"{ref} does not exists or is not a directory")

    patches = root / "patches"
    if patches.exists():
        if not patches.is_dir(): raise RuntimeError(f"{patches} is not a directory")
        __import__("shutil").rmtree(patches)
    patches.mkdir(parents=True)

    excludes = set()
    for glob in config.excludes:
        dirname = glob.split(os.sep, 1)[0]
        for excluded in src.rglob(glob):
            if (rel_str := str(excluded.relative_to(src))).startswith(dirname):
                excludes.add(rel_str)

    generated = []
    for target_file in sorted(src.rglob("*")):
        if not target_file.is_file(): continue

        rel_file = target_file.relative_to(src)
        if str(rel_file) in excludes: continue

        edited = target_file.relative_to(root)
        origin = (ref / rel_file).relative_to(root)

        result = subprocess.run(
            ("diff", "--unified", *ARGS, "--new-file", str(origin), str(edited)),
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
                l = result.stdout.splitlines(keepends=True)
                l[0] = TIMESTAMP.sub("", l[0])
                l[1] = TIMESTAMP.sub("", l[1])
                f.write(''.join(l))
            generated.append(patch)
    else:
        print(f"Successfully generated {len(generated)} patches")
