# Codex Handoff Skill

为项目保留可追溯的会话交接记录，而不保存会话原文。正式交接写入并可提交到
`.handoff/YYYY-MM-DD.md`；被 Git 忽略的 `.handoff/.raw/` 则保存机械化的 Git 状态快照，
作为忘记手动交接时的最佳努力保险。

## 能力与边界

- 在同一天内按会话追加或更新正式交接；重复交接会保留“人工备注”区。
- 记录 branch、HEAD、工作区状态、改动文件、diffstat、近期 commit，以及改动文件中的
  TODO/FIXME/XXX；不保存完整 diff、工具输出或会话原文。
- 新会话恢复时校验分支、HEAD 与工作区漂移；无漂移时只提出下一步，等待确认后再继续。
- `PostToolUse` 与 `SessionEnd` hook 仅运行本地 Python 脚本，不调用模型、不增加上下文，
  因此不消耗模型 token。
- 不自动执行 commit、push、reset、clean、删除或还原用户文件。

## 运行环境

- 已启用 hooks 的 Codex CLI
- Python 3.9 或更高版本
- Git
- macOS 或 Linux

## 安装

普通安装会复制 skill：

```sh
python3 install.py install --mode copy
```

开发本仓库时，建议使用软链接，更新源码后无需重新复制：

```sh
python3 install.py install --mode link
```

安装后重启 Codex，并在提示时信任 hook 命令。查询状态或卸载：

```sh
python3 install.py status
python3 install.py uninstall
```

安装器会在改动已有 `~/.codex/hooks.json` 前创建时间戳备份；卸载时只移除带
`handoff-v1` 标识的条目，不覆盖其他 hook。

## 使用方式

在需要启用保险快照的 Git 项目中执行：

```text
$handoff init
```

下班或切换会话前执行：

```text
$handoff
```

新会话恢复：

```text
$handoff resume
```

也可以直接输入 `/handoff`。它是可触发 skill 的普通文本提示，并非 Codex 的第三方内建
slash command。

## 性能与可靠性

当前 Codex 版本不支持异步 command hook，因此本 skill 使用同步、静默的 hook。每次工具
调用都会做一次轻量检查；同一会话 30 秒内命中防抖时不运行 Git，`SessionEnd` 会强制补拍。

本机实测中，强制 Git 快照约需 0.10 秒；防抖 hook 平均约 35 毫秒/次。强制杀进程、断电或
其他非正常结束仍可能丢失最近一个防抖窗口内的状态，因此 `$handoff` 生成的正式 Markdown
才是主要交接记录。
