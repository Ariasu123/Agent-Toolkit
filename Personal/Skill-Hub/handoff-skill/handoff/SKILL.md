---
name: handoff
description: Capture, update, and resume project session handoffs for Codex using tracked `.handoff/YYYY-MM-DD.md` summaries plus local Git-state snapshots. Use when the user invokes `$handoff`, writes `/handoff`, asks to initialize handoff tracking, wants an end-of-session recap, or asks to read a handoff and continue unfinished work in a fresh session.
---

# Handoff

Use the bundled `scripts/handoff.py` for deterministic state capture, session selection,
Markdown upsert, and drift checks. Resolve `<skill-dir>` to the directory containing this
`SKILL.md`; do not assume the project working directory contains the script.

## Choose the operation

- Treat no argument, `write`, recap requests, and textual `/handoff` as **write**.
- Treat `init` as **initialize only**.
- Treat `resume`, “read the latest handoff”, and “continue from handoff” as **resume**.

## Initialize

Run:

```sh
python3 <skill-dir>/scripts/handoff.py init --root "$PWD" --json
```

Report whether the project is Git-backed and whether an outer ignore rule hides `.handoff/`.
Do not edit the repository root `.gitignore`.

## Write a handoff

1. Run `init`, then force a current mechanical snapshot:

   ```sh
   python3 <skill-dir>/scripts/handoff.py capture --root "$PWD" --event manual --force --json
   ```

2. Summarize only facts supported by the current session and inspected project state. Build a
   Markdown body with exactly these generated headings:

   - `### 当前目标`
   - `### 已完成事项与证据`
   - `### 决策与理由`
   - `### 工作区与验证状态`
   - `### 未完成任务与下一步`
   - `### 阻塞、风险与未知项`
   - `### 恢复指令`

   Use project-relative paths, commit IDs, and exact verification commands. Use `- [ ]` for
   unfinished items. Never include a full diff, transcript, hidden reasoning, credentials, or
   unsupported claims.

3. Write that body to a temporary Markdown file under `.handoff/.raw/`, then run:

   ```sh
   python3 <skill-dir>/scripts/handoff.py upsert --root "$PWD" --body-file <draft-file> --json
   ```

4. Report the resulting formal handoff path and warn if it is ignored. Do not commit, push,
   delete, restore, or clean project files.

## Resume from a handoff

Run the read-only drift check, passing a date or session key when supplied:

```sh
python3 <skill-dir>/scripts/handoff.py resume --root "$PWD" --json
```

Interpret the JSON result:

- `selection_required`: present the candidates and ask the user to choose.
- `hard`: stop; describe the exact branch, HEAD, operation, or workspace differences.
- `soft`: mention that only `.handoff/**` commits advanced HEAD.
- `none`: present the saved goal, first unchecked item, and the exact action you propose.
- `degraded`: explain that only a mechanical raw snapshot exists; do not reconstruct missing
  decisions or conversation.
- `limited`: explain that non-Git drift validation is unavailable.

Always wait for explicit confirmation before modifying the project after a resume request.
Continue only within the original recorded scope; request new authority for broader or risky work.

## Safety rules

- Keep `.handoff/*.md` trackable and `.handoff/.raw/` ignored.
- Preserve text inside the generated handoff's manual-notes markers on repeated writes.
- Never auto-commit, push, reset, clean, delete user work, or overwrite an unrecognized handoff.
- Treat hook snapshots as best effort: abrupt process death can lose the most recent interval.
