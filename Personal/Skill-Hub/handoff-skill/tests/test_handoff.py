from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "handoff" / "scripts" / "handoff.py"
SPEC = importlib.util.spec_from_file_location("handoff_runtime", RUNTIME_PATH)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


class RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Handoff Test")
        git(self.root, "config", "user.email", "handoff@example.invalid")
        (self.root / "app.py").write_text("print('base')\n", encoding="utf-8")
        git(self.root, "add", "app.py")
        git(self.root, "commit", "-qm", "base")
        runtime.init_project(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_body(self, name: str = "draft.md") -> Path:
        body = self.root / ".handoff" / ".raw" / name
        body.parent.mkdir(parents=True, exist_ok=True)
        body.write_text(
            """### 当前目标
完成 handoff。

### 已完成事项与证据
- [x] 建立测试。

### 决策与理由
- 保持本地。

### 工作区与验证状态
- `python3 -m unittest`

### 未完成任务与下一步
- [ ] 运行下一项。

### 阻塞、风险与未知项
- 无。

### 恢复指令
读取本会话并等待确认。
""",
            encoding="utf-8",
        )
        return body


class CaptureTests(RepoCase):
    def test_capture_collects_changed_todos_and_excludes_handoff(self) -> None:
        (self.root / "app.py").write_text("# TODO: finish this\nprint('changed')\n", encoding="utf-8")
        (self.root / ".handoff" / "ignored.py").write_text("# TODO: do not collect\n", encoding="utf-8")
        snapshot = runtime.capture(self.root, "codex-test", "manual", force=True)
        self.assertIsNotNone(snapshot)
        assert snapshot
        self.assertEqual(snapshot["session_key"], "codex-test")
        self.assertEqual([item["path"] for item in snapshot["todos"]], ["app.py"])
        self.assertIn("app.py", snapshot["git_status"])
        self.assertNotIn(".handoff", snapshot["git_status"])

    def test_debounce_returns_previous_without_building_git_snapshot(self) -> None:
        first = runtime.capture(self.root, "codex-test", "manual", force=True)
        self.assertIsNotNone(first)
        with mock.patch.object(runtime, "build_snapshot", side_effect=AssertionError("must not run Git capture")):
            second = runtime.capture(self.root, "codex-test", "post-tool-use", force=False)
        self.assertEqual(first, second)

    def test_journal_deduplicates_unchanged_state(self) -> None:
        runtime.capture(self.root, "codex-test", "manual", force=True)
        runtime.capture(self.root, "codex-test", "session-end", force=True)
        journal = next((self.root / ".handoff" / ".raw").glob("*.jsonl"))
        self.assertEqual(len(journal.read_text(encoding="utf-8").splitlines()), 1)

    def test_parallel_captures_do_not_corrupt_journal(self) -> None:
        commands = [
            subprocess.Popen(
                ["python3", str(RUNTIME_PATH), "capture", "--root", str(self.root), "--event", "manual", "--force", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "CODEX_THREAD_ID": "parallel-test"},
            )
            for _ in range(4)
        ]
        for command in commands:
            stdout, stderr = command.communicate(timeout=10)
            self.assertEqual(command.returncode, 0, stderr)
            json.loads(stdout)
        journal = next((self.root / ".handoff" / ".raw").glob("*.jsonl"))
        for line in journal.read_text(encoding="utf-8").splitlines():
            json.loads(line)

    def test_retention_removes_old_journal(self) -> None:
        raw = self.root / ".handoff" / ".raw"
        raw.mkdir(parents=True, exist_ok=True)
        old = raw / "2000-01-01.jsonl"
        old.write_text("{}\n", encoding="utf-8")
        runtime.capture(self.root, "codex-test", "manual", force=True)
        self.assertFalse(old.exists())

    def test_hook_success_is_silent(self) -> None:
        payload = json.dumps({"cwd": str(self.root), "session_id": "silent-test"})
        result = subprocess.run(
            ["python3", str(RUNTIME_PATH), "hook", "--event", "post-tool-use"],
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


class UpsertTests(RepoCase):
    def test_upsert_preserves_manual_notes_and_replaces_session(self) -> None:
        body = self.write_body()
        first = runtime.upsert_handoff(self.root, body, "codex-test", "2026-07-18")
        path = Path(first["path"])
        text = path.read_text(encoding="utf-8")
        text = text.replace(runtime.MANUAL_BEGIN + "\n", runtime.MANUAL_BEGIN + "\n人工补充。\n")
        path.write_text(text, encoding="utf-8")
        body.write_text(body.read_text(encoding="utf-8").replace("完成 handoff。", "更新 handoff。"), encoding="utf-8")
        runtime.upsert_handoff(self.root, body, "codex-test", "2026-07-18")
        updated = path.read_text(encoding="utf-8")
        self.assertEqual(updated.count("handoff:session=codex-test begin"), 1)
        self.assertIn("人工补充。", updated)
        self.assertIn("更新 handoff。", updated)

    def test_different_sessions_append(self) -> None:
        body = self.write_body()
        runtime.upsert_handoff(self.root, body, "codex-one", "2026-07-18")
        runtime.upsert_handoff(self.root, body, "codex-two", "2026-07-18")
        text = (self.root / ".handoff" / "2026-07-18.md").read_text(encoding="utf-8")
        self.assertIn("handoff:session=codex-one begin", text)
        self.assertIn("handoff:session=codex-two begin", text)

    def test_rejects_control_markers_in_generated_body(self) -> None:
        body = self.write_body()
        body.write_text(body.read_text(encoding="utf-8") + "\n<!-- handoff:session=bad begin -->\n", encoding="utf-8")
        with self.assertRaises(runtime.HandoffError):
            runtime.upsert_handoff(self.root, body, "codex-test", "2026-07-18")


class ResumeTests(RepoCase):
    def test_no_drift_and_first_unfinished_task(self) -> None:
        body = self.write_body()
        runtime.upsert_handoff(self.root, body, "codex-test", "2026-07-18")
        result = runtime.resume_handoff(self.root, "2026-07-18", "codex-test")
        self.assertEqual(result["status"], "none")
        self.assertEqual(result["next_task"], "运行下一项。")

    def test_uncommitted_code_change_is_hard_drift(self) -> None:
        body = self.write_body()
        runtime.upsert_handoff(self.root, body, "codex-test", "2026-07-18")
        (self.root / "app.py").write_text("print('drift')\n", encoding="utf-8")
        result = runtime.resume_handoff(self.root, "2026-07-18", "codex-test")
        self.assertEqual(result["status"], "hard")
        self.assertIn("workspace", [item["field"] for item in result["differences"]])

    def test_handoff_only_commit_is_soft_drift(self) -> None:
        body = self.write_body()
        runtime.upsert_handoff(self.root, body, "codex-test", "2026-07-18")
        git(self.root, "add", ".handoff")
        git(self.root, "commit", "-qm", "record handoff")
        result = runtime.resume_handoff(self.root, "2026-07-18", "codex-test")
        self.assertEqual(result["status"], "soft")

    def test_code_commit_is_hard_drift(self) -> None:
        body = self.write_body()
        runtime.upsert_handoff(self.root, body, "codex-test", "2026-07-18")
        (self.root / "app.py").write_text("print('new commit')\n", encoding="utf-8")
        git(self.root, "add", "app.py")
        git(self.root, "commit", "-qm", "code change")
        result = runtime.resume_handoff(self.root, "2026-07-18", "codex-test")
        self.assertEqual(result["status"], "hard")
        self.assertIn("head", [item["field"] for item in result["differences"]])

    def test_raw_only_is_degraded(self) -> None:
        runtime.capture(self.root, "codex-test", "session-end", force=True)
        result = runtime.resume_handoff(self.root, None, None)
        self.assertEqual(result["status"], "degraded")


class NonGitTests(unittest.TestCase):
    def test_non_git_init_and_limited_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime.init_project(root)
            body = root / ".handoff" / ".raw" / "draft.md"
            body.parent.mkdir(parents=True, exist_ok=True)
            body.write_text("\n\n".join(f"{heading}\n非 Git。" for heading in runtime.REQUIRED_HEADINGS) + "\n", encoding="utf-8")
            runtime.upsert_handoff(root, body, "codex-test", "2026-07-18")
            result = runtime.resume_handoff(root, "2026-07-18", "codex-test")
            self.assertEqual(result["status"], "limited")


if __name__ == "__main__":
    unittest.main()
