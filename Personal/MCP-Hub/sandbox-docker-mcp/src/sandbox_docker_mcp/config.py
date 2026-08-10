"""独立 MCP 服务的配置模型与环境变量解析。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

NetworkMode = Literal["bridge", "none"]
ENV_PREFIX = "SANDBOX_DOCKER_MCP_"


class SandboxSettings(BaseModel):
    """Docker 沙盒的安全策略。"""

    model_config = ConfigDict(extra="forbid")

    image: str | None = None
    network: NetworkMode = "bridge"
    memory_mb: int = Field(default=4096, ge=128)
    cpus: float = Field(default=2.0, gt=0)
    pids_limit: int = Field(default=256, ge=16)
    git_write: bool = False
    protect_paths: list[str] = Field(default_factory=lambda: [".env", ".env.*"])

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("sandbox image must not be empty")
        return value

    @field_validator("protect_paths")
    @classmethod
    def validate_protect_paths(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            pattern = value.strip().replace("\\", "/")
            parts = Path(pattern).parts
            if not pattern or pattern.startswith("/") or Path(pattern).is_absolute() or ".." in parts:
                raise ValueError(
                    "protected paths must be non-empty workspace-relative patterns"
                )
            normalized.append(pattern)
        return normalized


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def settings_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    base: SandboxSettings | None = None,
) -> SandboxSettings:
    """将通用环境变量覆盖到安全默认值或给定基础配置。"""

    env = environ if environ is not None else os.environ
    updates: dict[str, object] = {}
    mapping = {
        "IMAGE": ("image", str),
        "NETWORK": ("network", str),
        "MEMORY_MB": ("memory_mb", int),
        "CPUS": ("cpus", float),
        "PIDS_LIMIT": ("pids_limit", int),
    }
    for suffix, (field, converter) in mapping.items():
        raw = env.get(f"{ENV_PREFIX}{suffix}")
        if raw is not None and raw != "":
            updates[field] = converter(raw)
    raw_git_write = env.get(f"{ENV_PREFIX}GIT_WRITE")
    if raw_git_write is not None:
        updates["git_write"] = _parse_bool(raw_git_write, "GIT_WRITE")
    raw_protected = env.get(f"{ENV_PREFIX}PROTECT_PATHS")
    if raw_protected is not None:
        updates["protect_paths"] = [item for item in raw_protected.split(os.pathsep) if item]

    current = base or SandboxSettings()
    return SandboxSettings.model_validate(
        {**current.model_dump(mode="python"), **updates}
    )


__all__ = ["ENV_PREFIX", "NetworkMode", "SandboxSettings", "settings_from_env"]
