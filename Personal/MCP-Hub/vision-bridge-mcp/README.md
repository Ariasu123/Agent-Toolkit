# vision-bridge-mcp

`vision-bridge-mcp` 是一个独立的 stdio MCP Server，为不具备视觉能力的模型
（如 DeepSeek 的 `deepseek-chat` / `deepseek-reasoner`）挂载识图能力：

```text
用户贴图 → CLI 客户端落盘为临时文件 → 文本模型拿到路径
        → 调用 view_image 工具 → vision-bridge-mcp 读取图片并 base64 编码
        → 转发给 OpenAI 兼容的视觉模型 → 返回文字描述 → 文本模型继续任务
```

视觉理解完全交给外部视觉模型完成，本地不做任何图像处理依赖。

## 工具

| 工具 | 说明 |
| --- | --- |
| `view_image(image_path, question?)` | 读取本地图片（png/jpg/jpeg/gif/webp/bmp），连同可选问题一起发给视觉模型，返回文字回答。`question` 留空时返回整体详细描述 |

在 CLI 中粘贴图片时，客户端通常会把图片落盘为临时文件并把路径提供给模型，
直接将该路径传给 `view_image` 即可。

## 环境要求

- macOS 或 Linux
- Python 3.11 及以上
- 推荐使用 [uv](https://docs.astral.sh/uv/)
- 一个 OpenAI 兼容的视觉模型端点（需自备 API key，或使用本地无鉴权端点）

## 安装

从 Agent-Toolkit 仓库安装：

```sh
uv tool install \
  'vision-bridge-mcp @ git+https://github.com/Ariasu123/Agent-Toolkit.git#subdirectory=Personal/MCP-Hub/vision-bridge-mcp'
```

源码开发：

```sh
git clone https://github.com/Ariasu123/Agent-Toolkit.git
cd Agent-Toolkit/Personal/MCP-Hub/vision-bridge-mcp
uv sync --group dev
uv run pytest -q
```

## 配置

全部通过环境变量配置，在 MCP 客户端配置的 `env` 字段中传入：

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `VISION_API_KEY` | 是 | 无 | 视觉端点的 API key；本地无鉴权端点（如 Ollama）显式置为空字符串，则不发送 Authorization 头 |
| `VISION_BASE_URL` | 是 | 无 | OpenAI 兼容端点地址（结尾的 `/` 或 `/chat/completions` 会被自动归一化） |
| `VISION_MODEL_NAME` | 是 | 无 | 视觉模型 ID |
| `VISION_MAX_IMAGE_BYTES` | 否 | `20971520`（20 MB） | 单张图片大小上限 |
| `VISION_TIMEOUT_S` | 否 | `60` | API 请求超时（秒） |

### 后端示例

以下仅为常见后端的配置示例，本项目不绑定任何一家：

| 后端 | `VISION_BASE_URL` | `VISION_MODEL_NAME` 示例 |
| --- | --- | --- |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4v-flash`（有免费额度） |
| 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-vl-max` / `qwen3-vl-flash` |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-VL-32B-Instruct` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen3-vl:4b`（`VISION_API_KEY` 置空） |

## MCP 客户端配置

安装后直接使用命令：

```json
{
  "mcpServers": {
    "vision-bridge": {
      "command": "vision-bridge-mcp",
      "env": {
        "VISION_API_KEY": "你的-key",
        "VISION_BASE_URL": "https://open.bigmodel.cn/api/paas/v4",
        "VISION_MODEL_NAME": "glm-4v-flash"
      }
    }
  }
}
```

不全局安装也可以让客户端通过 `uvx` 启动：

```json
{
  "mcpServers": {
    "vision-bridge": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Ariasu123/Agent-Toolkit.git#subdirectory=Personal/MCP-Hub/vision-bridge-mcp",
        "vision-bridge-mcp"
      ],
      "env": {
        "VISION_API_KEY": "你的-key",
        "VISION_BASE_URL": "https://open.bigmodel.cn/api/paas/v4",
        "VISION_MODEL_NAME": "glm-4v-flash"
      }
    }
  }
}
```

任何支持 stdio MCP 的客户端（Kimi Code、Claude Code、Codex、Cursor 等）
都可以使用同一组 `command` 与 `env`。

## 安全说明

- 本地 stdio 进程运行，不开放任何网络端口。
- 仅接受图片扩展名白名单（`.png .jpg .jpeg .gif .webp .bmp`），并做扩展名 +
  魔数双重校验，防止伪装成图片读取宿主任意文件。
- 图片大小默认限制 20 MB。
- 图片经 base64 编码后发送至你配置的视觉模型供应商，请留意其数据政策。
- 日志只写 stderr，不记录图片内容与 API key。

## 故障排查

- 工具返回"缺少环境变量"：检查客户端配置的 `env` 字段是否完整传入三件套。
- 工具返回"无法连接视觉模型端点"：确认 `VISION_BASE_URL` 可达，本地端点确认
  服务已启动（如 `ollama serve`）。
- 工具返回 HTTP 401/403：API key 无效或额度不足。
- 工具返回 HTTP 400 且提示不支持图片：所选模型不具备视觉能力，更换为 VL 系列模型。
- 首次接入建议用真实端点手动冒烟一次：在 CLI 贴一张图，确认文本模型能通过
  `view_image` 说出图片内容。

## 许可

MIT，详见 [LICENSE](LICENSE)。
