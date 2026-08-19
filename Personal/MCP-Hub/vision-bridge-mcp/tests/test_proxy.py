"""proxy ASGI 端到端：透传、拦截转换、鉴权头透传、错误路径。"""

import base64
import json

import httpx
import pytest

from vision_bridge_mcp import proxy

PNG_URI = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
).decode()


class FakeUpstreamResponse:
    def __init__(self, status_code=200, chunks=(b'{"ok": true}',)):
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}
        self._chunks = chunks

    async def aiter_raw(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self):
        pass


class FakeUpstreamClient:
    """替代 proxy 里的 httpx.AsyncClient，记录请求并返回固定响应。"""

    last_request: httpx.Request | None = None

    def __init__(self, timeout=None):
        pass

    def build_request(self, method, url, headers=None, content=None):
        return httpx.Request(method, url, headers=headers, content=content)

    async def send(self, request, stream=False):
        FakeUpstreamClient.last_request = request
        return FakeUpstreamResponse()

    async def aclose(self):
        pass


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("VISION_API_KEY", "sk-vision")
    monkeypatch.setenv("VISION_BASE_URL", "https://vision.test/v1")
    monkeypatch.setenv("VISION_MODEL_NAME", "glm-4v-flash")
    monkeypatch.setenv("VISION_PROXY_UPSTREAM", "https://upstream.test/v1")


@pytest.fixture
def upstream(monkeypatch):
    FakeUpstreamClient.last_request = None
    monkeypatch.setattr(proxy, "_make_upstream_client", lambda: FakeUpstreamClient())
    return FakeUpstreamClient


@pytest.fixture
def fake_vision(monkeypatch):
    async def fake(config, data_uri, question):
        return "一张报错截图：NullPointerException 第 42 行。"

    monkeypatch.setattr(proxy, "_call_vision_api", fake)


async def _post(app_client, path, **kwargs):
    return await app_client.post(path, **kwargs)


async def test_chat_with_image_translated(env, upstream, fake_vision):
    transport = httpx.ASGITransport(app=proxy.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-v4-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这个报错什么意思？"},
                            {"type": "image_url", "image_url": {"url": PNG_URI}},
                        ],
                    }
                ],
            },
            headers={"Authorization": "Bearer sk-deepseek-secret"},
        )
    assert resp.status_code == 200

    req = upstream.last_request
    assert req.url == "https://upstream.test/v1/chat/completions"
    # 客户端的 DeepSeek key 原样透传
    assert req.headers["authorization"] == "Bearer sk-deepseek-secret"
    # 上游收到的是纯文本请求，图片已被描述替换
    body = json.loads(req.content)
    assert b"image_url" not in req.content
    content = body["messages"][0]["content"]
    assert all(part["type"] == "text" for part in content)
    assert "NullPointerException 第 42 行" in content[1]["text"]


async def test_chat_without_image_forwarded_verbatim(env, upstream):
    raw = json.dumps(
        {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "hi"}]}
    ).encode()
    transport = httpx.ASGITransport(app=proxy.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/v1/chat/completions",
            content=raw,
            headers={"Content-Type": "application/json"},
        )
    assert upstream.last_request.content == raw  # 零 JSON 往返改动


async def test_non_chat_path_passthrough(env, upstream):
    transport = httpx.ASGITransport(app=proxy.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/v1/models")
    assert resp.status_code == 200
    assert upstream.last_request.method == "GET"
    assert upstream.last_request.url == "https://upstream.test/v1/models"


async def test_missing_config_returns_500(monkeypatch):
    for name in ("VISION_API_KEY", "VISION_BASE_URL", "VISION_MODEL_NAME"):
        monkeypatch.delenv(name, raising=False)
    transport = httpx.ASGITransport(app=proxy.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/v1/models")
    assert resp.status_code == 500
    assert "未正确配置" in resp.json()["error"]


async def test_upstream_unreachable_returns_502(env, monkeypatch, fake_vision):
    class DeadClient(FakeUpstreamClient):
        async def send(self, request, stream=False):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(proxy, "_make_upstream_client", lambda: DeadClient())
    transport = httpx.ASGITransport(app=proxy.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/v1/models")
    assert resp.status_code == 502
    assert "不可达" in resp.json()["error"]
