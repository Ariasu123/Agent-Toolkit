"""config.load_config 的环境变量解析与校验。"""

import pytest

from vision_bridge_mcp.config import (
    DEFAULT_MAX_IMAGE_BYTES,
    DEFAULT_TIMEOUT_S,
    ConfigError,
    load_config,
)

VALID_ENV = {
    "VISION_API_KEY": "sk-test",
    "VISION_BASE_URL": "https://example.com/v1",
    "VISION_MODEL_NAME": "glm-4v-flash",
}


def test_valid_env():
    config = load_config(VALID_ENV)
    assert config.api_key == "sk-test"
    assert config.base_url == "https://example.com/v1"
    assert config.model == "glm-4v-flash"
    assert config.max_image_bytes == DEFAULT_MAX_IMAGE_BYTES
    assert config.timeout_s == DEFAULT_TIMEOUT_S
    assert config.chat_completions_url == "https://example.com/v1/chat/completions"


def test_missing_api_key_raises():
    env = {k: v for k, v in VALID_ENV.items() if k != "VISION_API_KEY"}
    with pytest.raises(ConfigError, match="VISION_API_KEY"):
        load_config(env)


def test_empty_api_key_means_no_auth():
    config = load_config({**VALID_ENV, "VISION_API_KEY": ""})
    assert config.api_key is None


@pytest.mark.parametrize("missing", ["VISION_BASE_URL", "VISION_MODEL_NAME"])
def test_missing_required_vars_raise(missing):
    env = {k: v for k, v in VALID_ENV.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        load_config(env)


def test_base_url_must_be_http():
    with pytest.raises(ConfigError, match="http"):
        load_config({**VALID_ENV, "VISION_BASE_URL": "example.com/v1"})


@pytest.mark.parametrize(
    "raw",
    [
        "https://example.com/v1/",
        "https://example.com/v1/chat/completions",
    ],
)
def test_base_url_normalized(raw):
    config = load_config({**VALID_ENV, "VISION_BASE_URL": raw})
    assert config.chat_completions_url == "https://example.com/v1/chat/completions"


def test_optional_overrides():
    config = load_config(
        {**VALID_ENV, "VISION_MAX_IMAGE_BYTES": "1024", "VISION_TIMEOUT_S": "5.5"}
    )
    assert config.max_image_bytes == 1024
    assert config.timeout_s == 5.5


@pytest.mark.parametrize(
    "name,value",
    [
        ("VISION_MAX_IMAGE_BYTES", "abc"),
        ("VISION_MAX_IMAGE_BYTES", "-1"),
        ("VISION_TIMEOUT_S", "abc"),
        ("VISION_TIMEOUT_S", "0"),
    ],
)
def test_invalid_optional_values_raise(name, value):
    with pytest.raises(ConfigError, match=name):
        load_config({**VALID_ENV, name: value})
