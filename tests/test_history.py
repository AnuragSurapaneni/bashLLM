"""History behavior through an installed bashllm command."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class HistoryCommandTests(unittest.TestCase):
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
            check=True,
            capture_output=True,
            text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def invoke(self, *args):
        return subprocess.run(
            [self.cli, *map(str, args)],
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )

    def test_exact_repeat_is_blocked_with_previous_result(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.invoke("run", "--repo", root, "--cwd", root, "--json", "--", "echo once; exit 7")
            second = self.invoke("run", "--repo", root, "--cwd", root, "--json", "--", "echo once; exit 7")
            self.assertEqual(first.returncode, 7)
            self.assertEqual(second.returncode, 3)
            payload = json.loads(second.stdout)
            self.assertEqual(payload["status"], "not_executed")
            self.assertEqual(payload["previous_exit_code"], 7)
            self.assertIn("once", payload["previous_stdout"])

    def test_retry_executes_again_and_different_directory_is_independent(self):
        with tempfile.TemporaryDirectory() as root:
            other = Path(root) / "other"
            other.mkdir()
            marker = Path(root) / "marker"
            command = f"printf x >> {marker}"
            first = self.invoke("run", "--repo", root, "--cwd", root, "--", command)
            blocked = self.invoke("run", "--repo", root, "--cwd", root, "--", command)
            self.assertEqual(blocked.returncode, 3)
            self.assertEqual(marker.read_text(), "x")
            retry = self.invoke("run", "--repo", root, "--cwd", root, "--retry", "--", command)
            elsewhere = self.invoke("run", "--repo", root, "--cwd", other, "--", command)
            self.assertEqual((first.returncode, retry.returncode, elsewhere.returncode), (0, 0, 0))
            self.assertEqual(marker.read_text(), "xxx")

    def test_command_text_is_matched_exactly_and_repositories_are_independent(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            for repo, command in ((left, "echo hello"), (left, "echo  hello"), (right, "echo hello")):
                result = self.invoke("run", "--repo", repo, "--cwd", repo, "--", command)
                self.assertEqual(result.returncode, 0, result.stderr)
            blocked = self.invoke("run", "--repo", left, "--cwd", left, "--json", "--", "echo hello")
            self.assertEqual(blocked.returncode, 3)
            self.assertEqual(json.loads(blocked.stdout)["status"], "not_executed")

    def test_no_history_does_not_record_or_block(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "marker"
            command = f"printf x >> {marker}"
            first = self.invoke("run", "--repo", root, "--cwd", root, "--no-history", "--", command)
            second = self.invoke("run", "--repo", root, "--cwd", root, "--no-history", "--", command)
            normal = self.invoke("run", "--repo", root, "--cwd", root, "--", command)
            self.assertEqual((first.returncode, second.returncode, normal.returncode), (0, 0, 0))
            self.assertEqual(marker.read_text(), "xxx")
            self.assertEqual(len(json.loads(self.invoke("history", "--repo", root, "--json").stdout)), 1)

    def test_no_history_can_run_a_previously_recorded_command(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "marker"
            command = f"printf x >> {marker}"
            self.assertEqual(self.invoke("run", "--repo", root, "--cwd", root, "--", command).returncode, 0)
            self.assertEqual(self.invoke("run", "--repo", root, "--cwd", root, "--no-history", "--", command).returncode, 0)
            self.assertEqual(marker.read_text(), "xx")
            self.assertEqual(len(json.loads(self.invoke("history", "--repo", root, "--json").stdout)), 1)

    def test_recent_history_lists_attempts_and_private_storage(self):
        with tempfile.TemporaryDirectory() as root:
            for command in ("echo first", "echo second"):
                result = self.invoke("run", "--repo", root, "--cwd", root, "--", command)
                self.assertEqual(result.returncode, 0, result.stderr)
            recent = self.invoke("history", "--repo", root, "--limit", "1", "--json")
            self.assertEqual(recent.returncode, 0, recent.stderr)
            entries = json.loads(recent.stdout)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["command"], "echo second")
            self.assertEqual(entries[0]["stdout"], "second\n")
            self.assertEqual((Path(root) / ".bashllm").stat().st_mode & 0o777, 0o700)
            self.assertEqual((Path(root) / ".bashllm" / "history.sqlite3").stat().st_mode & 0o777, 0o600)

    def test_symlinked_history_paths_do_not_modify_external_targets(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            repo = Path(root)
            external_dir = Path(outside) / "external_state"
            external_dir.mkdir(mode=0o755)
            external_dir.chmod(0o755)
            (repo / ".bashllm").symlink_to(external_dir, target_is_directory=True)
            result = self.invoke("run", "--repo", repo, "--cwd", repo, "--", "echo safe")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(external_dir.stat().st_mode & 0o777, 0o755)
            self.assertFalse((external_dir / "history.sqlite3").exists())

        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            repo = Path(root)
            state = repo / ".bashllm"
            state.mkdir()
            external_file = Path(outside) / "external.sqlite3"
            external_file.write_bytes(b"keep this file")
            external_file.chmod(0o644)
            (state / "history.sqlite3").symlink_to(external_file)
            result = self.invoke("run", "--repo", repo, "--cwd", repo, "--", "echo safe")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(external_file.stat().st_mode & 0o777, 0o644)
            self.assertEqual(external_file.read_bytes(), b"keep this file")


if __name__ == "__main__":
    unittest.main()
