from collections.abc import Awaitable, Callable, Sequence, Mapping, Iterable
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal, overload, override

import mcp.types
from commons.types import AwaitableOr, SequenceOr
from key_value.aio.protocols import AsyncKeyValue
from mcp.types import Annotations, CreateTaskResult, Icon, ToolAnnotations
from pydantic import ValidationError as PydanticValidationError

from fastmcp.prompts import Prompt, PromptResult
from fastmcp.resources import Resource, ResourceResult, ResourceTemplate
from fastmcp.server.auth import AuthProvider
from fastmcp.server.lifespan import Lifespan
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.mixins import LifespanMixin, MCPOperationsMixin, TransportMixin
from fastmcp.server.providers import LocalProvider, Provider
from fastmcp.server.providers.aggregate import AggregateProvider
from fastmcp.server.tasks.config import TaskConfig, TaskMeta
from fastmcp.server.transforms import Transform
from fastmcp.tools import Tool, ToolResult
from fastmcp.utilities.authorization import AuthCheck
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.types import NotSet, NotSetT
from fastmcp.utilities.versions import VersionSpec

type DuplicateBehavior = Literal["warn", "error", "replace", "ignore"]
type LifespanCallable[T] = Callable[[FastMCP[T]], AbstractAsyncContextManager[T]]

# Copied from fastmcp/client/
from mcp.shared.context

type SamplingHandler[T, LifespanContextT] = Callable[
    [
        Sequence[mcp.types.SamplingMessage],
        mcp.types.CreateMessageRequestParams,
        mcp.shared.context.RequestContext[T, LifespanContextT]
    ],
    AwaitableOr[str | mcp.types.CreateMessageResult | mcp.types.CreateMessageResultWithTools]
]


class FastMCP[LifespanResultT](
    AggregateProvider,
    LifespanMixin,
    MCPOperationsMixin,
    TransportMixin,
):
    # <editor-fold defaultstate="collapsed" desc="def __init__(self, name, ...) -> None: ...">
    __slots__ = (
        "__provider",
        "__support_tasks_by_default",
        "_lifespan",
        "_lifespan_result",
        "_lifespan_result_set",
        "_lifespan_ref_count",
        "_lifespan_lock",
        "_started",
        "_mask_error_details",
        "_list_page_size",
        "_state_store",
        "_mcp_server",
        "auth",
        "strict_input_validation",
        "client_log_level",
        "experimental_capabilities",
        "middleware",
        "sampling_handler",
        "sampling_handler_behavior",
    )

    def __init__(
        self,
        name: str | None = None,
        /,
        instructions: str | None = None,
        *,
        version: str | int | float | None = None,
        website_url: str | None = None,
        icons: list[Icon] | None = None,
        auth: AuthProvider | None = None,
        middleware: Sequence[Middleware] | None = None,
        providers: Sequence[Provider] | None = None,
        transforms: Sequence[Transform] | None = None,
        lifespan: LifespanCallable | Lifespan | None = None,
        tools: Sequence[Tool | Callable[..., Any]] | None = None,
        on_duplicate: DuplicateBehavior = "warn",
        mask_error_details: bool = False,
        dereference_schemas: bool = True,
        strict_input_validation: bool = False,
        list_page_size: int | None = None,
        tasks: bool = False,
        session_state_store: AsyncKeyValue | None = None,
        sampling_handler: SamplingHandler | None = None,
        sampling_handler_behavior: Literal["always", "fallback"] = "fallback",
        client_log_level: mcp.types.LoggingLevel | None = None,
        experimental_capabilities: dict[str, dict[str, Any]] | None = None,
        **kwargs,
    ): ...
    # </editor-fold>

    # <editor-fold defaultstate="collapsed" desc="mcp_server properties">
    @property
    def name(self, /) -> str: ...

    @property
    def instructions(self, /) -> str | None: ...

    @instructions.setter
    def instructions(self, value: str | None, /) -> None: ...

    @property
    def version(self, /) -> str | None: ...

    @property
    def website_url(self, /) -> str | None: ...

    @property
    def icons(self, /) -> Sequence[Icon]: ...

    @property
    def local_provider(self, /) -> LocalProvider:
        """The server's local provider, which stores directly-registered components.

        Use this to remove components:

            mcp.local_provider.remove_tool("my_tool")
            mcp.local_provider.remove_resource("data://info")
            mcp.local_provider.remove_prompt("my_prompt")
        """
    # </editor-fold>

    async def _run_middleware[T, U](
            self, context: MiddlewareContext[T], call_next: Callable[[MiddlewareContext[T]], Awaitable[U]], /
    ) -> U:
        """Builds and executes the middleware chain."""

    def add_middleware(self, middleware: Middleware, /) -> None: ...

    @override
    def add_provider(self, provider: Provider, /, *, namespace: str = "") -> None:
        """Add a provider for dynamic tools, resources, and prompts.

        Providers are queried in registration order. The first provider to return
        a non-None result wins. Static components (registered via decorators)
        always take precedence over providers.

        Args:
            provider: A Provider instance that will provide components dynamically.
            namespace: Optional namespace prefix. When set:
                - Tools become "namespace_toolname"
                - Resources become "protocol://namespace/path"
                - Prompts become "namespace_promptname"
        """

    # -------------------------------------------------------------------------
    # Provider interface overrides - inherited from AggregateProvider
    # -------------------------------------------------------------------------
    # _list_tools, _list_resources, _list_resource_templates, _list_prompts
    # are inherited from AggregateProvider which handles aggregation and namespacing

    @override
    async def get_tasks(self, /) -> Sequence[FastMCPComponent]:
        """Get task-eligible components with all transforms applied.

        Overrides AggregateProvider.get_tasks() to apply server-level transforms
        after aggregation. AggregateProvider handles provider-level namespacing.
        """

    @override
    def add_transform(self, transform: Transform, /) -> None:
        """Add a server-level transform.

        Server-level transforms are applied after all providers are aggregated.
        They transform tools, resources, and prompts from ALL providers.

        Args:
            transform: The transform to add.

        Example:
            ```python
            from fastmcp.server.transforms import Namespace

            server = FastMCP("Server")
            server.add_transform(Namespace("api"))
            # All tools from all providers become "api_toolname"
            ```
        """

    @override
    async def list_tools(self, /, *, run_middleware: bool = True) -> Sequence[Tool]:
        """List all enabled tools from providers.

        Overrides Provider.list_tools() to add visibility filtering, auth filtering,
        and middleware execution. Returns all versions (no deduplication).
        Protocol handlers deduplicate for MCP wire format.
        """

    @override
    async def _get_tool(self, name: str, /, version: VersionSpec | None = None) -> Tool | None:
        """Get a tool by name via aggregation from providers.

        Extends AggregateProvider._get_tool() with component-level auth checks.

        Args:
            name: The tool name.
            version: Version filter (None returns highest version).

        Returns:
            The tool if found and authorized, None if not found or unauthorized.
        """

    @override
    async def get_tool(self, name: str, /, version: VersionSpec | None = None) -> Tool | None:
        """Get a tool by name, filtering disabled tools.

        Overrides Provider.get_tool() to add visibility filtering after all
        transforms (including session-level) have been applied. This ensures
        session transforms can override provider-level disables.

        When the highest version is disabled and no explicit version was
        requested, falls back to the next-highest enabled version.

        Args:
            name: The tool name.
            version: Version filter (None returns highest version).

        Returns:
            The tool if found and enabled, None otherwise.
        """

    @override
    async def list_resources(self, /, *, run_middleware: bool = True) -> Sequence[Resource]:
        """List all enabled resources from providers.

        Overrides Provider.list_resources() to add visibility filtering, auth filtering,
        and middleware execution. Returns all versions (no deduplication).
        Protocol handlers deduplicate for MCP wire format.
        """

    @override
    async def _get_resource(self, uri: str, /, version: VersionSpec | None = None) -> Resource | None:
        """Get a resource by URI via aggregation from providers.

        Extends AggregateProvider._get_resource() with component-level auth checks.

        Args:
            uri: The resource URI.
            version: Version filter (None returns highest version).

        Returns:
            The resource if found and authorized, None if not found or unauthorized.
        """

    @override
    async def get_resource(self, uri: str, /, version: VersionSpec | None = None) -> Resource | None:
        """Get a resource by URI, filtering disabled resources.

        Overrides Provider.get_resource() to add visibility filtering after all
        transforms (including session-level) have been applied.

        When the highest version is disabled and no explicit version was
        requested, falls back to the next-highest enabled version.

        Args:
            uri: The resource URI.
            version: Version filter (None returns highest version).

        Returns:
            The resource if found and enabled, None otherwise.
        """

    @override
    async def list_resource_templates(self, /, *, run_middleware: bool = True) -> Sequence[ResourceTemplate]:
        """List all enabled resource templates from providers.

        Overrides Provider.list_resource_templates() to add visibility filtering,
        auth filtering, and middleware execution. Returns all versions (no deduplication).
        Protocol handlers deduplicate for MCP wire format.
        """

    @override
    async def _get_resource_template(self, uri: str, /, version: VersionSpec | None = None) -> ResourceTemplate | None:
        """Get a resource template by URI via aggregation from providers.

        Extends AggregateProvider._get_resource_template() with component-level auth checks.

        Args:
            uri: The template URI to match.
            version: Version filter (None returns highest version).

        Returns:
            The template if found and authorized, None if not found or unauthorized.
        """

    @override
    async def get_resource_template(self, uri: str, /, version: VersionSpec | None = None) -> ResourceTemplate | None:
        """Get a resource template by URI, filtering disabled templates.

        Overrides Provider.get_resource_template() to add visibility filtering after
        all transforms (including session-level) have been applied.

        When the highest version is disabled and no explicit version was
        requested, falls back to the next-highest enabled version.

        Args:
            uri: The template URI.
            version: Version filter (None returns highest version).

        Returns:
            The template if found and enabled, None otherwise.
        """

    @override
    async def list_prompts(self, /, *, run_middleware: bool = True) -> Sequence[Prompt]:
        """List all enabled prompts from providers.

        Overrides Provider.list_prompts() to add visibility filtering, auth filtering,
        and middleware execution. Returns all versions (no deduplication).
        Protocol handlers deduplicate for MCP wire format.
        """

    @override
    async def _get_prompt(self, name: str, /, version: VersionSpec | None = None) -> Prompt | None:
        """Get a prompt by name via aggregation from providers.

        Extends AggregateProvider._get_prompt() with component-level auth checks.

        Args:
            name: The prompt name.
            version: Version filter (None returns highest version).

        Returns:
            The prompt if found and authorized, None if not found or unauthorized.
        """

    @override
    async def get_prompt(self, name: str, /, version: VersionSpec | None = None) -> Prompt | None:
        """Get a prompt by name, filtering disabled prompts.

        Overrides Provider.get_prompt() to add visibility filtering after all
        transforms (including session-level) have been applied.

        When the highest version is disabled and no explicit version was
        requested, falls back to the next-highest enabled version.

        Args:
            name: The prompt name.
            version: Version filter (None returns highest version).

        Returns:
            The prompt if found and enabled, None otherwise.
        """

    @overload
    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta,
    ) -> CreateTaskResult: ...
    @overload
    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: None = None,
    ) -> ToolResult: ...
    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta | None = None,
    ) -> ToolResult | CreateTaskResult:
        """Call a tool by name.

        This is the public API for executing tools. By default, middleware is applied.

        Args:
            name: The tool name
            arguments: Tool arguments (optional)
            version: Specific version to call. If None, calls highest version.
            run_middleware: If True (default), apply the middleware chain.
                Set to False when called from middleware to avoid re-applying.
            task_meta: If provided, execute as a background task and return
                CreateTaskResult. If None (default), execute synchronously and
                return ToolResult.

        Returns:
            ToolResult when task_meta is None.
            CreateTaskResult when task_meta is provided.

        Raises:
            NotFoundError: If tool not found or disabled
            ToolError: If tool execution fails
            ValidationError: If arguments fail validation
        """

    @overload
    async def read_resource(
        self,
        uri: str,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta,
    ) -> CreateTaskResult: ...
    @overload
    async def read_resource(
        self,
        uri: str,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: None = None,
    ) -> ResourceResult: ...
    async def read_resource(
        self,
        uri: str,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta | None = None,
    ) -> ResourceResult | CreateTaskResult:
        """Read a resource by URI.

        This is the public API for reading resources. By default, middleware is applied.
        Checks concrete resources first, then templates.

        Args:
            uri: The resource URI
            version: Specific version to read. If None, reads highest version.
            run_middleware: If True (default), apply the middleware chain.
                Set to False when called from middleware to avoid re-applying.
            task_meta: If provided, execute as a background task and return
                CreateTaskResult. If None (default), execute synchronously and
                return ResourceResult.

        Returns:
            ResourceResult when task_meta is None.
            CreateTaskResult when task_meta is provided.

        Raises:
            NotFoundError: If resource not found or disabled
            ResourceError: If resource read fails
        """

    @overload
    async def render_prompt(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta,
    ) -> CreateTaskResult: ...
    @overload
    async def render_prompt(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: None = None,
    ) -> PromptResult: ...
    async def render_prompt(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta | None = None,
    ) -> PromptResult | CreateTaskResult:
        """Render a prompt by name.

        This is the public API for rendering prompts. By default, middleware is applied.
        Use get_prompt() to retrieve the prompt definition without rendering.

        Args:
            name: The prompt name
            arguments: Prompt arguments (optional)
            version: Specific version to render. If None, renders highest version.
            run_middleware: If True (default), apply the middleware chain.
                Set to False when called from middleware to avoid re-applying.
            task_meta: If provided, execute as a background task and return
                CreateTaskResult. If None (default), execute synchronously and
                return PromptResult.

        Returns:
            PromptResult when task_meta is None.
            CreateTaskResult when task_meta is provided.

        Raises:
            NotFoundError: If prompt not found or disabled
            PromptError: If prompt rendering fails
        """

    @overload
    def tool[F](
            self,
            name_or_fn: F,
            *,
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: Sequence[Icon] | None = None,
            tags: Iterable[str] | None = None,
            output_schema: Mapping[str, Any] | NotSetT | None = NotSet,
            annotations: ToolAnnotations | Mapping[str, Any] | None = None,
            exclude_args: Sequence[str] | None = None,
            meta: Mapping[str, Any] | None = None,
            app: Mapping[str, Any] | bool | None = None,
            task: bool | TaskConfig | None = None,
            timeout: float | None = None,
            auth: SequenceOr[AuthCheck] | None = None,
            run_in_thread: bool = True,
    ) -> F: ...
    @overload
    def tool[F](
            self,
            name_or_fn: str | None = None,
            *,
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: Sequence[Icon] | None = None,
            tags: Iterable[str] | None = None,
            output_schema: Mapping[str, Any] | NotSetT | None = NotSet,
            annotations: ToolAnnotations | Mapping[str, Any] | None = None,
            exclude_args: Sequence[str] | None = None,
            meta: Mapping[str, Any] | None = None,
            app: Mapping[str, Any] | bool | None = None,
            task: bool | TaskConfig | None = None,
            timeout: float | None = None,
            auth: SequenceOr[AuthCheck] | None = None,
            run_in_thread: bool = True,
    ) -> Callable[[F], F]: ...
    def tool[F](
            self,
            name_or_fn: str | F | None = None,
            *,
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: Sequence[Icon] | None = None,
            tags: Iterable[str] | None = None,
            output_schema: Mapping[str, Any] | NotSetT | None = NotSet,
            annotations: ToolAnnotations | Mapping[str, Any] | None = None,
            exclude_args: Sequence[str] | None = None,
            meta: Mapping[str, Any] | None = None,
            app: Mapping[str, Any] | bool | None = None,
            task: bool | TaskConfig | None = None,
            timeout: float | None = None,
            auth: SequenceOr[AuthCheck] | None = None,
            run_in_thread: bool = True,
    ) -> Callable[[F], F] | F:
        """Decorator to register a tool.

        Tools can optionally request a Context object by adding a parameter with the
        Context type annotation. The context provides access to MCP capabilities like
        logging, progress reporting, and resource access.

        This decorator supports multiple calling patterns:
        - @server.tool (without parentheses)
        - @server.tool (with empty parentheses)
        - @server.tool("custom_name") (with name as first argument)
        - @server.tool(name="custom_name") (with name as keyword argument)
        - server.tool(function, name="custom_name") (direct function call)

        Args:
            name_or_fn: Either a function (when used as @tool), a string name, or None
            name: Optional name for the tool (keyword-only, alternative to name_or_fn)
            description: Optional description of what the tool does
            tags: Optional set of tags for categorizing the tool
            output_schema: Optional JSON schema for the tool's output
            annotations: Optional annotations about the tool's behavior
            exclude_args: Optional list of argument names to exclude from the tool schema.
                Deprecated: Use `Depends()` for dependency injection instead.
            meta: Optional meta information about the tool

        Examples:
            Register a tool with a custom name:
            ```python
            @server.tool
            def my_tool(x: int) -> str:
                return str(x)

            # Register a tool with a custom name
            @server.tool
            def my_tool(x: int) -> str:
                return str(x)

            @server.tool("custom_name")
            def my_tool(x: int) -> str:
                return str(x)

            @server.tool(name="custom_name")
            def my_tool(x: int) -> str:
                return str(x)

            # Direct function call
            server.tool(my_function, name="custom_name")
            ```
        """

    def resource[F](
            self,
            uri: str,
            *,
            name: str | None = None,
            version: str | int | None = None,
            title: str | None = None,
            description: str | None = None,
            icons: list[Icon] | None = None,
            mime_type: str | None = None,
            tags: set[str] | None = None,
            annotations: Annotations | dict[str, Any] | None = None,
            meta: dict[str, Any] | None = None,
            app: dict[str, Any] | bool | None = None,
            task: bool | TaskConfig | None = None,
            auth: AuthCheck | list[AuthCheck] | None = None,
    ) -> Callable[[F], F]:
        """Decorator to register a function as a resource.

        The function will be called when the resource is read to generate its content.
        The function can return:
        - str for text content
        - bytes for binary content
        - other types will be converted to JSON

        Resources can optionally request a Context object by adding a parameter with the
        Context type annotation. The context provides access to MCP capabilities like
        logging, progress reporting, and session information.

        If the URI contains parameters (e.g. "resource://{param}") or the function
        has parameters, it will be registered as a template resource.

        Args:
            uri: URI for the resource (e.g. "resource://my-resource" or "resource://{param}")
            name: Optional name for the resource
            description: Optional description of the resource
            mime_type: Optional MIME type for the resource
            tags: Optional set of tags for categorizing the resource
            annotations: Optional annotations about the resource's behavior
            meta: Optional meta information about the resource

        Examples:
            Register a resource with a custom name:
            ```python
            @server.resource("resource://my-resource")
            def get_data() -> str:
                return "Hello, world!"

            @server.resource("resource://my-resource")
            async get_data() -> str:
                data = await fetch_data()
                return f"Hello, world! {data}"

            @server.resource("resource://{city}/weather")
            def get_weather(city: str) -> str:
                return f"Weather for {city}"

            @server.resource("resource://{city}/weather")
            async def get_weather_with_context(city: str, ctx: Context) -> str:
                await ctx.info(f"Fetching weather for {city}")
                return f"Weather for {city}"

            @server.resource("resource://{city}/weather")
            async def get_weather(city: str) -> str:
                data = await fetch_weather(city)
                return f"Weather for {city}: {data}"
            ```
        """

    @overload
    def prompt[F](
            self,
            name_or_fn: F,
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
    ) -> F: ...
    @overload
    def prompt[F](
            self,
            name_or_fn: str | None = None,
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
    def prompt[F](
            self,
            name_or_fn: str | F | None = None,
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
    ) -> Callable[[F], F] | F:
        """Decorator to register a prompt.

        Prompts can optionally request a Context object by adding a parameter with the
        Context type annotation. The context provides access to MCP capabilities like
        logging, progress reporting, and session information.

        This decorator supports multiple calling patterns:
        - @server.prompt (without parentheses)
        - @server.prompt() (with empty parentheses)
        - @server.prompt("custom_name") (with name as first argument)
        - @server.prompt(name="custom_name") (with name as keyword argument)
        - server.prompt(function, name="custom_name") (direct function call)

        Args:
            name_or_fn: Either a function (when used as @prompt), a string name, or None
            name: Optional name for the prompt (keyword-only, alternative to name_or_fn)
            description: Optional description of what the prompt does
            tags: Optional set of tags for categorizing the prompt
            meta: Optional meta information about the prompt

        Examples:

            ```python
            @server.prompt
            def analyze_table(table_name: str) -> list[Message]:
                schema = read_table_schema(table_name)
                return [
                    {
                        "role": "user",
                        "content": f"Analyze this schema:\n{schema}"
                    }
                ]

            @server.prompt()
            async def analyze_with_context(table_name: str, ctx: Context) -> list[Message]:
                await ctx.info(f"Analyzing table {table_name}")
                schema = read_table_schema(table_name)
                return [
                    {
                        "role": "user",
                        "content": f"Analyze this schema:\n{schema}"
                    }
                ]

            @server.prompt("custom_name")
            async def analyze_file(path: str) -> list[Message]:
                content = await read_file(path)
                return [
                    {
                        "role": "user",
                        "content": {
                            "type": "resource",
                            "resource": {
                                "uri": f"file://{path}",
                                "text": content
                            }
                        }
                    }
                ]

            @server.prompt(name="custom_name")
            def another_prompt(data: str) -> list[Message]:
                return [{"role": "user", "content": data}]

            # Direct function call
            server.prompt(my_function, name="custom_name")
            ```
        """

    def mount(
            self,
            server: FastMCP[LifespanResultT],
            namespace: str | None = None,
            as_proxy: bool | None = None,
            tool_names: dict[str, str] | None = None,
            prefix: str | None = None,  # deprecated, use namespace
    ) -> None:
        """Mount another FastMCP server on this server with an optional namespace.

        Unlike importing (with import_server), mounting establishes a dynamic connection
        between servers. When a client interacts with a mounted server's objects through
        the parent server, requests are forwarded to the mounted server in real-time.
        This means changes to the mounted server are immediately reflected when accessed
        through the parent.

        When a server is mounted with a namespace:
        - Tools from the mounted server are accessible with namespaced names.
          Example: If server has a tool named "get_weather", it will be available as "namespace_get_weather".
        - Resources are accessible with namespaced URIs.
          Example: If server has a resource with URI "weather://forecast", it will be available as
          "weather://namespace/forecast".
        - Templates are accessible with namespaced URI templates.
          Example: If server has a template with URI "weather://location/{id}", it will be available
          as "weather://namespace/location/{id}".
        - Prompts are accessible with namespaced names.
          Example: If server has a prompt named "weather_prompt", it will be available as
          "namespace_weather_prompt".

        When a server is mounted without a namespace (namespace=None), its tools, resources, templates,
        and prompts are accessible with their original names. Multiple servers can be mounted
        without namespaces, and they will be tried in order until a match is found.

        The mounted server's lifespan is executed when the parent server starts, and its
        middleware chain is invoked for all operations (tool calls, resource reads, prompts).

        Args:
            server: The FastMCP server to mount.
            namespace: Optional namespace to use for the mounted server's objects. If None,
                the server's objects are accessible with their original names.
            as_proxy: Deprecated. Mounted servers now always have their lifespan and
                middleware invoked. To create a proxy server, use create_proxy()
                explicitly before mounting.
            tool_names: Optional mapping of original tool names to custom names. Use this
                to override namespaced names. Keys are the original tool names from the
                mounted server.
            prefix: Deprecated. Use namespace instead.
        """

    @classmethod
    def generate_name(cls, name: str | None = None) -> str: ...

    def __repr__(self, /) -> str:
        return f"{type(self).__name__}({self.name!r})"
