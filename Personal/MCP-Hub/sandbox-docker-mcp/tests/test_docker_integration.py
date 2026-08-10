from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sandbox_docker_mcp import DockerSandboxRuntime, SandboxSettings


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


pytestmark = pytest.mark.skipif(
    not docker_available(), reason="Docker daemon is not available"
)


async def test_real_container_isolation_and_cleanup(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("outside-host-secret", encoding="utf-8")
    (workspace / ".env").write_text("TOKEN=workspace-secret\n", encoding="utf-8")
    git_dir = workspace / ".git"
    git_dir.mkdir()

    runtime = DockerSandboxRuntime(
        workspace,
        SandboxSettings(network="none", memory_mb=512, cpus=1, pids_limit=64),
    )
    await runtime.start()
    container_id = runtime.container_id
    try:
        result = await runtime.execute(
            "printf sandbox-write | tee generated.txt; "
            f"cat {outside}; cat .env; test ! -S /var/run/docker.sock",
            timeout_s=10,
            abort=None,
            on_update=None,
            max_output_bytes=20_000,
        )
        assert result.exit_code == 0
        assert (workspace / "generated.txt").read_text(encoding="utf-8") == "sandbox-write"
        assert "outside-host-secret" not in result.output
        assert "workspace-secret" not in result.output

        git_write = await runtime.execute(
            "touch .git/must-not-write",
            timeout_s=10,
            abort=None,
            on_update=None,
            max_output_bytes=1024,
        )
        assert git_write.exit_code != 0

        inspected = subprocess.run(
            ["docker", "inspect", container_id or ""],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert '"NetworkMode": "none"' in inspected
        assert '"Privileged": false' in inspected
        assert "docker.sock" not in inspected
    finally:
        await runtime.close()
    assert container_id
    absent = subprocess.run(
        ["docker", "inspect", container_id], capture_output=True, check=False
    )
    assert absent.returncode != 0
