"""Installed-CLI behavior for static repository inspection."""

import json
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class InspectCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        environment = Path(cls.install_dir.name) / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        python = environment / "bin" / "python"
        subprocess.run(
            [python, "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(PROJECT)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def test_briefing_maps_repository_without_running_project_code(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "pyproject.toml").write_text("[project]\nname = 'sample'\n")
            (repo / "src" / "main.py").write_text(
                "from pathlib import Path\nPath('EXECUTED').write_text('yes')\n"
            )
            (repo / "tests" / "test_main.py").write_text("assert True\n")
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root, "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            briefing = (repo / ".bashllm" / "BRIEFING.md").read_text()
            self.assertEqual(Path(payload["briefing"]).resolve(), (repo / ".bashllm" / "BRIEFING.md").resolve())
            for finding in ("src/", "src/main.py", "tests/test_main.py", "pyproject.toml"):
                self.assertIn(finding, briefing)
            self.assertIn("Likely entry points", briefing)
            self.assertIn("Tests", briefing)
            self.assertIn("Build and test commands", briefing)
            self.assertFalse((repo / "EXECUTED").exists())
            repeated = subprocess.run(
                [self.cli, "inspect", "--repo", root, "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual((repo / ".bashllm" / "BRIEFING.md").read_text(), briefing)

    def test_unknown_language_has_file_map_and_limit_omissions(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "mystery.qx").write_text("opaque source\n")
            (repo / "extra.qx").write_text("more source\n")
            (repo / "nested").mkdir()
            (repo / "nested" / "deep.qx").write_text("deep source\n")
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root, "--max-files", "1", "--max-depth", "0", "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            briefing = (repo / ".bashllm" / "BRIEFING.md").read_text()
            self.assertIn("extra.qx", briefing)
            self.assertIn("file limit", briefing)
            self.assertIn("nested/", briefing)
            self.assertIn("depth limit", briefing)
            self.assertEqual(payload["files_scanned"], 1)
            self.assertEqual(len(payload["omissions"]), 2)

    def test_large_repository_bounds_briefing_and_reports_omission_counts(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            for number in range(50):
                (repo / f"file_{number:03}.qx").write_text("source\n")
                (repo / f"dir_{number:03}").mkdir()
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root, "--max-files", "1",
                 "--max-directories", "2", "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            briefing = (repo / ".bashllm" / "BRIEFING.md").read_text()
            self.assertEqual(payload["files_scanned"], 1)
            self.assertEqual(payload["directories_scanned"], 2)
            self.assertEqual(payload["omission_counts"]["file limit"], 49)
            self.assertEqual(payload["omission_counts"]["directory limit"], 48)
            self.assertLessEqual(len(payload["omissions"]), 20)
            self.assertIn("49 files", briefing)
            self.assertIn("48 directories", briefing)
            self.assertLess(len(briefing), 4000)

    def test_oversized_analyzed_content_is_reported_once_per_file(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "main.py").write_text("import requests\n" + "#" * 100)
            (repo / "pyproject.toml").write_text("[project]\nname = 'demo'\n" + "#" * 100)
            (repo / "package.json").write_text('{"scripts":{"test":"true"}}' + " " * 100)
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root, "--max-file-bytes", "32", "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            briefing = (repo / ".bashllm" / "BRIEFING.md").read_text()
            self.assertEqual(payload["omission_counts"]["content limit"], 3)
            self.assertEqual(set(payload["omissions"]), {
                "main.py: content limit", "pyproject.toml: content limit",
                "package.json: content limit",
            })
            self.assertIn("3 files skipped by content limit", briefing)

    def test_rejects_generated_state_symlinks(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            repo = Path(root)
            outside_path = Path(outside)
            (repo / ".bashllm").symlink_to(outside_path, target_is_directory=True)
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr.lower())
            self.assertFalse((outside_path / "BRIEFING.md").exists())

            (repo / ".bashllm").unlink()
            (repo / ".bashllm").mkdir()
            target = outside_path / "outside.md"
            target.write_text("original")
            (repo / ".bashllm" / "BRIEFING.md").symlink_to(target)
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr.lower())
            self.assertEqual(target.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
