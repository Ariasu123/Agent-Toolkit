# git-commit

一个用于规范化 git 提交的 Agent Skill：分析当前工作区变更，自动拆分为原子提交，生成中文描述的 Conventional Commits 消息，逐组经用户确认后执行。

## 行为

1. 检查工作区（`git status` / `git diff`），并参考仓库近期提交风格
2. 制定提交计划：混杂变更按模块/意图拆分为多个原子提交，同功能的实现+测试保持在同一提交
3. 逐组暂存（禁止 `git add .`）、复审暂存内容（查密钥、调试残留、无关改动）
4. 撰写 `type(scope): 中文描述` 格式的消息，不加 AI 署名
5. 每组经用户确认后执行 `git commit`；pre-commit hook 失败时如实报告，不绕过

只负责 commit，不做 push / rebase / amend 等操作。

## 安装

把 `SKILL.md` 所在目录拷入对应客户端的 skills 目录：

```bash
# Kimi Code / 通用 agents skills 目录
cp -r git-commit-skill ~/.agents/skills/git-commit

# Claude Code
cp -r git-commit-skill ~/.claude/skills/git-commit
```

重启客户端后生效。

## 触发

- 显式调用：`/git-commit`，可附带范围或意图提示，如 `/git-commit 只提交 auth 模块`
- 自然语言："帮我提交"、"commit 一下当前改动"等

## 消息示例

```text
feat(auth): 增加登录失败重试与限流
fix(report): 修复周报日期跨年时的周次计算
chore: 升级依赖并同步 lock 文件
```

## 许可

MIT
