"""Behavioral tests for the installed bashllm command."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class RunCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        environment = Path(cls.install_dir.name) / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        python = environment / "bin" / "python"
        subprocess.run(
            [python, "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(PROJECT)],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.cli = environment / "bin" / "bashllm"
        with tempfile.TemporaryDirectory() as root:
            probe = subprocess.run(
                [cls.cli, "run", "--repo", root, "--cwd", root, "--json", "--", "true"],
                capture_output=True, text=True,
            )
        if probe.returncode == 69:
            cls.install_dir.cleanup()
            required = (sys.platform == "linux" and os.environ.get("BASHLLM_REQUIRE_LINUX_SANDBOX") == "1") or (
                sys.platform == "darwin" and os.environ.get("BASHLLM_REQUIRE_MACOS_SANDBOX") == "1")
            if required:
                raise AssertionError(f"contained run is required: {probe.stdout}")
            raise unittest.SkipTest(f"contained run unavailable: {probe.stdout}")
        if probe.returncode != 0:
            cls.install_dir.cleanup()
            raise AssertionError(f"contained run probe failed: {probe.stdout} {probe.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def test_runs_in_requested_directory(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            work = repo / "nested"
            work.mkdir()
            result = subprocess.run(
                [self.cli, "run", "--repo", str(repo), "--cwd", str(work), "--json", "--", "pwd"],
                capture_output=True,
                text=True,
                env={**os.environ, "LC_ALL": "C"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["stdout"].strip(), str(work.resolve()))
            self.assertEqual(payload["exit_code"], 0)

    def test_timeout_stops_command(self):
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [
                    self.cli, "run", "--repo", root, "--cwd", root,
                    "--timeout", "0.1", "--json", "--", "sleep 3",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            self.assertEqual(result.returncode, 124, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["timed_out"])
            self.assertEqual(payload["exit_code"], 124)

    def test_caps_each_output_stream(self):
        with tempfile.TemporaryDirectory() as root:
            command = "printf '%0200d' 0; printf '%0200d' 0 >&2"
            result = subprocess.run(
                [
                    self.cli, "run", "--repo", root, "--cwd", root,
                    "--max-output", "32", "--json", "--", command,
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "LC_ALL": "C"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["stdout"], "0" * 32)
            self.assertEqual(payload["stderr"], "0" * 32)
            self.assertTrue(payload["stdout_truncated"])
            self.assertTrue(payload["stderr_truncated"])

    def test_default_output_limit_is_32_kib(self):
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [
                    self.cli, "run", "--repo", root, "--cwd", root,
                    "--json", "--", "printf '%032769d' 0",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "LC_ALL": "C"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["stdout"]), 32768)
            self.assertTrue(payload["stdout_truncated"])

    def test_reports_failure_in_human_readable_form(self):
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--", "echo failed >&2; exit 7"],
                capture_output=True,
                text=True,
                env={**os.environ, "LC_ALL": "C"},
            )
            self.assertEqual(result.returncode, 7)
            self.assertIn("failed", result.stderr)
            self.assertIn("exit_code=7", result.stderr)


if __name__ == "__main__":
    unittest.main()
