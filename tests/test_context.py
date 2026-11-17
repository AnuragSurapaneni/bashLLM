"""Installed-CLI behavior for repository handoffs."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class ContextCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        root = Path(cls.install_dir.name)
        source = root / "source"
        shutil.copytree(PROJECT / "src", source / "src")
        shutil.copy2(PROJECT / "pyproject.toml", source / "pyproject.toml")
        environment = root / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        subprocess.run(
            [environment / "bin" / "python", "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(source)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def invoke(self, *args):
        return subprocess.run([self.cli, *map(str, args)], capture_output=True, text=True,
                              env={**os.environ, "LC_ALL": "C"})

    def test_context_includes_briefing_recent_command_and_adjustable_budget(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "main.py").write_text("print('hello')\n")
            self.assertEqual(self.invoke("inspect", "--repo", root).returncode, 0)
            self.assertEqual(self.invoke("run", "--repo", root, "--cwd", root, "--", "echo tried").returncode, 0)
            small = self.invoke("context", "--repo", root, "--max-tokens", "80", "--json")
            large = self.invoke("context", "--repo", root, "--max-tokens", "4000", "--json")
            self.assertEqual(small.returncode, 0, small.stderr)
            self.assertEqual(large.returncode, 0, large.stderr)
            short = json.loads(small.stdout)
            full = json.loads(large.stdout)
            self.assertTrue(short["truncated"])
            self.assertFalse(full["truncated"])
            self.assertFalse(full["stale"])
            self.assertIn("main.py", full["briefing"])
            self.assertIn("echo tried", full["recent_commands"])
            self.assertLess(len(short["briefing"]), len(full["briefing"]))
            human = self.invoke("context", "--repo", root, "--max-tokens", "80")
            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertIn("Truncated", human.stdout)

    def test_context_detects_edits_additions_and_removals(self):
        for change in ("edit", "add", "remove"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                repo = Path(root)
                source = repo / "main.py"
                source.write_text("print('first')\n")
                self.assertEqual(self.invoke("inspect", "--repo", root).returncode, 0)
                if change == "edit":
                    source.write_text("print('second')\n")
                elif change == "add":
                    (repo / "added.py").write_text("pass\n")
                else:
                    source.unlink()
                result = self.invoke("context", "--repo", root, "--json")
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertTrue(payload["stale"])
                self.assertIn("inspect", payload["warning"])
                human = self.invoke("context", "--repo", root)
                self.assertIn("inspect", human.stdout)

    def test_context_requires_briefing_and_rejects_symlinked_state(self):
        with tempfile.TemporaryDirectory() as root:
            missing = self.invoke("context", "--repo", root)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("inspect", missing.stderr)
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            (Path(root) / ".bashllm").symlink_to(outside, target_is_directory=True)
            result = self.invoke("context", "--repo", root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr.lower())

    def test_inspect_rejects_symlinked_snapshot_without_changing_target(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            repo = Path(root)
            state = repo / ".bashllm"
            state.mkdir()
            target = Path(outside) / "snapshot.json"
            target.write_text("keep")
            (state / "inspection.json").symlink_to(target)
            result = self.invoke("inspect", "--repo", root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr.lower())
            self.assertEqual(target.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
