import sys
from pathlib import Path
from shlex import quote
from subprocess import PIPE, check_call

from hatch_shadow.managers import PackageManager


class PipPackageManager(PackageManager):
    @classmethod
    def is_supported(cls, root: str) -> bool:
        return (Path(root) / "requirements.txt").exists()

    def install_packages(self, target: str):
        return check_call([
            sys.executable,
            "-m", "pip",
            "install",
            "--upgrade",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "-r",
            quote(str(Path(self.root) / "requirements.txt")),
            "-t",
            quote(target),
        ], stdout=PIPE, stderr=PIPE, shell=False)
