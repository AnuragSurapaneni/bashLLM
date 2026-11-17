"""Installed CLI behavior for legacy Fortran and build descriptions."""

import json
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class FortranLegacyTests(unittest.TestCase):
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
                [self.cli, "inspect", "--repo", str(repo), "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            return (Path(payload["briefing"]).read_text(),
                    Path(payload["graph"]).read_text())

    def test_fixed_form_continuation_and_comment_columns(self):
        briefing, dot = self.inspect({
            "mod.for": "      MODULE LEGACY\n      END MODULE LEGACY\n",
            "main.f77": (
                "C     USE GHOST\n"
                "      PROGRAM DRIVER\n"
                "      USE LEG\n"
                "     1ACY\n"
                "      END PROGRAM DRIVER\n"
            ),
        })
        self.assertIn("Fortran module legacy — mod.for:1", briefing)
        self.assertIn("Fortran program driver — main.f77:2", briefing)
        self.assertIn('label="uses"', dot)
        self.assertIn('tooltip="main.f77:3: USE LEGACY"', dot)
        self.assertNotIn("ghost", dot.lower())

    def test_preprocessed_edges_and_includes_report_uncertainty(self):
        briefing, dot = self.inspect({
            "base.f90": "module base\nend module\n",
            "defs.inc": "integer :: value\n",
            "main.F90": (
                "#ifdef FEATURE\n"
                "program driver\n"
                "  use base\n"
                "  include 'defs.inc'\n"
                "#endif\n"
                "#include SOME_HEADER\n"
            ),
        })
        self.assertIn('label="uses (uncertain)"', dot)
        self.assertIn('label="includes (uncertain)"', dot)
        self.assertIn('tooltip="main.F90:4:', dot)
        self.assertIn('tooltip="main.F90:6:', dot)
        self.assertIn("uncertain relationship", briefing)

    def test_fixed_form_include_resolves_relative_file(self):
        briefing, dot = self.inspect({
            "src/main.f": "      PROGRAM DRIVER\n      INCLUDE 'values.inc'\n      END\n",
            "src/values.inc": "      INTEGER VALUE\n",
        })
        self.assertIn('label="includes"', dot)
        self.assertIn('tooltip="src/main.f:2:', dot)
        self.assertNotIn('label="includes (unresolved)"', dot)

    def test_uppercase_fixed_form_is_conservatively_uncertain(self):
        briefing, dot = self.inspect({
            "base.f": "      MODULE BASE\n      END MODULE BASE\n",
            "driver.F": "      PROGRAM DRIVER\n      USE BASE\n      END\n",
        })
        self.assertIn('label="uses (uncertain)"', dot)
        self.assertIn('tooltip="driver.F:2: USE BASE"', dot)
        self.assertIn("uncertain relationship", briefing)

    def test_fpm_cmake_and_make_targets_have_dependencies_and_evidence(self):
        briefing, dot = self.inspect({
            "fpm.toml": (
                'name = "legacy"\n'
                '[dependencies]\n'
                'json-fortran = { git = "https://example.invalid/json" }\n'
                '[[executable]]\n'
                'name = "driver"\n'
            ),
            "CMakeLists.txt": (
                "add_library(core src/core.f90)\n"
                "add_executable(app src/main.f90)\n"
                "target_link_libraries(app PRIVATE core)\n"
            ),
            "Makefile": "all: app\napp: src/main.f90\n",
            "src/core.f90": "module core\nend module\n",
            "src/main.f90": "program main\nend program\n",
        })
        for name in ("driver", "core", "app", "all", "json-fortran"):
            self.assertIn(name, dot)
        self.assertIn('label="depends on"', dot)
        self.assertIn('tooltip="CMakeLists.txt:3:', dot)
        self.assertIn('tooltip="Makefile:1:', dot)
        self.assertIn('tooltip="fpm.toml:3:', dot)
        self.assertIn("Fortran build target", briefing)

    def test_multiline_cmake_target_and_link_dependency(self):
        _, dot = self.inspect({
            "CMakeLists.txt": (
                "add_library(core\n  src/core.f90\n)\n"
                "add_executable(app\n  src/main.f90\n)\n"
                "target_link_libraries(app\n  PRIVATE core\n)\n"
            ),
            "src/core.f90": "module core\nend module\n",
            "src/main.f90": "program main\nend program\n",
        })
        self.assertIn('label="depends on", tooltip="CMakeLists.txt:7: core"', dot)
        self.assertIn('label="depends on", tooltip="CMakeLists.txt:1: src/core.f90"', dot)

    def test_cmake_only_non_fortran_repository_has_no_fortran_findings(self):
        briefing, dot = self.inspect({
            "CMakeLists.txt": "add_executable(app src/main.cpp)\n",
            "src/main.cpp": "int main() { return 0; }\n",
        })
        self.assertNotIn("Fortran build target", briefing)
        self.assertNotIn("Fortran build dependency", briefing)
        self.assertNotIn('label="app"', dot)


if __name__ == "__main__":
    unittest.main()
