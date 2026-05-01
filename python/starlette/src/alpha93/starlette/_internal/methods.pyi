from enum import Enum
from typing import Literal


type LiteralMethods = Literal["GET", "PUT", "POST", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"]

class Methods(Enum):
    get = "GET"
    put = "PUT"
    post = "POST"
    delete = "DELETE"
    options = "OPTIONS"
    head = "HEAD"
    patch = "PATCH"
    trace = "TRACE"
