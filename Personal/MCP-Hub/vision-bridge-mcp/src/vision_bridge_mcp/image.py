"""本地图片加载与安全校验。

防御目标：LLM 被注入后利用本工具读取宿主任意文件。
因此采用扩展名白名单 + 魔数嗅探双重校验，并限制文件大小，
只有"确实是图片"的文件才会被读出并编码外发。
"""

from __future__ import annotations

import base64
from pathlib import Path

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


class ImageError(Exception):
    """图片路径、格式或大小不合法。"""


def _sniff_mime(header: bytes) -> str | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"BM"):
        return "image/bmp"
    return None

_EXT_EXPECTED_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def validate_image_bytes(data: bytes, max_bytes: int) -> str:
    """校验图片字节内容（魔数 + 大小），返回嗅探出的 MIME。失败抛 ImageError。"""
    if not data:
        raise ImageError("图片内容为空")
    if len(data) > max_bytes:
        raise ImageError(
            f"图片大小 {len(data)} 字节超过上限 {max_bytes} 字节，"
            "可通过 VISION_MAX_IMAGE_BYTES 调整"
        )
    mime = _sniff_mime(data[:16])
    if mime is None:
        raise ImageError("内容不是受支持的图片格式（魔数校验失败）")
    return mime


def load_image_data_uri(image_path: str, max_bytes: int) -> str:
    """读取本地图片并返回 base64 data URI。任何校验失败都抛 ImageError。"""
    path = Path(image_path).expanduser()

    if not path.is_absolute():
        raise ImageError(f"image_path 必须是绝对路径，当前为 {image_path!r}")
    if not path.exists():
        raise ImageError(f"文件不存在：{path}")
    if not path.is_file():
        raise ImageError(f"不是普通文件：{path}")

    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageError(
            f"不支持的扩展名 {ext!r}，仅接受：{', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    size = path.stat().st_size
    if size == 0:
        raise ImageError(f"文件为空：{path}")
    if size > max_bytes:
        raise ImageError(
            f"图片大小 {size} 字节超过上限 {max_bytes} 字节，"
            "可通过 VISION_MAX_IMAGE_BYTES 调整"
        )

    data = path.read_bytes()
    mime = _sniff_mime(data[:16])
    if mime is None:
        raise ImageError(f"文件头不是受支持的图片格式（魔数校验失败）：{path}")
    if mime != _EXT_EXPECTED_MIME[ext]:
        raise ImageError(
            f"扩展名 {ext} 与实际格式 {mime} 不符（疑似伪装文件）：{path}"
        )

    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
