import builtins
import errno
import os


def __os_error(exc: builtins.OSError, /, **kwargs):
    for k, v in kwargs.items(): setattr(exc, k, v)
    return exc

def OSError(errno: int, summary: str, /, file_name: str | None = None, target_name: str | None = None):
    return __os_error(
        builtins.OSError(summary),
        errno=errno,
        strerror=os.strerror(errno),
        filename=file_name,
        filename2=target_name
    )

def IOError(file_name: str, summary: str, /, target_name: str | None = None):
    return builtins.OSError(errno.EIO, summary, file_name, target_name)

def FileNotFoundError(file_name: str, summary: str | None = None, /, target_name: str | None = None):
    return __os_error(builtins.FileNotFoundError(summary), filename=file_name, filename2=target_name)

def NotADirectoryError(file_name: str, summary: str | None = None, /, target_name: str | None = None):
    return __os_error(builtins.NotADirectoryError(summary), filename=file_name, filename2=target_name)
