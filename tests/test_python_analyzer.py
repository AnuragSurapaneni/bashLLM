"""Installed CLI behavior for Python project analysis."""

import json
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class PythonAnalyzerTests(unittest.TestCase):
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
            [environment / "bin" / "python", "-m", "pip", "install",
             "--no-build-isolation", "--no-deps", str(source)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def inspect(self, repo):
        result = subprocess.run(
            [self.cli, "inspect", "--repo", str(repo), "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        return Path(payload["briefing"]).read_text(), Path(payload["graph"]).read_text()

    def test_pyproject_scripts_dependencies_and_src_imports(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "src" / "acme").mkdir(parents=True)
            (repo / "pyproject.toml").write_text(
                "[project]\nname = 'acme'\ndependencies = ['requests>=2']\n"
                "[project.scripts]\nacme = 'acme.cli:main'\n"
            )
            (repo / "src" / "acme" / "__init__.py").write_text("")
            (repo / "src" / "acme" / "cli.py").write_text(
                "import requests\nfrom acme import core\ndef main(): pass\n"
            )
            (repo / "src" / "acme" / "core.py").write_text("VALUE = 1\n")
            briefing, dot = self.inspect(repo)
            self.assertIn("Python project `acme`", briefing)
            self.assertIn("`pyproject.toml`", briefing)
            self.assertIn("`acme` → `acme.cli:main`", briefing)
            self.assertIn("Declared dependency `requests>=2`", briefing)
            self.assertIn("Inferred import `requests`", briefing)
            self.assertIn('label="depends on (external)"', dot)
            self.assertIn('label="entry point"', dot)
            self.assertIn('label="imports"', dot)
            self.assertIn('label="src/acme/core.py"', dot)
            self.assertNotIn('label="acme"', dot)  # no false external import for src layout

    def test_setup_cfg_requirements_and_relative_imports(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "widget").mkdir()
            (repo / "setup.cfg").write_text(
                "[metadata]\nname = widget\n"
                "[options]\ninstall_requires =\n    click>=8\n"
                "[options.entry_points]\nconsole_scripts =\n    widget = widget.cli:main\n"
            )
            (repo / "requirements-dev.txt").write_text("pytest>=7\n-r requirements.txt\n")
            (repo / "widget" / "__init__.py").write_text("")
            (repo / "widget" / "cli.py").write_text(
                "from . import helper\nfrom .missing import value\n"
            )
            (repo / "widget" / "helper.py").write_text("VALUE = 1\n")
            briefing, dot = self.inspect(repo)
            self.assertIn("Declared dependency `click>=8` — `setup.cfg`", briefing)
            self.assertIn("Declared dependency `pytest>=7` — `requirements-dev.txt:1`", briefing)
            self.assertIn("`widget` → `widget.cli:main`", briefing)
            self.assertIn('label="widget/helper.py"', dot)
            self.assertIn('label="imports (unresolved)"', dot)

    def test_setup_py_is_read_statically(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "setup.py").write_text(
                "from setuptools import setup\n"
                "open('EXECUTED', 'w').write('bad')\n"
                "setup(name='static-demo', install_requires=['httpx>=0.25'], "
                "entry_points={'console_scripts': ['demo=tool:main']})\n"
            )
            (repo / "tool.py").write_text("def main(): pass\n")
            briefing, dot = self.inspect(repo)
            self.assertIn("Python project `static-demo` — `setup.py`", briefing)
            self.assertIn("Declared dependency `httpx>=0.25`", briefing)
            self.assertIn("`demo` → `tool:main`", briefing)
            self.assertIn('label="entry point"', dot)
            self.assertFalse((repo / "EXECUTED").exists())


if __name__ == "__main__":
    unittest.main()
