import os
import tempfile
from pathlib import Path
from shlex import quote
from subprocess import PIPE, check_call

from hatch_shadow.managers import PackageManager


class UvPackageManager(PackageManager):
    @classmethod
    def is_supported(cls, root: str) -> bool:
        return (Path(root) / "pyproject.toml").exists()

    def install_packages(self, target: str):
        fd, requirements = tempfile.mkstemp()
        os.close(fd)
        del fd

        check_call([
            "uv",
            "export",
            "--project",
            quote(str(self.root)),
            "--no-dev",
            "--no-header",
            "--no-emit-project",
            "--output-file",
            quote(requirements)
        ], stdout=PIPE, stderr=PIPE, shell=False)

        try:
            return check_call([
                "uv",
                "pip", "install",
                "--no-build",
                "--requirements",
                quote(requirements),
                "--target",
                quote(target),
            ], stdout=PIPE, stderr=PIPE, shell=False)
        finally:
            Path(requirements).unlink()
