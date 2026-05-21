import shutil
from pathlib import Path

from makepatch._config import PatcherConfig
from makepatch.core import PatchApplier

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Final


from ._rebuild import rebuild_patches

def init_patches():
    root: Final = Path(__import__("os").getcwd())
    config: Final = PatcherConfig.from_pyproject(root)
    patcher: Final = PatchApplier(config)

    patcher.resolve_sources()
    patcher.resolve_src()

    dst = root / "work" / "patched"
    if dst.exists():
        if not dst.is_dir(): raise RuntimeError(f"{dst} is not a directory")
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    patcher.copy(dst)
    exit(not patcher.apply(dst / config.module_source))
