"""Prompt decorator mixin for LocalProvider.

This module provides the PromptDecoratorMixin class that adds prompt
registration functionality to LocalProvider.
"""
from collections.abc import Callable, Sequence, Iterable, Mapping
from functools import partial
from typing import Any, overload

from commons.types import SequenceOr
from mcp.types import AnyFunction, Icon

from fastmcp.prompts import Prompt, FunctionPrompt
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.tasks import TaskConfig

from fastmcp.server.providers.local_provider import LocalProvider


class PromptDecoratorMixin:
    """Mixin class providing prompt decorator functionality for LocalProvider.

    This mixin contains all methods related to:
    - Prompt registration via add_prompt()
    - Prompt decorator (@provider.prompt)
    """

    def add_prompt(self: LocalProvider, prompt: Prompt | Callable[..., Any], /) -> Prompt:
        """Add a prompt to this provider's storage.

        Accepts either a Prompt object or a decorated function with __fastmcp__ metadata.
        """

    @overload
    def prompt[F: Callable](
        self: LocalProvider,
        name_or_fn: F,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: Sequence[Icon] | None = None,
        tags: Iterable[str] | None = None,
        enabled: bool = True,
        meta: Mapping[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: SequenceOr[AuthCheck] | None = None,
    ) -> F: ...

    @overload
    def prompt[F: Callable](
        self: LocalProvider,
        name_or_fn: str | None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: Sequence[Icon] | None = None,
        tags: Iterable[str] | None = None,
        enabled: bool = True,
        meta: Mapping[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: SequenceOr[AuthCheck] | None = None,
    ) -> Callable[[F], F]: ...

    def prompt[F: Callable](
        self: LocalProvider,
        name_or_fn: str | AnyFunction | None = None,
        *,
        name: str | None = None,
        version: str | int | None = None,
        title: str | None = None,
        description: str | None = None,
        icons: Sequence[Icon] | None = None,
        tags: Iterable[str] | None = None,
        enabled: bool = True,
        meta: Mapping[str, Any] | None = None,
        task: bool | TaskConfig | None = None,
        auth: SequenceOr[AuthCheck] | None = None,
    ) -> (
        Callable[[AnyFunction], FunctionPrompt]
        | FunctionPrompt
        | partial[Callable[[AnyFunction], FunctionPrompt] | FunctionPrompt]
    ):
        """Decorator to register a prompt.

        This decorator supports multiple calling patterns:
        - @provider.prompt (without parentheses)
        - @provider.prompt() (with empty parentheses)
        - @provider.prompt("custom_name") (with name as first argument)
        - @provider.prompt(name="custom_name") (with name as keyword argument)
        - provider.prompt(function, name="custom_name") (direct function call)

        Args:
            name_or_fn: Either a function (when used as @prompt), a string name, or None
            name: Optional name for the prompt (keyword-only, alternative to name_or_fn)
            title: Optional title for the prompt
            description: Optional description of what the prompt does
            icons: Optional icons for the prompt
            tags: Optional set of tags for categorizing the prompt
            enabled: Whether the prompt is enabled (default True). If False, adds to blocklist.
            meta: Optional meta information about the prompt
            task: Optional task configuration for background execution
            auth: Optional authorization checks for the prompt

        Returns:
            The registered FunctionPrompt or a decorator function.

        Example:
            ```python
            provider = LocalProvider()

            @provider.prompt
            def analyze(topic: str) -> list:
                return [{"role": "user", "content": f"Analyze: {topic}"}]

            @provider.prompt("custom_name")
            def my_prompt(data: str) -> list:
                return [{"role": "user", "content": data}]
            ```
        """
