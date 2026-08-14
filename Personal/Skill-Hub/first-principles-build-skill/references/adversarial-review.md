# 对抗性审查参考（Phase 4 / Phase 5）

## 严重度定义

| 级别 | 定义 | 处置 |
|---|---|---|
| P0 | 确定会产生错误结果、数据丢失、安全漏洞、崩溃 | 必须修复 + 复审 |
| P1 | 在可预见场景下会出错（边界、并发、错误路径），或需求明确遗漏 | 必须修复 + 复审 |
| P2 | 真实但影响有限的问题；显著的非必要复杂度 | 修复，或记录不修的理由 |
| P3 | 吹毛求疵、风格偏好 | 仅记录 |

## 审查纪律（两种模式通用）

1. **打破信心，而非确认**：你的默认假设是"这个实现是错的"，工作是找到证据。找不到证据时才允许说通过。
2. **攻击面优先级**：正确性/数据丢失 → 安全（注入、越权、密钥泄露）→ 并发/边界/错误处理 → 需求遗漏 → simplicity counterfactual → 风格（最后，且只报 P3）。
3. **material-only**：只报告会改变 ship/no-ship 决策的发现。凑数的发现会稀释真正重要的问题。
4. **证据强制**：每条发现必须带 `file:line` 和一句话复现/触发场景。没有证据的发现直接丢弃。
5. **simplicity counterfactual**：每份报告必须回答——"同样的必需行为和安全性，能否用更少的概念、层、入口或配置面实现？"能，则作为 P2 记录具体删什么。
6. **禁止泛化好评**：报告中不允许出现"整体质量不错""代码清晰"这类无信息量的句子。
7. **信息隔离**：审查者不得接触实现者的分析报告和推理叙述，只看任务需求 + 代码/diff + 测试结果。

## 模式 A — 子代理审查（默认）

用 `Agent(subagent_type="explore")` 启动新鲜上下文的只读审查者。提示词模板（按任务填充）：

```text
你是一个对抗性代码审查者（红队）。你的任务是证明下面的实现是错的，而不是确认它是对的。

## 任务需求（用户原始需求，逐字）
<粘贴用户的任务描述>

## 审查对象
工作目录：<cwd>
变更范围：<文件列表 / git diff 范围>

## 要求
1. 先读需求，再读全部变更代码及其直接调用方/被调方。
2. 按攻击面优先级找问题：正确性/数据丢失 → 安全 → 并发/边界/错误处理 → 需求遗漏 → 非必要复杂度。
3. 如项目有测试，运行相关测试并报告结果；尝试构造让实现失败的输入。
4. 每条发现：严重度(P0-P3) + file:line + 触发场景一句话。
5. 只报 material 发现（会改变 ship/no-ship 决策的）；每条必须有证据，无证据不报。
6. 最后回答 simplicity counterfactual：同样的必需行为能否用更少概念/层/配置实现？
7. 你不知道实现者的任何推理过程，也不要猜测其意图——只评判代码与需求的差距。

## 输出格式
VERDICT: SHIP / NO-SHIP
FINDINGS:
- [P0] file:line — 问题 — 触发场景
...
SIMPLICITY: <counterfactual 回答>
TESTS: <运行了什么测试，结果>
```

## 模式 B — 跨模型外部审查（`--external`）

检测与调用（在 Bash 中执行）：

```bash
# 检测：codex 优先，claude 兜底
if command -v codex >/dev/null 2>&1; then
  REVIEW_CLI=codex
elif command -v claude >/dev/null 2>&1; then
  REVIEW_CLI=claude
else
  # 输出 DEGRADED 横幅，回落模式 A
fi
```

调用前必须向用户说明将使用哪个 CLI。准备输入并调用：

```bash
# 组装审查输入：需求 + diff + 审查纪律（即本文件"审查纪律"一节全文）
git diff <base>...HEAD > /tmp/fp-review.diff   # 或收集变更文件全文

# codex 路径
codex exec --sandbox read-only "$(cat /tmp/fp-review-prompt.md)"

# claude 路径（注意：headless 需已认证；stdin 重定向 </dev/null 防挂起）
claude -p "$(cat /tmp/fp-review-prompt.md)" </dev/null
```

注意：

- diff 过大时裁剪到变更文件本身，不要整库投喂。
- 外部模型的自由文本输出由你（主会话）解析为统一的 FINDINGS 格式后落盘。
- 外部 CLI 调用失败（未认证、超时、限流）→ 告知用户失败原因，询问是回落模式 A 还是中止。

## Phase 5 复审规则

- 修复完成后，发起**新一轮独立审查**（模式 A：新开一个 explore 子代理；模式 B：再调一次 CLI），复审提示词追加：

```text
## 上一轮发现与修复对应关系
<上轮 FINDINGS 清单 + 每条的修复说明>
请验证：每条上轮发现是否真正被修复（读修复后的代码，不接受"应该修了"）；修复是否引入了新问题。
```

- 复审只查"旧发现是否闭环 + 新引入问题"，不做全量重审，除非改动面大到等于重写。
- 硬上限 3 轮（初始审查算第 1 轮）。超限仍有 P0/P1 → 停止并如实报告。

## 审查报告落盘格式

`.fp-reviews/YYYY-MM-DD-<task-slug>-review-round<N>.md`：

```markdown
# 对抗审查报告 Round <N>：<任务标题>
日期：YYYY-MM-DD ｜ 模式：subagent / external(<cli>) ｜ VERDICT: SHIP / NO-SHIP

## FINDINGS
- [P0] file:line — 问题 — 触发场景
...

## SIMPLICITY COUNTERFACTUAL
## 测试证据
## 处置记录（Round ≥2 时填写：上轮发现 → 已修复/未修复/不修理由）
```
