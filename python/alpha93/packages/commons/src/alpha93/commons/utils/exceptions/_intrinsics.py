def __intrinsics(identifier: str, /):
    identifier = identifier + ": "
    def __throw(message: str, /):
        raise NotImplementedError(identifier + message)
    return __throw

TODO = __intrinsics("TODO")
