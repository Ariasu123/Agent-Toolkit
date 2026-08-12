# MCP Server 最佳实践

## 快速参考

### Server 命名
- **Python**: `{service}_mcp`（例如 `slack_mcp`）
- **Node/TypeScript**: `{service}-mcp-server`（例如 `slack-mcp-server`）

### Tool 命名
- 使用 snake_case 并附加 service 前缀
- 格式：`{service}_{action}_{resource}`
- 示例：`slack_send_message`、`github_create_issue`

### Response Formats
- 同时支持 JSON 和 Markdown 格式
- JSON 用于程序化 processing
- Markdown 用于 human readability

### Pagination
- 始终遵守 `limit` 参数
- 返回 `has_more`、`next_offset`、`total_count`
- 默认 20-50 条

### Transport
- **Streamable HTTP**: 用于 remote server、多 client 场景
- **stdio**: 用于本地集成、命令行 tool
- 避免使用 SSE（已 deprecated，推荐使用 streamable HTTP）

---

## Server 命名约定

遵循以下标准化命名模式：

**Python**: 使用格式 `{service}_mcp`（小写加下划线）
- 示例：`slack_mcp`、`github_mcp`、`jira_mcp`

**Node/TypeScript**: 使用格式 `{service}-mcp-server`（小写加连字符）
- 示例：`slack-mcp-server`、`github-mcp-server`、`jira-mcp-server`

名称应具有通用性，能描述所集成的 service，易于从任务描述中推断，且不包含版本号。

---

## Tool 命名与设计

### Tool 命名

1. **使用 snake_case**: `search_users`、`create_project`、`get_channel_info`
2. **包含 service 前缀**: 预期你的 MCP server 可能与其他 MCP server 一起使用
   - 使用 `slack_send_message`，而不是仅 `send_message`
   - 使用 `github_create_issue`，而不是仅 `create_issue`
3. **采用动作导向**: 以动词开头（get、list、search、create 等）
4. **具体明确**: 避免可能与其他 server 冲突的通用名称

### Tool 设计

- Tool description 必须 narrow 且无歧义地描述功能
- Description 必须精确匹配实际功能
- 提供 tool annotations（readOnlyHint、destructiveHint、idempotentHint、openWorldHint）
- 保持 tool 操作聚焦且原子化

---

## Response Formats

所有返回数据的 tool 都应支持多种格式：

### JSON Format (`response_format="json"`)
- 机器可读的结构化数据
- 包含所有可用字段和 metadata
- 字段名和类型保持一致
- 用于程序化 processing

### Markdown Format (`response_format="markdown"`, 通常为默认)
- 人类可读的格式化文本
- 使用 headers、lists 和 formatting 提高清晰度
- 将 timestamps 转换为人类可读格式
- 显示 display names，并在括号中附带 IDs
- 省略冗余 metadata

---

## Pagination

对于列出 resource 的 tool：

- **始终尊重 `limit` 参数**
- **实现 pagination**: 使用 `offset` 或 cursor-based pagination
- **返回 pagination metadata**: 包含 `has_more`、`next_offset`/`next_cursor`、`total_count`
- **永远不要将所有结果加载到内存中**: 对于大数据集尤其重要
- **设置合理的默认 limit**: 通常 20-50 条

Pagination response 示例：
```json
{
  "total": 150,
  "count": 20,
  "offset": 0,
  "items": [...],
  "has_more": true,
  "next_offset": 20
}
```

---

## Transport 选项

### Streamable HTTP

**适用场景**: Remote server、web service、多 client 场景

**特点**:
- 基于 HTTP 的双向通信
- 支持多个 client 同时连接
- 可作为 web service 部署
- 支持 server-to-client notifications

**使用时机**:
- 同时服务多个 client
- 作为 cloud service 部署
- 与 web application 集成

### stdio

**适用场景**: 本地集成、命令行 tool

**特点**:
- 通过标准输入/输出流通信
- 设置简单，无需网络配置
- 作为 client 的 subprocess 运行

**使用时机**:
- 为本地开发环境构建 tool
- 与 desktop application 集成
- 单用户、单 session 场景

**注意**: stdio server 不应向 stdout 输出日志（使用 stderr 进行日志记录）

### Transport 选择

| 评判标准 | stdio | Streamable HTTP |
|-----------|-------|-----------------|
| **Deployment** | Local | Remote |
| **Clients** | Single | Multiple |
| **Complexity** | Low | Medium |
| **Real-time** | No | Yes |

---

## 安全最佳实践

### 认证与授权

**OAuth 2.1**:
- 使用来自权威机构的 certificates 的安全 OAuth 2.1
- 在处理请求前验证 access tokens
- 只接受专门发给你的 server 的 tokens

**API Keys**:
- 将 API keys 存储在环境变量中，绝不要写在代码里
- 在 server 启动时验证 keys
- 认证失败时提供清晰的错误信息

### 输入验证

- 清理 file paths 以防止 directory traversal
- 验证 URLs 和外部 identifiers
- 检查参数大小和范围
- 防止 system calls 中的 command injection
- 对所有输入使用 schema validation（Pydantic/Zod）

### 错误处理

- 不要向 clients 暴露内部错误
- 在 server 端记录安全相关错误
- 提供有帮助但不会泄露信息的错误信息
- 错误发生后清理资源

### DNS Rebinding 防护

对于本地运行的 streamable HTTP server：
- 启用 DNS rebinding protection
- 验证所有入站连接的 `Origin` header
- 绑定到 `127.0.0.1` 而不是 `0.0.0.0`

---

## Tool Annotations

提供 annotations 以帮助 clients 理解 tool 行为：

| Annotation | Type | Default | Description |
|-----------|------|---------|-------------|
| `readOnlyHint` | boolean | false | Tool 不会修改其环境 |
| `destructiveHint` | boolean | true | Tool 可能执行破坏性更新 |
| `idempotentHint` | boolean | false | 使用相同参数重复调用不会产生额外效果 |
| `openWorldHint` | boolean | true | Tool 与外部实体交互 |

**重要提示**: Annotations 只是 hints，不是安全保证。Clients 不应仅基于 annotations 做安全关键决策。

---

## 错误处理

- 使用标准 JSON-RPC error codes
- 在 result objects 中报告 tool errors（而不是 protocol-level errors）
- 提供有帮助、具体的错误信息，并给出建议的下一步操作
- 不要暴露内部实现细节
- 错误发生时正确清理资源

错误处理示例：
```typescript
try {
  const result = performOperation();
  return { content: [{ type: "text", text: result }] };
} catch (error) {
  return {
    isError: true,
    content: [{
      type: "text",
      text: `Error: ${error.message}. Try using filter='active_only' to reduce results.`
    }]
  };
}
```

---

## 测试要求

全面的测试应覆盖：

- **Functional testing**: 使用有效/无效输入验证正确执行
- **Integration testing**: 测试与外部系统的交互
- **Security testing**: 验证认证、输入清理、rate limiting
- **Performance testing**: 检查负载和超时下的行为
- **Error handling**: 确保正确报告错误并清理资源

---

## 文档要求

- 为所有 tool 和功能提供清晰的文档
- 包含可运行的示例（每个主要功能至少 3 个）
- 记录安全注意事项
- 说明所需 permissions 和 access levels
- 记录 rate limits 和 performance 特征
