from __future__ import annotations

import os
from pathlib import Path

import pytest

from sandbox_docker_mcp import DockerSandboxRuntime, SandboxSettings
from sandbox_docker_mcp.runtime import default_dockerfile


def test_default_dockerfile_has_toolchain_and_no_daemon() -> None:
    dockerfile = default_dockerfile()
    for token in ("python3.12", "uv", "bash", "git", "curl", "ripgrep"):
        assert token in dockerfile
    assert "docker" not in dockerfile.lower()


def test_run_args_have_security_limits_and_no_escape_hatches(tmp_path: Path) -> None:
    runtime = DockerSandboxRuntime(
        tmp_path,
        SandboxSettings(network="none", memory_mb=768, cpus=1.5, pids_limit=64),
    )
    args = runtime.build_run_args()
    joined = " ".join(args)
    assert args[:2] == ["run", "--detach"]
    assert ["--user", f"{os.getuid()}:{os.getgid()}"] == args[
        args.index("--user") : args.index("--user") + 2
    ]
    assert ["--network", "none"] == args[
        args.index("--network") : args.index("--network") + 2
    ]
    assert ["--memory", "768m"] == args[
        args.index("--memory") : args.index("--memory") + 2
    ]
    assert ["--cap-drop", "ALL"] == args[
        args.index("--cap-drop") : args.index("--cap-drop") + 2
    ]
    assert "no-new-privileges:true" in args
    assert "--privileged" not in args
    assert "--device" not in args
    assert "--publish" not in args
    assert "docker.sock" not in joined
    assert "io.sandbox-docker-mcp.managed=true" in args


def test_git_is_read_only_and_custom_opt_in_is_writable(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    protected = DockerSandboxRuntime(tmp_path, SandboxSettings()).build_run_args()
    mount = f"type=bind,src={git_dir},dst={git_dir}"
    assert f"{mount},readonly" in protected
    writable = DockerSandboxRuntime(
        tmp_path, SandboxSettings(git_write=True)
    ).build_run_args()
    assert mount in writable
    assert f"{mount},readonly" not in writable


def test_worktree_validation_rejects_crafted_host_mount(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    arbitrary = tmp_path / "private"
    workspace.mkdir()
    arbitrary.mkdir()
    (workspace / ".git").write_text(f"gitdir: {arbitrary}\n", encoding="utf-8")
    (arbitrary / "commondir").write_text(".\n", encoding="utf-8")
    (arbitrary / "gitdir").write_text("/other/.git\n", encoding="utf-8")
    runtime = DockerSandboxRuntime(workspace, SandboxSettings())
    assert runtime._git_mounts() == [workspace / ".git"]
    assert str(arbitrary) not in " ".join(runtime.build_run_args())


def test_secret_files_are_masked(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("TOKEN=secret\n", encoding="utf-8")
    args = DockerSandboxRuntime(tmp_path, SandboxSettings()).build_run_args()
    assert f"type=bind,src=/dev/null,dst={env},readonly" in args


async def test_orphan_cleanup_handles_new_and_legacy_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = DockerSandboxRuntime(tmp_path, SandboxSettings())
    calls = []

    async def fake_docker(*args, check=True):
        calls.append((args, check))
        if args[:2] == ("ps", "-a"):
            return "dead-container\t100\nlive-container\t200\n"
        return "__SANDBOX_DOCKER_MCP_EXIT_0__\n"

    monkeypatch.setattr(runtime, "_run_docker", fake_docker)
    monkeypatch.setattr(runtime, "_pid_is_alive", lambda pid: pid == 200)
    await runtime._cleanup_orphans()
    filters = [call[0][3] for call in calls if call[0][:2] == ("ps", "-a")]
    assert "label=io.sandbox-docker-mcp.managed=true" in filters
    assert "label=io.pion.managed=true" in filters
    assert any(call[0][:3] == ("rm", "-f", "dead-container") for call in calls)
    assert not any(call[0][:3] == ("rm", "-f", "live-container") for call in calls)
