"""image.load_image_data_uri 的格式、魔数与大小校验。"""

import base64

import pytest

from vision_bridge_mcp.image import ImageError, load_image_data_uri

MAX = 1024 * 1024

# 各格式的最小合法文件头（sniff 只读前 16 字节）
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF = b"GIF89a" + b"\x00" * 16
WEBP = b"RIFF" + b"\x04\x00\x00\x00" + b"WEBP" + b"\x00" * 8
BMP = b"BM" + b"\x00" * 16


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


@pytest.mark.parametrize(
    "name,data,mime",
    [
        ("a.png", PNG, "image/png"),
        ("a.jpg", JPEG, "image/jpeg"),
        ("a.jpeg", JPEG, "image/jpeg"),
        ("a.gif", GIF, "image/gif"),
        ("a.webp", WEBP, "image/webp"),
        ("a.bmp", BMP, "image/bmp"),
    ],
)
def test_valid_images(tmp_path, name, data, mime):
    uri = load_image_data_uri(_write(tmp_path, name, data), MAX)
    prefix, payload = uri.split(",", 1)
    assert prefix == f"data:{mime};base64"
    assert base64.b64decode(payload) == data


def test_relative_path_rejected(tmp_path):
    with pytest.raises(ImageError, match="绝对路径"):
        load_image_data_uri("a.png", MAX)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(ImageError, match="不存在"):
        load_image_data_uri(str(tmp_path / "nope.png"), MAX)


def test_unsupported_extension_rejected(tmp_path):
    with pytest.raises(ImageError, match="扩展名"):
        load_image_data_uri(_write(tmp_path, "a.txt", PNG), MAX)


def test_empty_file_rejected(tmp_path):
    with pytest.raises(ImageError, match="为空"):
        load_image_data_uri(_write(tmp_path, "a.png", b""), MAX)


def test_magic_mismatch_rejected(tmp_path):
    # PNG 内容伪装成 .jpg
    with pytest.raises(ImageError, match="不符"):
        load_image_data_uri(_write(tmp_path, "a.jpg", PNG), MAX)


def test_unknown_magic_rejected(tmp_path):
    with pytest.raises(ImageError, match="魔数"):
        load_image_data_uri(_write(tmp_path, "a.png", b"not an image...."), MAX)


def test_size_limit_enforced(tmp_path):
    big = PNG + b"\x00" * 2048
    with pytest.raises(ImageError, match="超过上限"):
        load_image_data_uri(_write(tmp_path, "a.png", big), max_bytes=1024)


def test_webp_requires_webp_chunk(tmp_path):
    # RIFF 头但非 WEBP（如 WAV）
    fake = b"RIFF" + b"\x04\x00\x00\x00" + b"WAVE" + b"\x00" * 8
    with pytest.raises(ImageError, match="魔数"):
        load_image_data_uri(_write(tmp_path, "a.webp", fake), MAX)
