# Agent-Toolkit

我的 Agent 能力扩展件集合：可复用的 Agent Skills 与 MCP Servers。

## 目录结构

```
General/                  # 通用能力（跨场景可复用）
├── Skill-Hub/            #   通用 Agent Skills
└── MCP-Hub/              #   通用 MCP Servers
Personal/                 # 个人能力（面向个人工作流）
├── Skill-Hub/            #   个人 Agent Skills
│   ├── handoff-skill/        # 会话交接管理 skill
│   └── weekly-report-skill/  # 科研周报 skill
└── MCP-Hub/              #   个人 MCP Servers
    └── sandbox-docker-mcp/   # Docker 隔离的文件与 Shell MCP
```

## 说明

- `Personal/Skill-Hub/` 下的两个 skill 分别从独立仓库 [handoff-skill] 与 [Weekly-report-skill] 以 `git subtree` 完整历史合并迁入，原始提交记录全部保留。
- [`Personal/MCP-Hub/sandbox-docker-mcp/`](Personal/MCP-Hub/sandbox-docker-mcp/) 是从 Pion 抽离的独立 Docker 沙盒 MCP Server。
- 新增 skill / MCP server 时，按"通用 vs 个人"归入 `General/` 或 `Personal/` 对应子目录。
