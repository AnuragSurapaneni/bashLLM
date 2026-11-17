"""Installed-CLI behavior for static architecture graphs."""

import json
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        environment = Path(cls.install_dir.name) / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        subprocess.run(
            [environment / "bin" / "python", "-m", "pip", "install",
             "--no-build-isolation", "--no-deps", str(PROJECT)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def inspect(self, repo, *options):
        result = subprocess.run(
            [self.cli, "inspect", "--repo", str(repo), "--json", *options],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), (repo / ".bashllm" / "BRIEFING.md").read_text()

    def test_graph_contains_structure_and_dependency_edges(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text("import helper\n")
            (repo / "helper.py").write_text("VALUE = 1\n")
            payload, briefing = self.inspect(repo)
            dot = Path(payload["graph"]).read_text()
            self.assertIn("```mermaid\nflowchart", briefing)
            self.assertIn("digraph bashllm {", dot)
            self.assertIn('label="contains"', dot)
            self.assertIn('label="imports"', dot)
            self.assertIn('label="helper.py"', dot)
            self.assertIn('label="src/main.py"', dot)

    def test_graph_distinguishes_external_unresolved_uncertain_and_cycles(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "pkg").mkdir()
            (repo / "pkg" / "__init__.py").write_text("")
            (repo / "pkg" / "a.py").write_text(
                "import pkg.b\nimport requests\nfrom .missing import item\n"
                "try:\n    import optional_plugin\nexcept ImportError:\n    pass\n"
            )
            (repo / "pkg" / "b.py").write_text("import pkg.a\n")
            _, briefing = self.inspect(repo)
            dot = (repo / ".bashllm" / "GRAPH.dot").read_text()
            self.assertIn('label="imports (external)"', dot)
            self.assertIn('label="imports (unresolved)"', dot)
            self.assertIn('label="imports (uncertain)"', dot)
            self.assertIn("Dependency cycle: pkg/a.py, pkg/b.py", briefing)
            self.assertIn("unresolved relationship", briefing)

    def test_graph_is_bounded_in_briefing_but_dot_keeps_scanned_relationships(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            for number in range(40):
                (repo / f"file_{number:02}.py").write_text("VALUE = 1\n")
            payload, briefing = self.inspect(repo, "--max-files", "30")
            dot = Path(payload["graph"]).read_text()
            mermaid = briefing.split("```mermaid\n", 1)[1].split("\n```", 1)[0]
            self.assertIn("Graph: ", briefing)
            self.assertIn("file_29.py", dot)
            self.assertNotIn("file_30.py", dot)
            self.assertIn("file limit", briefing)
            self.assertLess(len(mermaid.splitlines()), 60)

    def test_mermaid_keeps_dependency_when_directories_exceed_node_budget(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            for number in range(30):
                (repo / f"dir_{number:02}").mkdir()
            (repo / "main.py").write_text("import helper\n")
            (repo / "helper.py").write_text("VALUE = 1\n")
            _, briefing = self.inspect(repo)
            mermaid = briefing.split("```mermaid\n", 1)[1].split("\n```", 1)[0]
            self.assertIn('"main.py"', mermaid)
            self.assertIn('"helper.py"', mermaid)
            self.assertIn("-->|imports|", mermaid)
            self.assertLessEqual(sum('["' in line for line in mermaid.splitlines()), 24)

    def test_rejects_dot_artifact_symlink(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            repo = Path(root)
            state = repo / ".bashllm"
            state.mkdir()
            target = Path(outside) / "outside.dot"
            target.write_text("original")
            (state / "GRAPH.dot").symlink_to(target)
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr.lower())
            self.assertEqual(target.read_text(), "original")

    def test_long_dependency_cycle_does_not_exhaust_recursion(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            for number in range(1050):
                next_number = (number + 1) % 1050
                (repo / f"f_{number:04}.py").write_text(f"import f_{next_number:04}\n")
            payload, briefing = self.inspect(repo)
            self.assertEqual(payload["files_scanned"], 1050)
            self.assertIn("Dependency cycle:", briefing)
            self.assertIn("and 1042 more nodes", briefing)
            self.assertIn("f_1049.py", Path(payload["graph"]).read_text())


if __name__ == "__main__":
    unittest.main()
