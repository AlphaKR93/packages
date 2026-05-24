import inspect
from functools import partial

if __debug__ and __import__("typing").TYPE_CHECKING:
    from mcp.types import AnyFunction


class PromptDecoratorMixin:
    def add_prompt(self, prompt, /):
        enabled = True
        if inspect.isroutine(prompt):
            from fastmcp.decorators import get_fastmcp_meta
            from fastmcp.prompts import Prompt
            from fastmcp.prompts.function_prompt import PromptMeta

            assert not isinstance(prompt, Prompt), f"prompt is either callable or Prompt, got {type(prompt).__name__}"

            meta = get_fastmcp_meta(prompt)
            assert isinstance(meta, PromptMeta), \
                f"Expected Prompt or @prompt-decorated function, got {type(prompt).__name__}. " \
                "Use @prompt decorator or pass a Prompt instance."

            resolved_task = meta.task if meta.task is not None else False
            enabled = meta.enabled
            prompt = Prompt.from_function(
                prompt,
                name=meta.name,
                version=meta.version,
                title=meta.title,
                description=meta.description,
                icons=meta.icons,
                tags=meta.tags,
                meta=meta.meta,
                task=resolved_task,
                auth=meta.auth,
            )

        prompt: Prompt
        self._add_component(prompt)
        if not enabled:
            self.disable(keys={prompt.key})
        return prompt

    def prompt(self, name_or_fn = None, /, **kwargs):
        assert not isinstance(name_or_fn, classmethod), \
            "To decorate a classmethod, use @classmethod above @prompt. " \
            "See https://gofastmcp.com/servers/prompts#using-with-methods"

        if not inspect.isroutine(name_or_fn):
            if isinstance(name_or_fn, str):
                assert "name" not in kwargs, \
                    f"Cannot specify both a name as first argument and as keyword argument. " \
                    f"Use either @prompt('{name_or_fn}') or @prompt(name='{kwargs['name']}'), not both."
                kwargs["name"] = name_or_fn
            else:
                assert not name_or_fn, f"Invalid first argument: {type(name_or_fn)}"

            return partial(self.prompt, **kwargs)

        def decorate_and_register(fn: AnyFunction, /):
            # Check for unbound method
            try:
                params = list(inspect.signature(fn).parameters.keys())

                assert not params or params[0] not in ("self", "cls"), \
                    f"The function '{getattr(fn, "__name__", "<unknown>")}' has '{params[0]}' as its first parameter. " \
                    f"Use the standalone @prompt decorator and register the bound method."
            except (ValueError, TypeError):
                pass

            from fastmcp.prompts.function_prompt import PromptMeta

            metadata = PromptMeta(**kwargs)
            target = fn.__func__ if hasattr(fn, "__func__") else fn
            target.__fastmcp__ = metadata  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
            self.add_prompt(fn)
            return fn

        return decorate_and_register(name_or_fn)
