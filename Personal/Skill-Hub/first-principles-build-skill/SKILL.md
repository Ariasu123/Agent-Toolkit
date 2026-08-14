---
name: first-principles-build
version: "0.1.0"
description: "Implement a task with first-principles analysis before coding and adversarial review after coding, with auto-fix re-review loops. Use when the user says 用第一性原理做 / first-principles / 对抗审查 / adversarial review, or invokes /first-principles-build."
argument-hint: "first-principles-build <任务描述> [--external]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
homepage: https://github.com/ariasu/first-principles-build-skill
repository: https://github.com/ariasu/first-principles-build-skill
author: ariasu
license: MIT
user-invocable: true
---

# first-principles-build v0.1.0

用这套流程执行**非平凡**的实现任务：

```
Phase 1  第一性原理分析（写代码前，落盘）
Phase 2  方案确认（仅当分析推翻用户原设想时）
Phase 3  实现
Phase 4  对抗性审查（子代理模式 / --external 跨模型模式，落盘）
Phase 5  修复 + 复审循环（≤3 轮，P0/P1 必须清零）
```

## 适用边界

- 适用：新功能、架构决策、重构、涉及多个文件的修改、用户明确要求严格流程的任务。
- 不适用：改 typo、单行修复、纯问答、一次性脚本。如果用户在此类任务上触发了本 skill，先提示"此任务无需完整流程"并询问是否跳过 Phase 1 直接实现。

## 参数

- 默认：子代理审查模式（`Agent(subagent_type="explore")`，新鲜上下文，只读红队）。
- `--external`：跨模型审查模式，调用外部 CLI（检测顺序：`codex` → `claude`）。每次调用前必须向用户说明将调用哪个 CLI。两者都不可用时输出 DEGRADED 横幅并回落到子代理模式：

```text
⚠️  DEGRADED MODE: 未检测到 codex / claude CLI，跨模型审查不可用，回落到同模型子代理审查。同源偏见风险由用户知悉。
```

## Phase 1 — 第一性原理分析

严格按 `references/analysis-template.md` 的 5 步执行：

1. **问题本质** — 剥掉实现细节，回答"用户真正要解决的问题是什么、成功的判据是什么"。
2. **假设审计** — 列出任务描述和你自己脑补中的所有假设，逐条挑战：这是物理/本质约束，还是惯例约束？用表格呈现（Assumption / Challenge / Verdict）。
3. **不可约事实（Ground Truths）** — 只保留不依赖任何框架、库、惯例就能成立的事实。
4. **向上推理** — 从 Ground Truths 重新构建方案，禁止"因为业界都这么做"这类类比推理出现在推理链中。
5. **验证推理链** — 方案中的每个决策必须能回溯到某条 Ground Truth 或用户明示的需求；回溯不了的标记为"惯例选择"并说明理由。

产出写入 `<当前工作目录>/.fp-reviews/YYYY-MM-DD-<task-slug>-analysis.md`（先 `mkdir -p`），对话中只给摘要。

## Phase 2 — 方案确认

仅当 Phase 1 的结论**推翻了用户原始设想**（更简单的路径、不需要的方案、不同的技术选型）时，停下来向用户确认后再动手。分析结论与原设想一致时直接进入 Phase 3，不要打断用户。

## Phase 3 — 实现

正常编码。遵循项目现有规范，最小改动，有测试补测试。实现过程不因为有 skill 在身就过度设计——第一性原理的结论之一是"必要的复杂度才保留"。

## Phase 4 — 对抗性审查

审查提示词、P0–P3 定义、外部 CLI 调用片段见 `references/adversarial-review.md`。核心规则：

- **打破信心，而非确认**：审查者的任务是证明实现是错的，不是证明它是对的。
- **审查者只看到任务需求 + 代码/diff，看不到你的分析过程和推理**，防止被你的叙述说服。
- 攻击面优先级：正确性/数据丢失 → 安全 → 并发/边界 → 需求遗漏 → simplicity counterfactual（同样行为能否用更少概念/层/配置实现）→ 风格最后。
- material-only：只报告会改变 ship/no-ship 决策的发现，每条发现必须带 `file:line` 证据。
- 子代理模式：`Agent(subagent_type="explore")`（只读、可跑测试、不能改代码）。
- external 模式：把需求 + diff + 审查提示词发给 `codex exec` 或 `claude -p`，把返回解析成统一的发现格式。

产出写入 `.fp-reviews/YYYY-MM-DD-<task-slug>-review-round<N>.md`。

## Phase 5 — 修复 + 复审循环

- **P0/P1**：必须修复，然后发起新一轮独立复审（新开子代理 / 再调一次外部 CLI，不是让原审查者自我确认）。
- **P2**：修复，或在报告中明确记录不修复的理由。
- **P3**：仅记录。
- **硬上限 3 轮**。3 轮后仍有 P0/P1：停止，向用户如实报告遗留风险，**绝不假装通过**。

## 收尾

对话中输出最终摘要，包含：分析核心结论一句话、审查轮数与模式、各轮修复的问题数、遗留 P2/P3 清单、报告文件路径。保持简洁，不复述报告全文。

## 反模式（禁止）

- 把 Phase 1 写成流水账复述需求——假设审计表至少 3 行，否则说明任务太简单，不该走本流程。
- 审查者和实现者是同一个上下文（自我审查无效，同模型盲区不变）。
- 审查报告出现"总体不错，建议……"这类无证据的泛化结论。
- 修复后不复审就宣布完成。
- 为了显得流程完整而在分析中虚构不存在的权衡。
