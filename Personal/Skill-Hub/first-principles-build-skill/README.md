# first-principles-build-skill

实现完整任务的 Agent skill，做两件事：写代码之前先做第一性原理分析，写完之后必须过一轮对抗性审查。

第一性原理分析解决的是"上来就套方案"的问题。Agent 需要把任务里的假设全部列出来，区分哪些是问题的本质约束、哪些只是惯例，然后从确认无误的事实出发重新推导方案，而不是直接从记忆里的相似项目复制一个。分析结果存成文件，结论如果和用户最初的设想冲突，先确认再动手。

对抗性审查解决的是"自己审自己等于没审"的问题。审查在独立的上下文里进行：默认是新开一个只读子代理，给它需求和代码，但不给它实现者的推理过程，避免被实现者的叙述带偏。加 `--external` 则改用外部 CLI（codex 或 claude）让另一个模型来审，不同模型的盲区不同，抓得到本模型抓不到的问题；外部工具不可用时降级回子代理模式并明确提示。审查发现按 P0–P3 分级，P0/P1 必须修复后复审，最多三轮，超了就如实报告遗留风险，不允许假装通过。

分析和审查报告都落在当前工作目录的 `.fp-reviews/` 下。

## 用法

```text
/first-principles-build 实现用户认证模块
/first-principles-build --external 重构支付流程
```

也可以用自然语言触发，比如"用第一性原理做 XX，完成后对抗审查"。琐碎任务（改 typo、单行修复）不适用，skill 会提示跳过分析阶段。

## 文件

- `SKILL.md` — 主流程定义
- `references/analysis-template.md` — 第一性原理分析模板（五步）
- `references/adversarial-review.md` — 审查提示词、严重度定义、两种审查模式与复审规则

## 参考

方法上参考了几个开源项目：分析框架来自 [first-principles-skill](https://github.com/awesome-skills/first-principles-skill)；审查部分的分级标准、"只报告影响发布决策的问题"、跨模型审查的思路来自 [adversarial-review](https://github.com/robertoecf/adversarial-review)；[cc-thinking-skills](https://github.com/tjboudreaux/cc-thinking-skills) 和 [ngmeyer/skills](https://github.com/ngmeyer/skills) 提供了组织方式和"方法多样性优先于角度多样性"的依据，后者也是这里只做单审查者、不做多顾问投票的原因。

## License

MIT
