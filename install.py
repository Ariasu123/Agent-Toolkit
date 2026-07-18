#!/usr/bin/env python3
"""Install, inspect, or uninstall the Codex handoff skill."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


HOOK_ID = "handoff-v1"
MANAGED_FILE = ".handoff-install.json"
SOURCE_SKILL = Path(__file__).resolve().parent / "handoff"


class InstallError(RuntimeError):
    pass


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser().resolve() if configured else Path.home() / ".codex"


def timestamp() -> str:
    return dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def load_hooks(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"{path} must contain a JSON object")
    return value


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    destination = path.with_name(f"{path.name}.handoff-backup-{timestamp()}")
    counter = 1
    while destination.exists():
        destination = path.with_name(f"{path.name}.handoff-backup-{timestamp()}-{counter}")
        counter += 1
    shutil.copy2(path, destination)
    return destination


def is_managed_copy(path: Path) -> bool:
    marker = path / MANAGED_FILE
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    return isinstance(value, dict) and value.get("id") == HOOK_ID


def is_managed_link(path: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        return path.resolve() == SOURCE_SKILL.resolve()
    except OSError:
        return False


def ensure_safe_destination(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if is_managed_link(path) or is_managed_copy(path):
        return
    raise InstallError(f"refusing to overwrite unrecognized destination: {path}")


def remove_managed_destination(path: Path) -> None:
    if is_managed_link(path):
        path.unlink()
    elif is_managed_copy(path):
        shutil.rmtree(path)


def install_skill(destination: Path, mode: str) -> None:
    if not (SOURCE_SKILL / "SKILL.md").exists():
        raise InstallError(f"source skill is missing: {SOURCE_SKILL}")
    ensure_safe_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    remove_managed_destination(destination)
    if mode == "link":
        destination.symlink_to(SOURCE_SKILL, target_is_directory=True)
        return
    staging = Path(tempfile.mkdtemp(prefix=".handoff-install-", dir=destination.parent))
    try:
        shutil.rmtree(staging)
        shutil.copytree(SOURCE_SKILL, staging)
        atomic_json(staging / MANAGED_FILE, {"id": HOOK_ID, "source": str(SOURCE_SKILL)})
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def hook_group(command: str, timeout: int, status: str) -> dict[str, Any]:
    return {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": timeout,
                "statusMessage": status,
            }
        ],
    }


def hook_command(runtime: Path, event: str) -> str:
    python = shutil.which("python3") or "/usr/bin/python3"
    script = runtime / "scripts" / "handoff.py"
    # The marker is an inert environment assignment used for precise uninstall matching.
    return f"HANDOFF_HOOK_ID={HOOK_ID} {shlex_quote(python)} {shlex_quote(str(script))} hook --event {event}"


def shlex_quote(value: str) -> str:
    if value and all(character.isalnum() or character in "@%_+=:,./-" for character in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def is_handoff_hook(group: Any) -> bool:
    if not isinstance(group, dict):
        return False
    hooks = group.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(isinstance(item, dict) and HOOK_ID in str(item.get("command", "")) for item in hooks)


def merge_hooks(path: Path, runtime: Path) -> Path | None:
    value = load_hooks(path)
    changed = False
    # Dedicated Codex hooks.json wraps event groups under a top-level `hooks` object.
    # Migrate the early handoff-only flat shape if this installer previously wrote it.
    container = value.get("hooks")
    if container is None:
        container = {}
        value["hooks"] = container
        changed = True
    if not isinstance(container, dict):
        raise InstallError(f"{path}: hooks must be an object")
    if "description" not in value:
        value["description"] = "Codex lifecycle hooks managed in part by the handoff skill."
        changed = True
    for event in ("PostToolUse", "SessionEnd"):
        flat = value.get(event)
        if isinstance(flat, list) and flat and all(is_handoff_hook(item) for item in flat):
            value.pop(event, None)
            changed = True
    desired = {
        "PostToolUse": hook_group(hook_command(runtime, "post-tool-use"), 2, "Capturing handoff state"),
        "SessionEnd": hook_group(hook_command(runtime, "session-end"), 3, "Finalizing handoff state"),
    }
    for event, group in desired.items():
        existing = container.get(event, [])
        if existing is None:
            existing = []
        if not isinstance(existing, list):
            raise InstallError(f"{path}: {event} must be an array")
        filtered = [item for item in existing if not is_handoff_hook(item)]
        updated = [*filtered, group]
        if updated != existing:
            container[event] = updated
            changed = True
    if not changed:
        return None
    backup_path = backup(path)
    atomic_json(path, value)
    return backup_path


def remove_hooks(path: Path) -> Path | None:
    if not path.exists():
        return None
    value = load_hooks(path)
    changed = False
    container = value.get("hooks", {})
    if not isinstance(container, dict):
        raise InstallError(f"{path}: hooks must be an object")
    for event in ("PostToolUse", "SessionEnd"):
        existing = container.get(event)
        if not isinstance(existing, list):
            continue
        filtered = [item for item in existing if not is_handoff_hook(item)]
        if filtered != existing:
            changed = True
            if filtered:
                container[event] = filtered
            else:
                container.pop(event, None)
        flat = value.get(event)
        if isinstance(flat, list):
            filtered_flat = [item for item in flat if not is_handoff_hook(item)]
            if filtered_flat != flat:
                changed = True
                if filtered_flat:
                    value[event] = filtered_flat
                else:
                    value.pop(event, None)
    if not changed:
        return None
    backup_path = backup(path)
    atomic_json(path, value)
    return backup_path


def status(home: Path) -> dict[str, Any]:
    destination = home / "skills" / "handoff"
    hooks_path = home / "hooks.json"
    hooks = load_hooks(hooks_path) if hooks_path.exists() else {}
    container = hooks.get("hooks", {}) if isinstance(hooks, dict) else {}
    if not isinstance(container, dict):
        container = {}
    installed_hooks = {
        event: any(is_handoff_hook(group) for group in container.get(event, []) if isinstance(container.get(event), list))
        for event in ("PostToolUse", "SessionEnd")
    }
    return {
        "codex_home": str(home),
        "skill": str(destination),
        "mode": "link" if is_managed_link(destination) else ("copy" if is_managed_copy(destination) else "absent"),
        "hooks": installed_hooks,
    }


def command_install(args: argparse.Namespace) -> dict[str, Any]:
    home = codex_home()
    destination = home / "skills" / "handoff"
    install_skill(destination, args.mode)
    backup_path = merge_hooks(home / "hooks.json", destination)
    result = status(home)
    result["config_backup"] = str(backup_path) if backup_path else None
    result["trust_note"] = "Restart Codex and approve the new hook command when prompted."
    return result


def command_uninstall() -> dict[str, Any]:
    home = codex_home()
    destination = home / "skills" / "handoff"
    backup_path = remove_hooks(home / "hooks.json")
    if is_managed_link(destination) or is_managed_copy(destination):
        remove_managed_destination(destination)
    elif destination.exists() or destination.is_symlink():
        raise InstallError(f"refusing to remove unrecognized destination: {destination}")
    result = status(home)
    result["config_backup"] = str(backup_path) if backup_path else None
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("--mode", choices=("copy", "link"), default="copy")
    sub.add_parser("status")
    sub.add_parser("uninstall")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "install":
            result = command_install(args)
        elif args.command == "uninstall":
            result = command_uninstall()
        else:
            result = status(codex_home())
    except (InstallError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
