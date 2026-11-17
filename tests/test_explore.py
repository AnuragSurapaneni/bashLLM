"""Public CLI tests for bounded repository exploration."""

import json
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class ExploreCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        root = Path(cls.install_dir.name)
        source = root / "source"
        source.mkdir()
        shutil.copy2(PROJECT / "pyproject.toml", source)
        shutil.copytree(PROJECT / "src", source / "src")
        environment = root / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        python = environment / "bin" / "python"
        subprocess.run(
            [python, "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(source)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def invoke(self, repo, *arguments):
        return subprocess.run(
            [self.cli, *arguments, "--repo", str(repo)],
            capture_output=True, text=True,
        )

    def test_find_matches_and_excludes_generated_content(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("pass\n")
            (repo / "src" / "other.txt").write_text("text\n")
            (repo / ".bashllm").mkdir()
            (repo / ".bashllm" / "hidden.py").write_text("pass\n")
            result = self.invoke(repo, "find", "*.py", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["files"], ["src/app.py"])

    def test_find_reports_result_limit_in_both_forms(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "a.py").write_text("a")
            (repo / "b.py").write_text("b")
            result = self.invoke(repo, "find", "*.py", "--max-results", "1", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["files"], ["a.py"])
            self.assertTrue(json.loads(result.stdout)["truncated"])
            human = self.invoke(repo, "find", "*.py", "--max-results", "1")
            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertIn("a.py", human.stdout)
            self.assertIn("truncated", human.stderr)

    def test_search_returns_locations_and_no_matches(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("alpha\nneedle here\n")
            (repo / "build").mkdir()
            (repo / "build" / "artifact.py").write_text("needle hidden\n")
            result = self.invoke(repo, "search", "needle", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["matches"], [
                {"path": "src/app.py", "line": 2, "text": "needle here"},
            ])
            absent = self.invoke(repo, "search", "absent", "--json")
            self.assertEqual(absent.returncode, 0, absent.stderr)
            self.assertEqual(json.loads(absent.stdout)["matches"], [])

    def test_search_limits_matches(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "app.py").write_text("hit\nhit again\n")
            result = self.invoke(repo, "search", "hit", "--max-results", "1", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["matches"]), 1)
            self.assertTrue(payload["truncated"])

    def test_search_caps_long_match_text_and_reports_human_truncation(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "app.py").write_text("hit-abcdefghij\n")
            result = self.invoke(repo, "search", "hit", "--max-bytes", "5", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["matches"][0]["text"], "hit-a")
            self.assertTrue(payload["truncated"])
            human = self.invoke(repo, "search", "hit", "--max-bytes", "5")
            self.assertIn("app.py:1:hit-a", human.stdout)
            self.assertIn("truncated", human.stderr)

    def test_search_finds_late_match_in_very_long_line(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "app.py").write_text("x" * (2 * 1024 * 1024) + "needle\nnext line\n")
            result = self.invoke(repo, "search", "needle", "--max-bytes", "8", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["matches"], [
                {"path": "app.py", "line": 1, "text": "xxxxxxxx"},
            ])
            self.assertTrue(payload["truncated"])

    def test_read_limits_content_and_rejects_outside_path(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "note.txt").write_text("abcdef")
            result = self.invoke(repo, "read", "note.txt", "--max-bytes", "3", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["content"], "abc")
            self.assertTrue(json.loads(result.stdout)["truncated"])
            human = self.invoke(repo, "read", "note.txt", "--max-bytes", "3")
            self.assertEqual(human.stdout, "abc")
            self.assertIn("truncated", human.stderr)
            outside = self.invoke(repo, "read", "../outside.txt", "--json")
            self.assertNotEqual(outside.returncode, 0)


if __name__ == "__main__":
    unittest.main()
