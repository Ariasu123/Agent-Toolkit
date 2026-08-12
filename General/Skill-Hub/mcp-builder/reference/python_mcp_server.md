# Python MCP Server 实现指南

## 概述

本文提供使用 MCP Python SDK 实现 MCP server 的 Python 专用最佳实践与示例，涵盖 server 设置、tool 注册模式、基于 Pydantic 的输入校验、错误处理以及完整可运行示例。

---

## 快速参考

### 关键导入

```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
import httpx
```

### Server 初始化

```python
mcp = FastMCP("service_mcp")
```

### Tool 注册模式

```python
@mcp.tool(name="tool_name", annotations={...})
async def tool_function(params: InputModel) -> str:
    # 在此实现
    pass
```

---

## MCP Python SDK 与 FastMCP

官方 MCP Python SDK 提供 FastMCP，一个用于构建 MCP server 的高层框架。它提供：

- 根据函数签名与 docstring 自动生成 description 与 inputSchema
- 集成 Pydantic model 进行输入校验
- 基于装饰器的 tool 注册，使用 `@mcp.tool`

**完整 SDK 文档请使用 WebFetch 加载：**
`https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`

## Server 命名约定

Python MCP server 必须遵循以下命名模式：

- **格式**：`{service}_mcp`（小写加下划线）
- **示例**：`github_mcp`、`jira_mcp`、`stripe_mcp`

名称应当：

- 通用（不绑定特定功能）
- 描述所集成的服务/API
- 易于从任务描述中推断
- 不含版本号或日期

## Tool 实现

### Tool 命名

Tool 名称使用 snake_case（例如 `"search_users"`、`"create_project"`、`"get_channel_info"`），采用清晰、动作导向的命名。

**避免命名冲突**：包含服务上下文以防止重叠：

- 使用 `"slack_send_message"` 而不是仅 `"send_message"`
- 使用 `"github_create_issue"` 而不是仅 `"create_issue"`
- 使用 `"asana_list_tasks"` 而不是仅 `"list_tasks"`

### 使用 FastMCP 的 Tool 结构

Tool 使用 `@mcp.tool` 装饰器定义，并通过 Pydantic model 进行输入校验：

```python
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# 初始化 MCP server
mcp = FastMCP("example_mcp")

# 定义 Pydantic model 用于输入校验
class ServiceToolInput(BaseModel):
    '''service tool 操作的输入 model。'''
    model_config = ConfigDict(
        str_strip_whitespace=True,  # 自动去除字符串首尾空白
        validate_assignment=True,    # 赋值时校验
        extra='forbid'              # 禁止额外字段
    )

    param1: str = Field(..., description="第一个参数描述（例如：'user123'、'project-abc'）", min_length=1, max_length=100)
    param2: Optional[int] = Field(default=None, description="带约束的可选整数参数", ge=0, le=1000)
    tags: Optional[List[str]] = Field(default_factory=list, description="要应用的 tag 列表", max_items=10)

@mcp.tool(
    name="service_tool_name",
    annotations={
        "title": "Human-Readable Tool Title",
        "readOnlyHint": True,     # Tool 不修改环境
        "destructiveHint": False,  # Tool 不执行破坏性操作
        "idempotentHint": True,    # 重复调用无额外副作用
        "openWorldHint": False     # Tool 不与外部实体交互
    }
)
async def service_tool_name(params: ServiceToolInput) -> str:
    '''Tool 描述会自动成为 'description' 字段。

    本 tool 对服务执行特定操作，在处理前使用 ServiceToolInput Pydantic model
    校验所有输入。

    Args:
        params (ServiceToolInput): 已校验的输入参数，包含：
            - param1 (str): 第一个参数描述
            - param2 (Optional[int]): 带默认值的可选参数
            - tags (Optional[List[str]]): tag 列表

    Returns:
        str: 包含操作结果的 JSON 格式响应
    '''
    # 在此实现
    pass
```

## Pydantic v2 关键特性

- 使用 `model_config` 替代嵌套的 `Config` 类
- 使用 `field_validator` 替代已弃用的 `validator`
- 使用 `model_dump()` 替代已弃用的 `dict()`
- Validator 需要 `@classmethod` 装饰器
- Validator 方法需要类型提示

```python
from pydantic import BaseModel, Field, field_validator, ConfigDict

class CreateUserInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    name: str = Field(..., description="用户全名", min_length=1, max_length=100)
    email: str = Field(..., description="用户邮箱地址", pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: int = Field(..., description="用户年龄", ge=0, le=150)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Email 不能为空")
        return v.lower()
```

## 响应格式选项

为增强灵活性，支持多种输出格式：

```python
from enum import Enum

class ResponseFormat(str, Enum):
    '''tool 响应的输出格式。'''
    MARKDOWN = "markdown"
    JSON = "json"

class UserSearchInput(BaseModel):
    query: str = Field(..., description="搜索关键词")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="输出格式：'markdown' 表示人类可读，'json' 表示机器可读"
    )
```

**Markdown 格式**：

- 使用标题、列表和格式提升清晰度
- 将时间戳转换为人类可读格式（例如 `"2024-01-15 10:30:00 UTC"` 而非 epoch）
- 显示名称并在括号中附带 ID（例如 `"@john.doe (U123456)"`）
- 省略冗长元数据（例如只显示一个头像 URL，而非所有尺寸）
- 按逻辑分组相关信息

**JSON 格式**：

- 返回完整、结构化数据，便于程序处理
- 包含所有可用字段和元数据
- 使用一致的字段名和类型

## 分页实现

对于列出 resource 的 tool：

```python
class ListInput(BaseModel):
    limit: Optional[int] = Field(default=20, description="返回的最大结果数", ge=1, le=100)
    offset: Optional[int] = Field(default=0, description="分页时跳过的结果数", ge=0)

async def list_items(params: ListInput) -> str:
    # 发起带分页的 API 请求
    data = await api_request(limit=params.limit, offset=params.offset)

    # 返回分页信息
    response = {
        "total": data["total"],
        "count": len(data["items"]),
        "offset": params.offset,
        "items": data["items"],
        "has_more": data["total"] > params.offset + len(data["items"]),
        "next_offset": params.offset + len(data["items"]) if data["total"] > params.offset + len(data["items"]) else None
    }
    return json.dumps(response, indent=2)
```

## 错误处理

提供清晰、可操作的错误信息：

```python
def _handle_api_error(e: Exception) -> str:
    '''所有 tool 统一的错误格式化。'''
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 404:
            return "Error: Resource not found. Please check the ID is correct."
        elif e.response.status_code == 403:
            return "Error: Permission denied. You don't have access to this resource."
        elif e.response.status_code == 429:
            return "Error: Rate limit exceeded. Please wait before making more requests."
        return f"Error: API request failed with status {e.response.status_code}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."
    return f"Error: Unexpected error occurred: {type(e).__name__}"
```

## 共享工具

将通用功能抽取为可复用函数：

```python
# 共享 API 请求函数
async def _make_api_request(endpoint: str, method: str = "GET", **kwargs) -> dict:
    '''所有 API 调用的可复用函数。'''
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{API_BASE_URL}/{endpoint}",
            timeout=30.0,
            **kwargs
        )
        response.raise_for_status()
        return response.json()
```

## Async/Await 最佳实践

网络请求和 I/O 操作始终使用 async/await：

```python
# 良好：异步网络请求
async def fetch_data(resource_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_URL}/resource/{resource_id}")
        response.raise_for_status()
        return response.json()

# 不良：同步请求
def fetch_data(resource_id: str) -> dict:
    response = requests.get(f"{API_URL}/resource/{resource_id}")  # 阻塞
    return response.json()
```

## 类型提示

全程使用类型提示：

```python
from typing import Optional, List, Dict, Any

async def get_user(user_id: str) -> Dict[str, Any]:
    data = await fetch_user(user_id)
    return {"id": data["id"], "name": data["name"]}
```

## Tool Docstrings

每个 tool 必须具备包含显式类型信息的完整 docstring：

```python
async def search_users(params: UserSearchInput) -> str:
    '''
    按名称、邮箱或团队搜索 Example 系统中的用户。

    本 tool 在 Example 平台的所有用户资料中搜索，支持部分匹配和多种
    搜索过滤条件。它不会创建或修改用户，仅搜索已有用户。

    Args:
        params (UserSearchInput): 已校验的输入参数，包含：
            - query (str): 用于匹配姓名/邮箱的搜索字符串（例如："john"、"@example.com"、"team:marketing"）
            - limit (Optional[int]): 返回的最大结果数，范围为 1-100（默认：20）
            - offset (Optional[int]): 分页时跳过的结果数（默认：0）

    Returns:
        str: 包含搜索结果的 JSON 格式字符串，schema 如下：

        成功响应：
        {
            "total": int,           # 匹配总数
            "count": int,           # 本次响应中的结果数
            "offset": int,          # 当前分页偏移量
            "users": [
                {
                    "id": str,      # 用户 ID（例如："U123456789"）
                    "name": str,    # 全名（例如："John Doe"）
                    "email": str,   # 邮箱地址（例如："john@example.com"）
                    "team": str     # 团队名称（例如："Marketing"）- 可选
                }
            ]
        }

        错误响应：
        "Error: <error message>" 或 "No users found matching '<query>'"

    Examples:
        - 使用场景："Find all marketing team members" -> 参数 query="team:marketing"
        - 使用场景："Search for John's account" -> 参数 query="john"
        - 不要使用：需要创建用户时（改用 example_create_user）
        - 不要使用：已有用户 ID 且需要完整详情时（改用 example_get_user）

    Error Handling:
        - 输入校验错误由 Pydantic model 处理
        - 请求过多（429 状态）时返回 "Error: Rate limit exceeded"
        - API key 无效（401 状态）时返回 "Error: Invalid API authentication"
        - 返回格式化结果列表或 "No users found matching 'query'"
    '''
```

## 完整示例

下面是完整的 Python MCP server 示例：

```python
#!/usr/bin/env python3
'''
Example Service 的 MCP Server。

本 server 提供与 Example API 交互的 tool，包括用户搜索、项目管理
和数据导出能力。
'''

from typing import Optional, List, Dict, Any
from enum import Enum
import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# 初始化 MCP server
mcp = FastMCP("example_mcp")

# 常量
API_BASE_URL = "https://api.example.com/v1"

# 枚举
class ResponseFormat(str, Enum):
    '''tool 响应的输出格式。'''
    MARKDOWN = "markdown"
    JSON = "json"

# 用于输入校验的 Pydantic Models
class UserSearchInput(BaseModel):
    '''用户搜索操作的输入 model。'''
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    query: str = Field(..., description="用于匹配姓名/邮箱的搜索字符串", min_length=2, max_length=200)
    limit: Optional[int] = Field(default=20, description="返回的最大结果数", ge=1, le=100)
    offset: Optional[int] = Field(default=0, description="分页时跳过的结果数", ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="输出格式")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query 不能为空或仅包含空白字符")
        return v.strip()

# 共享工具函数
async def _make_api_request(endpoint: str, method: str = "GET", **kwargs) -> dict:
    '''所有 API 调用的可复用函数。'''
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{API_BASE_URL}/{endpoint}",
            timeout=30.0,
            **kwargs
        )
        response.raise_for_status()
        return response.json()

def _handle_api_error(e: Exception) -> str:
    '''所有 tool 统一的错误格式化。'''
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 404:
            return "Error: Resource not found. Please check the ID is correct."
        elif e.response.status_code == 403:
            return "Error: Permission denied. You don't have access to this resource."
        elif e.response.status_code == 429:
            return "Error: Rate limit exceeded. Please wait before making more requests."
        return f"Error: API request failed with status {e.response.status_code}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."
    return f"Error: Unexpected error occurred: {type(e).__name__}"

# Tool 定义
@mcp.tool(
    name="example_search_users",
    annotations={
        "title": "Search Example Users",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def example_search_users(params: UserSearchInput) -> str:
    '''按名称、邮箱或团队搜索 Example 系统中的用户。

    [完整 docstring 见上文]
    '''
    try:
        # 使用已校验参数发起 API 请求
        data = await _make_api_request(
            "users/search",
            params={
                "q": params.query,
                "limit": params.limit,
                "offset": params.offset
            }
        )

        users = data.get("users", [])
        total = data.get("total", 0)

        if not users:
            return f"No users found matching '{params.query}'"

        # 根据请求的格式格式化响应
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"# User Search Results: '{params.query}'", ""]
            lines.append(f"Found {total} users (showing {len(users)})")
            lines.append("")

            for user in users:
                lines.append(f"## {user['name']} ({user['id']})")
                lines.append(f"- **Email**: {user['email']}")
                if user.get('team'):
                    lines.append(f"- **Team**: {user['team']}")
                lines.append("")

            return "\n".join(lines)

        else:
            # 机器可读的 JSON 格式
            import json
            response = {
                "total": total,
                "count": len(users),
                "offset": params.offset,
                "users": users
            }
            return json.dumps(response, indent=2)

    except Exception as e:
        return _handle_api_error(e)

if __name__ == "__main__":
    mcp.run()
```

---

## FastMCP 高级特性

### Context 参数注入

FastMCP 可自动将 `Context` 参数注入 tool，以支持日志、进度报告、resource 读取和用户交互等高级能力：

```python
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("example_mcp")

@mcp.tool()
async def advanced_search(query: str, ctx: Context) -> str:
    '''带有 context 访问权限的高级 tool，用于日志和进度。'''

    # 报告长时间操作的进度
    await ctx.report_progress(0.25, "Starting search...")

    # 记录日志用于调试
    await ctx.log_info("Processing query", {"query": query, "timestamp": datetime.now()})

    # 执行搜索
    results = await search_api(query)
    await ctx.report_progress(0.75, "Formatting results...")

    # 访问 server 配置
    server_name = ctx.fastmcp.name

    return format_results(results)

@mcp.tool()
async def interactive_tool(resource_id: str, ctx: Context) -> str:
    '''可向用户请求额外输入的 tool。'''

    # 在需要时请求敏感信息
    api_key = await ctx.elicit(
        prompt="Please provide your API key:",
        input_type="password"
    )

    # 使用提供的 key
    return await api_call(resource_id, api_key)
```

**Context 能力：**

- `ctx.report_progress(progress, message)` - 报告长时间操作的进度
- `ctx.log_info(message, data)` / `ctx.log_error()` / `ctx.log_debug()` - 日志
- `ctx.elicit(prompt, input_type)` - 向用户请求输入
- `ctx.fastmcp.name` - 访问 server 配置
- `ctx.read_resource(uri)` - 读取 MCP resource

### Resource 注册

将数据暴露为 resource，以实现高效的基于模板的访问：

```python
@mcp.resource("file://documents/{name}")
async def get_document(name: str) -> str:
    '''将文档暴露为 MCP resource。

    Resource 适用于静态或半静态、不需要复杂参数的数据。
    它们使用 URI 模板实现灵活访问。
    '''
    document_path = f"./docs/{name}"
    with open(document_path, "r") as f:
        return f.read()

@mcp.resource("config://settings/{key}")
async def get_setting(key: str, ctx: Context) -> str:
    '''通过 context 将配置暴露为 resource。'''
    settings = await load_settings()
    return json.dumps(settings.get(key, {}))
```

**何时使用 Resource 与 Tool：**

- **Resource**：用于简单参数的数据访问（URI 模板）
- **Tool**：用于需要校验和业务逻辑的复杂操作

### 结构化输出类型

FastMCP 支持字符串之外的多种返回类型：

```python
from typing import TypedDict
from dataclasses import dataclass
from pydantic import BaseModel

# 使用 TypedDict 返回结构化数据
class UserData(TypedDict):
    id: str
    name: str
    email: str

@mcp.tool()
async def get_user_typed(user_id: str) -> UserData:
    '''返回结构化数据 - FastMCP 处理序列化。'''
    return {"id": user_id, "name": "John Doe", "email": "john@example.com"}

# 使用 Pydantic model 进行复杂校验
class DetailedUser(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    metadata: Dict[str, Any]

@mcp.tool()
async def get_user_detailed(user_id: str) -> DetailedUser:
    '''返回 Pydantic model - 自动生成 schema。'''
    user = await fetch_user(user_id)
    return DetailedUser(**user)
```

### 生命周期管理

初始化跨请求持久化的资源：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def app_lifespan():
    '''管理 server 生命周期内的资源。'''
    # 初始化连接、加载配置等
    db = await connect_to_database()
    config = load_configuration()

    # 提供给所有 tool 使用
    yield {"db": db, "config": config}

    # 关闭时清理
    await db.close()

mcp = FastMCP("example_mcp", lifespan=app_lifespan)

@mcp.tool()
async def query_data(query: str, ctx: Context) -> str:
    '''通过 context 访问 lifespan 资源。'''
    db = ctx.request_context.lifespan_state["db"]
    results = await db.query(query)
    return format_results(results)
```

### Transport 选项

FastMCP 支持两种主要 transport 机制：

```python
# stdio transport（用于本地 tool）- 默认
if __name__ == "__main__":
    mcp.run()

# Streamable HTTP transport（用于远程 server）
if __name__ == "__main__":
    mcp.run(transport="streamable_http", port=8000)
```

**Transport 选择：**

- **stdio**：命令行 tool、本地集成、子进程执行
- **Streamable HTTP**：Web 服务、远程访问、多 client

---

## 代码最佳实践

### 代码可组合性与可复用性

你的实现必须优先考虑可组合性和代码复用：

1. **抽取通用功能**：
   - 为跨多个 tool 使用的操作创建可复用的 helper 函数
   - 构建共享 API client 处理 HTTP 请求，避免重复代码
   - 将错误处理逻辑集中在 utility 函数中
   - 将业务逻辑抽取为可组合的专用函数
   - 抽取共享的 Markdown 或 JSON 字段选择与格式化功能

2. **避免重复**：
   - 禁止在 tool 之间复制粘贴相似代码
   - 如果发现自己在写两次相似逻辑，请将其抽取为函数
   - 分页、过滤、字段选择和格式化等通用操作应共享
   - 认证/授权逻辑应集中管理

### Python 专用最佳实践

1. **使用 Type Hints**：始终为函数参数和返回值添加类型注解
2. **Pydantic Models**：为所有输入校验定义清晰的 Pydantic model
3. **避免手动校验**：让 Pydantic 通过约束处理输入校验
4. **合理导入**：按组导入（标准库、第三方、本地）
5. **错误处理**：使用具体异常类型（`httpx.HTTPStatusError`，而非通用 Exception）
6. **异步上下文管理器**：对需要清理的资源使用 `async with`
7. **常量**：使用 UPPER_CASE 定义模块级常量

## 质量检查清单

在最终确定 Python MCP server 实现前，请确认：

### 策略设计

- [ ] Tool 支持完整工作流，而非仅作为 API endpoint 包装器
- [ ] Tool 名称反映自然的任务拆分
- [ ] 响应格式针对 agent 上下文效率进行优化
- [ ] 在合适的地方使用人类可读的标识符
- [ ] 错误信息引导 agent 正确使用

### 实现质量

- [ ] 聚焦实现：最重要、最有价值的 tool 已实现
- [ ] 所有 tool 都具有描述性名称和文档
- [ ] 相似操作的返回类型一致
- [ ] 所有外部调用都实现了错误处理
- [ ] Server 名称遵循 `{service}_mcp` 格式
- [ ] 所有网络操作使用 async/await
- [ ] 通用功能抽取为可复用函数
- [ ] 错误信息清晰、可操作且具有指导性
- [ ] 输出经过正确校验和格式化

### Tool 配置

- [ ] 所有 tool 在装饰器中实现了 `name` 和 `annotations`
- [ ] Annotations 设置正确（readOnlyHint、destructiveHint、idempotentHint、openWorldHint）
- [ ] 所有 tool 使用 Pydantic BaseModel 进行输入校验，并定义 Field()
- [ ] 所有 Pydantic Field 具有显式类型、描述和约束
- [ ] 所有 tool 具有包含显式输入/输出类型的完整 docstring
- [ ] Docstring 包含 dict/JSON 返回的完整 schema 结构
- [ ] Pydantic model 处理输入校验（无需手动校验）

### 高级特性（如适用）

- [ ] 使用 Context 注入进行日志、进度或请求输入
- [ ] 为合适的数据 endpoint 注册 Resource
- [ ] 为持久连接实现 Lifespan 管理
- [ ] 使用结构化输出类型（TypedDict、Pydantic models）
- [ ] 配置合适的 transport（stdio 或 streamable HTTP）

### 代码质量

- [ ] 文件包含正确的导入，包括 Pydantic 导入
- [ ] 在适用处正确实现分页
- [ ] 为可能返回大量结果集的操作提供过滤选项
- [ ] 所有异步函数都使用 `async def` 正确定义
- [ ] HTTP client 使用遵循异步模式和正确的上下文管理器
- [ ] 全程使用类型提示
- [ ] 常量在模块级使用 UPPER_CASE 定义

### 测试

- [ ] Server 成功运行：`python your_server.py --help`
- [ ] 所有导入正确解析
- [ ] 示例 tool 调用按预期工作
- [ ] 错误场景被优雅处理
