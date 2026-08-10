from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sandbox_docker_mcp import SandboxCommandResult, SandboxSettings, WorkspaceGuard
from sandbox_docker_mcp.tools import BashArgs, BashTool, build_tools


class FakeRuntime:
    backend = "docker"

    def __init__(self, workspace: Path, result: SandboxCommandResult | None = None) -> None:
        settings = SandboxSettings()
        self.guard = WorkspaceGuard(workspace, settings.protect_paths, [".git"])
        self.result = result or SandboxCommandResult("ok\n", 0)

    def describe(self):
        return {"backend": "docker", "containerId": "123456789abc"}

    async def close(self):
        return None

    async def execute(self, command, *, timeout_s, abort, on_update, max_output_bytes):
        return self.result


async def test_tools_enforce_workspace_and_roundtrip(tmp_path: Path) -> None:
    tools = build_tools(FakeRuntime(tmp_path))
    write = await tools["write"].execute(
        tools["write"].validate({"path": "note.txt", "content": "hello\n"})
    )
    assert "Successfully wrote" in write.text
    read = await tools["read"].execute(tools["read"].validate({"path": "note.txt"}))
    assert "hello" in read.text
    edit = await tools["edit"].execute(
        tools["edit"].validate(
            {"path": "note.txt", "old_string": "hello", "new_string": "mcp"}
        )
    )
    assert "1 occurrence" in edit.text
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "mcp\n"

    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    denied = await tools["read"].execute(
        tools["read"].validate({"path": str(outside)})
    )
    assert "denied" in denied.text
    assert denied.details and denied.details["denied"] is True


async def test_bash_nonzero_timeout_and_abort_contract(tmp_path: Path) -> None:
    failed = BashTool(
        FakeRuntime(tmp_path, SandboxCommandResult("oops\n", 7))
    )
    result = await failed.execute(BashArgs(command="false"))
    assert "[exit code 7]" in result.text
    assert result.details and result.details["exitCode"] == 7

    timed_out = BashTool(
        FakeRuntime(tmp_path, SandboxCommandResult("early\n", None, timed_out=True))
    )
    result = await timed_out.execute(BashArgs(command="sleep 30", timeout_s=1))
    assert "timed out" in result.text

    aborted = BashTool(
        FakeRuntime(tmp_path, SandboxCommandResult("early\n", None, aborted=True))
    )
    result = await aborted.execute(BashArgs(command="sleep 30"))
    assert "aborted" in result.text.lower()


@asynccontextmanager
async def sandbox_session(workspace: Path):
    script = Path(__file__).parent / "fixtures" / "host_server.py"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(script)],
        env=dict(os.environ),
        cwd=str(workspace),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def text_of(result) -> str:
    return "".join(
        block.text for block in result.content if getattr(block, "type", "") == "text"
    )


async def test_stdio_mcp_lists_tools_and_handles_calls(tmp_path: Path) -> None:
    async with sandbox_session(tmp_path) as session:
        listed = await session.list_tools()
        assert {"bash", "read", "write", "edit"} == {
            tool.name for tool in listed.tools
        }
        bash = await session.call_tool("bash", {"command": "echo hello-mcp"})
        assert not bash.isError
        assert "hello-mcp" in text_of(bash)
        write = await session.call_tool(
            "write", {"path": "note.txt", "content": "from-mcp\n"}
        )
        assert not write.isError
        read = await session.call_tool("read", {"path": "note.txt"})
        assert "from-mcp" in text_of(read)
        invalid = await session.call_tool("bash", {})
        assert invalid.isError
        unknown = await session.call_tool("unknown", {})
        assert unknown.isError
