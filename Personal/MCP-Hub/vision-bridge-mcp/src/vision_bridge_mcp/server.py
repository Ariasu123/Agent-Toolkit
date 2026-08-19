"""vision-bridge-mcp 的 MCP server 定义与 CLI 入口。

只暴露一个工具 view_image：读取本地图片，转发给 OpenAI 兼容的视觉模型，
返回文本描述。stdout 严格留给 MCP JSON-RPC，诊断信息只写 stderr。
"""

from __future__ import annotations

import logging
import sys

import httpx
from mcp.server.fastmcp import FastMCP

from vision_bridge_mcp.config import ConfigError, VisionConfig, load_config
from vision_bridge_mcp.image import ImageError, load_image_data_uri

logger = logging.getLogger("vision-bridge-mcp")

DEFAULT_QUESTION = "请详细描述这张图片的内容。"

mcp = FastMCP(
    "vision-bridge-mcp",
    instructions=(
        "为不具备视觉能力的模型提供识图能力。当用户粘贴/提供了本地图片路径，"
        "而当前模型无法直接看图时，调用 view_image 获取图片的文字描述后继续任务。"
    ),
)


def _build_payload(config: VisionConfig, data_uri: str, question: str) -> dict:
    return {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
    }


async def _call_vision_api(config: VisionConfig, data_uri: str, question: str) -> str:
    headers = {"Content-Type": "application/json"}
    if config.api_key is not None:
        headers["Authorization"] = f"Bearer {config.api_key}"

    try:
        async with httpx.AsyncClient(timeout=config.timeout_s) as client:
            response = await client.post(
                config.chat_completions_url,
                headers=headers,
                json=_build_payload(config, data_uri, question),
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        return f"错误：请求视觉模型超时（{config.timeout_s:g}s）。可通过 VISION_TIMEOUT_S 调整。"
    except httpx.HTTPStatusError as exc:
        # 只回传状态码与截断的响应摘要，绝不包含请求头/密钥
        body = exc.response.text[:500]
        return f"错误：视觉模型 API 返回 HTTP {exc.response.status_code}。响应摘要：{body}"
    except httpx.HTTPError as exc:
        return f"错误：无法连接视觉模型端点 {config.base_url}（{type(exc).__name__}）。"

    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        return f"错误：视觉模型响应格式不符合预期（{type(exc).__name__}）。原始响应摘要：{response.text[:500]}"


@mcp.tool()
async def view_image(image_path: str, question: str = "") -> str:
    """查看一张本地图片并返回文字描述，供不具备视觉能力的模型使用。

    Args:
        image_path: 本地图片的绝对路径（png/jpg/jpeg/gif/webp/bmp，≤20MB）。
                    CLI 中粘贴的图片通常会被客户端落盘为临时文件，直接传该路径即可。
        question:   想就图片提问的内容；留空则返回整体详细描述。
    """
    try:
        config = load_config()
    except ConfigError as exc:
        return f"错误：vision-bridge-mcp 未正确配置。{exc}"

    try:
        data_uri = load_image_data_uri(image_path, config.max_image_bytes)
    except ImageError as exc:
        return f"错误：{exc}"

    logger.info("view_image: %s (%d bytes base64)", image_path, len(data_uri))
    return await _call_vision_api(config, data_uri, question or DEFAULT_QUESTION)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,  # stdout 只用于 MCP JSON-RPC
        format="%(name)s: %(levelname)s: %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
