from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from sandbox_docker_mcp import (
    SandboxSettings,
    WorkspaceAccessError,
    WorkspaceGuard,
    settings_from_env,
)


def test_settings_secure_defaults_and_environment_precedence() -> None:
    defaults = SandboxSettings()
    assert defaults.network == "bridge"
    assert defaults.memory_mb == 4096
    assert defaults.cpus == 2.0
    assert defaults.pids_limit == 256
    assert defaults.git_write is False
    assert defaults.protect_paths == [".env", ".env.*"]

    settings = settings_from_env(
        {
            "SANDBOX_DOCKER_MCP_IMAGE": "example:sandbox",
            "SANDBOX_DOCKER_MCP_NETWORK": "none",
            "SANDBOX_DOCKER_MCP_MEMORY_MB": "512",
            "SANDBOX_DOCKER_MCP_CPUS": "1.5",
            "SANDBOX_DOCKER_MCP_PIDS_LIMIT": "64",
            "SANDBOX_DOCKER_MCP_GIT_WRITE": "true",
            "SANDBOX_DOCKER_MCP_PROTECT_PATHS": f".env{os.pathsep}secrets/*.json",
        }
    )
    assert settings == SandboxSettings(
        image="example:sandbox",
        network="none",
        memory_mb=512,
        cpus=1.5,
        pids_limit=64,
        git_write=True,
        protect_paths=[".env", "secrets/*.json"],
    )


@pytest.mark.parametrize("pattern", ["", "../outside", "/absolute"])
def test_settings_reject_unsafe_protected_patterns(pattern: str) -> None:
    with pytest.raises(ValidationError, match="protected paths"):
        SandboxSettings(protect_paths=[pattern])


def test_guard_allows_workspace_paths_and_rejects_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    guard = WorkspaceGuard(workspace, [".env", ".env.*"])
    assert guard.resolve("src/main.py") == workspace / "src" / "main.py"
    with pytest.raises(WorkspaceAccessError, match="outside workspace"):
        guard.resolve("../outside.txt")
    with pytest.raises(WorkspaceAccessError, match="protected"):
        guard.resolve("nested/.env.local")


def test_guard_rejects_existing_and_future_symlink_escapes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "link").symlink_to(outside, target_is_directory=True)
    guard = WorkspaceGuard(workspace)
    with pytest.raises(WorkspaceAccessError, match="outside workspace"):
        guard.resolve("link/existing.txt")
    with pytest.raises(WorkspaceAccessError, match="outside workspace"):
        guard.resolve("link/future.txt")


def test_guard_file_open_resists_parent_symlink_swap(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    parent = workspace / "parent"
    parent.mkdir()
    target = outside / "target.txt"
    target.write_text("safe", encoding="utf-8")
    guard = WorkspaceGuard(workspace)
    guard.resolve("parent/target.txt", "write")
    parent.rename(workspace / "old-parent")
    parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises((WorkspaceAccessError, OSError)):
        guard.open_file("parent/target.txt", "write", os.O_WRONLY | os.O_CREAT)
    assert target.read_text(encoding="utf-8") == "safe"
