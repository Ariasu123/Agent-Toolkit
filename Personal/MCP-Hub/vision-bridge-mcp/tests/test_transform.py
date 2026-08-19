"""proxy 消息体转换：data URI 校验与 image_url → 文本替换。"""

import base64

import pytest

from vision_bridge_mcp import proxy
from vision_bridge_mcp.config import VisionConfig
from vision_bridge_mcp.image import ImageError

CONFIG = VisionConfig(
    api_key="sk-vision", base_url="https://vision.test/v1", model="glm-4v-flash"
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()


def _payload(*contents):
    return {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": c} for c in contents]}


def _image_part(url):
    return {"type": "image_url", "image_url": {"url": url}}


@pytest.fixture
def fake_vision(monkeypatch):
    calls = []

    async def fake(config, data_uri, question):
        calls.append(data_uri)
        return "一只猫坐在键盘上。"

    monkeypatch.setattr(proxy, "_call_vision_api", fake)
    return calls


async def test_image_replaced_with_text(fake_vision):
    payload, n = await proxy.transform_payload(
        _payload([{"type": "text", "text": "图里有什么？"}, _image_part(PNG_URI)]), CONFIG
    )
    assert n == 1
    content = payload["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "图里有什么？"}
    assert content[1]["type"] == "text"
    assert "[图片1的内容]" in content[1]["text"]
    assert "一只猫坐在键盘上。" in content[1]["text"]
    # 原样 data URI 被送去视觉模型
    assert fake_vision == [PNG_URI]


async def test_text_only_message_untouched(fake_vision):
    original = _payload("你好")
    payload, n = await proxy.transform_payload(original, CONFIG)
    assert n == 0
    assert payload["messages"][0]["content"] == "你好"
    assert fake_vision == []


async def test_multiple_images_numbered(fake_vision):
    payload, n = await proxy.transform_payload(
        _payload([_image_part(PNG_URI)], [_image_part(PNG_URI)]), CONFIG
    )
    assert n == 2
    first = payload["messages"][0]["content"][0]["text"]
    second = payload["messages"][1]["content"][0]["text"]
    assert "[图片1的内容]" in first
    assert "[图片2的内容]" in second


async def test_corrupt_base64_degrades_to_note(fake_vision):
    payload, n = await proxy.transform_payload(
        _payload([_image_part("data:image/png;base64,!!!not-base64!!!")]), CONFIG
    )
    assert n == 1
    text = payload["messages"][0]["content"][0]["text"]
    assert "无法处理" in text
    assert fake_vision == []  # 不合法图片不外发


async def test_http_url_image_degrades_to_note(fake_vision):
    payload, _ = await proxy.transform_payload(
        _payload([_image_part("https://example.com/a.png")]), CONFIG
    )
    text = payload["messages"][0]["content"][0]["text"]
    assert "无法处理" in text
    assert fake_vision == []


async def test_mime_mismatch_rejected(fake_vision):
    uri = "data:image/jpeg;base64," + base64.b64encode(PNG).decode()  # 声明 jpeg 实为 png
    payload, _ = await proxy.transform_payload(_payload([_image_part(uri)]), CONFIG)
    assert "不符" in payload["messages"][0]["content"][0]["text"]
    assert fake_vision == []


async def test_vision_failure_degrades_to_note(monkeypatch):
    async def failing(config, data_uri, question):
        return "错误：视觉模型 API 返回 HTTP 429。响应摘要：overload"

    monkeypatch.setattr(proxy, "_call_vision_api", failing)
    payload, _ = await proxy.transform_payload(_payload([_image_part(PNG_URI)]), CONFIG)
    text = payload["messages"][0]["content"][0]["text"]
    assert "识别暂时不可用" in text  # 不阻断对话


def test_extract_data_uri_oversize():
    big = PNG + b"\x00" * 100
    uri = "data:image/png;base64," + base64.b64encode(big).decode()
    with pytest.raises(ImageError, match="超过上限"):
        proxy._extract_data_uri(uri, max_bytes=32)
