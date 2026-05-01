from dataclasses import dataclass

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any, Literal


@dataclass(frozen=True)
class Depends:
    """
    Declare a FastAPI dependency.

    It takes a single "dependable" callable (like a function).

    Don't call it directly, FastAPI will call it for you.

    Read more about it in the
    [FastAPI docs for Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/).

    **Example**

    ```python
    from typing import Annotated

    from fastapi import Depends, FastAPI

    app = FastAPI()


    async def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):
        return {"q": q, "skip": skip, "limit": limit}


    @app.get("/items/")
    async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
        return commons
    ```
    """

    dependency: Callable[..., Any] | None = None
    """
    A "dependable" callable (like a function).

    Don't call it directly, FastAPI will call it for you, just pass the object
    directly.

    Read more about it in the
    [FastAPI docs for Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
    """

    use_cache: bool = True
    """
    By default, after a dependency is called the first time in a request, if
    the dependency is declared again for the rest of the request (for example
    if the dependency is needed by several dependencies), the value will be
    re-used for the rest of the request.

    Set `use_cache` to `False` to disable this behavior and ensure the
    dependency is called again (if declared more than once) in the same request.

    Read more about it in the
    [FastAPI docs about sub-dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/#using-the-same-dependency-multiple-times)
    """

    scope: Literal["function", "request"] | None = None
    """
    Mainly for dependencies with `yield`, define when the dependency function
    should start (the code before `yield`) and when it should end (the code
    after `yield`).

    * `"function"`: start the dependency before the *path operation function*
        that handles the request, end the dependency after the *path operation
        function* ends, but **before** the response is sent back to the client.
        So, the dependency function will be executed **around** the *path operation
        **function***.
    * `"request"`: start the dependency before the *path operation function*
        that handles the request (similar to when using `"function"`), but end
        **after** the response is sent back to the client. So, the dependency
        function will be executed **around** the **request** and response cycle.

    Read more about it in the
    [FastAPI docs for FastAPI Dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope)
    """


@dataclass(frozen=True)
class Security(Depends):
    """
    Declare a FastAPI Security dependency.

    The only difference with a regular dependency is that it can declare OAuth2
    scopes that will be integrated with OpenAPI and the automatic UI docs (by default
    at `/docs`).

    It takes a single "dependable" callable (like a function).

    Don't call it directly, FastAPI will call it for you.

    Read more about it in the
    [FastAPI docs for Security](https://fastapi.tiangolo.com/tutorial/security/) and
    in the
    [FastAPI docs for OAuth2 scopes](https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/).

    **Example**

    ```python
    from typing import Annotated

    from fastapi import Security, FastAPI

    from .db import User
    from .security import get_current_active_user

    app = FastAPI()

    @app.get("/users/me/items/")
    async def read_own_items(
        current_user: Annotated[User, Security(get_current_active_user, scopes=["items"])]
    ):
        return [{"item_id": "Foo", "owner": current_user.username}]
    ```
    """

    scopes: Sequence[str] | None = None
    """
    OAuth2 scopes required for the *path operation* that uses this Security
    dependency.

    The term "scope" comes from the OAuth2 specification, it seems to be
    intentionally vague and interpretable. It normally refers to permissions,
    in cases to roles.

    These scopes are integrated with OpenAPI (and the API docs at `/docs`).
    So they are visible in the OpenAPI specification.

    Read more about it in the
    [FastAPI docs about OAuth2 scopes](https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/)
    """
