"""server 模块：请求体结构、鉴权头、错误路径与工具端到端行为（mock HTTP）。"""

import json

import httpx
import pytest

from vision_bridge_mcp import server
from vision_bridge_mcp.config import VisionConfig

CONFIG = VisionConfig(
    api_key="sk-test",
    base_url="https://example.com/v1",
    model="glm-4v-flash",
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.text = json.dumps(payload)

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeClient:
    """记录最后一次请求并返回固定响应，替代 httpx.AsyncClient。"""

    last_request: dict | None = None

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        FakeClient.last_request = {"url": url, "headers": headers, "json": json}
        return FakeResponse({"choices": [{"message": {"content": "图中是一只猫。"}}]})


@pytest.fixture
def fake_client(monkeypatch):
    FakeClient.last_request = None
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeClient)
    return FakeClient


async def test_request_payload_structure(fake_client):
    result = await server._call_vision_api(CONFIG, "data:image/png;base64,AAAA", "描述一下")
    assert result == "图中是一只猫。"

    req = fake_client.last_request
    assert req["url"] == "https://example.com/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer sk-test"

    payload = req["json"]
    assert payload["model"] == "glm-4v-flash"
    content = payload["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "描述一下"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/png;base64,AAAA"


async def test_no_auth_header_when_keyless(fake_client):
    config = VisionConfig(api_key=None, base_url="http://localhost:11434/v1", model="qwen3-vl:4b")
    await server._call_vision_api(config, "data:image/png;base64,AAAA", "q")
    assert "Authorization" not in fake_client.last_request["headers"]


async def test_http_error_sanitized(monkeypatch):
    class ErrorClient(FakeClient):
        async def post(self, url, headers=None, json=None):
            request = httpx.Request("POST", url)
            response = httpx.Response(401, text='{"error": "invalid key"}', request=request)
            raise httpx.HTTPStatusError("err", request=request, response=response)

    monkeypatch.setattr(server.httpx, "AsyncClient", ErrorClient)
    result = await server._call_vision_api(CONFIG, "data:image/png;base64,AAAA", "q")
    assert "HTTP 401" in result
    assert "sk-test" not in result


async def test_timeout_error(monkeypatch):
    class TimeoutClient(FakeClient):
        async def post(self, url, headers=None, json=None):
            raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(server.httpx, "AsyncClient", TimeoutClient)
    result = await server._call_vision_api(CONFIG, "data:image/png;base64,AAAA", "q")
    assert "超时" in result


async def test_view_image_missing_config(monkeypatch):
    for name in ("VISION_API_KEY", "VISION_BASE_URL", "VISION_MODEL_NAME"):
        monkeypatch.delenv(name, raising=False)
    result = await server.view_image("/tmp/whatever.png")
    assert "未正确配置" in result


async def test_view_image_end_to_end(monkeypatch, tmp_path, fake_client):
    monkeypatch.setenv("VISION_API_KEY", "sk-test")
    monkeypatch.setenv("VISION_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("VISION_MODEL_NAME", "glm-4v-flash")

    image = tmp_path / "shot.png"
    image.write_bytes(PNG)

    result = await server.view_image(str(image))
    assert result == "图中是一只猫。"
    # 默认问题被使用
    content = fake_client.last_request["json"]["messages"][0]["content"]
    assert content[0]["text"] == server.DEFAULT_QUESTION


async def test_view_image_rejects_non_image(tmp_path, fake_client):
    bad = tmp_path / "secret.png"  # 扩展名合法但内容不是 PNG
    bad.write_bytes(b"AKIAIOSFODNN7EXAMPLE")
    result = await server.view_image(str(bad))
    assert "错误" in result
    assert fake_client.last_request is None  # 不应发起任何外发请求
