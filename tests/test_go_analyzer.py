"""Installed CLI behavior for Go project inspection."""

import json
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class GoAnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        root = Path(cls.install_dir.name)
        source = root / "source"
        source.mkdir()
        shutil.copytree(PROJECT / "src", source / "src")
        shutil.copy2(PROJECT / "pyproject.toml", source / "pyproject.toml")
        environment = root / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        subprocess.run(
            [environment / "bin" / "python", "-m", "pip", "install",
             "--no-build-isolation", "--no-deps", str(source)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def inspect(self, files):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            for name, content in files.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run(
                [self.cli, "inspect", "--repo", root, "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            return Path(payload["briefing"]).read_text(), Path(payload["graph"]).read_text()

    def test_module_packages_entry_and_declared_dependency(self):
        briefing, dot = self.inspect({
            "go.mod": "module example.com/demo\n\ngo 1.22\nrequire github.com/acme/lib v1.2.3\n",
            "cmd/tool/main.go": "package main\nfunc main() {}\n",
            "internal/work/work.go": "package work\nfunc Do() {}\n",
        })
        self.assertIn("Go module `example.com/demo` — `go.mod:1`", briefing)
        self.assertIn("Go package `main` — `cmd/tool/main.go:1`", briefing)
        self.assertIn("Go package `work` — `internal/work/work.go:1`", briefing)
        self.assertIn("Go entry point `cmd/tool/main.go:2`", briefing)
        self.assertIn("Declared Go dependency `github.com/acme/lib` (external) — `go.mod:4`", briefing)
        self.assertIn('label="depends on (external)"', dot)
        self.assertIn('label="entry point"', dot)
        self.assertIn('tooltip="go.mod:4', dot)

    def test_imports_resolve_internal_and_label_external_and_unresolved(self):
        briefing, dot = self.inspect({
            "go.mod": (
                "module example.com/demo\n\ngo 1.22\nrequire (\n"
                "    github.com/acme/lib v1.2.3\n)\n"
            ),
            "cmd/tool/main.go": (
                "package main\nimport (\n"
                "    \"example.com/demo/internal/work\"\n"
                "    lib \"github.com/acme/lib/subpkg\"\n"
                "    \"example.com/demo/missing\"\n"
                "    \"github.com/other/undeclared\"\n"
                ")\nfunc main() {}\n"
            ),
            "internal/work/work.go": "package work\n",
        })
        self.assertIn("Declared Go dependency `github.com/acme/lib` (external) — `go.mod:5`", briefing)
        self.assertIn("Inferred Go import `example.com/demo/internal/work` (internal) — `cmd/tool/main.go:3`", briefing)
        self.assertIn("Inferred Go import `github.com/acme/lib/subpkg` (external) — `cmd/tool/main.go:4`", briefing)
        self.assertIn("Inferred Go import `example.com/demo/missing` (unresolved) — `cmd/tool/main.go:5`", briefing)
        self.assertIn("Inferred Go import `github.com/other/undeclared` (unresolved) — `cmd/tool/main.go:6`", briefing)
        self.assertIn('label="imports"', dot)
        self.assertIn('label="imports (external)"', dot)
        self.assertIn('label="imports (unresolved)"', dot)
        self.assertIn('tooltip="cmd/tool/main.go:3:', dot)

    def test_scanned_nested_module_is_an_internal_dependency(self):
        briefing, dot = self.inspect({
            "go.mod": "module example.com/app\nrequire example.com/helper v0.0.0\n",
            "main.go": "package main\nimport \"example.com/helper\"\nfunc main() {}\n",
            "helper/go.mod": "module example.com/helper\n",
            "helper/helper.go": "package helper\n",
        })
        self.assertIn("Declared Go dependency `example.com/helper` (internal) — `go.mod:2`", briefing)
        self.assertIn("Inferred Go import `example.com/helper` (internal) — `main.go:2`", briefing)
        self.assertIn('label="depends on"', dot)

    def test_mutual_package_imports_report_cycle_with_file_evidence(self):
        briefing, dot = self.inspect({
            "go.mod": "module example.com/demo\n",
            "alpha/alpha.go": 'package alpha\nimport "example.com/demo/beta"\n',
            "beta/beta.go": 'package beta\nimport "example.com/demo/alpha"\n',
        })
        self.assertIn("Dependency cycle: Go package alpha (alpha), Go package beta (beta)", briefing)
        self.assertIn('tooltip="alpha/alpha.go:2:', dot)
        self.assertIn('tooltip="beta/beta.go:2:', dot)


if __name__ == "__main__":
    unittest.main()
