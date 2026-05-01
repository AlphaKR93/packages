from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence, Iterable
from typing import Any, TypedDict, Unpack

from commons.types import Wrapper
from fastapi.params import Depends
from fastapi.types import GenerateUniqueIdFunction
from pydantic.main import IncEx
from starlette.responses import Response
from starlette.routing import BaseRoute


class RouteParams(TypedDict, total=False):
    name: str
    """
    Name for this *path operation*. Only used internally.
    """

    response_model: Any
    """
    The type to use for the response.

    It could be any valid Pydantic *field* type. So, it doesn't have to
    be a Pydantic model, it could be other things, like a `list`, `dict`,
    etc.

    It will be used for:

    * Documentation: the generated OpenAPI (and the UI at `/docs`) will
        show it as the response (JSON Schema).
    * Serialization: you could return an arbitrary object and the
        `response_model` would be used to serialize that object into the
        corresponding JSON.
    * Filtering: the JSON sent to the client will only contain the data
        (fields) defined in the `response_model`. If you returned an object
        that contains an attribute `password` but the `response_model` does
        not include that field, the JSON sent to the client would not have
        that `password`.
    * Validation: whatever you return will be serialized with the
        `response_model`, converting any data as necessary to generate the
        corresponding JSON. But if the data in the object returned is not
        valid, that would mean a violation of the contract with the client,
        so it's an error from the API developer. So, FastAPI will raise an
        error and return a 500 error code (Internal Server Error).

    Read more about it in the
    [FastAPI docs for Response Model](https://fastapi.tiangolo.com/tutorial/response-model/).
    """

    status_code: int
    """
    The default status code to be used for the response.

    You could override the status code by returning a response directly.

    Read more about it in the
    [FastAPI docs for Response Status Code](https://fastapi.tiangolo.com/tutorial/response-status-code/).
    """

    dependencies: Sequence[Depends]
    """
    A list of dependencies (using `Depends()`) to be applied to the
    *path operation*.

    Read more about it in the
    [FastAPI docs for Dependencies in path operation decorators](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/).
    """

    methods: Iterable[str]

    operation_id: str
    """
    Custom operation ID to be used by this *path operation*.

    By default, it is generated automatically.

    If you provide a custom operation ID, you need to make sure it is
    unique for the whole API.

    You can customize the
    operation ID generation with the parameter
    `generate_unique_id_function` in the `FastAPI` class.

    Read more about it in the
    [FastAPI docs about how to Generate Clients](https://fastapi.tiangolo.com/advanced/generate-clients/#custom-generate-unique-id-function).
    """

    response_model_include: IncEx
    """
    Configuration passed to Pydantic to include only certain fields in the
    response data.

    Read more about it in the
    [FastAPI docs for Response Model - Return Type](https://fastapi.tiangolo.com/tutorial/response-model/#response_model_include-and-response_model_exclude).
    """

    response_model_exclude: IncEx
    """
    Configuration passed to Pydantic to exclude certain fields in the
    response data.

    Read more about it in the
    [FastAPI docs for Response Model - Return Type](https://fastapi.tiangolo.com/tutorial/response-model/#response_model_include-and-response_model_exclude).
    """

    response_model_by_alias: bool
    """
    Configuration passed to Pydantic to define if the response model
    should be serialized by alias when an alias is used.

    Read more about it in the
    [FastAPI docs for Response Model - Return Type](https://fastapi.tiangolo.com/tutorial/response-model/#response_model_include-and-response_model_exclude).
    """

    response_model_exclude_unset: bool
    """
    Configuration passed to Pydantic to define if the response data
    should have all the fields, including the ones that were not set and
    have their default values. This is different from
    `response_model_exclude_defaults` in that if the fields are set,
    they will be included in the response, even if the value is the same
    as the default.

    When `True`, default values are omitted from the response.

    Read more about it in the
    [FastAPI docs for Response Model - Return Type](https://fastapi.tiangolo.com/tutorial/response-model/#use-the-response_model_exclude_unset-parameter).
    """

    response_model_exclude_defaults: bool
    """
    Configuration passed to Pydantic to define if the response data
    should have all the fields, including the ones that have the same value
    as the default. This is different from `response_model_exclude_unset`
    in that if the fields are set but contain the same default values,
    they will be excluded from the response.

    When `True`, default values are omitted from the response.

    Read more about it in the
    [FastAPI docs for Response Model - Return Type](https://fastapi.tiangolo.com/tutorial/response-model/#use-the-response_model_exclude_unset-parameter).
    """

    response_model_exclude_none: bool
    """
    Configuration passed to Pydantic to define if the response data should
    exclude fields set to `None`.

    This is much simpler (less smart) than `response_model_exclude_unset`
    and `response_model_exclude_defaults`. You probably want to use one of
    those two instead of this one, as those allow returning `None` values
    when it makes sense.

    Read more about it in the
    [FastAPI docs for Response Model - Return Type](https://fastapi.tiangolo.com/tutorial/response-model/#response_model_exclude_none).
    """

    response_class: type[Response]
    """
    Response class to be used for this *path operation*.

    This will not be used if you return a response directly.

    Read more about it in the
    [FastAPI docs for Custom Response - HTML, Stream, File, others](https://fastapi.tiangolo.com/advanced/custom-response/#redirectresponse).
    """

    callbacks: list[BaseRoute]
    """
    List of *path operations* that will be used as OpenAPI callbacks.

    This is only for OpenAPI documentation, the callbacks won't be used
    directly.

    It will be added to the generated OpenAPI (e.g. visible at `/docs`).

    Read more about it in the
    [FastAPI docs for OpenAPI Callbacks](https://fastapi.tiangolo.com/advanced/openapi-callbacks/).
    """

    generate_unique_id: GenerateUniqueIdFunction
    """
    Customize the function used to generate unique IDs for the *path
    operations* shown in the generated OpenAPI.

    This is particularly useful when automatically generating clients or
    SDKs for your API.

    Read more about it in the
    [FastAPI docs about how to Generate Clients](https://fastapi.tiangolo.com/advanced/generate-clients/#custom-generate-unique-id-function).
    """

    strict_content_type: bool

    deprecated: bool
    """
    Mark this *path operation* as deprecated.

    It will be added to the generated OpenAPI (e.g. visible at `/docs`).
    """


type Endpoint = Callable[..., Any]

class Routable(ABC):
    @abstractmethod
    def add_api_route(self, path: str, endpoint: Callable[..., Any], /, **kwargs: Unpack[RouteParams]): ...

    def api_route[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]: ...

    def get[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP GET operation.

        ## Example

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/items/")
        def read_items():
            return [{"name": "Empanada"}, {"name": "Arepa"}]
        ```
        """

    def put[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP PUT operation.

        ## Example

        ```python
        from fastapi import FastAPI
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str
            description: str | None = None

        app = FastAPI()

        @app.put("/items/{item_id}")
        def replace_item(item_id: str, item: Item):
            return {"message": "Item replaced", "id": item_id}
        ```
        """

    def post[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP POST operation.

        ## Example

        ```python
        from fastapi import FastAPI
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str
            description: str | None = None

        app = FastAPI()

        @app.post("/items/")
        def create_item(item: Item):
            return {"message": "Item created"}
        ```
        """

    def delete[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP DELETE operation.

        ## Example

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.delete("/items/{item_id}")
        def delete_item(item_id: str):
            return {"message": "Item deleted"}
        ```
        """

    def options[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP OPTIONS operation.

        ## Example

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.options("/items/")
        def get_item_options():
            return {"additions": ["Aji", "Guacamole"]}
        ```
        """

    def head[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP HEAD operation.

        ## Example

        ```python
        from fastapi import FastAPI, Response

        app = FastAPI()

        @app.head("/items/", status_code=204)
        def get_items_headers(response: Response):
            response.headers["X-Cat-Dog"] = "Alone in the world"
        ```
        """

    def patch[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP PATCH operation.

        ## Example

        ```python
        from fastapi import FastAPI
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str
            description: str | None = None

        app = FastAPI()

        @app.patch("/items/")
        def update_item(item: Item):
            return {"message": "Item updated in place"}
        ```
        """

    def trace[T: Endpoint](self, path: str, /, **kwargs: Unpack[RouteParams]) -> Wrapper[T]:
        """
        Add a *path operation* using an HTTP TRACE operation.

        ## Example

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.trace("/items/{item_id}")
        def trace_item(item_id: str):
            return None
        ```
        """
