from collections.abc import Generator, Mapping, Iterable, Sequence, Callable
from contextlib import contextmanager
from contextvars import Token
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Any, overload

from commons.types import SequenceOr
from mcp.server.elicitation import DeclinedElicitation, CancelledElicitation
from mcp.server.session import ServerSession
from mcp.shared.context import RequestContext
from mcp.types import (
    Request,
    Resource as SDKResource,
    Prompt as SDKPrompt,
    GetPromptResult,
    LoggingLevel,
    Root,
    ServerNotificationType,
    SamplingMessage,
    ModelPreferences,
    ElicitResult
)
from pydantic import AnyUrl

from fastmcp.resources import ResourceResult
from fastmcp.server import FastMCP
from fastmcp.server.elicitation import AcceptedElicitation
from fastmcp.server.sampling import SamplingTool
from fastmcp.server.sampling.run import ToolChoiceOption, SampleStep, SamplingResult
from fastmcp.server.transforms import Visibility
from fastmcp.utilities.versions import VersionSpec

type TransportType = Literal["stdio", "sse", "streamable-http"]

def set_transport(transport: TransportType, /) -> Token[TransportType | None]:
    """Set the current transport type. Returns token for reset."""

def reset_transport(token: Token[TransportType | None], /) -> None:
    """Reset transport to previous value."""

@contextmanager
def set_context(context: Context, /) -> Generator[Context, None, None]: ...


@dataclass
class LogData:
    """Data object for passing log arguments to client-side handlers.

    This provides an interface to match the Python standard library logging,
    for compatibility with structured logging.
    """

    msg: str
    extra: Mapping[str, Any] | None = None


@dataclass
class Context:
    """Context object providing access to MCP capabilities.

    This provides a cleaner interface to MCP's RequestContext functionality.
    It gets injected into tool and resource functions that request it via type hints.

    To use context in a tool function, add a parameter with the Context type annotation:

    ```python
    @server.tool
    async def my_tool(x: int, ctx: Context) -> str:
        # Log messages to the client
        await ctx.info(f"Processing {x}")
        await ctx.debug("Debug info")
        await ctx.warning("Warning message")
        await ctx.error("Error message")

        # Report progress
        await ctx.report_progress(50, 100, "Processing")

        # Access resources
        data = await ctx.read_resource("resource://data")

        # Get request info
        request_id = ctx.request_id
        client_id = ctx.client_id

        # Manage state across the session (persists across requests)
        await ctx.set_state("key", "value")
        value = await ctx.get_state("key")

        # Store non-serializable values for the current request only
        await ctx.set_state("client", http_client, serializable=False)

        return str(x)
    ```

    State Management:
    Context provides session-scoped state that persists across requests within
    the same MCP session. State is automatically keyed by session, ensuring
    isolation between different clients.

    State set during `on_initialize` middleware will persist to subsequent tool
    calls when using the same session object (STDIO, SSE, single-server HTTP).
    For distributed/serverless HTTP deployments where different machines handle
    the init and tool calls, state is isolated by the mcp-session-id header.

    The context parameter name can be anything as long as it's annotated with Context.
    The context is optional - tools that don't need it can omit the parameter.

    """
    __slots__ = (
        "_fastmcp",
        "_session",
        "_tokens",
        "_task_id",
        "_origin_request_id",
        "_request_state",
    )

    def __init__(
            self,
            fastmcp: FastMCP,
            /,
            session: ServerSession | None = None,
            *,
            task_id: str | None = None,
            origin_request_id: str | None = None,
    ): ...

    async def __aenter__(self, /):
        """Enter the context manager and set this context as the current context."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /
    ):
        """Exit the context manager and reset the most recent token."""

    @property
    def fastmcp(self, /) -> FastMCP:
        """Get the FastMCP instance."""

    @property
    def session(self, /) -> ServerSession:
        """Access to the underlying session for advanced usage.

        In request mode: Returns the session from the active request context.
        In background task mode: Returns the session stored at Context creation.

        Raises RuntimeError if no session is available.
        """

    @property
    def is_background_task(self, /) -> bool:
        """True when this context is running in a background task (Docket worker).

        When True, certain operations like elicit() and sample() will use
        task-aware implementations that can pause the task and wait for
        client input.

        Example:
            ```python
            @server.tool(task=True)
            async def my_task(ctx: Context) -> str:
                # Works transparently in both foreground and background task modes
                result = await ctx.elicit("Need input", str)
                return str(result)
            ```
        """

    @property
    def client_id(self, /) -> str | None:
        """Get the client ID if available."""

    @property
    def request_id(self, /) -> str:
        """Get the unique ID for this request.

        Raises RuntimeError if MCP request context is not available.
        """

    @property
    def session_id(self, /) -> str:
        """Get the MCP session ID for ALL transports.

        Returns the session ID that can be used as a key for session-based
        data storage (e.g., Redis) to share data between tool calls within
        the same client session.

        Returns:
            The session ID for StreamableHTTP transports, or a generated ID
            for other transports.

        Raises:
            RuntimeError if no session is available.

        Example:
            ```python
            @server.tool
            def store_data(data: dict, ctx: Context) -> str:
                session_id = ctx.session_id
                redis_client.set(f"session:{session_id}:data", json.dumps(data))
                return f"Data stored for session {session_id}"
            ```
        """

    @property
    def task_id(self, /) -> str | None:
        """Get the background task ID if running in a background task.

        Returns None if not running in a background task context.
        """

    @property
    def origin_request_id(self, /) -> str | None:
        """Get the request ID that originated this execution, if available.

        In foreground request mode, this is the current request_id.
        In background task mode, this is the request_id captured when the task
        was submitted, if one was available.
        """

    @property
    def request_context(self, /) -> RequestContext[ServerSession, Any, Request] | None:
        """Access to the underlying request context.

        Returns None when the MCP session has not been established yet.
        Returns the full RequestContext once the MCP session is available.

        For HTTP request access in middleware, use `get_http_request()` from fastmcp.server.dependencies,
        which works whether or not the MCP session is available.

        Example in middleware:
        ```python
        async def on_request(self, context, call_next):
            ctx = context.fastmcp_context
            if ctx.request_context:
                # MCP session available - can access session_id, request_id, etc.
                session_id = ctx.session_id
            else:
                # MCP session not available yet - use HTTP helpers
                from fastmcp.server.dependencies import get_http_request
                request = get_http_request()
            return await call_next(context)
        ```
        """

    @property
    def lifespan_context(self, /) -> Mapping[str, Any]:
        """Access the server's lifespan context.

        Returns the context dict yielded by *this* server's lifespan function.
        For a mounted child this is the child's own lifespan, not the parent's
        — the MCP session always belongs to the parent, so reading from the
        request context would return the parent's. We read directly from the
        server's cached lifespan result instead, which is set by the
        per-server ``_lifespan_manager`` regardless of mount position.

        Returns an empty dict if no lifespan was configured.

        Example:
        ```python
        @server.tool
        def my_tool(ctx: Context) -> str:
            db = ctx.lifespan_context.get("db")
            if db:
                return db.query("SELECT 1")
            return "No database connection"
        ```
        """

    @property
    def transport(self, /) -> TransportType | None:
        """Get the current transport type.

        Returns the transport type used to run this server: "stdio", "sse",
        or "streamable-http". Returns None if called outside of a server context.
        """

    async def report_progress(self, progress: float, total: float | None = None, message: str | None = None) -> None:
        """Report progress for the current operation.

        Works in both foreground (MCP progress notifications) and background
        (Docket task execution) contexts.

        Args:
            progress: Current progress value e.g. 24
            total: Optional total value e.g. 100
            message: Optional status message describing current progress
        """

    @staticmethod
    async def _paginate_list(
            request_factory: Callable[[str | None], Any],
            call_method: Callable[[Any], Any],
            extract_items: Callable[[Any], Sequence[Any]],
    ) -> Sequence[Any]:
        """Generic pagination helper for list operations.

        Args:
            request_factory: Function that creates a request from a cursor
            call_method: Async method to call with the request
            extract_items: Function to extract items from the result

        Returns:
            List of all items across all pages
        """

    async def list_resources(self, /) -> list[SDKResource]:
        """List all available resources from the server.

        Returns:
            List of Resource objects available on the server
        """

    async def list_prompts(self, /) -> list[SDKPrompt]:
        """List all available prompts from the server.

        Returns:
            List of Prompt objects available on the server
        """

    async def get_prompt(self, name: str, arguments: dict[str, Any] | None = None, /) -> GetPromptResult:
        """Get a prompt by name with optional arguments.

        Args:
            name: The name of the prompt to get
            arguments: Optional arguments to pass to the prompt

        Returns:
            The prompt result
        """

    async def read_resource(self, uri: str | AnyUrl, /) -> ResourceResult:
        """Read a resource by URI.

        Args:
            uri: Resource URI to read

        Returns:
            ResourceResult with contents
        """

    def client_supports_extension(self, extension_id: str, /) -> bool:
        """Check whether the connected client supports a given MCP extension.

        Inspects the ``extensions`` extra field on ``ClientCapabilities``
        sent by the client during initialization.

        Returns ``False`` when no session is available (e.g., outside a
        request context) or when the client did not advertise the extension.

        Example::

            from fastmcp.apps.config import UI_EXTENSION_ID

            @mcp.tool
            async def my_tool(ctx: Context) -> str:
                if ctx.client_supports_extension(UI_EXTENSION_ID):
                    return "UI-capable client"
                return "text-only client"
        """

    async def log(
            self,
            message: str,
            /,
            *,
            level: LoggingLevel = "info",
            logger_name: str | None = None,
            extra: Mapping[str, Any] | None = None,
            **kwargs,
    ) -> None:
        """Send a log message to the client.

        Messages sent to Clients are also logged to the `fastmcp.server.context.to_client` logger with a level of `DEBUG`.

        Args:
            message: Log message
            level: Optional log level. One of "debug", "info", "notice", "warning", "error", "critical",
                "alert", or "emergency". Default is "info".
            logger_name: Optional logger name
            extra: Optional mapping for additional arguments
        """

    async def debug(
            self,
            message: str,
            /,
            *,
            logger_name: str | None = None,
            extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a `DEBUG`-level message to the connected MCP Client.

        Messages sent to Clients are also logged to the `fastmcp.server.context.to_client` logger with a level of `DEBUG`."""

    async def info(
            self,
            message: str,
            /,
            *,
            logger_name: str | None = None,
            extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a `INFO`-level message to the connected MCP Client.

        Messages sent to Clients are also logged to the `fastmcp.server.context.to_client` logger with a level of `DEBUG`."""

    async def warning(
            self,
            message: str,
            /,
            *,
            logger_name: str | None = None,
            extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a `WARNING`-level message to the connected MCP Client.

        Messages sent to Clients are also logged to the `fastmcp.server.context.to_client` logger with a level of `DEBUG`."""

    async def error(
            self,
            message: str,
            /,
            logger_name: str | None = None,
            extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a `ERROR`-level message to the connected MCP Client.

        Messages sent to Clients are also logged to the `fastmcp.server.context.to_client` logger with a level of `DEBUG`."""

    async def list_roots(self, /) -> Sequence[Root]:
        """List the roots available to the server, as indicated by the client."""

    async def send_notification(self, notification: ServerNotificationType, /) -> None:
        """Send a notification to the client immediately.

        Args:
            notification: An MCP notification instance (e.g., ToolListChangedNotification())
        """

    async def close_sse_stream(self, /) -> None:
        """Close the current response stream to trigger client reconnection.

        When using StreamableHTTP transport with an EventStore configured, this
        method gracefully closes the HTTP connection for the current request.
        The client will automatically reconnect (after `retry_interval` milliseconds)
        and resume receiving events from where it left off via the EventStore.

        This is useful for long-running operations to avoid load balancer timeouts.
        Instead of holding a connection open for minutes, you can periodically close
        and let the client reconnect.

        Example:
            ```python
            @mcp.tool
            async def long_running_task(ctx: Context) -> str:
                for i in range(100):
                    await ctx.report_progress(i, 100)

                    # Close connection every 30 iterations to avoid LB timeouts
                    if i % 30 == 0 and i > 0:
                        await ctx.close_sse_stream()

                    await do_work()
                return "Done"
            ```

        Note:
            This is a no-op (with a debug log) if not using StreamableHTTP
            transport with an EventStore configured.
        """

    async def sample_step(
            self,
            messages: str | Sequence[str | SamplingMessage],
            /,
            *,
            system_prompt: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            model_preferences: ModelPreferences | str | Sequence[str] | None = None,e,
            tools: Sequence[SamplingTool | Callable[..., Any]] | None = None,
            tool_choice: ToolChoiceOption | str | None = None,
            execute_tools: bool = True,
            mask_error_details: bool | None = None,
            tool_concurrency: int | None = None,
    ) -> SampleStep:
        """
        Make a single LLM sampling call.

        This is a stateless function that makes exactly one LLM call and optionally
        executes any requested tools. Use this for fine-grained control over the
        sampling loop.

        Args:
            messages: The message(s) to send. Can be a string, list of strings,
                or list of SamplingMessage objects.
            system_prompt: Optional system prompt for the LLM.
            temperature: Optional sampling temperature.
            max_tokens: Maximum tokens to generate. Defaults to 512.
            model_preferences: Optional model preferences.
            tools: Optional list of tools the LLM can use.
            tool_choice: Tool choice mode ("auto", "required", or "none").
            execute_tools: If True (default), execute tool calls and append results
                to history. If False, return immediately with tool_calls available
                in the step for manual execution.
            mask_error_details: If True, mask detailed error messages from tool
                execution. When None (default), uses the global settings value.
                Tools can raise ToolError to bypass masking.
            tool_concurrency: Controls parallel execution of tools:
                - None (default): Sequential execution (one at a time)
                - 0: Unlimited parallel execution
                - N > 0: Execute at most N tools concurrently
                If any tool has sequential=True, all tools execute sequentially
                regardless of this setting.

        Returns:
            SampleStep containing:
            - .response: The raw LLM response
            - .history: Messages including input, assistant response, and tool results
            - .is_tool_use: True if the LLM requested tool execution
            - .tool_calls: List of tool calls (if any)
            - .text: The text content (if any)

        Example:
            messages = "Research X"

            while True:
                step = await ctx.sample_step(messages, tools=[search])

                if not step.is_tool_use:
                    print(step.text)
                    break

                # Continue with tool results
                messages = step.history
        """

    @overload
    async def sample[T](
            self,
            messages: str | Sequence[str | SamplingMessage],
            /,
            *,
            system_prompt: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            model_preferences: ModelPreferences | str | Sequence[str] | None = None,
            tools: Sequence[SamplingTool | Callable[..., Any]] | None = None,
            result_type: type[T],
            mask_error_details: bool | None = None,
            tool_concurrency: int | None = None,
    ) -> SamplingResult[T]: ...
    @overload
    async def sample(
            self,
            messages: str | Sequence[str | SamplingMessage],
            /,
            *,
            system_prompt: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            model_preferences: ModelPreferences | str | Sequence[str] | None = None,
            tools: Sequence[SamplingTool | Callable[..., Any]] | None = None,
            result_type: None = None,
            mask_error_details: bool | None = None,
            tool_concurrency: int | None = None,
    ) -> SamplingResult[str]: ...
    async def sample[T](
            self,
            messages: str | Sequence[str | SamplingMessage],
            /,
            *,
            system_prompt: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            model_preferences: ModelPreferences | str | Sequence[str] | None = None,
            tools: Sequence[SamplingTool | Callable[..., Any]] | None = None,
            result_type: type[T] | None = None,
            mask_error_details: bool | None = None,
            tool_concurrency: int | None = None,
    ) -> SamplingResult[T] | SamplingResult[str]:
        """
        Send a sampling request to the client and await the response.

        This method runs to completion automatically. When tools are provided,
        it executes a tool loop: if the LLM returns a tool use request, the tools
        are executed and the results are sent back to the LLM. This continues
        until the LLM provides a final text response.

        When result_type is specified, a synthetic `final_response` tool is
        created. The LLM calls this tool to provide the structured response,
        which is validated against the result_type and returned as `.result`.

        For fine-grained control over the sampling loop, use sample_step() instead.

        Args:
            messages: The message(s) to send. Can be a string, list of strings,
                or list of SamplingMessage objects.
            system_prompt: Optional system prompt for the LLM.
            temperature: Optional sampling temperature.
            max_tokens: Maximum tokens to generate. Defaults to 512.
            model_preferences: Optional model preferences.
            tools: Optional list of tools the LLM can use. Accepts plain
                functions or SamplingTools.
            result_type: Optional type for structured output. When specified,
                a synthetic `final_response` tool is created and the LLM's
                response is validated against this type.
            mask_error_details: If True, mask detailed error messages from tool
                execution. When None (default), uses the global settings value.
                Tools can raise ToolError to bypass masking.
            tool_concurrency: Controls parallel execution of tools:
                - None (default): Sequential execution (one at a time)
                - 0: Unlimited parallel execution
                - N > 0: Execute at most N tools concurrently
                If any tool has sequential=True, all tools execute sequentially
                regardless of this setting.

        Returns:
            SamplingResult[T] containing:
            - .text: The text representation (raw text or JSON for structured)
            - .result: The typed result (str for text, parsed object for structured)
            - .history: All messages exchanged during sampling

        Note:
            Background task support for sampling is planned for a future release.
            Currently, sampling in background tasks requires using the low-level
            session.create_message() API directly.
        """

    @overload
    async def elicit(
            self,
            message: str,
            response_type: None,
            /,
            *,
            response_title: str | None = None,
            response_description: str | None = None,
    ) -> AcceptedElicitation[Mapping[str, Any]] | DeclinedElicitation | CancelledElicitation: ...

    """When response_type is None, the accepted elicitation will contain an
    empty dict"""

    @overload
    async def elicit[T](
            self,
            message: str,
            response_type: type[T],
            /,
            *,
            response_title: str | None = None,
            response_description: str | None = None,
    ) -> AcceptedElicitation[T] | DeclinedElicitation | CancelledElicitation: ...

    """When response_type is not None, the accepted elicitation will contain the
    response data"""

    @overload
    async def elicit(
            self,
            message: str,
            response_type: Sequence[str],
            /,
            *,
            response_title: str | None = None,
            response_description: str | None = None,
    ) -> AcceptedElicitation[str] | DeclinedElicitation | CancelledElicitation: ...

    """When response_type is a list of strings, the accepted elicitation will
    contain the selected string response"""

    @overload
    async def elicit(
            self,
            message: str,
            response_type: Mapping[str, Mapping[str, str]],
            /,
            *,
            response_title: str | None = None,
            response_description: str | None = None,
    ) -> AcceptedElicitation[str] | DeclinedElicitation | CancelledElicitation: ...

    """When response_type is a dict mapping keys to title dicts, the accepted
    elicitation will contain the selected key"""

    @overload
    async def elicit(
            self,
            message: str,
            response_type: Sequence[Sequence[str]],
            /,
            *,
            response_title: str | None = None,
            response_description: str | None = None,
    ) -> AcceptedElicitation[Sequence[str]] | DeclinedElicitation | CancelledElicitation: ...

    """When response_type is a list containing a list of strings (multi-select),
    the accepted elicitation will contain a list of selected strings"""

    @overload
    async def elicit(
            self,
            message: str,
            response_type: Sequence[Mapping[str, Mapping[str, str]]],
            /,
            *,
            response_title: str | None = None,
            response_description: str | None = None,
    ) -> AcceptedElicitation[Sequence[str]] | DeclinedElicitation | CancelledElicitation: ...

    """When response_type is a list containing a dict mapping keys to title dicts
    (multi-select with titles), the accepted elicitation will contain a list of
    selected keys"""

    async def elicit[T](
            self,
            message: str,
            response_type: type[T] | SequenceOr[Sequence[str]] | SequenceOr[Mapping[str, Mapping[str, str]]] | None = None,
            /,
            *,
            response_title: str | None = None,
            response_description: str | None = None,
    ) -> (
            AcceptedElicitation[T]
            | AcceptedElicitation[str]
            | AcceptedElicitation[Sequence[str]]
            | AcceptedElicitation[Mapping[str, Any]]
            | DeclinedElicitation
            | CancelledElicitation
    ):
        """
        Send an elicitation request to the client and await the response.

        Call this method at any time to request additional information from
        the user through the client. The client must support elicitation,
        or the request will error.

        Note that the MCP protocol only supports simple object schemas with
        primitive types. You can provide a dataclass, TypedDict, or BaseModel to
        comply. If you provide a primitive type, an object schema with a single
        "value" field will be generated for the MCP interaction and
        automatically deconstructed into the primitive type upon response.

        Passing ``response_type=None`` (or omitting it) is deprecated and will
        be removed in a future version. The resulting empty-schema form-mode
        request is ambiguous and causes some clients (e.g. VS Code) to hang on
        an empty form. Pass an explicit ``response_type`` describing the data
        you want back.

        Args:
            message: A human-readable message explaining what information is needed
            response_type: The type of the response, which should be a primitive
                type or dataclass or BaseModel. If it is a primitive type, an
                object schema with a single "value" field will be generated.
            response_title: Optional label to display for the wrapped ``value``
                field when ``response_type`` is a scalar, Literal, Enum, or one
                of the dict/list shorthand forms. Overrides the auto-generated
                "Value" label. Raises ``TypeError`` if passed with a BaseModel,
                dataclass, or ``None`` response type (use ``Field(title=...)``
                on the model instead).
            response_description: Optional description to attach to the wrapped
                ``value`` field. Same scope rules as ``response_title``.

        Note:
            This method works transparently in both request and background task
            contexts. In background task mode (SEP-1686), it will set the task
            status to "input_required" and wait for the client to provide input.
        """

    async def _elicit_for_task(
            self,
            /,
            message: str,
            schema: dict[str, Any],
    ) -> ElicitResult:
        """Send an elicitation request from a background task (SEP-1686).

        This method handles elicitation when running in a Docket worker context,
        where there's no active MCP request. It:
        1. Sets the task status to "input_required"
        2. Sends the elicitation request with task metadata
        3. Waits for the client to provide input via tasks/sendInput
        4. Returns the result and resumes task execution

        Args:
            message: The message to display to the user
            schema: The JSON schema for the expected response

        Returns:
            ElicitResult with the user's response

        Raises:
            RuntimeError: If not running in a background task context
        """

    def _make_state_key(self, key: str, /) -> str:
        """Create session-prefixed key for state storage."""

    async def set_state(
            self, key: str, value: Any, /, *, serializable: bool = True
    ) -> None:
        """Set a value in the state store.

        By default, values are stored in the session-scoped state store and
        persist across requests within the same MCP session. Values must be
        JSON-serializable (dicts, lists, strings, numbers, etc.).

        For non-serializable values (e.g., HTTP clients, database connections),
        pass ``serializable=False``. These values are stored in a request-scoped
        dict and only live for the current MCP request (tool call, resource
        read, or prompt render). They will not be available in subsequent
        requests.

        The key is automatically prefixed with the session identifier.
        """

    async def get_state(self, key: str, /) -> Any:
        """Get a value from the state store.

        Checks request-scoped state first (set with ``serializable=False``),
        then falls back to the session-scoped state store.

        Returns None if the key is not found.
        """

    async def delete_state(self, key: str, /) -> None:
        """Delete a value from the state store.

        Removes from both request-scoped and session-scoped stores.
        """

    # -------------------------------------------------------------------------
    # Session visibility control
    # -------------------------------------------------------------------------

    async def _get_visibility_rules(self, /) -> Sequence[Mapping[str, Any]]:
        """Load visibility rule dicts from session state."""

    async def _get_session_transforms(self, /) -> Sequence[Visibility]:
        """Get session-specific Visibility transforms from state store."""

    async def enable_components(
            self,
            /,
            *,
            names: Iterable[str] | None = None,
            keys: Iterable[str] | None = None,
            version: VersionSpec | None = None,
            tags: Iterable[str] | None = None,
            components: Iterable[Literal["tool", "resource", "template", "prompt"]] | None = None,
            match_all: bool = False,
    ) -> None:
        """Enable components matching criteria for this session only.

        Session rules override global transforms. Rules accumulate - each call
        adds a new rule to the session. Later marks override earlier ones
        (Visibility transform semantics).

        Sends notifications to this session only: ToolListChangedNotification,
        ResourceListChangedNotification, and PromptListChangedNotification.

        Args:
            names: Component names or URIs to match.
            keys: Component keys to match (e.g., {"tool:my_tool@v1"}).
            version: Component version spec to match.
            tags: Tags to match (component must have at least one).
            components: Component types to match (e.g., {"tool", "prompt"}).
            match_all: If True, matches all components regardless of other criteria.
        """

    async def disable_components(
            self,
            /,
            *,
            names: Iterable[str] | None = None,
            keys: Iterable[str] | None = None,
            version: VersionSpec | None = None,
            tags: Iterable[str] | None = None,
            components: Iterable[Literal["tool", "resource", "template", "prompt"]] | None = None,
            match_all: bool = False,
    ) -> None:
        """Disable components matching criteria for this session only.

        Session rules override global transforms. Rules accumulate - each call
        adds a new rule to the session. Later marks override earlier ones
        (Visibility transform semantics).

        Sends notifications to this session only: ToolListChangedNotification,
        ResourceListChangedNotification, and PromptListChangedNotification.

        Args:
            names: Component names or URIs to match.
            keys: Component keys to match (e.g., {"tool:my_tool@v1"}).
            version: Component version spec to match.
            tags: Tags to match (component must have at least one).
            components: Component types to match (e.g., {"tool", "prompt"}).
            match_all: If True, matches all components regardless of other criteria.
        """

    async def reset_visibility(self, /) -> None:
        """Clear all session visibility rules.

        Use this to reset session visibility back to global defaults.

        Sends notifications to this session only: ToolListChangedNotification,
        ResourceListChangedNotification, and PromptListChangedNotification.
        """
