"""命令行入口。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from .config import SandboxSettings, settings_from_env
from .server import serve


def run(
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="要挂载的工作区；默认使用当前目录"),
    ] = None,
    image: Annotated[
        str | None,
        typer.Option("--image", help="使用已有的自定义 Docker 镜像"),
    ] = None,
    network: Annotated[
        str | None,
        typer.Option("--network", help="Docker 网络模式：bridge 或 none"),
    ] = None,
    memory_mb: Annotated[
        int | None,
        typer.Option("--memory-mb", help="容器内存上限，单位 MB"),
    ] = None,
    cpus: Annotated[
        float | None,
        typer.Option("--cpus", help="容器 CPU 上限"),
    ] = None,
    pids_limit: Annotated[
        int | None,
        typer.Option("--pids-limit", help="容器进程数上限"),
    ] = None,
    git_write: Annotated[
        bool | None,
        typer.Option("--git-write/--no-git-write", help="允许或禁止写入 Git 元数据"),
    ] = None,
    protect_path: Annotated[
        list[str] | None,
        typer.Option("--protect-path", help="要遮蔽的工作区相对路径，可重复传入"),
    ] = None,
) -> None:
    """启动只通过 stdio 通信的 Docker 沙盒 MCP 服务。"""

    settings = settings_from_env()
    updates: dict[str, object] = {
        key: value
        for key, value in {
            "image": image,
            "network": network,
            "memory_mb": memory_mb,
            "cpus": cpus,
            "pids_limit": pids_limit,
            "git_write": git_write,
            "protect_paths": protect_path,
        }.items()
        if value is not None
    }
    settings = SandboxSettings.model_validate(
        {**settings.model_dump(mode="python"), **updates}
    )
    asyncio.run(serve(workspace=workspace, settings=settings))


def app() -> None:
    typer.run(run)


__all__ = ["app", "run"]
