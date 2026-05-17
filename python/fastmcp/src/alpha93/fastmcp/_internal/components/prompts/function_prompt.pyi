from collections.abc import Callable
from typing import overload, Any, override

from mcp.types import Icon
from pydantic.json_schema import SkipJsonSchema

from fastmcp.prompts import Message, PromptResult
from fastmcp.prompts.function_prompt import PromptMeta
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.tasks import TaskConfig

from .base import Prompt


class FunctionPrompt(Prompt):
    """A prompt that is a function."""

    fn: SkipJsonSchema[Callable[..., Any]]

    # noinspection PyIncorrectDocstring
    @classmethod
    def from_function(
            cls,
            fn: Callable[..., Any],
            /,
            metadata: PromptMeta | None = None,
            *,
            # Keep individual params for backwards compat
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: list[Icon] | None = None,
            tags: set[str] | None = None,
            meta: dict[str, Any] | None = None,
            task: bool | TaskConfig | None = None,
            auth: AuthCheck | list[AuthCheck] | None = None,
    ) -> FunctionPrompt:
        """Create a Prompt from a function.

        Args:
            fn: The function to wrap
            metadata: PromptMeta object with all configuration. If provided,
                individual parameters must not be passed.
            name, title, etc.: Individual parameters for backwards compatibility.
                Cannot be used together with metadata parameter.

        The function can return:
        - str: wrapped as single user Message
        - list[Message | str]: converted to list[Message]
        - PromptResult: used directly
        """

    @override
    async def render(self, arguments: dict[str, Any] | None = None, /) -> str | list[Message | str] | PromptResult:
        ...

@overload
def prompt[F: Callable](fn: F) -> F: ...
@overload
def prompt[F: Callable](
        name_or_fn: str,
        *,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: list[Icon] | None = None,
        tags: set[str] | None = None,
        meta: dict[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: AuthCheck | list[AuthCheck] | None = None,
) -> Callable[[F], F]: ...
@overload
def prompt[F: Callable](
        name_or_fn: None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: list[Icon] | None = None,
        tags: set[str] | None = None,
        meta: dict[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: AuthCheck | list[AuthCheck] | None = None,
) -> Callable[[F], F]: ...
@overload
def prompt(
        name_or_fn: str | Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: list[Icon] | None = None,
        tags: set[str] | None = None,
        meta: dict[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: AuthCheck | list[AuthCheck] | None = None,
) -> Any:
    """Standalone decorator to mark a function as an MCP prompt.

    Returns the original function with metadata attached. Register with a server
    using mcp.add_prompt().
    """
