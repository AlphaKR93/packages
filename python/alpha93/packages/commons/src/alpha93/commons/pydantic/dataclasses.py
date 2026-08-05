if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any

    from _typeshed import DataclassInstance
    from pydantic import BaseModel


def to_model(dataclass: type[DataclassInstance], /) -> type[BaseModel]:
    """
    Converts `dataclasses.dataclass` class into `pydantic.BaseModel`.
    """

    from pydantic import BaseModel, ConfigDict, create_model, dataclasses

    _pydantic: Any = dataclasses.dataclass(dataclass, config=ConfigDict(use_attribute_docstrings=True))
    return create_model(
        _pydantic.__name__,
        __base__=BaseModel,
        __module__=_pydantic.__module__,
        __doc__=_pydantic.__doc__,
        __validators__=None,    # TODO
        __cls_kwargs__=None,    # TODO
        __qualname__=None,
        __config__=_pydantic.__pydantic_config__,
        **{k: (v.annotation, v) for k, v in _pydantic.__pydantic_fields__.items()}
    )
