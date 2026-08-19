"""环境变量配置读取与校验。

配置全部来自环境变量，优先级只有一个来源，不做配置文件：
- VISION_API_KEY        必填；置为空字符串表示本地无鉴权端点（如 Ollama），不发送 Authorization 头
- VISION_BASE_URL       必填，OpenAI 兼容端点，如 https://open.bigmodel.cn/api/paas/v4
- VISION_MODEL_NAME     必填，视觉模型 ID
- VISION_MAX_IMAGE_BYTES 可选，默认 20971520 (20 MB)
- VISION_TIMEOUT_S      可选，默认 60
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MAX_IMAGE_BYTES = 20 * 1024 * 1024
DEFAULT_TIMEOUT_S = 60.0


class ConfigError(Exception):
    """环境变量缺失或非法。"""


@dataclass(frozen=True)
class VisionConfig:
    api_key: str | None  # None 表示不发送 Authorization 头
    base_url: str  # 已去掉尾部 "/" 和可选的 "/chat/completions"
    model: str
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES
    timeout_s: float = DEFAULT_TIMEOUT_S

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url}/chat/completions"


def _require(env: dict[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise ConfigError(
            f"缺少环境变量 {name}。请在 MCP 客户端配置的 env 字段中设置；"
            "参考 README 的后端示例表。"
        )
    return value.strip()


def _parse_int(env: dict[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"环境变量 {name} 必须是整数，当前为 {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"环境变量 {name} 必须为正整数，当前为 {value}")
    return value


def _parse_float(env: dict[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"环境变量 {name} 必须是数字，当前为 {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"环境变量 {name} 必须为正数，当前为 {value}")
    return value


def load_config(env: dict[str, str] | None = None) -> VisionConfig:
    env = os.environ if env is None else env

    raw_key = env.get("VISION_API_KEY")
    if raw_key is None:
        raise ConfigError(
            "缺少环境变量 VISION_API_KEY。如使用本地无鉴权端点（如 Ollama），"
            "请显式将其置为空字符串以跳过 Authorization 头。"
        )
    api_key = raw_key.strip() or None

    base_url = _require(env, "VISION_BASE_URL")
    base_url = base_url.removesuffix("/").removesuffix("/chat/completions")
    if not base_url.startswith(("http://", "https://")):
        raise ConfigError(
            f"VISION_BASE_URL 必须是 http(s) URL，当前为 {base_url!r}"
        )

    model = _require(env, "VISION_MODEL_NAME")

    return VisionConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_image_bytes=_parse_int(
            env, "VISION_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES
        ),
        timeout_s=_parse_float(env, "VISION_TIMEOUT_S", DEFAULT_TIMEOUT_S),
    )
