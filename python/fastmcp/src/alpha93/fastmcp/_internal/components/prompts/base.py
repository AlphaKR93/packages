from abc import ABC, abstractmethod
from typing import ClassVar

from mcp.types import Prompt as SDKPrompt, PromptArgument as SDKPromptArgument
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from fastmcp.prompts.base import Message, PromptArgument, PromptResult
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent


if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any

    from fastmcp.utilities.tasks import TaskMeta

    from .function_prompt import FunctionPrompt


class Prompt(ABC, FastMCPComponent):
    """A prompt template that can be rendered with parameters."""

    KEY_PREFIX: ClassVar[str] = "prompt"

    arguments: list[PromptArgument] | None
    """Arguments that can be passed to the prompt"""

    auth: SkipJsonSchema[AuthCheck | list[AuthCheck] | None] = Field(exclude=True)
    """Authorization checks for this prompt"""

    def to_mcp_prompt(self, **overrides):
        """Convert the prompt to an MCP prompt."""
        arguments = [
            SDKPromptArgument(
                name=arg.name,
                description=arg.description,
                required=arg.required,
            )
            for arg in self.arguments or []
        ]

        return SDKPrompt(
            name=overrides.get("name", self.name),
            description=overrides.get("description", self.description),
            arguments=arguments,
            title=overrides.get("title", self.title),
            icons=overrides.get("icons", self.icons),
            _meta=overrides.get(  # type: ignore[call-arg]  # _meta is Pydantic alias for meta field
                "_meta", self.get_meta()
            ),  # ty:ignore[unknown-argument]
        )

    @classmethod
    def from_function(cls, fn, /, **kwargs):
        """Create a Prompt from a function.

        The function can return:
        - str: wrapped as single user Message
        - list[Message | str]: converted to list[Message]
        - PromptResult: used directly
        """
        from .function_prompt import FunctionPrompt

        return FunctionPrompt.from_function(fn, **kwargs)

    @abstractmethod
    async def render(self, arguments: dict[str, Any] | None = None, /) -> str | list[Message | str] | PromptResult:
        """Render the prompt with arguments.

        Subclasses must implement this method. Return one of:
        - str: Wrapped as single user Message
        - list[Message | str]: Converted to list[Message]
        - PromptResult: Used directly
        """

    def convert_result(self, raw_value, /) -> PromptResult:
        """Convert a raw return value to PromptResult.

        Accepts:
            - PromptResult: passed through
            - str: wrapped as single Message
            - list[Message | str]: converted to list[Message]

        Raises:
            TypeError: for unsupported types
        """
        if isinstance(raw_value, PromptResult):
            return raw_value

        if isinstance(raw_value, str):
            return PromptResult(raw_value, description=self.description, meta=self.meta)

        if isinstance(raw_value, list | tuple):
            messages: list[Message] = []
            for i, item in enumerate(raw_value):
                if isinstance(item, Message):
                    messages.append(item)
                elif isinstance(item, str):
                    messages.append(Message(item))
                else:
                    raise TypeError(
                        f"messages[{i}] must be Message or str, got {type(item).__name__}. "
                        f"Use Message({item!r}) to wrap the value."
                    )
            return PromptResult(messages, description=self.description, meta=self.meta)

        raise TypeError(
            f"Prompt must return str, list[Message], or PromptResult, "
            f"got {type(raw_value).__name__}"
        )

    async def _render(
            self,
            arguments: dict[str, Any] | None = None,
            /,
            task_meta: TaskMeta | None = None,
    ):
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
        from fastmcp.server.tasks.routing import check_background_task

        task_result = await check_background_task(
            component=self,
            task_type="prompt",
            arguments=arguments,
            task_meta=task_meta,
        )
        if task_result:
            return task_result

        # Synchronous execution
        result = await self.render(arguments)
        return self.convert_result(result)

    def get_span_attributes(self, /) -> dict[str, Any]:
        return super().get_span_attributes() | {
            "fastmcp.component.type": "prompt",
            "fastmcp.provider.type": "LocalProvider",
        }
