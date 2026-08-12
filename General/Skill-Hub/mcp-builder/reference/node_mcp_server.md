# Node/TypeScript MCP Server 实现指南

## 概述

本文档提供使用 MCP TypeScript SDK 实现 MCP server 的 Node/TypeScript 专属最佳实践与示例。内容涵盖项目结构、server 初始化、tool 注册模式、使用 Zod 进行输入校验、错误处理以及完整可运行示例。

---

## 快速参考

### 关键导入
```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import express from "express";
import { z } from "zod";
```

### Server 初始化
```typescript
const server = new McpServer({
  name: "service-mcp-server",
  version: "1.0.0"
});
```

### Tool 注册模式
```typescript
server.registerTool(
  "tool_name",
  {
    title: "Tool Display Name",
    description: "What the tool does",
    inputSchema: { param: z.string() },
    outputSchema: { result: z.string() }
  },
  async ({ param }) => {
    const output = { result: `Processed: ${param}` };
    return {
      content: [{ type: "text", text: JSON.stringify(output) }],
      structuredContent: output // 结构化数据的现代写法
    };
  }
);
```

---

## MCP TypeScript SDK

官方 MCP TypeScript SDK 提供：
- 用于初始化 server 的 `McpServer` 类
- 用于注册 tool 的 `registerTool` 方法
- 与 Zod schema 集成以进行运行时输入校验
- 类型安全的 tool handler 实现

**重要 — 仅使用现代 API：**
- **推荐**：`server.registerTool()`、`server.registerResource()`、`server.registerPrompt()`
- **不推荐**：旧版已废弃的 API，如 `server.tool()`、`server.setRequestHandler(ListToolsRequestSchema, ...)` 或手动 handler 注册
- `register*` 方法提供更好的类型安全、自动 schema 处理，是推荐做法

完整细节请参阅 references 中的 MCP SDK 文档。

## Server 命名约定

Node/TypeScript MCP server 必须遵循以下命名模式：
- **格式**：`{service}-mcp-server`（小写连字符）
- **示例**：`github-mcp-server`、`jira-mcp-server`、`stripe-mcp-server`

server 名称应满足：
- 通用（不绑定特定功能）
- 描述所集成的 service/API
- 易于从任务描述中推断
- 不包含版本号或日期

## 项目结构

为 Node/TypeScript MCP server 创建如下结构：

```
{service}-mcp-server/
├── package.json
├── tsconfig.json
├── README.md
├── src/
│   ├── index.ts          # 主入口，初始化 McpServer
│   ├── types.ts          # TypeScript 类型定义与接口
│   ├── tools/            # tool 实现（按领域拆分为单个文件）
│   ├── services/         # API client 与共享工具
│   ├── schemas/          # Zod 校验 schema
│   └── constants.ts      # 共享常量（API_URL、CHARACTER_LIMIT 等）
└── dist/                 # 构建后的 JavaScript 文件（入口：dist/index.js）
```

## Tool 实现

### Tool 命名

tool 名称使用 snake_case（如 `"search_users"`、`"create_project"`、`"get_channel_info"`），命名应清晰且动作导向。

**避免命名冲突**：携带 service 上下文以防止重名：
- 使用 `"slack_send_message"` 而非 `"send_message"`
- 使用 `"github_create_issue"` 而非 `"create_issue"`
- 使用 `"asana_list_tasks"` 而非 `"list_tasks"`

### Tool 结构

使用 `registerTool` 方法注册 tool，并满足以下要求：
- 使用 Zod schema 进行运行时输入校验与类型安全
- 必须显式提供 `description` 字段 —— JSDoc 注释不会自动提取
- 显式提供 `title`、`description`、`inputSchema` 与 `annotations`
- `inputSchema` 必须是 Zod schema 对象（不是 JSON schema）
- 为所有参数和返回值显式标注类型

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

const server = new McpServer({
  name: "example-mcp",
  version: "1.0.0"
});

// 用于输入校验的 Zod schema
const UserSearchInputSchema = z.object({
  query: z.string()
    .min(2, "Query must be at least 2 characters")
    .max(200, "Query must not exceed 200 characters")
    .describe("Search string to match against names/emails"),
  limit: z.number()
    .int()
    .min(1)
    .max(100)
    .default(20)
    .describe("Maximum results to return"),
  offset: z.number()
    .int()
    .min(0)
    .default(0)
    .describe("Number of results to skip for pagination"),
  response_format: z.nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format: 'markdown' for human-readable or 'json' for machine-readable")
}).strict();

// 从 Zod schema 推导类型
type UserSearchInput = z.infer<typeof UserSearchInputSchema>;

server.registerTool(
  "example_search_users",
  {
    title: "Search Example Users",
    description: `Search for users in the Example system by name, email, or team.

This tool searches across all user profiles in the Example platform, supporting partial matches and various search filters. It does NOT create or modify users, only searches existing ones.

Args:
  - query (string): Search string to match against names/emails
  - limit (number): Maximum results to return, between 1-100 (default: 20)
  - offset (number): Number of results to skip for pagination (default: 0)
  - response_format ('markdown' | 'json'): Output format (default: 'markdown')

Returns:
  For JSON format: Structured data with schema:
  {
    "total": number,           // Total number of matches found
    "count": number,           // Number of results in this response
    "offset": number,          // Current pagination offset
    "users": [
      {
        "id": string,          // User ID (e.g., "U123456789")
        "name": string,        // Full name (e.g., "John Doe")
        "email": string,       // Email address
        "team": string,        // Team name (optional)
        "active": boolean      // Whether user is active
      }
    ],
    "has_more": boolean,       // Whether more results are available
    "next_offset": number      // Offset for next page (if has_more is true)
  }

Examples:
  - Use when: "Find all marketing team members" -> params with query="team:marketing"
  - Use when: "Search for John's account" -> params with query="john"
  - Don't use when: You need to create a user (use example_create_user instead)

Error Handling:
  - Returns "Error: Rate limit exceeded" if too many requests (429 status)
  - Returns "No users found matching '<query>'" if search returns empty`,
    inputSchema: UserSearchInputSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: true
    }
  },
  async (params: UserSearchInput) => {
    try {
      // 输入校验由 Zod schema 处理
      // 使用校验后的参数发起 API 请求
      const data = await makeApiRequest<any>(
        "users/search",
        "GET",
        undefined,
        {
          q: params.query,
          limit: params.limit,
          offset: params.offset
        }
      );

      const users = data.users || [];
      const total = data.total || 0;

      if (!users.length) {
        return {
          content: [{
            type: "text",
            text: `No users found matching '${params.query}'`
          }]
        };
      }

      // 准备结构化输出
      const output = {
        total,
        count: users.length,
        offset: params.offset,
        users: users.map((user: any) => ({
          id: user.id,
          name: user.name,
          email: user.email,
          ...(user.team ? { team: user.team } : {}),
          active: user.active ?? true
        })),
        has_more: total > params.offset + users.length,
        ...(total > params.offset + users.length ? {
          next_offset: params.offset + users.length
        } : {})
      };

      // 根据请求的格式生成文本表示
      let textContent: string;
      if (params.response_format === ResponseFormat.MARKDOWN) {
        const lines = [`# User Search Results: '${params.query}'`, "",
          `Found ${total} users (showing ${users.length})`, ""];
        for (const user of users) {
          lines.push(`## ${user.name} (${user.id})`);
          lines.push(`- **Email**: ${user.email}`);
          if (user.team) lines.push(`- **Team**: ${user.team}`);
          lines.push("");
        }
        textContent = lines.join("\n");
      } else {
        textContent = JSON.stringify(output, null, 2);
      }

      return {
        content: [{ type: "text", text: textContent }],
        structuredContent: output // 结构化数据的现代写法
      };
    } catch (error) {
      return {
        content: [{
          type: "text",
          text: handleApiError(error)
        }]
      };
    }
  }
);
```

## 使用 Zod Schema 进行输入校验

Zod 提供运行时类型校验：

```typescript
import { z } from "zod";

// 带校验的基础 schema
const CreateUserSchema = z.object({
  name: z.string()
    .min(1, "Name is required")
    .max(100, "Name must not exceed 100 characters"),
  email: z.string()
    .email("Invalid email format"),
  age: z.number()
    .int("Age must be a whole number")
    .min(0, "Age cannot be negative")
    .max(150, "Age cannot be greater than 150")
}).strict();  // 使用 .strict() 禁止额外字段

// 枚举
enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json"
}

const SearchSchema = z.object({
  response_format: z.nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format")
});

// 带默认值的可选字段
const PaginationSchema = z.object({
  limit: z.number()
    .int()
    .min(1)
    .max(100)
    .default(20)
    .describe("Maximum results to return"),
  offset: z.number()
    .int()
    .min(0)
    .default(0)
    .describe("Number of results to skip")
});
```

## Response Format 选项

为增强灵活性，支持多种输出格式：

```typescript
enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json"
}

const inputSchema = z.object({
  query: z.string(),
  response_format: z.nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format: 'markdown' for human-readable or 'json' for machine-readable")
});
```

**Markdown 格式**：
- 使用标题、列表与格式提升可读性
- 将时间戳转换为人类可读格式
- 展示显示名称并在括号中附带 ID
- 省略冗长元数据
- 按逻辑分组相关信息

**JSON 格式**：
- 返回完整、结构化的数据，便于程序处理
- 包含所有可用字段与元数据
- 使用一致的字段名与类型

## Pagination 实现

对于列出 resource 的 tool：

```typescript
const ListSchema = z.object({
  limit: z.number().int().min(1).max(100).default(20),
  offset: z.number().int().min(0).default(0)
});

async function listItems(params: z.infer<typeof ListSchema>) {
  const data = await apiRequest(params.limit, params.offset);

  const response = {
    total: data.total,
    count: data.items.length,
    offset: params.offset,
    items: data.items,
    has_more: data.total > params.offset + data.items.length,
    next_offset: data.total > params.offset + data.items.length
      ? params.offset + data.items.length
      : undefined
  };

  return JSON.stringify(response, null, 2);
}
```

## 字符限制与截断

添加 `CHARACTER_LIMIT` 常量以防止响应过大：

```typescript
// 在 constants.ts 的模块级定义
export const CHARACTER_LIMIT = 25000;  // 最大响应字符数

async function searchTool(params: SearchInput) {
  let result = generateResponse(data);

  // 超过字符限制时进行截断
  if (result.length > CHARACTER_LIMIT) {
    const truncatedData = data.slice(0, Math.max(1, data.length / 2));
    response.data = truncatedData;
    response.truncated = true;
    response.truncation_message =
      `Response truncated from ${data.length} to ${truncatedData.length} items. ` +
      `Use 'offset' parameter or add filters to see more results.`;
    result = JSON.stringify(response, null, 2);
  }

  return result;
}
```

## 错误处理

提供清晰、可操作的错误信息：

```typescript
import axios, { AxiosError } from "axios";

function handleApiError(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.response) {
      switch (error.response.status) {
        case 404:
          return "Error: Resource not found. Please check the ID is correct.";
        case 403:
          return "Error: Permission denied. You don't have access to this resource.";
        case 429:
          return "Error: Rate limit exceeded. Please wait before making more requests.";
        default:
          return `Error: API request failed with status ${error.response.status}`;
      }
    } else if (error.code === "ECONNABORTED") {
      return "Error: Request timed out. Please try again.";
    }
  }
  return `Error: Unexpected error occurred: ${error instanceof Error ? error.message : String(error)}`;
}
```

## 共享工具函数

将通用功能提取为可复用函数：

```typescript
// 共享 API 请求函数
async function makeApiRequest<T>(
  endpoint: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
  data?: any,
  params?: any
): Promise<T> {
  try {
    const response = await axios({
      method,
      url: `${API_BASE_URL}/${endpoint}`,
      data,
      params,
      timeout: 30000,
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
}
```

## Async/Await 最佳实践

网络请求与 I/O 操作始终使用 async/await：

```typescript
// 推荐：异步网络请求
async function fetchData(resourceId: string): Promise<ResourceData> {
  const response = await axios.get(`${API_URL}/resource/${resourceId}`);
  return response.data;
}

// 不推荐：Promise 链
function fetchData(resourceId: string): Promise<ResourceData> {
  return axios.get(`${API_URL}/resource/${resourceId}`)
    .then(response => response.data);  // 更难阅读和维护
}
```

## TypeScript 最佳实践

1. **使用 Strict TypeScript**：在 tsconfig.json 中启用 strict 模式
2. **定义 Interfaces**：为所有数据结构创建清晰的 interface 定义
3. **避免 `any`**：使用 proper types 或 `unknown` 替代 `any`
4. **使用 Zod 进行运行时校验**：使用 Zod schema 校验外部数据
5. **使用 Type Guards**：为复杂类型检查创建 type guard 函数
6. **错误处理**：始终使用 try-catch 并做 proper 的错误类型检查
7. **空安全**：使用可选链（`?.`）与空值合并（`??`）

```typescript
// 推荐：结合 Zod 与 interface 的类型安全写法
interface UserResponse {
  id: string;
  name: string;
  email: string;
  team?: string;
  active: boolean;
}

const UserSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email(),
  team: z.string().optional(),
  active: z.boolean()
});

type User = z.infer<typeof UserSchema>;

async function getUser(id: string): Promise<User> {
  const data = await apiCall(`/users/${id}`);
  return UserSchema.parse(data);  // 运行时校验
}

// 不推荐：使用 any
async function getUser(id: string): Promise<any> {
  return await apiCall(`/users/${id}`);  // 无类型安全
}
```

## 包配置

### package.json

```json
{
  "name": "{service}-mcp-server",
  "version": "1.0.0",
  "description": "MCP server for {Service} API integration",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "start": "node dist/index.js",
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "clean": "rm -rf dist"
  },
  "engines": {
    "node": ">=18"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.6.1",
    "axios": "^1.7.9",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "tsx": "^4.19.2",
    "typescript": "^5.7.2"
  }
}
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "allowSyntheticDefaultImports": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

## 完整示例

```typescript
#!/usr/bin/env node
/**
 * MCP Server for Example Service.
 *
 * This server provides tools to interact with Example API, including user search,
 * project management, and data export capabilities.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import axios, { AxiosError } from "axios";

// Constants
const API_BASE_URL = "https://api.example.com/v1";
const CHARACTER_LIMIT = 25000;

// Enums
enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json"
}

// Zod schemas
const UserSearchInputSchema = z.object({
  query: z.string()
    .min(2, "Query must be at least 2 characters")
    .max(200, "Query must not exceed 200 characters")
    .describe("Search string to match against names/emails"),
  limit: z.number()
    .int()
    .min(1)
    .max(100)
    .default(20)
    .describe("Maximum results to return"),
  offset: z.number()
    .int()
    .min(0)
    .default(0)
    .describe("Number of results to skip for pagination"),
  response_format: z.nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format: 'markdown' for human-readable or 'json' for machine-readable")
}).strict();

type UserSearchInput = z.infer<typeof UserSearchInputSchema>;

// Shared utility functions
async function makeApiRequest<T>(
  endpoint: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
  data?: any,
  params?: any
): Promise<T> {
  try {
    const response = await axios({
      method,
      url: `${API_BASE_URL}/${endpoint}`,
      data,
      params,
      timeout: 30000,
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
}

function handleApiError(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.response) {
      switch (error.response.status) {
        case 404:
          return "Error: Resource not found. Please check the ID is correct.";
        case 403:
          return "Error: Permission denied. You don't have access to this resource.";
        case 429:
          return "Error: Rate limit exceeded. Please wait before making more requests.";
        default:
          return `Error: API request failed with status ${error.response.status}`;
      }
    } else if (error.code === "ECONNABORTED") {
      return "Error: Request timed out. Please try again.";
    }
  }
  return `Error: Unexpected error occurred: ${error instanceof Error ? error.message : String(error)}`;
}

// Create MCP server instance
const server = new McpServer({
  name: "example-mcp",
  version: "1.0.0"
});

// Register tools
server.registerTool(
  "example_search_users",
  {
    title: "Search Example Users",
    description: `[Full description as shown above]`,
    inputSchema: UserSearchInputSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: true
    }
  },
  async (params: UserSearchInput) => {
    // Implementation as shown above
  }
);

// Main function
// For stdio (local):
async function runStdio() {
  if (!process.env.EXAMPLE_API_KEY) {
    console.error("ERROR: EXAMPLE_API_KEY environment variable is required");
    process.exit(1);
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MCP server running via stdio");
}

// For streamable HTTP (remote):
async function runHTTP() {
  if (!process.env.EXAMPLE_API_KEY) {
    console.error("ERROR: EXAMPLE_API_KEY environment variable is required");
    process.exit(1);
  }

  const app = express();
  app.use(express.json());

  app.post('/mcp', async (req, res) => {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true
    });
    res.on('close', () => transport.close());
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  });

  const port = parseInt(process.env.PORT || '3000');
  app.listen(port, () => {
    console.error(`MCP server running on http://localhost:${port}/mcp`);
  });
}

// Choose transport based on environment
const transport = process.env.TRANSPORT || 'stdio';
if (transport === 'http') {
  runHTTP().catch(error => {
    console.error("Server error:", error);
    process.exit(1);
  });
} else {
  runStdio().catch(error => {
    console.error("Server error:", error);
    process.exit(1);
  });
}
```

---

## 高级 MCP 特性

### Resource 注册

将数据以 resource 形式暴露，实现基于 URI 的高效访问：

```typescript
import { ResourceTemplate } from "@modelcontextprotocol/sdk/types.js";

// 使用 URI template 注册 resource
server.registerResource(
  {
    uri: "file://documents/{name}",
    name: "Document Resource",
    description: "Access documents by name",
    mimeType: "text/plain"
  },
  async (uri: string) => {
    // 从 URI 中提取参数
    const match = uri.match(/^file:\/\/documents\/(.+)$/);
    if (!match) {
      throw new Error("Invalid URI format");
    }

    const documentName = match[1];
    const content = await loadDocument(documentName);

    return {
      contents: [{
        uri,
        mimeType: "text/plain",
        text: content
      }]
    };
  }
);

// 动态列出可用 resource
server.registerResourceList(async () => {
  const documents = await getAvailableDocuments();
  return {
    resources: documents.map(doc => ({
      uri: `file://documents/${doc.name}`,
      name: doc.name,
      mimeType: "text/plain",
      description: doc.description
    }))
  };
});
```

**何时使用 Resource 与 Tool：**
- **Resource**：通过简单 URI 参数访问数据
- **Tool**：需要校验与业务逻辑的复杂操作
- **Resource**：数据相对静态或基于 template
- **Tool**：操作有副作用或涉及复杂工作流

### Transport 选项

TypeScript SDK 支持两种主要 transport 机制：

#### Streamable HTTP（推荐用于远程 Server）

```typescript
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express from "express";

const app = express();
app.use(express.json());

app.post('/mcp', async (req, res) => {
  // 为每个请求创建新的 transport（无状态，避免请求 ID 冲突）
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true
  });

  res.on('close', () => transport.close());

  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

app.listen(3000);
```

#### stdio（用于本地集成）

```typescript
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const transport = new StdioServerTransport();
await server.connect(transport);
```

**Transport 选择：**
- **Streamable HTTP**：Web service、远程访问、多 client
- **stdio**：命令行工具、本地开发、子进程集成

### Notification 支持

当 server 状态变化时通知 client：

```typescript
// tool 列表变化时通知
server.notification({
  method: "notifications/tools/list_changed"
});

// resource 变化时通知
server.notification({
  method: "notifications/resources/list_changed"
});
```

谨慎使用 notification —— 仅在 server 能力真正变化时发送。

---

## 代码最佳实践

### 代码可组合性与可复用性

实现必须优先考虑可组合性与代码复用：

1. **提取通用功能**：
   - 将多个 tool 共用的操作提取为可复用 helper 函数
   - 构建共享 API client 处理 HTTP 请求，避免重复代码
   - 将错误处理逻辑集中到工具函数
   - 将业务逻辑提取为可组合的独立函数
   - 提取共享的 markdown 或 JSON 字段选择与格式化功能

2. **避免重复**：
   - 禁止在 tool 之间复制粘贴相似代码
   - 若发现自己在写两次相似逻辑，将其提取为函数
   - pagination、过滤、字段选择、格式化等通用操作应共享
   - 认证/授权逻辑应集中管理

## 构建与运行

运行前始终先构建 TypeScript 代码：

```bash
# 构建项目
npm run build

# 运行 server
npm start

# 开发模式，自动重载
npm run dev
```

在认为实现完成前，始终确保 `npm run build` 成功完成。

## 质量清单

在最终确定 Node/TypeScript MCP server 实现前，请确认：

### 战略设计
- [ ] Tool 支持完整工作流，而非仅是 API endpoint 包装器
- [ ] Tool 名称反映自然任务拆分
- [ ] Response format 针对 agent 上下文效率优化
- [ ] 在适当位置使用人类可读标识符
- [ ] 错误信息引导 agent 正确使用

### 实现质量
- [ ] 聚焦实现：已完成最重要、最有价值的 tool
- [ ] 所有 tool 均使用 `registerTool` 注册且配置完整
- [ ] 所有 tool 均包含 `title`、`description`、`inputSchema` 与 `annotations`
- [ ] Annotations 设置正确（readOnlyHint、destructiveHint、idempotentHint、openWorldHint）
- [ ] 所有 tool 使用 Zod schema 进行运行时输入校验，并启用 `.strict()`
- [ ] 所有 Zod schema 具有 proper 约束与描述性错误信息
- [ ] 所有 tool 描述全面，包含显式输入/输出类型
- [ ] 描述包含返回值示例与完整 schema 文档
- [ ] 错误信息清晰、可操作且具有指导性

### TypeScript 质量
- [ ] 为所有数据结构定义 TypeScript interface
- [ ] 在 tsconfig.json 中启用 Strict TypeScript
- [ ] 不使用 `any` 类型 —— 使用 `unknown` 或 proper 类型
- [ ] 所有 async 函数具有显式 `Promise<T>` 返回类型
- [ ] 错误处理使用 proper type guard（如 `axios.isAxiosError`、`z.ZodError`）

### 高级特性（如适用）
- [ ] 为合适的数据 endpoint 注册 resource
- [ ] 配置合适的 transport（stdio 或 streamable HTTP）
- [ ] 为动态 server 能力实现 notification
- [ ] 使用 SDK interface 保持类型安全

### 项目配置
- [ ] package.json 包含所有必要依赖
- [ ] 构建脚本在 dist/ 目录生成可工作的 JavaScript
- [ ] 主入口正确配置为 dist/index.js
- [ ] Server 名称遵循 `{service}-mcp-server` 格式
- [ ] tsconfig.json 已正确配置 strict 模式

### 代码质量
- [ ] 在适用处正确实现 pagination
- [ ] 大响应检查 `CHARACTER_LIMIT` 常量并带清晰信息截断
- [ ] 为可能的大结果集提供过滤选项
- [ ] 所有网络操作优雅处理超时与连接错误
- [ ] 通用功能提取为可复用函数
- [ ] 相似操作的返回类型保持一致

### 测试与构建
- [ ] `npm run build` 成功完成且无错误
- [ ] dist/index.js 已创建且可执行
- [ ] Server 可运行：`node dist/index.js --help`
- [ ] 所有 import 正确解析
- [ ] 示例 tool 调用按预期工作
