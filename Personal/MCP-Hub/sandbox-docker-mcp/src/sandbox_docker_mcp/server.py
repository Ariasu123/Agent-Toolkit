"""stdio MCP server。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .config import SandboxSettings
from .runtime import DockerSandboxRuntime
from .tools import Runtime, build_tools


def create_server(runtime: Runtime) -> Server:
    tools = build_tools(runtime)
    server: Server = Server("sandbox-docker-mcp@0.1.0")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.parameters,
            )
            for tool in tools.values()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        tool = tools.get(name)
        if tool is None:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )
        try:
            args = tool.validate(arguments)
            result = await tool.execute(args)  # type: ignore[arg-type]
        except ValueError as exc:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=str(exc))],
                isError=True,
            )
        except Exception as exc:
            return types.CallToolResult(
                content=[
                    types.TextContent(type="text", text=f"{type(exc).__name__}: {exc}")
                ],
                isError=True,
            )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.text)],
            isError=result.is_error,
        )

    return server


async def serve(
    workspace: Path | None = None,
    settings: SandboxSettings | None = None,
    *,
    runtime: Runtime | None = None,
) -> None:
    """启动 stdio MCP；runtime 参数只用于嵌入式适配和测试。"""

    owned_runtime = runtime is None
    active_runtime = runtime or DockerSandboxRuntime(
        workspace or Path.cwd(), settings or SandboxSettings()
    )
    server = create_server(active_runtime)
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        try:
            await asyncio.wait_for(active_runtime.close(), timeout=10)
        except Exception:
            label = "owned" if owned_runtime else "injected"
            print(
                f"sandbox-docker-mcp: failed to clean up {label} runtime",
                file=sys.stderr,
            )


__all__ = ["create_server", "serve"]
