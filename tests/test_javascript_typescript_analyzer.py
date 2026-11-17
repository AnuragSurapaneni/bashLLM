"""Installed CLI behavior for JavaScript and TypeScript inspection."""

import json
import shutil
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class JavaScriptTypeScriptAnalyzerTests(unittest.TestCase):
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
            return Path(payload["briefing"]).read_text(), Path(payload["graph"]).read_text()

    def test_javascript_manifest_scripts_entry_and_dependencies(self):
        briefing, dot = self.inspect({
            "package.json": json.dumps({
                "name": "web-tool", "main": "./src/index.js",
                "bin": {"web-tool": "./bin/cli.js"},
                "scripts": {"build": "node build.js", "start": "node bin/cli.js"},
                "dependencies": {"chalk": "^5.0.0"},
                "devDependencies": {"vitest": "^2.0.0"},
            }),
            "src/index.js": "import { helper } from './helper.js';\nimport chalk from 'chalk';\n",
            "src/helper.js": "export const helper = 1;\n",
            "bin/cli.js": "#!/usr/bin/env node\nimport '../src/index.js';\n",
        })
        self.assertIn("JavaScript package `web-tool`", briefing)
        self.assertIn("Script `build`", briefing)
        self.assertIn("Script `start`", briefing)
        self.assertIn("Entry point `main`", briefing)
        self.assertIn("Entry point `bin.web-tool`", briefing)
        self.assertIn("Declared dependency `chalk@^5.0.0`", briefing)
        self.assertIn("Declared dependency `vitest@^2.0.0`", briefing)
        self.assertIn("Inferred import `chalk`", briefing)
        self.assertIn('label="imports"', dot)
        self.assertIn('label="imports (external)"', dot)
        self.assertIn('label="src/helper.js"', dot)
        self.assertIn('tooltip="src/index.js:1:', dot)
        self.assertIn('label="entry point"', dot)
        self.assertIn('label="depends on (external)"', dot)

    def test_typescript_extensionless_index_reexports_and_missing_import(self):
        briefing, dot = self.inspect({
            "package.json": json.dumps({
                "name": "@acme/core", "module": "./src/index.ts",
                "types": "./src/index.ts", "scripts": {"typecheck": "tsc --noEmit"},
            }),
            "src/index.ts": (
                "export { value } from './lib';\n"
                "import type { Thing } from './types';\n"
                "import { gone } from './missing';\n"
                "const lazy = import('lodash');\n"
            ),
            "src/lib/index.ts": "export const value = 1;\n",
            "src/types.ts": "export type Thing = number;\n",
        })
        self.assertIn("TypeScript package `@acme/core`", briefing)
        self.assertIn("Script `typecheck`", briefing)
        self.assertIn("Entry point `module`", briefing)
        self.assertIn("Entry point `types`", briefing)
        self.assertIn("Inferred import `lodash`", briefing)
        self.assertIn("Unresolved import `./missing`", briefing)
        self.assertIn('label="src/lib/index.ts"', dot)
        self.assertIn('label="src/types.ts"', dot)
        self.assertIn('label="imports (unresolved)"', dot)
        self.assertIn('label="imports (external)"', dot)

    def test_standalone_modern_extensions_are_source_files_with_languages(self):
        briefing, dot = self.inspect({
            "main.mjs": "import './helper.cjs';\n",
            "helper.cjs": "module.exports = 1;\n",
            "types.mts": "import type { Value } from './value.cts';\n",
            "value.cts": "export type Value = number;\n",
        })
        self.assertIn("- JavaScript", briefing)
        self.assertIn("- TypeScript", briefing)
        sources = briefing.split("## Source files\n", 1)[1].split("\n## ", 1)[0]
        for filename in ("main.mjs", "helper.cjs", "types.mts", "value.cts"):
            self.assertIn(f"`{filename}`", sources)
        self.assertIn('label="imports"', dot)
        self.assertIn('label="helper.cjs"', dot)
        self.assertIn('label="value.cts"', dot)


if __name__ == "__main__":
    unittest.main()
