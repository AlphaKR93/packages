import errno
import os


class UnsupportedError(NotImplementedError):
    pass

class OSNotImplementedError(NotImplementedError, OSError):
    errno = errno.ENOSYS
    strerror = os.strerror(errno)

    def __init__(self, /, *args, **kwargs):
        self.errno = errno.ENOSYS
        self.strerror = os.strerror(self.errno)
        super().__init__(*args, **kwargs)

class OSUnsupportedError(UnsupportedError, OSNotImplementedError):
    errno = errno.ENOTSUP
    strerror = os.strerror(errno)

    def __init__(self, /, *args, **kwargs):
        self.errno = errno.ENOTSUP
        self.strerror = os.strerror(self.errno)
        super().__init__(*args, **kwargs)
