import inspect
from functools import partial

from mcp.types import ToolAnnotations


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from mcp.types import AnyFunction


class ToolDecoratorMixin:
    def add_tool(self, tool, /):
        enabled = True
        if inspect.isroutine(tool):
            from fastmcp.decorators import get_fastmcp_meta
            from fastmcp.tools import Tool
            from fastmcp.tools.function_tool import ToolMeta

            assert not isinstance(tool, Tool), "tool should be either callable or Tool"

            fmeta = get_fastmcp_meta(tool)
            if fmeta is not None and isinstance(fmeta, ToolMeta):
                resolved_task = fmeta.task if fmeta.task is not None else False
                enabled = fmeta.enabled

                # Merge ToolMeta.app into the meta dict
                tool_meta = fmeta.meta or {}
                if fmeta.app is not None:
                    tool_meta["ui"] = True if isinstance(fmeta.app, bool) else dict(fmeta.app)

                tool = Tool.from_function(
                    tool,
                    name=fmeta.name,
                    version=fmeta.version,
                    title=fmeta.title,
                    description=fmeta.description,
                    icons=fmeta.icons,
                    tags=fmeta.tags,
                    output_schema=fmeta.output_schema,
                    annotations=fmeta.annotations,
                    meta=tool_meta,
                    task=resolved_task,
                    exclude_args=fmeta.exclude_args,
                    serializer=fmeta.serializer,
                    timeout=fmeta.timeout,
                    auth=fmeta.auth,
                    run_in_thread=fmeta.run_in_thread,
                )
            else:
                tool = Tool.from_function(tool)

        tool: Tool
        self._add_component(tool)
        if not enabled:
            self.disable(keys={tool.key})
        return tool

    # NOTE: This method mirrors fastmcp.tools.tool() but adds registration,
    # the `enabled` param, and supports deprecated params (serializer, exclude_args).
    # When deprecated params are removed, this should delegate to the standalone
    # decorator to reduce duplication.
    def tool(self, name_or_fn = None, /, **kwargs):
        assert not isinstance(name_or_fn, classmethod), "To decorate a classmethod, use @classmethod above @tool. " \
                                                        "See https://gofastmcp.com/servers/tools#using-with-methods"

        if isinstance(annotations := kwargs.get("annotations"), dict):
            kwargs["annotations"] = ToolAnnotations(**annotations)

        if not inspect.isroutine(name_or_fn):
            if isinstance(name_or_fn, str):
                # Case 3: @tool("custom_name") - name passed as first argument
                assert "name" not in kwargs, \
                    f"Cannot specify both a name as the first argument and as a keyword argument. " \
                    f"Use either @tool('{name_or_fn}') or @tool(name='{kwargs['name']}'), not both."
                kwargs["name"] = name_or_fn
            else:
                # Case 4: @tool() or @tool(name="something") - use keyword name
                assert not name_or_fn, \
                    f"The first argument to @tool must be a function, string, or None, got {type(name_or_fn)}"

            # Return partial for cases where we need to wait for the function
            return partial(self.tool, **kwargs)

        def decorate_and_register(fn: AnyFunction, /) -> AnyFunction:
            # Check for unbound method
            try:
                params = list(inspect.signature(fn).parameters.keys())

                assert not params or params[0] not in ("self", "cls"), \
                    f"The function '{getattr(fn, "__name__", "<unknown>")}' has '{params[0]}' as its first parameter. " \
                    f"Use the standalone @tool decorator and register the bound method." \
                    f"See https://gofastmcp.com/servers/tools#using-with-methods"
            except (ValueError, TypeError):
                pass

            from fastmcp.tools.function_tool import ToolMeta

            metadata = ToolMeta(**kwargs)
            target = fn.__func__ if hasattr(fn, "__func__") else fn
            target.__fastmcp__ = metadata  # type: ignore[attr-defined]  # ty:ignore[unresolved-attribute]
            self.add_tool(fn)
            return fn

        name_or_fn: Callable[..., Any]
        return decorate_and_register(name_or_fn)
