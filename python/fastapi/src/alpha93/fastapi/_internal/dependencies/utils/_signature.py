import inspect
from typing import ForwardRef

from commons import constant
from pydantic.v1.typing import evaluate_forwardref

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Final


@constant
def _get_signature():
    import sys

    __kwargs: Final = {}
    if sys.version_info >= (3, 14):
        from annotationlib import Format

        __kwargs["annotation_format"] = Format.FORWARDREF

    def __func(call: Callable[..., Any], /) -> inspect.Signature:
        try:
            return inspect.signature(call, eval_str=True)
        except NameError:
            # Handle type annotations with if TYPE_CHECKING, not used by FastAPI
            # e.g. dependency return types
            return inspect.signature(call, **__kwargs)
    return __func

def get_typed_annotation(annotation, globalns, /):
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        annotation = evaluate_forwardref(annotation, globalns, globalns)
        if annotation is type(None):
            return None
    return annotation

def get_typed_signature(call: Callable[..., Any], /) -> inspect.Signature:
    globalns: Final = getattr(inspect.unwrap(call), "__globals__", {})
    return inspect.Signature([
        inspect.Parameter(
            param.name,
            param.kind,
            default=param.default,
            annotation=get_typed_annotation(param.annotation, globalns),
        )
        for param in _get_signature(call).parameters.values()
    ])

def get_typed_return_annotation(call: Callable[..., Any], /) -> Any:
    return None if (annotation := _get_signature(call).return_annotation) is inspect.Signature.empty \
        else get_typed_annotation(annotation, getattr(inspect.unwrap(call), "__globals__", {}))
