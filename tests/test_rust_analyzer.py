"""Installed CLI behavior for Rust project inspection."""

import json
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class RustAnalyzerTests(unittest.TestCase):
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

    def test_cargo_package_targets_and_declared_dependencies(self):
        briefing, dot = self.inspect({
            "Cargo.toml": (
                "[package]\nname = 'demo-app'\nversion = '0.1.0'\n"
                "[dependencies]\nserde = '1'\n"
            ),
            "src/lib.rs": "pub fn value() -> u8 { 1 }\n",
            "src/main.rs": "fn main() {}\n",
            "src/bin/tool.rs": "fn main() {}\n",
        })
        self.assertIn("Rust package `demo-app` — `Cargo.toml`", briefing)
        self.assertIn("Rust library target `demo_app` — `src/lib.rs`", briefing)
        self.assertIn("Rust binary target `demo-app` — `src/main.rs`", briefing)
        self.assertIn("Rust binary target `tool` — `src/bin/tool.rs`", briefing)
        self.assertIn("Declared Rust dependency `serde` (external)", briefing)
        self.assertIn('label="depends on (external)"', dot)
        self.assertIn('label="defines"', dot)
        self.assertIn('tooltip="Cargo.toml:', dot)

    def test_workspace_dependencies_and_source_references(self):
        briefing, dot = self.inspect({
            "Cargo.toml": (
                "[workspace]\nmembers = ['app', 'helper']\n"
                "[workspace.dependencies]\nhelper = { path = 'helper' }\n"
            ),
            "app/Cargo.toml": (
                "[package]\nname = 'app'\nversion = '0.1.0'\n"
                "[dependencies]\nhelper = { workspace = true }\n"
                "[[bin]]\nname = 'runner'\npath = 'src/runner.rs'\n"
            ),
            "app/src/runner.rs": (
                "mod local;\nuse helper::answer;\nuse missing::thing;\nfn main() {}\n"
            ),
            "app/src/local.rs": "pub fn local() {}\n",
            "helper/Cargo.toml": "[package]\nname = 'helper'\nversion = '0.1.0'\n",
            "helper/src/lib.rs": "pub fn answer() -> u8 { 42 }\n",
        })
        self.assertIn("Rust binary target `runner` — `app/src/runner.rs`", briefing)
        self.assertIn("Declared Rust dependency `helper` (internal)", briefing)
        self.assertIn("Inferred Rust reference `helper` (internal) — `app/src/runner.rs:2`", briefing)
        self.assertIn("Inferred Rust reference `missing` (unresolved) — `app/src/runner.rs:3`", briefing)
        self.assertIn('label="depends on"', dot)
        self.assertIn('label="uses"', dot)
        self.assertIn('label="uses (unresolved)"', dot)
        self.assertIn('label="imports"', dot)
        self.assertIn('tooltip="app/src/runner.rs:1:', dot)


if __name__ == "__main__":
    unittest.main()
