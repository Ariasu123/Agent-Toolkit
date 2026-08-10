"""仅供测试使用的宿主 runtime stdio 服务。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sandbox_docker_mcp import SandboxCommandResult, SandboxSettings, WorkspaceGuard
from sandbox_docker_mcp.server import serve


class HostRuntime:
    backend = "host-test"

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.guard = WorkspaceGuard(self.workspace, [".env", ".env.*"])

    def describe(self):
        return {"backend": self.backend, "containerId": None}

    async def close(self):
        return None

    async def execute(self, command, *, timeout_s, abort, on_update, max_output_bytes):
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            command,
            cwd=self.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), timeout_s)
        except TimeoutError:
            proc.kill()
            output, _ = await proc.communicate()
            return SandboxCommandResult(
                output[-max_output_bytes:].decode("utf-8", "replace"),
                None,
                truncated=len(output) > max_output_bytes,
                timed_out=True,
            )
        return SandboxCommandResult(
            output[-max_output_bytes:].decode("utf-8", "replace"),
            proc.returncode,
            truncated=len(output) > max_output_bytes,
        )


asyncio.run(
    serve(
        settings=SandboxSettings(),
        runtime=HostRuntime(Path.cwd()),
    )
)
