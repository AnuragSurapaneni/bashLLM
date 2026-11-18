"""Adversarial behavior of the installed CLI on a native Linux host."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "linux", "native Linux containment test")
class LinuxSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        environment = Path(cls.install_dir.name) / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        subprocess.run(
            [environment / "bin" / "python", "-m", "pip", "install", "--no-build-isolation",
             "--no-deps", str(PROJECT)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"
        with tempfile.TemporaryDirectory() as root:
            probe = cls.invoke(root, "true")
        if probe.returncode == 69:
            cls.install_dir.cleanup()
            if os.environ.get("BASHLLM_REQUIRE_LINUX_SANDBOX") == "1":
                raise AssertionError(f"Linux containment is required: {probe.stdout}")
            raise unittest.SkipTest(f"Linux containment unavailable: {probe.stdout}")
        if probe.returncode != 0:
            cls.install_dir.cleanup()
            raise AssertionError(f"Linux containment probe failed: {probe.stdout} {probe.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    @classmethod
    def invoke(cls, root, command, *options, env=None):
        return subprocess.run(
            [cls.cli, "run", "--agent", "--repo", str(root), "--cwd", str(root),
             "--json", *options, "--", command],
            capture_output=True, text=True, env=env,
        )

    def test_repository_writes_and_private_temporary_files(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "created"
            result = self.invoke(root, f"printf ok > {marker}; temporary=$(mktemp); printf tmp > \"$temporary\"; printf '%s' \"$temporary\"")
            self.assertEqual(result.returncode, 0, result.stdout)
            temporary = json.loads(result.stdout)["stdout"]
            self.assertEqual(marker.read_text(), "ok")
            self.assertTrue(temporary.startswith("/tmp/"))
            next_run = self.invoke(root, f"test ! -e {temporary}")
            self.assertEqual(next_run.returncode, 0, next_run.stdout)

    def test_outside_files_and_symlink_escape_are_denied(self):
        with tempfile.TemporaryDirectory() as outer:
            repo = Path(outer) / "repo"
            repo.mkdir()
            secret = Path(outer) / "outside-secret"
            secret.write_text("keep")
            (repo / "link").symlink_to(secret)
            reading = self.invoke(repo, f"test ! -r {secret} && test ! -r {repo / 'link'} && "
                                        f"bash -c 'test ! -r {secret}'")
            self.assertEqual(reading.returncode, 0, reading.stdout)
            self.invoke(repo, f"printf bad > {secret}")
            self.assertEqual(secret.read_text(), "keep")

    def test_inherited_secret_environment_is_removed(self):
        with tempfile.TemporaryDirectory() as root:
            environment = {**os.environ, "BASHLLM_TEST_SECRET": "should-not-appear"}
            result = self.invoke(root, "test -z \"${BASHLLM_TEST_SECRET+x}\"", env=environment)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_home_tool_requires_an_explicit_owner_grant(self):
        with tempfile.TemporaryDirectory() as outer:
            root = Path(outer)
            repo = root / "repo"
            repo.mkdir()
            home = root / "home"
            home.mkdir()
            secret = home / "secret"
            secret.write_text("private")
            tools = home / "tools"
            tools.mkdir()
            executable = tools / "bashllm-granted-tool"
            executable.write_text("#!/bin/bash\nprintf granted\n")
            executable.chmod(0o755)
            environment = {**os.environ, "HOME": str(home)}
            denied = self.invoke(repo, f"test ! -r {secret} && ! command -v bashllm-granted-tool",
                                 env=environment)
            self.assertEqual(denied.returncode, 0, denied.stdout)
            configuration = home / ".config" / "bashllm"
            configuration.mkdir(parents=True)
            (configuration / "tool-grants.json").write_text(json.dumps({str(repo): [str(tools)]}))
            allowed = self.invoke(repo, f"test ! -r {secret} && bashllm-granted-tool",
                                  env=environment)
            self.assertEqual(allowed.returncode, 0, allowed.stdout)
            self.assertEqual(json.loads(allowed.stdout)["stdout"], "granted")

    def test_host_loopback_service_is_unreachable(self):
        with socket.socket() as server, tempfile.TemporaryDirectory() as root:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            result = self.invoke(root, f"bash -c 'echo connected > /dev/tcp/127.0.0.1/{port}'")
            self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_agent_attempts_include_execution_repeat_and_retry(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "marker"
            command = f"printf x >> {marker}"
            first = self.invoke(root, command)
            repeated = self.invoke(root, command)
            retried = self.invoke(root, command, "--retry")
            self.assertEqual((first.returncode, repeated.returncode, retried.returncode),
                             (0, 3, 0))
            self.assertEqual(json.loads(repeated.stdout)["status"], "not_executed")
            self.assertEqual(marker.read_text(), "xx")
            history = subprocess.run([self.cli, "history", "--repo", root, "--json"],
                                     capture_output=True, text=True)
            self.assertEqual(history.returncode, 0, history.stderr)
            entries = json.loads(history.stdout)
            self.assertEqual([entry["status"] for entry in entries],
                             ["executed", "not_executed", "executed"])
