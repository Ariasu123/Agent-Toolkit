# MCP Server Evaluation 指南

## 概述

本文档提供为 MCP server 创建 comprehensive evaluations 的指导。Evaluations 用于测试 LLM 能否仅使用提供的 tool，有效地通过你的 MCP server 回答真实且复杂的问题。

---

## 快速参考

### Evaluation 要求
- 创建 10 个人类可读的问题
- 问题必须是 READ-ONLY、INDEPENDENT、NON-DESTRUCTIVE
- 每个问题需要多次 tool 调用（可能多达数十次）
- 答案必须是单一、可验证的值
- 答案必须是 STABLE（不会随时间变化）

### 输出格式
```xml
<evaluation>
   <qa_pair>
      <question>Your question here</question>
      <answer>Single verifiable answer</answer>
   </qa_pair>
</evaluation>
```

---

## Evaluations 的目的

衡量 MCP server 质量的标准，不在于 server 实现 tool 的完善程度，而在于这些实现（input/output schema、docstring/description、功能）能否使 LLM 在没有其他上下文、仅访问 MCP server 的情况下，回答真实且困难的问题。

## Evaluation 概览

创建 10 个人类可读的问题，要求仅使用 READ-ONLY、INDEPENDENT、NON-DESTRUCTIVE 和 IDEMPOTENT 操作来回答。每个问题应满足：
- 真实可信
- 清晰简洁
- 无歧义
- 复杂，可能需要数十次 tool 调用或步骤
- 可提前确定一个单一、可验证的答案

## 问题设计指南

### 核心要求

1. **问题必须相互独立**
   - 每个问题不应依赖其他问题的答案
   - 不应假设处理其他问题时已经执行过写操作

2. **问题必须仅要求 NON-DESTRUCTIVE 和 IDEMPOTENT 的 tool 使用**
   - 不应指示或要求修改状态以得到正确答案

3. **问题必须真实、清晰、简洁且复杂**
   - 必须需要另一个 LLM 使用多个（可能多达数十个）tool 或步骤来回答

### 复杂度与深度

4. **问题必须需要深入探索**
   - 考虑多跳问题，需要多个子问题和顺序 tool 调用
   - 每一步都应从之前步骤获得的信息中受益

5. **问题可能需要大量分页**
   - 可能需要遍历多页结果
   - 可能需要查询旧数据（1-2 年前）以找到冷门信息
   - 问题必须足够困难

6. **问题必须需要深度理解**
   - 而非停留在表层知识
   - 可将复杂观点设计为 True/False 问题，要求提供证据
   - 可使用多选题格式，LLM 需要搜索不同假设

7. **问题不能通过直接的关键词搜索解决**
   - 不要包含目标内容中的具体关键词
   - 使用同义词、相关概念或改写
   - 需要多次搜索、分析多个相关项、提取上下文，然后推导出答案

### Tool 测试

8. **问题应 stress-test tool 的返回值**
   - 可能触发返回大型 JSON 对象或列表的 tool，使 LLM 不堪重负
   - 应要求理解多种数据形态：
     - ID 和名称
     - 时间戳和日期时间（月、日、年、秒）
     - 文件 ID、名称、扩展名和 mimetype
     - URL、GID 等
   - 应测试 tool 返回所有有用数据形式的能力

9. **问题应主要反映真实的人类使用场景**
   - 即人类在 LLM 辅助下真正关心的信息检索任务

10. **问题可能需要数十次 tool 调用**
    - 这对上下文有限的 LLM 构成挑战
    - 促使 MCP server tool 减少返回的信息量

11. **包含具有一定歧义的问题**
    - 可能是歧义的，或需要艰难决策来选择调用哪些 tool
    - 迫使 LLM 可能犯错或误解
    - 确保尽管存在歧义，仍然有单一可验证的答案

### 稳定性

12. **问题必须设计成答案不会变化**
    - 不要问依赖"当前状态"的动态问题
    - 例如，不要统计：
      - 帖子的 reaction 数量
      - 线程的回复数量
      - 频道成员数量

13. **不要让 MCP server 限制你创建的问题类型**
    - 创建具有挑战性和复杂性的问题
    - 有些问题可能无法用现有 MCP server tool 解决
    - 问题可能要求特定输出格式（datetime vs. epoch time，JSON vs. MARKDOWN）
    - 问题可能需要数十次 tool 调用才能完成

## 答案设计指南

### 可验证性

1. **答案必须可通过直接字符串比较验证**
   - 如果答案可以用多种格式重写，在问题中明确指定输出格式
   - 例如："使用 YYYY/MM/DD。"、"回答 True 或 False。"、"仅回答 A、B、C 或 D。"
   - 答案应为单一可验证值，例如：
     - User ID、user name、display name、first name、last name
     - Channel ID、channel name
     - Message ID、字符串
     - URL、标题
     - 数值
     - 时间戳、日期时间
     - 布尔值（针对 True/False 问题）
     - Email address、phone number
     - File ID、file name、file extension
     - 多选题答案
   - 答案不应需要特殊格式或复杂的结构化输出
   - 将使用 DIRECT STRING COMPARISON 验证答案

### 可读性

2. **答案通常应优先使用人类可读格式**
   - 例如：名称、名字、姓氏、日期时间、文件名、消息字符串、URL、yes/no、true/false、a/b/c/d
   - 而非不透明的 ID（但 ID 也可接受）
   - 绝大多数答案应为人类可读

### 稳定性

3. **答案必须是 STABLE/STATIONARY**
   - 查看旧内容（例如已结束的对话、已上线的项目、已回答的问题）
   - 基于"已闭环"的概念创建问题，这些概念始终返回相同答案
   - 问题可要求考虑固定时间窗口，以避免非稳定答案
   - 依赖不太可能变化的上下文
   - 例如：如果查找论文名称，要足够具体，以免与之后发表的论文混淆

4. **答案必须清晰且无歧义**
   - 问题必须设计成只有一个清晰的答案
   - 答案可以通过使用 MCP server tool 推导得出

### 多样性

5. **答案必须多样化**
   - 答案应为单一可验证值，形态和格式多样
   - User 概念：user ID、user name、display name、first name、last name、email address、phone number
   - Channel 概念：channel ID、channel name、channel topic
   - Message 概念：message ID、message string、timestamp、month、day、year

6. **答案不能是复杂结构**
   - 不是值列表
   - 不是复杂对象
   - 不是 ID 或字符串列表
   - 不是自然语言文本
   - 除非答案可以方便地通过 DIRECT STRING COMPARISON 验证
   - 并且能够真实地被复现
   - LLM 不太可能以其他顺序或格式返回相同列表

## Evaluation 流程

### 步骤 1：文档检查

阅读目标 API 的文档以了解：
- 可用 endpoint 和功能
- 如果存在歧义，从网络获取更多信息
- 尽可能并行化此步骤
- 确保每个 subagent 仅检查文件系统或网络上的文档

### 步骤 2：Tool 检查

列出 MCP server 中可用的 tool：
- 直接检查 MCP server
- 理解 input/output schema、docstring 和 description
- 此阶段不要实际调用 tool

### 步骤 3：建立理解

重复步骤 1 和 2，直到形成良好理解：
- 多次迭代
- 思考你想创建的任务类型
- 精炼你的理解
- 任何阶段都不要读取 MCP server 实现本身的代码
- 运用直觉和理解，创建合理、真实但极具挑战性的任务

### 步骤 4：只读内容检查

理解 API 和 tool 后，使用 MCP server tool：
- 仅使用 READ-ONLY 和 NON-DESTRUCTIVE 操作检查内容
- 目标：识别具体内容（例如 user、channel、message、project、task），用于创建真实问题
- 不应调用任何修改状态的工具
- 不会读取 MCP server 实现本身的代码
- 通过独立 sub-agent 并行化此步骤，各自进行独立探索
- 确保每个 subagent 仅执行 READ-ONLY、NON-DESTRUCTIVE 和 IDEMPOTENT 操作
- 注意：某些 tool 可能返回大量数据，导致上下文耗尽
- 进行增量、小范围、有针对性的 tool 调用来探索
- 在所有 tool 调用请求中使用 `limit` 参数限制结果数量（<10）
- 使用分页

### 步骤 5：任务生成

检查内容后，创建 10 个人类可读的问题：
- LLM 应能借助 MCP server 回答这些问题
- 遵循以上所有问题和答案指南

## 输出格式

每个 QA pair 包含一个问题和一个答案。输出应为具有以下结构的 XML 文件：

```xml
<evaluation>
   <qa_pair>
      <question>Find the project created in Q2 2024 with the highest number of completed tasks. What is the project name?</question>
      <answer>Website Redesign</answer>
   </qa_pair>
   <qa_pair>
      <question>Search for issues labeled as "bug" that were closed in March 2024. Which user closed the most issues? Provide their username.</question>
      <answer>sarah_dev</answer>
   </qa_pair>
   <qa_pair>
      <question>Look for pull requests that modified files in the /api directory and were merged between January 1 and January 31, 2024. How many different contributors worked on these PRs?</question>
      <answer>7</answer>
   </qa_pair>
   <qa_pair>
      <question>Find the repository with the most stars that was created before 2023. What is the repository name?</question>
      <answer>data-pipeline</answer>
   </qa_pair>
</evaluation>
```

## Evaluation 示例

### 好问题

**示例 1：需要深入探索的多跳问题（GitHub MCP）**
```xml
<qa_pair>
   <question>Find the repository that was archived in Q3 2023 and had previously been the most forked project in the organization. What was the primary programming language used in that repository?</question>
   <answer>Python</answer>
</qa_pair>
```

这个问题很好，因为：
- 需要多次搜索找到已归档 repository
- 需要识别归档前 fork 数最多的项目
- 需要检查 repository 详情以确定语言
- 答案是简单、可验证的值
- 基于历史（已闭环）数据，不会变化

**示例 2：需要理解上下文而不依赖关键词匹配（项目管理 MCP）**
```xml
<qa_pair>
   <question>Locate the initiative focused on improving customer onboarding that was completed in late 2023. The project lead created a retrospective document after completion. What was the lead's role title at that time?</question>
   <answer>Product Manager</answer>
</qa_pair>
```

这个问题很好，因为：
- 不使用具体项目名称（"focused on improving customer onboarding"）
- 需要找到特定时间段内已完成的项目
- 需要识别 project lead 及其角色
- 需要从 retrospective document 中理解上下文
- 答案人类可读且稳定
- 基于已完成的工作（不会变化）

**示例 3：需要多步复杂聚合（Issue Tracker MCP）**
```xml
<qa_pair>
   <question>Among all bugs reported in January 2024 that were marked as critical priority, which assignee resolved the highest percentage of their assigned bugs within 48 hours? Provide the assignee's username.</question>
   <answer>alex_eng</answer>
</qa_pair>
```

这个问题很好，因为：
- 需要按日期、优先级和状态过滤 bug
- 需要按 assignee 分组并计算解决率
- 需要理解时间戳以确定 48 小时窗口
- 测试分页能力（可能需要处理大量 bug）
- 答案是单一 username
- 基于特定时间段的历史数据

**示例 4：需要跨多种数据类型综合（CRM MCP）**
```xml
<qa_pair>
   <question>Find the account that upgraded from the Starter to Enterprise plan in Q4 2023 and had the highest annual contract value. What industry does this account operate in?</question>
   <answer>Healthcare</answer>
</qa_pair>
```

这个问题很好，因为：
- 需要理解 subscription tier 变更
- 需要在特定时间范围内识别 upgrade 事件
- 需要比较 contract value
- 必须访问 account industry 信息
- 答案简单且可验证
- 基于已完成的历史交易

### 差问题

**示例 1：答案会随时间变化**
```xml
<qa_pair>
   <question>How many open issues are currently assigned to the engineering team?</question>
   <answer>47</answer>
</qa_pair>
```

这个问题很差，因为：
- 随着 issue 被创建、关闭或重新分配，答案会变化
- 不基于稳定/静止数据
- 依赖动态的"当前状态"

**示例 2：关键词搜索即可解决，过于简单**
```xml
<qa_pair>
   <question>Find the pull request with title "Add authentication feature" and tell me who created it.</question>
   <answer>developer123</answer>
</qa_pair>
```

这个问题很差，因为：
- 可通过直接搜索 exact title 解决
- 不需要深入探索或理解
- 不需要综合或分析

**示例 3：答案格式不明确**
```xml
<qa_pair>
   <question>List all the repositories that have Python as their primary language.</question>
   <answer>repo1, repo2, repo3, data-pipeline, ml-tools</answer>
</qa_pair>
```

这个问题很差，因为：
- 答案是列表，可能以任意顺序返回
- 难以通过直接字符串比较验证
- LLM 可能以不同格式返回（JSON 数组、逗号分隔、换行分隔）
- 更好的是询问特定聚合（count）或极值（most stars）

## 验证流程

创建 evaluations 后：

1. **检查 XML 文件**，理解 schema
2. **并行加载每个任务指令**，使用 MCP server 和 tool 自行尝试解答，找出正确答案
3. **标记任何需要 WRITE 或 DESTRUCTIVE 操作**的步骤
4. **汇总所有正确答案**，替换文档中不正确的答案
5. **移除任何需要 WRITE 或 DESTRUCTIVE 操作**的 `<qa_pair>`

记住要并行化任务解答，以避免上下文耗尽，然后汇总所有答案，最后一次性修改文件。

## 创建高质量 Evaluation 的技巧

1. 在生成任务前**认真思考并提前规划**
2. 有机会时**并行化**以加速过程并管理上下文
3. **聚焦真实使用场景**，即人类实际想要完成的任务
4. **创建具有挑战性的问题**，测试 MCP server 的能力边界
5. 使用历史数据和已闭环概念**确保稳定性**
6. 使用 MCP server tool 自行解答问题，**验证答案**
7. 根据过程中学到的内容**迭代和优化**

---

# 运行 Evaluations

创建 evaluation 文件后，可以使用提供的 evaluation harness 测试你的 MCP server。

## 环境准备

1. **安装依赖**

   ```bash
   pip install -r scripts/requirements.txt
   ```

   或手动安装：
   ```bash
   pip install mcp
   ```

2. **设置 API Key**

   ```bash
   export API_KEY=your_api_key_here
   ```

## Evaluation 文件格式

Evaluation 文件使用 XML 格式，包含 `<qa_pair>` 元素：

```xml
<evaluation>
   <qa_pair>
      <question>Find the project created in Q2 2024 with the highest number of completed tasks. What is the project name?</question>
      <answer>Website Redesign</answer>
   </qa_pair>
   <qa_pair>
      <question>Search for issues labeled as "bug" that were closed in March 2024. Which user closed the most issues? Provide their username.</question>
      <answer>sarah_dev</answer>
   </qa_pair>
</evaluation>
```

## 运行 Evaluations

evaluation 脚本（`scripts/evaluation.py`）支持三种 transport 类型：

**重要说明：**
- **stdio transport**：evaluation 脚本会自动启动并管理 MCP server 进程。不要手动运行 server。
- **sse/http transports**：你必须在运行 evaluation 前单独启动 MCP server。脚本会连接到指定 URL 上已在运行的 server。

### 1. 本地 STDIO Server

对于本地运行的 MCP server（脚本会自动启动 server）：

```bash
python scripts/evaluation.py \
  -t stdio \
  -c python \
  -a my_mcp_server.py \
  evaluation.xml
```

带环境变量：
```bash
python scripts/evaluation.py \
  -t stdio \
  -c python \
  -a my_mcp_server.py \
  -e API_KEY=abc123 \
  -e DEBUG=true \
  evaluation.xml
```

### 2. Server-Sent Events (SSE)

对于基于 SSE 的 MCP server（你必须先启动 server）：

```bash
python scripts/evaluation.py \
  -t sse \
  -u https://example.com/mcp \
  -H "Authorization: Bearer token123" \
  -H "X-Custom-Header: value" \
  evaluation.xml
```

### 3. HTTP (Streamable HTTP)

对于基于 HTTP 的 MCP server（你必须先启动 server）：

```bash
python scripts/evaluation.py \
  -t http \
  -u https://example.com/mcp \
  -H "Authorization: Bearer token123" \
  evaluation.xml
```

## 命令行选项

```
usage: evaluation.py [-h] [-t {stdio,sse,http}] [-m MODEL] [-c COMMAND]
                     [-a ARGS [ARGS ...]] [-e ENV [ENV ...]] [-u URL]
                     [-H HEADERS [HEADERS ...]] [-o OUTPUT]
                     eval_file

positional arguments:
  eval_file             Path to evaluation XML file

optional arguments:
  -h, --help            Show help message
  -t, --transport       Transport type: stdio, sse, or http (default: stdio)
  -m, --model           AI model to use (default: gpt-4o)
  -o, --output          Output file for report (default: print to stdout)

stdio options:
  -c, --command         Command to run MCP server (e.g., python, node)
  -a, --args            Arguments for the command (e.g., server.py)
  -e, --env             Environment variables in KEY=VALUE format

sse/http options:
  -u, --url             MCP server URL
  -H, --header          HTTP headers in 'Key: Value' format
```

## 输出

evaluation 脚本生成一份详细报告，包括：

- **汇总统计**：
  - 准确率（correct/total）
  - 平均任务耗时
  - 每个任务平均 tool 调用次数
  - 总 tool 调用次数

- **每个任务的结果**：
  - Prompt 和期望回答
  - Agent 的实际回答
  - 答案是否正确（✅/❌）
  - 耗时和 tool 调用详情
  - Agent 对其方法的总结
  - Agent 对 tool 的反馈

### 保存报告到文件

```bash
python scripts/evaluation.py \
  -t stdio \
  -c python \
  -a my_server.py \
  -o evaluation_report.md \
  evaluation.xml
```

## 完整示例工作流

以下是创建和运行 evaluation 的完整示例：

1. **创建 evaluation 文件**（`my_evaluation.xml`）：

```xml
<evaluation>
   <qa_pair>
      <question>Find the user who created the most issues in January 2024. What is their username?</question>
      <answer>alice_developer</answer>
   </qa_pair>
   <qa_pair>
      <question>Among all pull requests merged in Q1 2024, which repository had the highest number? Provide the repository name.</question>
      <answer>backend-api</answer>
   </qa_pair>
   <qa_pair>
      <question>Find the project that was completed in December 2023 and had the longest duration from start to finish. How many days did it take?</question>
      <answer>127</answer>
   </qa_pair>
</evaluation>
```

2. **安装依赖**：

```bash
pip install -r scripts/requirements.txt
export API_KEY=your_api_key
```

3. **运行 evaluation**：

```bash
python scripts/evaluation.py \
  -t stdio \
  -c python \
  -a github_mcp_server.py \
  -e GITHUB_TOKEN=ghp_xxx \
  -o github_eval_report.md \
  my_evaluation.xml
```

4. **查看报告** `github_eval_report.md`：
   - 查看哪些问题通过/失败
   - 阅读 agent 对 tool 的反馈
   - 识别改进空间
   - 迭代优化 MCP server 设计

## 故障排查

### 连接错误

如果遇到连接错误：
- **STDIO**：检查命令和参数是否正确
- **SSE/HTTP**：检查 URL 是否可访问，headers 是否正确
- 确保所需的 API key 已设置在环境变量或 headers 中

### 准确率过低

如果很多 evaluation 失败：
- 查看每个任务的 agent 反馈
- 检查 tool description 是否清晰完整
- 验证 input parameter 是否文档化良好
- 考虑 tool 返回的数据是否过多或过少
- 确保错误信息具有可操作性

### 超时问题

如果任务超时：
- 使用更强的模型（例如 `gpt-4o`）
- 检查 tool 是否返回过多数据
- 验证分页是否正常工作
- 考虑简化复杂问题
