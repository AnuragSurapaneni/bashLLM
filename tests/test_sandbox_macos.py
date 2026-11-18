"""Installed-CLI containment behavior on a native macOS host."""

import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "darwin", "native macOS containment test")
class MacOSSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path("/usr/bin/sandbox-exec").is_file():
            raise unittest.SkipTest("sandbox-exec is not installed")
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
            if os.environ.get("BASHLLM_REQUIRE_MACOS_SANDBOX") == "1":
                raise AssertionError(f"macOS containment is required: {probe.stdout}")
            raise unittest.SkipTest(f"macOS containment unavailable: {probe.stdout}")
        if probe.returncode != 0:
            cls.install_dir.cleanup()
            raise AssertionError(f"macOS containment probe failed: {probe.stdout} {probe.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    @classmethod
    def invoke(cls, repo, command, *options, env=None):
        return subprocess.run(
            [cls.cli, "run", "--agent", "--repo", str(repo), "--cwd", str(repo),
             "--json", *options, "--", command],
            capture_output=True, text=True, env=env,
        )

    def test_repository_write_and_private_temporary_file(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "created"
            command = (
                f"printf ok > {shlex.quote(str(marker))} || exit; "
                "temporary=$(mktemp \"$TMPDIR/bashllm.XXXXXX\") || exit; "
                "printf tmp > \"$temporary\" || exit; "
                "printf '%s\\n%s\\n' \"$TMPDIR\" \"$temporary\""
            )
            result = self.invoke(root, command)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(marker.read_text(), "ok")
            temporary_root, temporary = json.loads(result.stdout)["stdout"].splitlines()
            self.assertTrue(Path(temporary).is_relative_to(Path(temporary_root)), temporary)
            self.assertTrue(temporary_root.startswith("/private/tmp/"), temporary_root)
            self.assertEqual(self.invoke(root, f"test ! -e {shlex.quote(temporary)}").returncode, 0)

    def test_outside_file_and_symlink_escape_are_denied(self):
        with tempfile.TemporaryDirectory() as outer:
            repo = Path(outer) / "repo"
            repo.mkdir()
            secret = Path(outer) / "outside-secret"
            secret.write_text("keep")
            link = repo / "link"
            link.symlink_to(secret)
            command = (
                f"! cat {shlex.quote(str(secret))} >/dev/null 2>&1 && "
                f"! cat {shlex.quote(str(link))} >/dev/null 2>&1"
            )
            result = self.invoke(repo, command)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.invoke(repo, f"printf bad > {shlex.quote(str(secret))}")
            self.assertEqual(secret.read_text(), "keep")

    def test_inherited_secret_environment_is_removed(self):
        with tempfile.TemporaryDirectory() as root:
            environment = {**os.environ, "BASHLLM_TEST_SECRET": "should-not-appear"}
            result = self.invoke(root, 'test -z "${BASHLLM_TEST_SECRET+x}"', env=environment)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_host_loopback_service_is_unreachable(self):
        with socket.socket() as server, tempfile.TemporaryDirectory() as root:
            server.bind(("127.0.0.1", 0))
            server.listen(2)
            port = server.getsockname()[1]
            command = f"echo connected > /dev/tcp/127.0.0.1/{port}"
            control = subprocess.run(["/bin/bash", "-c", command], capture_output=True, text=True)
            if control.returncode:
                self.skipTest(f"host Bash cannot make a control connection: {control.stderr}")
            result = self.invoke(root, f"/bin/bash -c {shlex.quote(command)}")
            self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_unavailable_tool_path_refuses_without_running_command(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "marker"
            unavailable = Path(root) / "no-such-tool"
            result = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json",
                 "--tool-path", str(unavailable), "--", f"touch {shlex.quote(str(marker))}"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 69, result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "backend_unavailable")
            self.assertFalse(marker.exists())
