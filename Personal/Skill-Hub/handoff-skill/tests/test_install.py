from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INSTALL_PATH = ROOT / "install.py"
SPEC = importlib.util.spec_from_file_location("handoff_install", INSTALL_PATH)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "codex"
        self.home.mkdir(parents=True)
        self.environment = mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temp.cleanup()

    def test_link_install_is_idempotent_and_preserves_other_hooks(self) -> None:
        hooks_path = self.home / "hooks.json"
        hooks_path.write_text(
            json.dumps({"description": "existing", "hooks": {"PreToolUse": [{"matcher": "x", "hooks": [{"type": "command", "command": "/usr/bin/true"}]}]}}),
            encoding="utf-8",
        )
        args = type("Args", (), {"mode": "link"})()
        first = installer.command_install(args)
        second = installer.command_install(args)
        self.assertEqual(first["mode"], "link")
        self.assertEqual(second["mode"], "link")
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        self.assertIn("PreToolUse", hooks["hooks"])
        self.assertEqual(len(hooks["hooks"]["PostToolUse"]), 1)
        self.assertEqual(len(hooks["hooks"]["SessionEnd"]), 1)
        self.assertIn(installer.HOOK_ID, hooks["hooks"]["PostToolUse"][0]["hooks"][0]["command"])
        self.assertTrue(list(self.home.glob("hooks.json.handoff-backup-*")))

    def test_copy_install_and_precise_uninstall(self) -> None:
        args = type("Args", (), {"mode": "copy"})()
        installer.command_install(args)
        destination = self.home / "skills" / "handoff"
        self.assertTrue((destination / installer.MANAGED_FILE).exists())
        hooks_path = self.home / "hooks.json"
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        hooks["hooks"]["PostToolUse"].insert(0, {"matcher": "other", "hooks": [{"type": "command", "command": "/usr/bin/true"}]})
        hooks_path.write_text(json.dumps(hooks), encoding="utf-8")
        result = installer.command_uninstall()
        self.assertEqual(result["mode"], "absent")
        remaining = json.loads(hooks_path.read_text(encoding="utf-8"))
        self.assertEqual(len(remaining["hooks"]["PostToolUse"]), 1)
        self.assertEqual(remaining["hooks"]["PostToolUse"][0]["matcher"], "other")
        self.assertNotIn("SessionEnd", remaining["hooks"])

    def test_refuses_unrecognized_destination(self) -> None:
        destination = self.home / "skills" / "handoff"
        destination.mkdir(parents=True)
        (destination / "user-file").write_text("keep", encoding="utf-8")
        args = type("Args", (), {"mode": "copy"})()
        with self.assertRaises(installer.InstallError):
            installer.command_install(args)
        self.assertTrue((destination / "user-file").exists())


if __name__ == "__main__":
    unittest.main()
