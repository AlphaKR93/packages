import re
import secrets
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import partial
from typing import Any, cast, override

import httpx
import mcp.types
from anyio import Lock, Event
from key_value.aio.adapters.pydantic import PydanticAdapter
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl
from pydantic import ValidationError as PydanticValidationError

from fastmcp.exceptions import AuthorizationError, FastMCPError, NotFoundError, PromptError, ResourceError, ToolError
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.mixins import LifespanMixin, MCPOperationsMixin, TransportMixin
from fastmcp.server.low_level import LowLevelServer
from fastmcp.server.providers.aggregate import AggregateProvider
from fastmcp.server.transforms.visibility import apply_session_transforms, is_enabled
from fastmcp.server.transforms.tool_transform import ToolTransform, ToolTransformConfig
from fastmcp.server.server import StateValue, _logger
from fastmcp.server.providers import LocalProvider
from fastmcp.tools import Tool
from fastmcp.utilities.authorization import AuthContext, run_auth_checks
from fastmcp.utilities.components import _coerce_version
from fastmcp.utilities.versions import version_sort_key

import alpha93.fastmcp._internal.server.context as _ctx
from alpha93._tmp_commons import catch


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, MutableSequence, Sequence
    from contextlib import AbstractAsyncContextManager
    from typing import Final, Literal

    from commons.types import AwaitableOr
    from key_value.aio.protocols import AsyncKeyValue
    from mcp.types import CreateTaskResult, Icon

    from fastmcp.prompts import Prompt, PromptResult
    from fastmcp.resources import Resource, ResourceResult, ResourceTemplate
    from fastmcp.server.auth import AuthProvider
    from fastmcp.server.lifespan import Lifespan
    from fastmcp.server.middleware import Middleware
    from fastmcp.server.providers import Provider
    from fastmcp.server.transforms import Transform
    from fastmcp.tools import ToolResult
    from fastmcp.utilities.tasks import TaskMeta
    from fastmcp.utilities.versions import VersionSpec

    type DuplicateBehavior = Literal["warn", "error", "replace", "ignore"]
    type Transport = Literal["stdio", "http"]
    type LifespanCallable[T] = Callable[[FastMCP[T]], AbstractAsyncContextManager[T]]

    # Copied from fastmcp/client/
    import mcp.shared.context

    type SamplingHandler[T, LifespanContextT] = Callable[
        [
            Sequence[mcp.types.SamplingMessage],
            mcp.types.CreateMessageRequestParams,
            mcp.shared.context.RequestContext[T, LifespanContextT]
        ],
        AwaitableOr[str | mcp.types.CreateMessageResult | mcp.types.CreateMessageResultWithTools]
    ]


# Compiled URI parsing regex to split a URI into protocol and path components
URI_PATTERN: Final = re.compile(r"^([^:]+://)(.*?)$")
_authorize = catch(AuthorizationError)


class FastMCP[LifespanResultT](
    AggregateProvider,
    LifespanMixin,
    MCPOperationsMixin,
    TransportMixin,
):
    # <editor-fold defaultstate="collapsed" desc="def __init__(self, name, ...) -> None: ...">
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
        lifespan: LifespanCallable[LifespanResultT] | Lifespan | None = None,
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
    ):
        assert list_page_size is None or list_page_size > 0, "list_page_size must be positive"

        # Handle Lifespan instances (they're callable) or regular lifespan functions
        if lifespan is None:
            lifespan = default_lifespan

        # Initialize Provider (sets up _transforms)
        super().__init__()

        self.__provider: Final = LocalProvider(on_duplicate)
        self.__support_tasks_by_default: Final = tasks

        self._lifespan: Final = cast("LifespanCallable[LifespanResultT]", lifespan)
        self._lifespan_result: LifespanResultT | None = None
        self._lifespan_result_set: bool = False
        self._lifespan_ref_count: int = 0
        self._lifespan_lock: Final = Lock()
        self._started: Final = Event()
        self._mask_error_details: Final = mask_error_details
        self._list_page_size: Final = list_page_size

        if not session_state_store:
            try:
                from key_value.aio.stores.memory import MemoryStore

                session_state_store = MemoryStore()
            except ImportError as e:
                raise e

        self._state_store: Final = PydanticAdapter[StateValue](session_state_store, StateValue, default_collection="fastmcp_state")

        self.auth: Final = auth
        self.strict_input_validation: Final = strict_input_validation
        self.client_log_level: Final = client_log_level
        self.experimental_capabilities: Final[Mapping[str, Mapping[str, Any]]] = experimental_capabilities or {}
        self.middleware: Final[MutableSequence[Middleware]] = list(middleware) if middleware else []

        # Add providers using AggregateProvider's add_provider
        # LocalProvider is always first (no namespace)
        self.add_provider(self.local_provider)
        for p in providers or []:
            self.add_provider(p)

        for t in transforms or []:
            self.add_transform(t)

        # Generate random ID if no name provided
        self._mcp_server: Final = LowLevelServer[LifespanResultT, Any](
            self,
            name=name or self.generate_name(),
            version=_coerce_version(version) or __import__("fastmcp").__version__,
            lifespan=_lifespan_proxy(self),
            instructions=instructions,
            website_url=website_url,
            icons=icons,
        )

        if tools:
            for tool in tools:
                if not isinstance(tool, Tool):
                    tool: Callable[..., Any]
                    tool: Tool = Tool.from_function(tool)
                self.local_provider.add_tool(tool)

        if dereference_schemas:
            from fastmcp.server.middleware.dereference import DereferenceRefsMiddleware

            self.middleware.append(DereferenceRefsMiddleware())

        # Set up MCP protocol handlers
        self._setup_handlers()

        self.sampling_handler: Final[SamplingHandler | None] = sampling_handler
        self.sampling_handler_behavior: Final[Literal["always", "fallback"]] = sampling_handler_behavior
    # </editor-fold>

    # <editor-fold defaultstate="collapsed" desc="mcp_server properties">
    @property
    def name(self, /):
        return self._mcp_server.name

    @property
    def instructions(self, /):
        return self._mcp_server.instructions

    @instructions.setter
    def instructions(self, value, /):
        self._mcp_server.instructions = value

    @property
    def version(self, /):
        return self._mcp_server.version

    @property
    def website_url(self, /):
        return self._mcp_server.website_url

    @property
    def icons(self, /):
        return list(self._mcp_server.icons) if self._mcp_server.icons else []

    @property
    def local_provider(self, /):
        return self.__provider
    # </editor-fold>

    async def _run_middleware(self, context, call_next, /):
        """Builds and executes the middleware chain."""
        chain = call_next
        for mw in reversed(self.middleware):
            chain = partial(mw, call_next=chain)
        return await chain(context)

    def add_middleware(self, middleware, /):
        self.middleware.append(middleware)

    # -------------------------------------------------------------------------
    # Provider interface overrides - inherited from AggregateProvider
    # -------------------------------------------------------------------------
    # _list_tools, _list_resources, _list_resource_templates, _list_prompts
    # are inherited from AggregateProvider which handles aggregation and namespacing

    @override
    async def get_tasks(self, /):
        # Get tasks from AggregateProvider (handles aggregation and namespacing)
        components = list(await super().get_tasks())

        # Separate by component type for server-level transform application
        tools = []; resources = []; templates = []; prompts = []
        for component in components:
            l = tools if isinstance(component, Tool) \
                else resources if isinstance(component, Resource) \
                else templates if isinstance(component, ResourceTemplate) \
                else prompts if isinstance(component, Prompt) \
                else None
            assert l, f"Unexpected component type: {type(component)}"
            l.append(component)

        # Apply server-level transforms sequentially
        components = []
        for transform in self.transforms:
            components.append(await transform.list_tools(tools))
            components.append(await transform.list_resources(resources))
            components.append(await transform.list_resource_templates(templates))
            components.append(await transform.list_prompts(prompts))

        return components

    @override
    async def list_tools(self, /, *, run_middleware = True):
        async with _ctx.Context(self) as ctx:
            if run_middleware:
                mw_context = MiddlewareContext(
                    message=mcp.types.ListToolsRequest(method="tools/list"),
                    source="client",
                    type="request",
                    method="tools/list",
                    fastmcp_context=ctx,
                )
                return await self._run_middleware(mw_context, lambda context: self.list_tools(run_middleware=False))

            # Get all tools, apply session transforms, then filter enabled
            # and model-visible (app-only tools are hidden from the model).
            tools = await super().list_tools()
            tools = await apply_session_transforms(tools)

            skip_auth, token = _get_auth_context()
            authorized: list[Tool] = []
            for tool in tools:
                if not is_enabled(tool) or _is_backend_tool(tool):
                    continue

                if not skip_auth and tool.auth:
                    ctx_ = AuthContext(token=token, component=tool)

                    # noinspection PyTypeChecker,PyUnresolvedReferences
                    granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                    if not granted or exc:
                        continue
                authorized.append(tool)
            return authorized

    @override
    async def _get_tool(self, name, /, version = None):
        # Get tool from AggregateProvider (handles aggregation and namespacing)
        tool = await super()._get_tool(name, version)
        if tool is None:
            return None

        # Component auth - return None if unauthorized (consistent with list filtering)
        skip_auth, token = _get_auth_context()
        if not skip_auth and tool.auth:
            ctx_ = AuthContext(token=token, component=tool)

            # noinspection PyTypeChecker,PyUnresolvedReferences
            granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
            if not granted or exc:
                return None

        return tool

    @override
    async def get_tool(self, name, /, version = None):
        tool = await super().get_tool(name, version)
        if tool is None:
            return None

        # Apply session transforms to single item
        tools = await apply_session_transforms([tool])
        if tools and is_enabled(tools[0]) and not _is_backend_tool(tools[0]):
            return tools[0]

        # The highest version is disabled (or app-only). If an explicit version
        # was requested, respect that. Otherwise fall back to the next-highest
        # enabled, model-visible version.
        if version:
            return None

        all_tools = [t for t in await super().list_tools() if t.name == name]
        all_tools = await apply_session_transforms(all_tools)
        all_tools = [t for t in all_tools if is_enabled(t) and not _is_backend_tool(t)]

        skip_auth, token = _get_auth_context()
        authorized: list[Tool] = []
        for tool in all_tools:
            if not skip_auth and tool.auth:
                ctx_ = AuthContext(token=token, component=tool)

                # noinspection PyTypeChecker,PyUnresolvedReferences
                granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                if not granted or exc:
                    continue
            authorized.append(tool)

        return max(authorized, key=version_sort_key) if authorized else None

    @override
    async def list_resources(self, /, *, run_middleware = True):
        async with _ctx.Context(self) as ctx:
            if run_middleware:
                mw_context = MiddlewareContext(
                    message={},
                    source="client",
                    type="request",
                    method="resources/list",
                    fastmcp_context=ctx,
                )
                return await self._run_middleware(mw_context, lambda context: self.list_resources(run_middleware=False))

            # Get all resources, apply session transforms, then filter enabled
            resources: Sequence[Resource] = list(await super().list_resources())
            resources = await apply_session_transforms(resources)
            resources = [r for r in resources if is_enabled(r)]

            skip_auth, token = _get_auth_context()
            authorized: list[Resource] = []
            for resource in resources:
                if not skip_auth and resource.auth:
                    ctx_ = AuthContext(token=token, component=resource)

                    # noinspection PyTypeChecker,PyUnresolvedReferences
                    granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                    if not granted or exc:
                        continue
                authorized.append(resource)
            return authorized

    @override
    async def _get_resource(self, uri, /, version = None):
        # Get resource from AggregateProvider (handles aggregation and namespacing)
        resource = await super()._get_resource(uri, version)
        if resource is None:
            return None

        # Component auth - return None if unauthorized (consistent with list filtering)
        skip_auth, token = _get_auth_context()
        if not skip_auth and resource.auth is not None:
            ctx_ = AuthContext(token=token, component=resource)

            # noinspection PyTypeChecker,PyUnresolvedReferences
            granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
            if not granted or exc:
                return None

        return resource

    @override
    async def get_resource(self, uri, /, version = None):
        resource = await super().get_resource(uri, version)
        if resource is None:
            return None

        # Apply session transforms to single item
        resources = await apply_session_transforms([resource])
        if resources and is_enabled(resources[0]):
            return resources[0]

        if version is not None:
            return None

        all_resources = [r for r in await super().list_resources() if str(r.uri) == uri]
        all_resources = await apply_session_transforms(all_resources)
        all_resources = [r for r in all_resources if is_enabled(r)]

        skip_auth, token = _get_auth_context()
        authorized: list[Resource] = []
        for resource in all_resources:
            if not skip_auth and resource.auth:
                ctx_ = AuthContext(token=token, component=resource)

                # noinspection PyTypeChecker,PyUnresolvedReferences
                granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                if not granted or exc:
                    continue
            authorized.append(resource)

        return max(authorized, key=version_sort_key) if authorized else None

    @override
    async def list_resource_templates(self, /, *, run_middleware = True):
        async with _ctx.Context(self) as ctx:
            if run_middleware:
                mw_context = MiddlewareContext(
                    message={},
                    source="client",
                    type="request",
                    method="resources/templates/list",
                    fastmcp_context=ctx,
                )
                return await self._run_middleware(
                    mw_context,
                    lambda context: self.list_resource_templates(run_middleware=False)
                )

            # Get all templates, apply session transforms, then filter enabled
            templates = await super().list_resource_templates()
            templates = await apply_session_transforms(templates)
            templates = [t for t in templates if is_enabled(t)]

            skip_auth, token = _get_auth_context()
            authorized: list[ResourceTemplate] = []
            for template in templates:
                if not skip_auth and template.auth:
                    ctx_ = AuthContext(token=token, component=template)

                    # noinspection PyTypeChecker,PyUnresolvedReferences
                    granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                    if not granted or exc:
                        continue
                authorized.append(template)
            return authorized

    @override
    async def _get_resource_template(self, uri, /, version = None):
        # Get template from AggregateProvider (handles aggregation and namespacing)
        template = await super()._get_resource_template(uri, version)
        if template is None:
            return None

        # Component auth - return None if unauthorized (consistent with list filtering)
        skip_auth, token = _get_auth_context()
        if not skip_auth and template.auth:
            ctx_ = AuthContext(token=token, component=template)

            # noinspection PyTypeChecker,PyUnresolvedReferences
            granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
            if not granted or exc:
                return None

        return template

    @override
    async def get_resource_template(self, uri, /, version = None):
        template = await super().get_resource_template(uri, version)
        if template is None:
            return None

        # Apply session transforms to single item
        templates = await apply_session_transforms([template])
        if templates and is_enabled(templates[0]):
            return templates[0]

        if version is not None:
            return None

        all_templates = [t for t in await super().list_resource_templates() if t.matches(uri)]
        all_templates = await apply_session_transforms(all_templates)
        all_templates = [t for t in all_templates if is_enabled(t)]

        skip_auth, token = _get_auth_context()
        authorized: list[ResourceTemplate] = []
        for template in all_templates:
            if not skip_auth and template.auth:
                ctx_ = AuthContext(token=token, component=template)

                # noinspection PyTypeChecker,PyUnresolvedReferences
                granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                if not granted or exc:
                    continue
            authorized.append(template)

        return max(authorized, key=version_sort_key) if authorized else None

    @override
    async def list_prompts(self, /, *, run_middleware = True):
        async with _ctx.Context(self) as ctx:
            if run_middleware:
                mw_context = MiddlewareContext(
                    message={},
                    source="client",
                    type="request",
                    method="prompts/list",
                    fastmcp_context=ctx,
                )
                return await self._run_middleware(
                    mw_context,
                    lambda context: self.list_prompts(run_middleware=False),
                )

            # Get all prompts, apply session transforms, then filter enabled
            prompts = await super().list_prompts()
            prompts = await apply_session_transforms(prompts)
            prompts = [p for p in prompts if is_enabled(p)]

            skip_auth, token = _get_auth_context()
            authorized: list[Prompt] = []
            for prompt in prompts:
                if not skip_auth and prompt.auth:
                    ctx_ = AuthContext(token=token, component=prompt)

                    # noinspection PyTypeChecker,PyUnresolvedReferences
                    granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                    if not granted or exc:
                        continue
                authorized.append(prompt)
            return authorized

    @override
    async def _get_prompt(self, name, /, version = None):
        # Get prompt from AggregateProvider (handles aggregation and namespacing)
        prompt = await super()._get_prompt(name, version)
        if prompt is None:
            return None

        # Component auth - return None if unauthorized (consistent with list filtering)
        skip_auth, token = _get_auth_context()
        if not skip_auth and prompt.auth:
            ctx_ = AuthContext(token=token, component=prompt)

            # noinspection PyTypeChecker,PyUnresolvedReferences
            granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
            if not granted or exc:
                return None

        return prompt

    @override
    async def get_prompt(self, name, /, version = None):
        prompt = await super().get_prompt(name, version)
        if prompt is None:
            return None

        # Apply session transforms to single item
        prompts = await apply_session_transforms([prompt])
        if prompts and is_enabled(prompts[0]):
            return prompts[0]

        if version is not None:
            return None

        all_prompts = [p for p in await super().list_prompts() if p.name == name]
        all_prompts = list(await apply_session_transforms(all_prompts))
        all_prompts = [p for p in all_prompts if is_enabled(p)]

        skip_auth, token = _get_auth_context()
        authorized: list[Prompt] = []
        for prompt in all_prompts:
            if not skip_auth and prompt.auth:
                ctx_ = AuthContext(token=token, component=prompt)

                # noinspection PyTypeChecker,PyUnresolvedReferences
                granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                if not granted or exc:
                    continue
            authorized.append(prompt)

        return max(authorized, key=version_sort_key) if authorized else None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        /,
        *,
        task_meta: TaskMeta | None = None,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
    ) -> ToolResult | CreateTaskResult:
        # Note: fn_key enrichment happens here after finding the tool.
        # For mounted servers, the parent's provider sets fn_key to the
        # namespaced key before delegating, ensuring correct Docket routing.

        # Two routing paths:
        #   1. Hashed-name path — backend tools that opted into
        #      app-callable visibility. Recognized by their
        #      `<hash>_<local_name>` format and resolved via the
        #      reverse-hash map. Address is known eagerly.
        #   2. Display-name path — everything else. Goes through normal
        #      `get_tool` aggregation/transforms. Address is determined
        #      after resolution by walking the registry.
        async with _ctx.Context(self) as ctx:
            if run_middleware:
                mw_context = MiddlewareContext(
                    message=mcp.types.CallToolRequestParams(name=name, arguments=arguments or {}),
                    source="client",
                    type="request",
                    method="tools/call",
                    fastmcp_context=ctx,
                )
                # noinspection PyTypeChecker
                return await self._run_middleware(
                    mw_context,
                    lambda context: self.call_tool(
                        context.message.name,
                        context.message.arguments or {},
                        version=version,
                        run_middleware=False,
                        task_meta=task_meta,
                    )
                )

            # Try normal display-name resolution first.
            tool = await self.get_tool(name, version)

            # If that fails, try hashed-name dispatch. This walks
            # the provider tree recursively (same pattern as the old
            # get_app_tool) looking for a tool whose stored hash
            # matches the parsed prefix.
            if tool is None:
                from fastmcp.server.providers.addressing import parse_hashed_backend_name

                if hashed := parse_hashed_backend_name(name):
                    digest, local_name = hashed
                    if tool := await self.get_tool_by_hash(digest, local_name):
                        # Auth still applies on the bypass path.
                        skip_auth, token = _get_auth_context()
                        if not skip_auth and tool.auth:
                            ctx_ = AuthContext(token=token, component=tool)

                            # noinspection PyTypeChecker,PyUnresolvedReferences
                            granted, exc = await _authorize(lambda: run_auth_checks(tool.auth, ctx_))
                            if not granted or exc:
                                raise NotFoundError(f"Unknown tool: {name!r}")
                            # authorized
                        # authorized (public)
                # tool: None

            # No tool found
            if tool is None:
                raise NotFoundError(f"Unknown tool: {name!r}")

            if task_meta and not task_meta.fn_key:
                task_meta = replace(task_meta, fn_key=tool.key)

            try:
                # noinspection PyTypeChecker
                return await tool._run(arguments or {}, task_meta=task_meta)
            except FastMCPError as e:
                _logger.log(
                    e.log_level, f"Error calling tool {name!r}", exc_info=False
                )
                raise
            except PydanticValidationError as e:
                # fastmcp's own ValidationError is a FastMCPError, already handled above.
                _logger.warning(
                    "Invalid arguments for tool %r: %s",
                    name,
                    e.errors(include_url=False),
                )
                raise
            except Exception as e:
                _logger.exception(f"Error calling tool {name!r}")
                # Handle actionable errors that should reach the LLM
                # even when masking is enabled
                if isinstance(e, httpx.HTTPStatusError):
                    if e.response.status_code == 429:
                        raise ToolError(
                            "Rate limited by upstream API, please retry later"
                        ) from e
                if isinstance(e, httpx.TimeoutException):
                    raise ToolError(
                        "Upstream request timed out, please retry"
                    ) from e
                # Standard masking logic
                if self._mask_error_details:
                    raise ToolError(f"Error calling tool {name!r}") from e
                raise ToolError(f"Error calling tool {name!r}: {e}") from e

    async def read_resource(
        self,
        uri: str,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta | None = None,
    ) -> ResourceResult | CreateTaskResult:
        # Note: fn_key enrichment happens here after finding the resource/template.
        # Resources and templates use different key formats:
        # - Resources use resource.key (derived from the concrete URI)
        # - Templates use template.key (the template pattern)
        # For mounted servers, the parent's provider sets fn_key to the
        # namespaced key before delegating, ensuring correct Docket routing.

        async with _ctx.Context(self) as ctx:
            if run_middleware:
                uri_param = AnyUrl(uri)
                mw_context = MiddlewareContext(
                    message=mcp.types.ReadResourceRequestParams(uri=uri_param),
                    source="client",
                    type="request",
                    method="resources/read",
                    fastmcp_context=ctx,
                )
                # noinspection PyTypeChecker
                return await self._run_middleware(
                    mw_context,
                    lambda context: self.read_resource(
                        str(context.message.uri),
                        version=version,
                        run_middleware=False,
                        task_meta=task_meta,
                    ),
                )

            # Intercept synthetic Prefab renderer URIs before normal
            # resolution. The resource isn't stored anywhere — we
            # build it on demand from the matching tool's CSP.

            # Try concrete resources first (transforms + auth via _get_resource)
            resource = await self.get_resource(uri, version=version)
            read_fn: Callable[[], Awaitable[ResourceResult | CreateTaskResult]]
            if resource is not None:
                if task_meta and not task_meta.fn_key:
                    task_meta = replace(task_meta, fn_key=resource.key)

                read_fn = lambda: resource._read(task_meta=task_meta)
            else:
                # Try templates (transforms + auth via get_resource_template)
                template = await self.get_resource_template(uri, version=version)
                if template is None:
                    if version is None:
                        raise NotFoundError(f"Unknown resource: {uri!r}")
                    raise NotFoundError(f"Unknown resource: {uri!r} version {version!r}")

                params = template.matches(uri)
                if not params:
                    async def _read_fn():
                        raise FastMCPError(f"Misconfigured resource {uri!r}: params should not be None")
                    read_fn = _read_fn
                else:
                    if task_meta and not task_meta.fn_key:
                        task_meta = replace(task_meta, fn_key=template.key)

                    # noinspection PyTypeChecker
                    read_fn = lambda: template._read(uri, params, task_meta=task_meta)

            try:
                # noinspection PyTypeChecker
                return await read_fn()
            except FastMCPError as e:
                _logger.log(
                    e.log_level, f"Error reading resource {uri!r}", exc_info=True
                )
                raise
            except McpError:
                _logger.exception(f"Error reading resource {uri!r}")
                raise
            except Exception as e:
                _logger.exception(f"Error reading resource {uri!r}")
                # Handle actionable errors that should reach the LLM
                if isinstance(e, httpx.HTTPStatusError):
                    if e.response.status_code == 429:
                        raise ResourceError(
                            "Rate limited by upstream API, please retry later"
                        ) from e
                if isinstance(e, httpx.TimeoutException):
                    raise ResourceError(
                        "Upstream request timed out, please retry"
                    ) from e
                # Standard masking logic
                if self._mask_error_details:
                    raise ResourceError(f"Error reading resource {uri!r}") from e
                raise ResourceError(f"Error reading resource {uri!r}: {e}") from e

    async def render_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        /,
        *,
        version: VersionSpec | None = None,
        run_middleware: bool = True,
        task_meta: TaskMeta | None = None,
    ) -> PromptResult | CreateTaskResult:
        async with _ctx.Context(self) as ctx:
            if run_middleware:
                mw_context = MiddlewareContext(
                    message=mcp.types.GetPromptRequestParams(name=name, arguments=arguments),
                    source="client",
                    type="request",
                    method="prompts/get",
                    fastmcp_context=ctx,
                )
                # noinspection PyTypeChecker
                return await self._run_middleware(
                    mw_context,
                    lambda context: self.render_prompt(
                        context.message.name,
                        context.message.arguments,
                        version=version,
                        run_middleware=False,
                        task_meta=task_meta,
                    ),
                )

            prompt = await self.get_prompt(name, version=version)
            if not prompt:
                raise NotFoundError(f"Unknown prompt: {name!r}")

            if task_meta is not None and task_meta.fn_key is None:
                task_meta = replace(task_meta, fn_key=prompt.key)

            try:
                # noinspection PyTypeChecker
                return await prompt._render(arguments, task_meta=task_meta)
            except FastMCPError as e:
                _logger.log(
                    e.log_level, f"Error rendering prompt {name!r}", exc_info=True
                )
                raise
            except McpError:
                _logger.exception(f"Error rendering prompt {name!r}")
                raise
            except Exception as e:
                _logger.exception(f"Error rendering prompt {name!r}")
                if self._mask_error_details:
                    raise PromptError(f"Error rendering prompt {name!r}") from e
                raise PromptError(f"Error rendering prompt {name!r}: {e}") from e

    def tool(self, fname = None, /, *, app = None, **kwargs):
        # Merge app config into meta["ui"] (wire format) before passing to provider
        if app:
            if not (meta := kwargs.get("meta")):
                meta = kwargs["meta"] = {}
            meta["ui"] = True if isinstance(app, bool) else dict(app)
        if kwargs.get("task") is None:
            kwargs["task"] = self.__support_tasks_by_default

        # Delegate to LocalProvider with server-level defaults
        return self.local_provider.tool(fname, **kwargs)

    def resource(self, uri, /, *, app = None, **kwargs):
        # Catch incorrect decorator usage early (before any processing)
        assert isinstance(uri, str), "The @resource was used incorrectly, it requires a URI as the first argument. " \
                                     "Use @resource('uri') instead of @resource"

        # Merge app config into meta["ui"] (wire format) before passing to provider
        if app:
            if not (meta := kwargs.get("meta")):
                meta = kwargs["meta"] = {}
            meta["ui"] = True if isinstance(app, bool) else dict(app)
        if kwargs.get("task") is None:
            kwargs["task"] = self.__support_tasks_by_default

        # Delegate to LocalProvider with server-level defaults
        return self.local_provider.resource(uri, **kwargs)

    def prompt(self, fname = None, /, **kwargs):
        if kwargs.get("task") is None:
            kwargs["task"] = self.__support_tasks_by_default

        # Delegate to LocalProvider with server-level defaults
        return self.local_provider.prompt(fname, **kwargs)

    def mount(self, server, /, tool_names = None, **kwargs) -> None:
        from fastmcp.server.providers.fastmcp_provider import FastMCPProvider

        assert server is not self, "Cannot mount a server onto itself"
        assert "as_proxy" not in kwargs.keys(), \
            "as_proxy is deprecated; mounted servers now always have their lifespan " \
            "and middleware invoked. To create a proxy server, use create_proxy() explicitly."
        assert "prefix" not in kwargs.keys(), "The 'prefix' parameter is deprecated, use 'namespace' instead"

        # Warn if parent masks errors but child doesn't (or vice versa)
        if self._mask_error_details and not server._mask_error_details:
            _logger.warning(
                f"Parent server {self.name!r} has mask_error_details=True but "
                f"mounted server {server.name!r} does not. Error details from "
                f"{server.name!r} may leak through to clients. Set "
                f"mask_error_details=True on the child server to prevent this."
            )

        # Create provider and add it with namespace
        provider: Provider = FastMCPProvider(server)

        # Apply tool renames first (scoped to this provider), then namespace
        # So foo → bar with namespace="baz" becomes baz_bar
        if tool_names:
            transforms = {
                old_name: ToolTransformConfig(name=new_name)
                for old_name, new_name in tool_names.items()
            }
            provider = provider.wrap_transform(ToolTransform(transforms))

        # Use add_provider with namespace (applies namespace in AggregateProvider)
        self.add_provider(provider, **kwargs)

    def __repr__(self, /):
        return f"{type(self).__name__}({self.name!r})"

    @classmethod
    def generate_name(cls, name: str | None = None, /) -> str:
        return '-'.join((i for i in (cls.__name__, name, secrets.token_hex(2)) if i is not None))


def _get_auth_context() -> tuple[bool, Any]:
    """Get auth context for the current request.

    Returns a tuple of (skip_auth, token) where:
    - skip_auth=True means auth checks should be skipped (STDIO transport)
    - token is the access token for HTTP transports (may be None if unauthenticated)

    Uses late import to avoid circular import with context.py.
    """
    # noinspection PyUnresolvedReferences
    from alpha93.fastmcp._internal.server.context import _current_transport

    is_stdio = _current_transport.get() == "stdio"
    if is_stdio:
        return True, None
    from fastmcp.server.dependencies import get_access_token

    return False, get_access_token()


def _is_backend_tool(tool: Tool, /) -> bool:
    """Check whether a tool is handled specially as backend tool

    Tools registered via ``@app.tool()`` (without ``model=True``) have
    ``meta["ui"]["visibility"] == ["app"]`` — they are callable by app UIs
    but should not appear in tool list the client passes to the model.

    They are handled specially for in various ways - e.g. they are looked
    up via get_app_tool(), and don't appear in the tools/list output.
    (FIXME: the latter isn't correct behavior according to the mcp-apps spec.)

    Returns True (a backend tool) when:
    - The tool has ``meta.fastmcp.app``.
    - The tool has ``meta.ui.visibility``.
    - The visibility is precisely ``["app"]``.

    Returns False otherwise.
    """
    meta = tool.meta
    if not meta:
        return False

    fastmcp = meta.get("fastmcp")
    if not isinstance(fastmcp, dict) or fastmcp.get("app") is None:
        return False

    ui = meta.get("ui")
    if not isinstance(ui, dict):
        return False

    visibility = ui.get("visibility")
    if not isinstance(visibility, list):
        return False

    return len(visibility) == 1 and visibility[0] == "app"


@asynccontextmanager
async def default_lifespan(_, /) -> AsyncIterator[Any]:
    """Default lifespan context manager that does nothing.

    Args:
        server: The server instance this lifespan is managing

    Returns:
        An empty dictionary as the lifespan result.
    """
    yield {}


def _lifespan_proxy[T](fastmcp_server: FastMCP[T], /) -> Callable[[LowLevelServer[T]], AbstractAsyncContextManager[T]]:
    # noinspection PyProtectedMember
    @asynccontextmanager
    async def wrap(_, /) -> AsyncIterator[T]:
        if fastmcp_server._lifespan is default_lifespan:
            yield {}  # ty:ignore[invalid-yield]
            return

        if not fastmcp_server._lifespan_result_set:
            raise RuntimeError(
                "FastMCP server has a lifespan defined but no lifespan result is set, which means the server's context manager was not entered. "
                " Are you running the server in a way that supports lifespans? If so, please file an issue at https://github.com/PrefectHQ/fastmcp/issues."
            )

        yield fastmcp_server._lifespan_result  # ty:ignore[invalid-yield]

    return wrap
