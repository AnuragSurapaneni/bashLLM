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

    def test_failed_run_has_attempt_id_and_bounded_diagnostic(self):
        with tempfile.TemporaryDirectory() as root:
            result = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--",
                 "python3 -c 'import absent_test_package'"],
                capture_output=True, text=True,
            )
            payload = json.loads(result.stdout)
            self.assertGreater(payload["attempt_id"], 0)
            self.assertEqual(payload["diagnostic"]["category"], "missing_module")
            self.assertIn("absent_test_package", payload["diagnostic"]["evidence"])
            self.assertLessEqual(len(payload["diagnostic"]["next_steps"]), 3)
            history = subprocess.run(
                [self.cli, "history", "--repo", root, "--json"],
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(json.loads(history.stdout)[0]["id"], payload["attempt_id"])

    def test_diagnose_reports_python_environment_and_missing_dependency(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "1"\ndependencies = ["absent_test_package>=1"]\n',
                encoding="utf-8",
            )
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--",
                 "python3 -c 'import absent_test_package'"],
                capture_output=True, text=True,
            )
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id), "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(check.returncode, 0, check.stderr + check.stdout)
            payload = json.loads(check.stdout)
            self.assertEqual(payload["recorded_attempt"]["id"], attempt_id)
            self.assertEqual(payload["recorded_attempt"]["command"],
                             "python3 -c 'import absent_test_package'")
            self.assertIn("absent_test_package", payload["recorded_attempt"]["error_excerpt"])
            self.assertIn("stderr_truncated", payload["recorded_attempt"])
            self.assertIn("PATH", payload["environment"])
            self.assertIn("python", payload["python"]["version"].lower())
            self.assertTrue(payload["python"]["sys_path"])
            self.assertEqual(payload["dependencies"][0]["status"], "missing")
            self.assertLessEqual(len(check.stdout.rstrip("\n")), 1600)

    def test_diagnostic_redacts_secret_and_reports_syntax_location(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--",
                 "python3 broken.py; echo TOKEN=hidden-value >&2; exit 1"],
                capture_output=True, text=True,
            )
            payload = json.loads(run.stdout)
            self.assertEqual(payload["diagnostic"]["category"], "syntax_error")
            self.assertEqual(payload["diagnostic"]["location"]["line"], 1)
            self.assertNotIn("hidden-value", json.dumps(payload["diagnostic"]))

    def test_diagnose_checks_optional_group_only_when_selected(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "1"\n'
                'dependencies = ["absent_core_package"]\n'
                '[project.optional-dependencies]\n'
                'dev = ["absent_dev_package"]\n', encoding="utf-8",
            )
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--", "python3 -c 'exit(1)'"],
                capture_output=True, text=True,
            )
            attempt_id = str(json.loads(run.stdout)["attempt_id"])
            base = [self.cli, "diagnose", "--repo", root, "--attempt-id", attempt_id, "--json"]
            core = json.loads(subprocess.run(base, capture_output=True, text=True, check=True).stdout)
            self.assertEqual([item["requirement"] for item in core["dependencies"]],
                             ["absent_core_package"])
            small = subprocess.run(base + ["--max-detail", "800"],
                                   capture_output=True, text=True, check=True)
            self.assertLessEqual(len(small.stdout.rstrip("\n")), 800)
            selected = json.loads(subprocess.run(base + ["--group", "dev", "--max-detail", "4000"],
                                                 capture_output=True, text=True, check=True).stdout)
            self.assertEqual([item["requirement"] for item in selected["dependencies"]],
                             ["absent_core_package", "absent_dev_package"])

    def test_diagnose_without_python_still_reports_sanitized_environment(self):
        with tempfile.TemporaryDirectory() as root:
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--", "exit 2"],
                capture_output=True, text=True,
            )
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                 "--max-detail", "800", "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(check.returncode, 0, check.stderr + check.stdout)
            payload = json.loads(check.stdout)
            self.assertEqual(payload["status"], "interpreter_ambiguous")
            self.assertIn("PATH", payload["environment"])
            self.assertLessEqual(len(check.stdout.rstrip("\n")), 800)

    def test_diagnose_recognizes_environment_prefix_before_python(self):
        with tempfile.TemporaryDirectory() as root:
            for command in ("env python3 -c 'exit(1)'", "FOO=bar python3 -c 'exit(1)'"):
                with self.subTest(command=command):
                    run = subprocess.run(
                        [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--", command],
                        capture_output=True, text=True,
                    )
                    attempt_id = json.loads(run.stdout)["attempt_id"]
                    check = subprocess.run(
                        [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                         "--json"], capture_output=True, text=True,
                    )
                    self.assertEqual(json.loads(check.stdout)["python"]["status"], "checked")

    def test_multiple_shell_commands_leave_python_interpreter_ambiguous(self):
        with tempfile.TemporaryDirectory() as root:
            for separator in ("; ", "\n"):
                with self.subTest(separator=separator):
                    command = "python3 -c 'exit(1)'" + separator + "./venv/bin/python -c 'exit(1)'"
                    run = subprocess.run(
                        [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--", command],
                        capture_output=True, text=True,
                    )
                    attempt_id = json.loads(run.stdout)["attempt_id"]
                    check = subprocess.run(
                        [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                         "--json"], capture_output=True, text=True,
                    )
                    self.assertEqual(json.loads(check.stdout)["python"]["status"], "ambiguous")

    def test_diagnostic_redacts_space_separated_credential_flag(self):
        with tempfile.TemporaryDirectory() as root:
            command = "python3 -c 'exit(1)' --token hidden-value"
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--", command],
                capture_output=True, text=True,
            )
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                 "--json"], capture_output=True, text=True,
            )
            self.assertNotIn("hidden-value", check.stdout)
            self.assertIn("[REDACTED]", check.stdout)

    def test_diagnostic_redacts_credentials_in_declared_dependency(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "1"\n'
                'dependencies = ["demo-package @ https://user:password@example.com/pkg.whl"]\n',
                encoding="utf-8")
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--",
                 "python3 -c 'exit(1)'"], capture_output=True, text=True,
            )
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                 "--max-detail", "4000", "--json"], capture_output=True, text=True,
            )
            self.assertNotIn("user:password", check.stdout)
            self.assertIn("[REDACTED]", check.stdout)

    def test_diagnose_rejects_missing_and_invalid_attempt_ids_as_json(self):
        with tempfile.TemporaryDirectory() as root:
            for arguments in ([], ["--attempt-id"], ["--attempt-id", "abc"],
                              ["--attempt-id", "0"]):
                with self.subTest(arguments=arguments):
                    check = subprocess.run(
                        [self.cli, "diagnose", "--repo", root, "--json", *arguments],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(check.returncode, 2)
                    self.assertIn("error", json.loads(check.stdout))

    def test_failure_categories_and_evidence_limits(self):
        scenarios = (
            ("no_such_tool_123", "missing_executable", False),
            ("python3 -c 'raise RuntimeError(\"VersionConflict: requires 2 but you have 1\")'",
             "version_conflict", False),
            ("python3 -c 'open(\"missing-data\")'", "python_traceback", False),
            ("echo TOKEN=hidden-value >&2; exit 1", "unclassified", False),
            ("sleep 2", "unclassified", True),
        )
        for command, category, timed_out in scenarios:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as root:
                options = ["--timeout", "0.1"] if timed_out else []
                run = subprocess.run(
                    [self.cli, "run", "--repo", root, "--cwd", root, "--json",
                     *options, "--", command], capture_output=True, text=True,
                )
                payload = json.loads(run.stdout)
                self.assertEqual(payload["diagnostic"]["category"], category)
                self.assertEqual(payload["diagnostic"]["timed_out"], timed_out)
                self.assertNotIn("hidden-value", json.dumps(payload["diagnostic"]))

    def test_diagnostic_probe_cannot_write_repository(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            marker = repo / "marker"
            interpreter = repo / "python"
            interpreter.write_text("#!/bin/sh\nprintf changed > marker\nexit 1\n", encoding="utf-8")
            interpreter.chmod(0o755)
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--", "./python -c ignored"],
                capture_output=True, text=True,
            )
            self.assertEqual(marker.read_text(), "changed")
            marker.write_text("original", encoding="utf-8")
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id), "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(json.loads(check.stdout)["status"], "probe_unverified")
            self.assertEqual(marker.read_text(), "original")

    def test_unsupported_requirement_is_unverified_even_when_absent(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "1"\n'
                'dependencies = ["absent_demo_package[extra]>=1"]\n', encoding="utf-8")
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--",
                 "python3 -c 'exit(1)'"], capture_output=True, text=True,
            )
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                 "--json"], capture_output=True, text=True,
            )
            self.assertEqual(json.loads(check.stdout)["dependencies"][0]["status"], "unverified")

    def test_diagnose_reports_incompatible_installed_distribution(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            environment = repo / ".venv"
            venv.create(environment, with_pip=False, symlinks=False)
            site_packages = environment / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
            distribution = site_packages / "demo_package-1.0.dist-info"
            distribution.mkdir(parents=True, exist_ok=True)
            (distribution / "METADATA").write_text("Name: demo-package\nVersion: 1.0\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text(
                '[project]\nname = "sample"\nversion = "1"\n'
                'dependencies = ["demo-package>=2"]\n', encoding="utf-8")
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", root, "--json", "--",
                 ".venv/bin/python -c 'exit(1)'"], capture_output=True, text=True,
            )
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                 "--max-detail", "4000", "--json"], capture_output=True, text=True,
            )
            payload = json.loads(check.stdout)
            self.assertTrue(payload["python"].get("virtual_environment"), payload)
            self.assertEqual(payload["dependencies"][0]["status"], "incompatible")
            self.assertEqual(payload["dependencies"][0]["installed_version"], "1.0")

    def test_diagnose_uses_nearest_project_and_skips_optional_requirements_file(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root) / "service"
            work.mkdir()
            (work / "pyproject.toml").write_text(
                '[project]\nname = "service"\nversion = "1"\n'
                'dependencies = ["absent_service_package"]\n', encoding="utf-8")
            (work / "requirements-dev.txt").write_text("absent_dev_package\n", encoding="utf-8")
            run = subprocess.run(
                [self.cli, "run", "--repo", root, "--cwd", str(work), "--json", "--",
                 "python3 -c 'exit(1)'"], capture_output=True, text=True,
            )
            attempt_id = json.loads(run.stdout)["attempt_id"]
            check = subprocess.run(
                [self.cli, "diagnose", "--repo", root, "--attempt-id", str(attempt_id),
                 "--max-detail", "4000", "--json"], capture_output=True, text=True,
            )
            payload = json.loads(check.stdout)
            self.assertEqual([entry["requirement"] for entry in payload["dependencies"]],
                             ["absent_service_package"])
            self.assertIn("dev", payload["optional_groups"])


if __name__ == "__main__":
    unittest.main()
