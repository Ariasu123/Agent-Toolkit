# sandbox-docker-mcp

`sandbox-docker-mcp` 是一个独立的 stdio MCP Server，把 `bash`、`read`、
`write`、`edit` 四个开发工具放入项目级 Docker 安全边界中。它最初从
[Pion](https://github.com/Ariasu123/Pion) 抽离，现在可以被 Pion、Codex、
Claude Code、Cursor 及其他支持 stdio MCP 的客户端单独使用。

## 安全模型

- 每个 MCP 进程创建一个一次性、非 root 容器，结束时自动删除。
- 仅绑定挂载指定工作区，不挂载 Docker socket，也不继承宿主环境变量。
- 删除全部 Linux capabilities，启用 `no-new-privileges`，并限制内存、CPU
  和进程数。
- `.env`、`.env.*` 默认在容器内被遮蔽；可添加其他保护路径。
- Git 元数据默认只读，并校验普通仓库和 Git worktree 的真实关系，防止伪造
  `.git` 文件请求任意宿主目录挂载。
- `--network none` 可关闭容器网络。默认 `bridge` 允许出站访问，不适合直接
  处理可能主动外传源码的不可信仓库。
- 命令超时或中断后会回收容器状态；下次启动也会清理本项目及旧 Pion 版本
  遗留的孤儿容器。

这不是虚拟机级隔离。Docker daemon、宿主内核和自定义镜像仍属于信任边界。

## 环境要求

- macOS 或 Linux
- Python 3.11 及以上
- Docker CLI，以及可访问的 Docker Desktop、OrbStack 或 Docker Engine
- 推荐使用 [uv](https://docs.astral.sh/uv/)

## 安装

从 Agent-Toolkit 仓库安装：

```sh
uv tool install \
  'sandbox-docker-mcp @ git+https://github.com/Ariasu123/Agent-Toolkit.git#subdirectory=Personal/MCP-Hub/sandbox-docker-mcp'
```

源码开发：

```sh
git clone https://github.com/Ariasu123/Agent-Toolkit.git
cd Agent-Toolkit/Personal/MCP-Hub/sandbox-docker-mcp
uv sync --group dev
uv run pytest -q
```

## MCP 客户端配置

安装后可直接使用命令：

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "sandbox-docker-mcp",
      "args": ["--network", "none"]
    }
  }
}
```

如果不希望全局安装，也可以让客户端通过 `uvx` 启动：

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Ariasu123/Agent-Toolkit.git#subdirectory=Personal/MCP-Hub/sandbox-docker-mcp",
        "sandbox-docker-mcp",
        "--network",
        "none"
      ]
    }
  }
}
```

Codex、Claude Code 和 Cursor 只要支持 stdio MCP，都可以使用同一组
`command`、`args` 和 `env`。MCP 进程的当前目录会被当作工作区；也可以显式
传入 `--workspace /absolute/path`。

Pion 用户无需额外配置，继续运行：

```sh
pion --sandbox mcp
```

## 工具

| 工具 | 说明 |
| --- | --- |
| `bash` | 在容器内运行 Bash，合并 stdout/stderr，并限制输出大小和执行时间 |
| `read` | 读取工作区内的 UTF-8 文本，带行号、分页和输出限制 |
| `write` | 在工作区内创建或覆盖文件，并安全创建父目录 |
| `edit` | 对单个文件执行精确文本替换，默认要求匹配唯一 |

文件工具使用基于目录文件描述符和 `O_NOFOLLOW` 的路径遍历，避免路径穿越、
symlink 逃逸及解析后替换父目录的竞态攻击。

## 参数与环境变量

CLI 参数优先于环境变量，环境变量优先于安全默认值。

| CLI 参数 | 环境变量 | 默认值 |
| --- | --- | --- |
| `--image` | `SANDBOX_DOCKER_MCP_IMAGE` | 自动构建 `sandbox-docker-mcp:0.1.0` |
| `--network` | `SANDBOX_DOCKER_MCP_NETWORK` | `bridge` |
| `--memory-mb` | `SANDBOX_DOCKER_MCP_MEMORY_MB` | `4096` |
| `--cpus` | `SANDBOX_DOCKER_MCP_CPUS` | `2.0` |
| `--pids-limit` | `SANDBOX_DOCKER_MCP_PIDS_LIMIT` | `256` |
| `--git-write` | `SANDBOX_DOCKER_MCP_GIT_WRITE` | `false` |
| `--protect-path` | `SANDBOX_DOCKER_MCP_PROTECT_PATHS` | `.env`、`.env.*` |

`--protect-path` 可重复使用。环境变量中的多个保护路径使用操作系统的路径列表
分隔符：macOS/Linux 为冒号。

自定义镜像必须已存在于本机。未设置镜像时，服务会使用项目内置 Dockerfile
自动构建包含 Python、uv、Bash、Git、curl、编译工具和 ripgrep 的默认镜像。

## 故障排查

- `Docker CLI was not found`：安装 Docker，并确认 `docker` 位于 `PATH`。
- `Docker daemon is unavailable`：启动 Docker Desktop、OrbStack 或 Docker Engine，
  再运行 `docker info` 检查连接。
- `configured sandbox image is not available locally`：先构建或拉取 `--image`
  指定的镜像。
- Git 命令不能写入：这是默认保护；只有明确需要时才启用 `--git-write`。
- 工具提示 protected/outside workspace：目标路径被保护或不在 MCP 工作区内。

## 许可与来源

项目使用 MIT License。代码从 Pion 的 Docker 沙盒和 MCP 服务实现中抽离，详见
[`NOTICE.md`](NOTICE.md)。
