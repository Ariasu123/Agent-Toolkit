---
name: mcp-builder
description: 创建高质量 MCP (Model Context Protocol) server 的指南，使 LLM 能通过设计良好的 tool 与外部服务交互。在构建 MCP server 以集成外部 API 或服务时触发，支持 Python (FastMCP) 或 Node/TypeScript (MCP SDK)。
---

# MCP Server 开发指南

## 概述

创建 MCP (Model Context Protocol) server，使 LLM 能通过设计良好的 tool 与外部服务交互。MCP server 的质量取决于它帮助 LLM 完成实际任务的能力。

---

# 流程

## 🚀 高层工作流

创建高质量 MCP server 包含四个主要阶段：

### 阶段 1：深入研究与规划

#### 1.1 理解现代 MCP 设计

**API 覆盖 vs. 工作流 Tool：**
在全面 API endpoint 覆盖与专用工作流 tool 之间取得平衡。工作流 tool 对特定任务可能更方便，而全面覆盖让 agent 能灵活组合操作。不同 client 表现各异：有些 client 通过代码执行组合基础 tool 效果更好，有些则更适配高层工作流。不确定时，优先全面 API 覆盖。

**Tool 命名与可发现性：**
清晰、描述性的 tool 名称帮助 agent 快速找到合适的 tool。使用一致前缀（例如 `github_create_issue`、`github_list_repos`）并以动作导向命名。

**上下文管理：**
Agent 受益于简洁的 tool 描述以及过滤/分页结果的能力。设计返回聚焦、相关数据的 tool。部分 client 支持代码执行，可帮助 agent 高效过滤和处理数据。

**可操作的错误信息：**
错误信息应通过具体建议和后续步骤引导 agent 解决问题。

#### 1.2 学习 MCP 协议文档

**浏览 MCP 规范：**

从 sitemap 开始查找相关页面：`https://modelcontextprotocol.io/sitemap.xml`

然后使用 `.md` 后缀获取特定页面以 markdown 格式阅读（例如 `https://modelcontextprotocol.io/specification/draft.md`）。

重点查看：
- 规范概述与架构
- Transport 机制（streamable HTTP、stdio）
- Tool、resource、prompt 定义

#### 1.3 学习框架文档

**推荐技术栈：**
- **Language**: TypeScript（高质量 SDK 支持，兼容多数执行环境如 MCPB。AI 模型擅长生成 TypeScript code，得益于其广泛使用、静态类型和优秀的 linting 工具）
- **Transport**: 远程 server 使用 streamable HTTP，采用 stateless JSON（更易扩展和维护，优于 stateful session 和 streaming response）；本地 server 使用 stdio。

**加载框架文档：**

- **MCP Best Practices**: [📋 View Best Practices](./reference/mcp_best_practices.md) - 核心指南

**TypeScript（推荐）：**
- **TypeScript SDK**: 使用 WebFetch 加载 `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md`
- [⚡ TypeScript Guide](./reference/node_mcp_server.md) - TypeScript 模式与示例

**Python：**
- **Python SDK**: 使用 WebFetch 加载 `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`
- [🐍 Python Guide](./reference/python_mcp_server.md) - Python 模式与示例

#### 1.4 规划实现

**理解 API：**
查看服务 API 文档，识别关键 endpoint、认证要求和数据模型。按需使用 web search 和 WebFetch。

**Tool 选择：**
优先全面 API 覆盖。列出待实现的 endpoint，从最常见操作开始。

---

### 阶段 2：实现

#### 2.1 搭建项目结构

参考语言专属指南进行项目初始化：
- [⚡ TypeScript Guide](./reference/node_mcp_server.md) - 项目结构、package.json、tsconfig.json
- [🐍 Python Guide](./reference/python_mcp_server.md) - 模块组织、依赖

#### 2.2 实现核心基础设施

创建共享工具：
- 带认证的 API client
- 错误处理 helper
- 响应格式化（JSON/Markdown）
- 分页支持

#### 2.3 实现 Tool

对每个 tool：

**输入 Schema：**
- TypeScript 使用 Zod，Python 使用 Pydantic
- 包含约束和清晰描述
- 在字段描述中添加示例

**输出 Schema：**
- 尽可能定义 `outputSchema` 以返回结构化数据
- 在 tool response 中使用 `structuredContent`（TypeScript SDK 特性）
- 帮助 client 理解和处理 tool 输出

**Tool 描述：**
- 功能简洁摘要
- 参数描述
- 返回类型 schema

**实现：**
- I/O 操作使用 async/await
- 使用可操作的错误信息进行恰当的错误处理
- 在适用处支持分页
- 使用现代 SDK 时同时返回 text content 和 structured data

**Annotations：**
- `readOnlyHint`: true/false
- `destructiveHint`: true/false
- `idempotentHint`: true/false
- `openWorldHint`: true/false

---

### 阶段 3：审查与测试

#### 3.1 代码质量

审查以下方面：
- 无重复代码（DRY 原则）
- 一致的错误处理
- 完整类型覆盖
- 清晰的 tool 描述

#### 3.2 构建与测试

**TypeScript：**
- 运行 `npm run build` 验证编译
- 使用 MCP Inspector 测试：`npx @modelcontextprotocol/inspector`

**Python：**
- 验证语法：`python -m py_compile your_server.py`
- 使用 MCP Inspector 测试

详细测试方法和质量清单请参阅语言专属指南。

---

### 阶段 4：创建 Evaluations

实现 MCP server 后，创建全面的 evaluations 以测试其有效性。

**加载 [✅ Evaluation Guide](./reference/evaluation.md) 获取完整评估指南。**

#### 4.1 理解 Evaluation 目的

使用 evaluations 测试 LLM 是否能有效使用你的 MCP server 回答真实、复杂的问题。

#### 4.2 创建 10 个 Evaluation 问题

按照 evaluation guide 中的流程创建有效评估：

1. **Tool Inspection**：列出可用 tool 并理解其能力
2. **内容探索**：使用 READ-ONLY 操作探索可用数据
3. **问题生成**：创建 10 个复杂、真实的问题
4. **答案验证**：自行解答每个问题以验证答案

#### 4.3 Evaluation 要求

确保每个问题满足：
- **Independent**：不依赖其他问题
- **Read-only**：仅需要非破坏性操作
- **Complex**：需要多次 tool 调用和深入探索
- **Realistic**：基于人类关心的真实用例
- **Verifiable**：单一、清晰的答案，可通过字符串比较验证
- **Stable**：答案不会随时间变化

#### 4.4 输出格式

创建如下结构的 XML 文件：

```xml
<evaluation>
  <qa_pair>
    <question>Find discussions about AI model launches with animal codenames. One model needed a specific safety designation that uses the format ASL-X. What number X was being determined for the model named after a spotted wild cat?</question>
    <answer>3</answer>
  </qa_pair>
<!-- More qa_pairs... -->
</evaluation>
```

---

# 参考文件

## 📚 文档库

开发过程中按需加载以下资源：

### 核心 MCP 文档（优先加载）
- **MCP Protocol**: 先从 sitemap `https://modelcontextprotocol.io/sitemap.xml` 开始，再用 `.md` 后缀获取特定页面
- [📋 MCP Best Practices](./reference/mcp_best_practices.md) - 通用 MCP 指南，包括：
  - Server 和 tool 命名约定
  - Response format 指南（JSON vs Markdown）
  - Pagination 最佳实践
  - Transport 选择（streamable HTTP vs stdio）
  - 安全与错误处理标准

### SDK 文档（阶段 1/2 加载）
- **Python SDK**: 从 `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md` 获取
- **TypeScript SDK**: 从 `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md` 获取

### 语言专属实现指南（阶段 2 加载）
- [🐍 Python Implementation Guide](./reference/python_mcp_server.md) - 完整 Python/FastMCP 指南，包括：
  - Server 初始化模式
  - Pydantic model 示例
  - 使用 `@mcp.tool` 注册 tool
  - 完整可运行示例
  - 质量清单

- [⚡ TypeScript Implementation Guide](./reference/node_mcp_server.md) - 完整 TypeScript 指南，包括：
  - 项目结构
  - Zod schema 模式
  - 使用 `server.registerTool` 注册 tool
  - 完整可运行示例
  - 质量清单

### Evaluation 指南（阶段 4 加载）
- [✅ Evaluation Guide](./reference/evaluation.md) - 完整 evaluation 创建指南，包括：
  - 问题创建指南
  - 答案验证策略
  - XML 格式规范
  - 示例问题与答案
  - 使用提供的脚本运行 evaluation
