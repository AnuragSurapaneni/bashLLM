"""Installed-CLI behavior for modern Fortran repository inspection."""

import json
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class FortranAnalyzerTests(unittest.TestCase):
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

    def test_mixed_case_program_uses_module_from_another_free_form_extension(self):
        briefing, dot = self.inspect({
            "src/MATH.F95": "MoDuLe Math_Utils\nend module Math_Utils\n",
            "src/main.f90": "PrOgRaM Main\n  UsE MATH_UTILS\nend program Main\n",
        })
        self.assertIn("Fortran", briefing)
        self.assertIn('label="module math_utils"', dot)
        self.assertIn('label="program main"', dot)
        self.assertIn('label="uses"', dot)
        self.assertIn('tooltip="src/main.f90:2:', dot)
        self.assertIn("program main", briefing)
        self.assertIn("module math_utils", briefing)

    def test_continuations_submodules_and_use_statuses_have_source_evidence(self):
        briefing, dot = self.inspect({
            "base.f03": "MoDuLe Base\nend module Base\n",
            "child.f08": (
                "SuBmOdUlE (BASE) Child\n"
                "  UsE & ! continued USE\n"
                "  &Base\n"
                "end submodule Child\n"
            ),
            "grandchild.f90": "submodule (base:CHILD) Grandchild\nend submodule\n",
            "main.f95": (
                "program driver\n"
                "  use, intrinsic :: ISO_FORTRAN_ENV\n"
                "  use, non_intrinsic :: Missing_Local\n"
                "  use Third_Party\n"
                "  use ba&\n"
                "  &se\n"
                "end program\n"
            ),
        })
        for label in (
            'label="submodule child"', 'label="submodule grandchild"',
            'label="uses (intrinsic)"', 'label="uses (external)"',
            'label="uses (unresolved)"', 'label="extends"',
            'tooltip="child.f08:1:', 'tooltip="child.f08:2:',
            'tooltip="main.f95:5:',
        ):
            self.assertIn(label, dot)
        self.assertIn("Fortran submodule child — child.f08:1", briefing)
        self.assertIn("Fortran USE missing_local (unresolved) — main.f95:3", briefing)
        self.assertIn("Fortran USE third_party (external) — main.f95:4", briefing)

    def test_module_procedures_are_not_reported_as_modules(self):
        briefing, dot = self.inspect({
            "implementation.f90": (
                "module actual_module\n"
                "contains\n"
                "  module pure function calculate() result(value)\n"
                "  end function\n"
                "end module actual_module\n"
            ),
        })
        self.assertIn('label="module actual_module"', dot)
        self.assertNotIn('label="module pure"', dot)
        self.assertNotIn("Fortran module pure", briefing)


if __name__ == "__main__":
    unittest.main()
