"""vision-bridge-proxy：本机 HTTP 代理，让纯文本模型会话获得原生贴图体验。

原理：把客户端（kimi-code 等）的 provider base_url 指向本代理。绝大多数请求
原样透传给上游（如 DeepSeek）；仅当 chat/completions 请求的消息中含图片
（image_url data URI）时，先调用 OpenAI 兼容视觉模型把图片翻译成文字描述，
替换后再转发——上游收到的永远是纯文本请求。

安全边界：只监听 127.0.0.1；客户端的 Authorization 头原样透传给上游，
代理本身只持有视觉模型的 key，且日志不记录任何凭据与图片内容。
"""

from __future__ import annotations

import base64
import binascii
import copy
import json
import logging
import os
import sys

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from vision_bridge_mcp.config import ConfigError, VisionConfig, load_config
from vision_bridge_mcp.image import ImageError, validate_image_bytes
from vision_bridge_mcp.server import _call_vision_api

logger = logging.getLogger("vision-bridge-proxy")

DEFAULT_UPSTREAM = "https://api.deepseek.com/v1"
DEFAULT_PORT = 18990
HOST = "127.0.0.1"

IMAGE_QUESTION = (
    "请描述这张图片的内容，供一个看不到图片的纯文本模型理解。"
    "如果图片中包含文字、代码或报错信息，请完整转录。"
)

# 请求侧丢弃 host/content-length（由 httpx 重建）与 accept-encoding（要求上游返回
# 未压缩字节流，便于原样管道）；响应侧丢弃逐跳头。
_REQUEST_DROP_HEADERS = {"host", "content-length", "accept-encoding", "connection"}
_RESPONSE_DROP_HEADERS = {"content-length", "transfer-encoding", "connection"}


def _extract_data_uri(url: str, max_bytes: int) -> str:
    """校验 data URI 并原样返回；任何不合法都抛 ImageError。"""
    if not url.startswith("data:"):
        raise ImageError("仅支持 data URI 形式的内联图片")
    header, _, payload = url[5:].partition(",")
    declared = header.split(";")[0]
    try:
        data = base64.b64decode(payload)
    except (binascii.Error, ValueError) as exc:
        raise ImageError("图片 base64 解码失败") from exc
    sniffed = validate_image_bytes(data, max_bytes)
    if declared and declared != sniffed:
        raise ImageError(f"声明的格式 {declared} 与实际 {sniffed} 不符")
    return url


async def _translate_image(url: str, config: VisionConfig, index: int) -> str:
    """把一张图片翻译成文本块。失败降级为说明文字，绝不抛出阻断对话。"""
    try:
        data_uri = _extract_data_uri(url, config.max_image_bytes)
    except ImageError as exc:
        logger.warning("image %d rejected: %s", index, exc)
        return f"[图片{index}：无法处理（{exc}）]"
    logger.info("image %d: translating via %s", index, config.model)
    result = await _call_vision_api(config, data_uri, IMAGE_QUESTION)
    if result.startswith("错误"):
        logger.warning("image %d vision call failed: %s", index, result[:120])
        return f"[图片{index}：识别暂时不可用（{result[:100]}）]"
    return f"[图片{index}的内容]\n{result}"


async def transform_payload(payload: dict, config: VisionConfig) -> tuple[dict, int]:
    """把消息中的 image_url 部分替换为文本描述。返回 (新 payload, 图片数)。"""
    payload = copy.deepcopy(payload)
    index = 0
    for message in payload.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        new_content = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                index += 1
                url = (part.get("image_url") or {}).get("url", "")
                new_content.append(
                    {"type": "text", "text": await _translate_image(url, config, index)}
                )
            else:
                new_content.append(part)
        message["content"] = new_content
    return payload, index


def _make_upstream_client() -> httpx.AsyncClient:
    """上游客户端工厂，单独抽出便于测试替换。"""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
    )


async def _forward(request: Request, body: bytes, config: VisionConfig) -> Response:
    upstream = os.environ.get("VISION_PROXY_UPSTREAM", DEFAULT_UPSTREAM).rstrip("/")
    path = request.url.path
    if path.startswith("/v1/"):
        path = path[3:]  # 上游 base 自带 /v1，去掉重复段
    url = upstream + path
    if request.url.query:
        url += "?" + request.url.query

    if request.method == "POST" and path.endswith("/chat/completions") and b"image_url" in body:
        try:
            payload, n = await transform_payload(json.loads(body), config)
            if n:
                logger.info("translated %d image(s) for chat/completions", n)
                body = json.dumps(payload).encode("utf-8")
        except Exception:
            logger.exception("transform failed, forwarding original body")

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _REQUEST_DROP_HEADERS
    }

    client = _make_upstream_client()
    try:
        upstream_req = client.build_request(
            request.method, url, headers=headers, content=body
        )
        upstream_resp = await client.send(upstream_req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.error("upstream unreachable: %s", type(exc).__name__)
        return JSONResponse(
            {"error": f"上游 {upstream} 不可达：{type(exc).__name__}"}, status_code=502
        )

    async def stream():
        try:
            async for chunk in upstream_resp.aiter_raw():
                yield chunk
        finally:
            await upstream_resp.aclose()
            await client.aclose()

    resp_headers = {
        k: v
        for k, v in upstream_resp.headers.items()
        if k.lower() not in _RESPONSE_DROP_HEADERS
    }
    return StreamingResponse(
        stream(), status_code=upstream_resp.status_code, headers=resp_headers
    )


async def handle(request: Request) -> Response:
    try:
        config = load_config()
    except ConfigError as exc:
        return JSONResponse(
            {"error": f"vision-bridge-proxy 未正确配置：{exc}"}, status_code=500
        )
    return await _forward(request, await request.body(), config)


app = Starlette(
    routes=[
        Route(
            "/{path:path}",
            handle,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        )
    ]
)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(name)s: %(levelname)s: %(message)s",
    )
    try:
        config = load_config()  # 启动即校验，失败立刻可见
    except ConfigError as exc:
        print(f"vision-bridge-proxy 启动失败：{exc}", file=sys.stderr)
        sys.exit(1)
    port = int(os.environ.get("VISION_PROXY_PORT", DEFAULT_PORT))
    print(
        f"vision-bridge-proxy 监听 http://{HOST}:{port}，上游 {os.environ.get('VISION_PROXY_UPSTREAM', DEFAULT_UPSTREAM)}，视觉模型 {config.model}",
        file=sys.stderr,
    )
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
