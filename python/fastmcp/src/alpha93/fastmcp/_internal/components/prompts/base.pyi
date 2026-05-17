from abc import ABC, abstractmethod
from typing import ClassVar, overload

from mcp.types import Prompt as SDKPrompt
from mcp.types import PromptArgument as SDKPromptArgument
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from fastmcp.prompts.base import Message, PromptArgument, PromptResult
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from mcp.types import Icon, CreateTaskResult

    from fastmcp.utilities.tasks import TaskConfig, TaskMeta

    from .function_prompt import FunctionPrompt


class Prompt(ABC, FastMCPComponent):
    """A prompt template that can be rendered with parameters."""

    KEY_PREFIX: ClassVar[str] = "prompt"

    arguments: list[PromptArgument] | None
    """Arguments that can be passed to the prompt"""

    auth: SkipJsonSchema[AuthCheck | list[AuthCheck] | None] = Field(exclude=True)
    """Authorization checks for this prompt"""

    def to_mcp_prompt(self, **overrides: Any) -> SDKPrompt:
        """Convert the prompt to an MCP prompt."""

    @classmethod
    def from_function(
            cls,
            fn: Callable[..., Any],
            /,
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
    ) -> FunctionPrompt:
        """Create a Prompt from a function.

        The function can return:
        - str: wrapped as single user Message
        - list[Message | str]: converted to list[Message]
        - PromptResult: used directly
        """

    @abstractmethod
    async def render(self, arguments: dict[str, Any] | None = None, /) -> str | list[Message | str] | PromptResult:
        """Render the prompt with arguments.

        Subclasses must implement this method. Return one of:
        - str: Wrapped as single user Message
        - list[Message | str]: Converted to list[Message]
        - PromptResult: Used directly
        """

    def convert_result(self, raw_value: Any, /) -> PromptResult:
        """Convert a raw return value to PromptResult.

        Accepts:
            - PromptResult: passed through
            - str: wrapped as single Message
            - list[Message | str]: converted to list[Message]

        Raises:
            TypeError: for unsupported types
        """

    @overload
    async def _render(
            self,
            arguments: dict[str, Any] | None = None,
            /,
            task_meta: None = None,
    ) -> PromptResult: ...

    @overload
    async def _render(
            self,
            arguments: dict[str, Any] | None,
            /,
            task_meta: TaskMeta,
    ) -> CreateTaskResult: ...

    async def _render(
            self,
            arguments: dict[str, Any] | None = None,
            /,
            task_meta: TaskMeta | None = None,
    ) -> PromptResult | CreateTaskResult:
        """Server entry point that handles task routing.

        This allows ANY Prompt subclass to support background execution by setting
        task_config.mode to "supported" or "required". The server calls this
        method instead of render() directly.

        Args:
            arguments: Prompt arguments
            task_meta: If provided, execute as background task and return
                CreateTaskResult. If None (default), execute synchronously and
                return PromptResult.

        Returns:
            PromptResult when task_meta is None.
            CreateTaskResult when task_meta is provided.

        Subclasses can override this to customize task routing behavior.
        For example, FastMCPProviderPrompt overrides to delegate to child
        middleware without submitting to Docket.
        """

    def get_span_attributes(self, /) -> dict[str, Any]:
        ...
