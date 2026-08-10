#!/usr/bin/env python3
"""Deterministic local runtime for the Codex handoff skill."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable


SCHEMA_VERSION = 1
DEFAULT_CONFIG = {
    "version": SCHEMA_VERSION,
    "enabled": True,
    "retention_days": 30,
    "debounce_seconds": 30,
}
MAX_TODOS = 50
MAX_TODO_LINE = 300
MAX_TODO_FILE_BYTES = 1024 * 1024
GIT_TIMEOUT_SECONDS = 0.75
SESSION_BEGIN = "<!-- handoff:session={key} begin -->"
SESSION_END = "<!-- handoff:session={key} end -->"
MANUAL_BEGIN = "<!-- handoff:manual begin -->"
MANUAL_END = "<!-- handoff:manual end -->"
STATE_PREFIX = "<!-- handoff:state "
TODO_RE = re.compile(r"\b(?:TODO|FIXME|XXX)\b", re.IGNORECASE)
REQUIRED_HEADINGS = (
    "### 当前目标",
    "### 已完成事项与证据",
    "### 决策与理由",
    "### 工作区与验证状态",
    "### 未完成任务与下一步",
    "### 阻塞、风险与未知项",
    "### 恢复指令",
)


class HandoffError(RuntimeError):
    pass


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def run_git(root: Path, args: list[str], timeout: float = GIT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def git_text(root: Path, args: list[str], timeout: float = GIT_TIMEOUT_SECONDS) -> str:
    result = run_git(root, args, timeout)
    if result.returncode != 0:
        return ""
    return result.stdout.rstrip("\n")


def git_root(path: Path) -> Path | None:
    try:
        result = run_git(path, ["rev-parse", "--show-toplevel"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).resolve()


def find_opted_in_root(path: Path) -> Path | None:
    current = path.resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / ".handoff" / "config.json"
        config = read_json(config_path)
        if config and config.get("enabled") is True:
            return candidate
    return None


def workspace_root(path: Path) -> tuple[Path, bool]:
    root = git_root(path)
    return (root, True) if root else (path.resolve(), False)


def load_config(root: Path) -> dict[str, Any]:
    value = read_json(root / ".handoff" / "config.json")
    if value is None:
        raise HandoffError("missing or invalid .handoff/config.json")
    config = dict(DEFAULT_CONFIG)
    config.update(value)
    if config.get("version") != SCHEMA_VERSION:
        raise HandoffError(f"unsupported handoff config version: {config.get('version')}")
    if not isinstance(config.get("retention_days"), int) or config["retention_days"] < 1:
        raise HandoffError("retention_days must be a positive integer")
    if not isinstance(config.get("debounce_seconds"), int) or config["debounce_seconds"] < 0:
        raise HandoffError("debounce_seconds must be a non-negative integer")
    return config


def session_key(raw_session_id: str | None = None) -> str:
    value = raw_session_id or os.environ.get("CODEX_THREAD_ID") or "unknown-session"
    digest = hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:12]
    return f"codex-{digest}"


def hook_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.buffer.read(1024 * 1024)
        value = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def payload_cwd(payload: dict[str, Any]) -> Path:
    for key in ("cwd", "codex_cwd", "project_root"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return Path(value)
    return Path.cwd()


def payload_session_id(payload: dict[str, Any]) -> str | None:
    for key in ("session_id", "thread_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return os.environ.get("CODEX_THREAD_ID")


def acquire_lock(path: Path, wait_seconds: float) -> Any | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.01)


def normalize_nul(raw: str) -> list[str]:
    return [part for part in raw.split("\0") if part]


def changed_paths(root: Path) -> list[str]:
    tracked = git_text(
        root,
        ["diff", "--name-only", "-z", "HEAD", "--", ".", ":(exclude).handoff/**"],
    )
    if not tracked and not git_text(root, ["rev-parse", "--verify", "HEAD"]):
        tracked = git_text(root, ["ls-files", "-z", "--", ".", ":(exclude).handoff/**"])
    untracked = git_text(
        root,
        ["ls-files", "--others", "--exclude-standard", "-z", "--", ".", ":(exclude).handoff/**"],
    )
    result: list[str] = []
    seen: set[str] = set()
    for item in normalize_nul(tracked) + normalize_nul(untracked):
        if item not in seen and not item.startswith(".handoff/"):
            seen.add(item)
            result.append(item)
    return result


def collect_todos(root: Path, paths: Iterable[str]) -> list[dict[str, Any]]:
    todos: list[dict[str, Any]] = []
    for relative in paths:
        if len(todos) >= MAX_TODOS:
            break
        path = root / relative
        try:
            if not path.is_file() or path.stat().st_size > MAX_TODO_FILE_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", "replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if TODO_RE.search(line):
                todos.append({"path": relative, "line": number, "text": line.strip()[:MAX_TODO_LINE]})
                if len(todos) >= MAX_TODOS:
                    break
    return todos


def git_operation(root: Path) -> str | None:
    candidates = (
        ("merge", "MERGE_HEAD"),
        ("rebase", "rebase-merge"),
        ("rebase", "rebase-apply"),
        ("cherry-pick", "CHERRY_PICK_HEAD"),
        ("revert", "REVERT_HEAD"),
        ("bisect", "BISECT_LOG"),
    )
    for name, marker in candidates:
        value = git_text(root, ["rev-parse", "--git-path", marker])
        marker_path = Path(value) if Path(value).is_absolute() else root / value
        if value and marker_path.exists():
            return name
    return None


def build_snapshot(root: Path, key: str, event: str) -> dict[str, Any]:
    branch = git_text(root, ["symbolic-ref", "--quiet", "--short", "HEAD"]) or None
    head = git_text(root, ["rev-parse", "--verify", "HEAD"]) or None
    status = git_text(
        root,
        ["status", "--porcelain=v2", "--branch", "--untracked-files=all", "--", ".", ":(exclude).handoff/**"],
    )
    staged = git_text(root, ["diff", "--cached", "--name-status", "--", ".", ":(exclude).handoff/**"])
    unstaged = git_text(root, ["diff", "--name-status", "--", ".", ":(exclude).handoff/**"])
    untracked = git_text(
        root,
        ["ls-files", "--others", "--exclude-standard", "--", ".", ":(exclude).handoff/**"],
    )
    diffstat_parts = [
        git_text(root, ["diff", "--cached", "--stat", "--", ".", ":(exclude).handoff/**"]),
        git_text(root, ["diff", "--stat", "--", ".", ":(exclude).handoff/**"]),
    ]
    operation = git_operation(root)
    workspace_lines = [line for line in status.splitlines() if not line.startswith("# ")]
    workspace_source = json_dump({"status": workspace_lines, "operation": operation})
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": iso_now(),
        "capture_epoch": time.time(),
        "event": event,
        "session_key": key,
        "branch": branch,
        "head": head,
        "operation": operation,
        "git_status": status,
        "name_status": {
            "staged": staged.splitlines() if staged else [],
            "unstaged": unstaged.splitlines() if unstaged else [],
            "untracked": untracked.splitlines() if untracked else [],
        },
        "diffstat": "\n".join(part for part in diffstat_parts if part),
        "recent_commits": git_text(root, ["log", "-5", "--pretty=format:%h%x09%cs%x09%s"]).splitlines(),
        "todos": collect_todos(root, changed_paths(root)),
        "workspace_fingerprint": hashlib.sha256(workspace_source.encode("utf-8")).hexdigest(),
    }
    return snapshot


def cleanup_raw(raw_dir: Path, retention_days: int) -> None:
    cutoff = now_local().date() - dt.timedelta(days=retention_days)
    for path in raw_dir.glob("????-??-??.jsonl"):
        try:
            file_date = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            try:
                path.unlink()
            except OSError:
                pass
    sessions = raw_dir / "sessions"
    cutoff_epoch = time.time() - retention_days * 86400
    for path in sessions.glob("*.json") if sessions.exists() else ():
        value = read_json(path)
        if value and float(value.get("capture_epoch", cutoff_epoch + 1)) < cutoff_epoch:
            try:
                path.unlink()
            except OSError:
                pass


def save_snapshot(root: Path, snapshot: dict[str, Any], previous: dict[str, Any] | None) -> None:
    raw_dir = root / ".handoff" / ".raw"
    sessions = raw_dir / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    session_path = sessions / f"{snapshot['session_key']}.json"
    atomic_write(session_path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    if not previous or previous.get("workspace_fingerprint") != snapshot.get("workspace_fingerprint") or previous.get("head") != snapshot.get("head") or previous.get("branch") != snapshot.get("branch"):
        journal = raw_dir / f"{now_local().date().isoformat()}.jsonl"
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json_dump(snapshot) + "\n")
        os.chmod(journal, 0o600)


def capture(root: Path, key: str, event: str, force: bool = False) -> dict[str, Any] | None:
    config = load_config(root)
    if not config.get("enabled"):
        return None
    raw_dir = root / ".handoff" / ".raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    lock = acquire_lock(raw_dir / ".lock", 0.5 if force else 0.1)
    if lock is None:
        return None
    try:
        session_path = raw_dir / "sessions" / f"{key}.json"
        previous = read_json(session_path)
        if not force and previous:
            elapsed = time.time() - float(previous.get("capture_epoch", 0))
            if elapsed < int(config["debounce_seconds"]):
                return previous
        actual_root = git_root(root)
        if actual_root != root.resolve():
            return None
        snapshot = build_snapshot(root, key, event)
        save_snapshot(root, snapshot, previous)
        cleanup_raw(raw_dir, int(config["retention_days"]))
        return snapshot
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def init_project(requested: Path) -> dict[str, Any]:
    root, is_git = workspace_root(requested)
    handoff_dir = root / ".handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    config_path = handoff_dir / "config.json"
    if config_path.exists():
        config = load_config(root)
    else:
        config = dict(DEFAULT_CONFIG)
        atomic_write(config_path, json.dumps(config, ensure_ascii=False, indent=2) + "\n", 0o644)
    ignore_path = handoff_dir / ".gitignore"
    if ignore_path.exists():
        lines = ignore_path.read_text(encoding="utf-8").splitlines()
        if ".raw/" not in lines:
            lines.append(".raw/")
            atomic_write(ignore_path, "\n".join(lines) + "\n", 0o644)
    else:
        atomic_write(ignore_path, ".raw/\n", 0o644)
    ignored = False
    if is_git:
        probe = run_git(root, ["check-ignore", "-q", ".handoff/config.json"])
        ignored = probe.returncode == 0
    return {"root": str(root), "git": is_git, "config": config, "handoff_ignored": ignored}


def session_metadata(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "session_key": snapshot.get("session_key"),
        "updated_at": snapshot.get("captured_at"),
        "branch": snapshot.get("branch"),
        "head": snapshot.get("head"),
        "operation": snapshot.get("operation"),
        "workspace_fingerprint": snapshot.get("workspace_fingerprint"),
    }


def manual_text(block: str) -> str:
    pattern = re.compile(re.escape(MANUAL_BEGIN) + r"\n?(.*?)\n?" + re.escape(MANUAL_END), re.DOTALL)
    match = pattern.search(block)
    return match.group(1).strip("\n") if match else ""


def render_block(snapshot: dict[str, Any], body: str, preserved_manual: str = "") -> str:
    key = str(snapshot["session_key"])
    branch = snapshot.get("branch") or "detached"
    captured = dt.datetime.fromisoformat(str(snapshot["captured_at"]))
    metadata = json_dump(session_metadata(snapshot))
    body = body.strip()
    return "\n".join(
        [
            SESSION_BEGIN.format(key=key),
            f"## {captured.strftime('%H:%M')} · `{branch}` · `{key}`",
            f"{STATE_PREFIX}{metadata} -->",
            "<!-- handoff:generated begin -->",
            body,
            "<!-- handoff:generated end -->",
            "",
            "### 人工备注",
            MANUAL_BEGIN,
            preserved_manual,
            MANUAL_END,
            SESSION_END.format(key=key),
        ]
    ).rstrip() + "\n"


def upsert_handoff(root: Path, body_file: Path, key: str, date_value: str | None) -> dict[str, Any]:
    init_result = init_project(root)
    actual_root = Path(init_result["root"])
    if not init_result["git"]:
        snapshot = {
            "session_key": key,
            "captured_at": iso_now(),
            "branch": None,
            "head": None,
            "operation": None,
            "workspace_fingerprint": None,
        }
    else:
        snapshot = capture(actual_root, key, "manual", force=True)
        if snapshot is None:
            raise HandoffError("unable to capture Git state")
    body = body_file.read_text(encoding="utf-8")
    if "<!-- handoff:" in body:
        raise HandoffError("generated body must not contain handoff control markers")
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in body]
    if missing:
        raise HandoffError("generated body is missing required headings: " + ", ".join(missing))
    date_name = date_value or now_local().date().isoformat()
    try:
        dt.date.fromisoformat(date_name)
    except ValueError as exc:
        raise HandoffError("date must use YYYY-MM-DD") from exc
    destination = actual_root / ".handoff" / f"{date_name}.md"
    existing = destination.read_text(encoding="utf-8") if destination.exists() else f"# Handoff · {date_name}\n\n"
    start = SESSION_BEGIN.format(key=key)
    end = SESSION_END.format(key=key)
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    old_match = pattern.search(existing)
    preserved = manual_text(old_match.group(0)) if old_match else ""
    block = render_block(snapshot, body, preserved)
    if old_match:
        updated = existing[: old_match.start()] + block + existing[old_match.end() :]
    else:
        updated = existing.rstrip() + "\n\n" + block
    atomic_write(destination, updated, 0o644)
    return {"path": str(destination), "session_key": key, "state": session_metadata(snapshot), "handoff_ignored": init_result["handoff_ignored"]}


def parse_handoffs(root: Path, date_value: str | None = None) -> list[dict[str, Any]]:
    handoff_dir = root / ".handoff"
    paths = [handoff_dir / f"{date_value}.md"] if date_value else sorted(handoff_dir.glob("????-??-??.md"), reverse=True)
    result: list[dict[str, Any]] = []
    pattern = re.compile(r"<!-- handoff:session=([^ ]+) begin -->(.*?)<!-- handoff:session=\1 end -->", re.DOTALL)
    state_re = re.compile(r"<!-- handoff:state (\{.*?\}) -->")
    generated_re = re.compile(r"<!-- handoff:generated begin -->\n?(.*?)\n?<!-- handoff:generated end -->", re.DOTALL)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in pattern.finditer(text):
            state_match = state_re.search(match.group(2))
            generated_match = generated_re.search(match.group(2))
            if not state_match:
                continue
            try:
                state = json.loads(state_match.group(1))
            except json.JSONDecodeError:
                continue
            result.append({"file": str(path), "date": path.stem, "session_key": match.group(1), "state": state, "body": generated_match.group(1).strip() if generated_match else ""})
    return result


def current_snapshot(root: Path) -> dict[str, Any]:
    key = session_key()
    return build_snapshot(root, key, "resume-check")


def only_handoff_commits(root: Path, old_head: str, new_head: str) -> bool:
    ancestor = run_git(root, ["merge-base", "--is-ancestor", old_head, new_head])
    if ancestor.returncode != 0:
        return False
    changed = run_git(root, ["diff", "--name-only", f"{old_head}..{new_head}", "--", ".", ":(exclude).handoff/**"])
    return changed.returncode == 0 and not changed.stdout.strip()


def committed_path_changes(root: Path, old_head: str | None, new_head: str | None) -> list[str]:
    if not old_head or not new_head:
        return []
    result = run_git(root, ["diff", "--name-status", f"{old_head}..{new_head}", "--", ".", ":(exclude).handoff/**"])
    return result.stdout.splitlines()[:100] if result.returncode == 0 else []


def first_unfinished(body: str) -> str | None:
    match = re.search(r"^\s*- \[ \]\s+(.+)$", body, re.MULTILINE)
    return match.group(1).strip() if match else None


def degraded_raw(root: Path, branch: str | None = None) -> dict[str, Any] | None:
    sessions = root / ".handoff" / ".raw" / "sessions"
    candidates: list[dict[str, Any]] = []
    for path in sessions.glob("*.json") if sessions.exists() else ():
        value = read_json(path)
        if value:
            candidates.append(value)
    if not candidates:
        return None
    matching = [item for item in candidates if item.get("branch") == branch]
    if matching:
        candidates = matching
    candidates.sort(key=lambda item: float(item.get("capture_epoch", 0)), reverse=True)
    return {"status": "degraded", "reason": "no formal handoff found; using mechanical snapshot only", "snapshot": candidates[0]}


def resume_handoff(root: Path, date_value: str | None, requested_key: str | None) -> dict[str, Any]:
    actual_root, is_git = workspace_root(root)
    records = parse_handoffs(actual_root, date_value)
    if requested_key:
        records = [record for record in records if record["session_key"] == requested_key or record["session_key"].endswith(requested_key)]
    if not records:
        branch = git_text(actual_root, ["symbolic-ref", "--quiet", "--short", "HEAD"]) or None if is_git else None
        degraded = degraded_raw(actual_root, branch)
        return degraded or {"status": "not_found", "reason": "no matching formal handoff or raw snapshot"}
    if not is_git:
        if len(records) != 1:
            return {"status": "selection_required", "candidates": [{"file": item["file"], "session_key": item["session_key"], "updated_at": item["state"].get("updated_at")} for item in records]}
        record = records[0]
        return {"status": "limited", "reason": "non-Git workspace; drift validation unavailable", "record": record, "next_task": first_unfinished(record["body"])}
    live_snapshot = current_snapshot(actual_root)
    current = session_metadata(live_snapshot)
    if not requested_key:
        matching = [record for record in records if record["state"].get("branch") == current.get("branch")]
        if not matching:
            return {"status": "selection_required", "reason": "no handoff matches the current branch", "candidates": [{"file": item["file"], "session_key": item["session_key"], "branch": item["state"].get("branch"), "updated_at": item["state"].get("updated_at")} for item in records[:10]]}
        records = matching
    records.sort(key=lambda item: str(item["state"].get("updated_at") or ""), reverse=True)
    if len(records) > 1 and records[0]["state"].get("updated_at") == records[1]["state"].get("updated_at"):
        return {"status": "selection_required", "reason": "multiple equally recent handoffs", "candidates": [{"file": item["file"], "session_key": item["session_key"], "updated_at": item["state"].get("updated_at")} for item in records[:10]]}
    record = records[0]
    saved = record["state"]
    differences: list[dict[str, Any]] = []
    if saved.get("branch") != current.get("branch"):
        differences.append({"field": "branch", "saved": saved.get("branch"), "current": current.get("branch")})
    if saved.get("operation") != current.get("operation"):
        differences.append({"field": "operation", "saved": saved.get("operation"), "current": current.get("operation")})
    if saved.get("workspace_fingerprint") != current.get("workspace_fingerprint"):
        saved_raw = read_json(actual_root / ".handoff" / ".raw" / "sessions" / f"{record['session_key']}.json")
        differences.append(
            {
                "field": "workspace",
                "saved": saved.get("workspace_fingerprint"),
                "current": current.get("workspace_fingerprint"),
                "saved_git_status": saved_raw.get("git_status") if saved_raw and saved_raw.get("workspace_fingerprint") == saved.get("workspace_fingerprint") else None,
                "current_git_status": live_snapshot.get("git_status"),
            }
        )
    soft_head = False
    if saved.get("head") != current.get("head"):
        if saved.get("head") and current.get("head") and only_handoff_commits(actual_root, saved["head"], current["head"]):
            soft_head = True
        else:
            differences.append(
                {
                    "field": "head",
                    "saved": saved.get("head"),
                    "current": current.get("head"),
                    "changed_paths": committed_path_changes(actual_root, saved.get("head"), current.get("head")),
                }
            )
    status = "hard" if differences else ("soft" if soft_head else "none")
    return {"status": status, "record": record, "current": current, "differences": differences, "soft_head_change": soft_head, "next_task": first_unfinished(record["body"])}


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_hook(args: argparse.Namespace) -> int:
    payload = hook_payload()
    try:
        opted_root = find_opted_in_root(payload_cwd(payload))
        if opted_root is None:
            return 0
        key = session_key(payload_session_id(payload))
        capture(opted_root, key, args.event, force=args.event == "session-end")
    except Exception:
        return 0
    return 0


def parser() -> argparse.ArgumentParser:
    root_parser = argparse.ArgumentParser(description=__doc__)
    sub = root_parser.add_subparsers(dest="command", required=True)
    hook = sub.add_parser("hook")
    hook.add_argument("--event", choices=("post-tool-use", "session-end"), required=True)
    init = sub.add_parser("init")
    init.add_argument("--root", type=Path, default=Path.cwd())
    init.add_argument("--json", action="store_true")
    cap = sub.add_parser("capture")
    cap.add_argument("--root", type=Path, default=Path.cwd())
    cap.add_argument("--event", default="manual")
    cap.add_argument("--force", action="store_true")
    cap.add_argument("--json", action="store_true")
    upsert = sub.add_parser("upsert")
    upsert.add_argument("--root", type=Path, default=Path.cwd())
    upsert.add_argument("--body-file", type=Path, required=True)
    upsert.add_argument("--date")
    upsert.add_argument("--session-id")
    upsert.add_argument("--json", action="store_true")
    resume = sub.add_parser("resume")
    resume.add_argument("--root", type=Path, default=Path.cwd())
    resume.add_argument("--date")
    resume.add_argument("--session-key")
    resume.add_argument("--json", action="store_true")
    return root_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "hook":
        return command_hook(args)
    try:
        if args.command == "init":
            result = init_project(args.root)
        elif args.command == "capture":
            root, is_git = workspace_root(args.root)
            if not is_git:
                result = {"status": "skipped", "reason": "not a Git worktree", "root": str(root)}
            else:
                if not (root / ".handoff" / "config.json").exists():
                    init_project(root)
                result = capture(root, session_key(), args.event, args.force) or {"status": "skipped"}
        elif args.command == "upsert":
            root, _ = workspace_root(args.root)
            result = upsert_handoff(root, args.body_file, session_key(args.session_id), args.date)
        elif args.command == "resume":
            result = resume_handoff(args.root, args.date, args.session_key)
        else:
            raise HandoffError("unsupported command")
    except (HandoffError, OSError, subprocess.TimeoutExpired) as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1
    if getattr(args, "json", False):
        print_json(result)
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
