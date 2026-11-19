"""Installed-CLI behavior for the portable agent contract and refusal path."""

import json
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class AgentIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_dir = tempfile.TemporaryDirectory()
        environment = Path(cls.install_dir.name) / "venv"
        venv.create(environment, with_pip=True, system_site_packages=True)
        subprocess.run(
            [environment / "bin" / "python", "-m", "pip", "install", "--no-build-isolation",
             "--no-deps", str(PROJECT)],
            check=True, capture_output=True, text=True,
        )
        cls.cli = environment / "bin" / "bashllm"

    @classmethod
    def tearDownClass(cls):
        cls.install_dir.cleanup()

    def invoke(self, *arguments):
        return subprocess.run([self.cli, *map(str, arguments)], capture_output=True, text=True)

    def test_agent_spec_describes_read_and_execution_contract(self):
        result = self.invoke("agent-spec", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], 2)
        commands = {entry["name"]: entry for entry in payload["commands"]}
        self.assertEqual(set(commands), {"inspect", "context", "find", "search", "read", "history", "result", "diagnose", "run"})
        self.assertIn("--agent", commands["run"]["arguments"]["required"])
        self.assertIn("--no-history", commands["run"]["arguments"]["forbidden"])
        self.assertIn("backend_unavailable", commands["run"]["result_by_status"])
        self.assertEqual(commands["history"]["result_container"], "array")

    def test_agent_can_explore_without_execution_backend(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "main.py").write_text("print('needle')\n")
            self.assertEqual(self.invoke("inspect", "--repo", root, "--json").returncode, 0)
            context = json.loads(self.invoke("context", "--repo", root, "--json").stdout)
            self.assertIn("main.py", context["briefing"])
            self.assertEqual(json.loads(self.invoke("find", "*.py", "--repo", root, "--json").stdout)["files"], ["main.py"])
            self.assertEqual(json.loads(self.invoke("search", "needle", "--repo", root, "--json").stdout)["matches"][0]["path"], "main.py")
            self.assertIn("needle", json.loads(self.invoke("read", "main.py", "--repo", root, "--json").stdout)["content"])

    def test_agent_refusal_is_structured_audited_and_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "marker"
            result = self.invoke("run", "--agent", "--repo", root, "--cwd", root,
                                 "--json", "--", f"touch {marker}")
            if result.returncode != 69:
                self.skipTest("a verified execution backend is available on this host")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "backend_unavailable")
            self.assertFalse(marker.exists())
            human = self.invoke("run", "--repo", root, "--cwd", root,
                                "--", f"touch {marker}")
            self.assertEqual(human.returncode, 69)
            self.assertIn("run refused", human.stderr)
            self.assertFalse(marker.exists())
            entries = json.loads(self.invoke("history", "--repo", root, "--json").stdout)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["status"], "backend_unavailable")
            self.assertEqual(entries[0]["command"], f"touch {marker}")
            repeated = self.invoke("run", "--agent", "--repo", root, "--cwd", root,
                                   "--json", "--", f"touch {marker}")
            retried = self.invoke("run", "--agent", "--retry", "--repo", root,
                                  "--cwd", root, "--json", "--", f"touch {marker}")
            self.assertEqual((repeated.returncode, retried.returncode), (69, 69))
            self.assertEqual(len(json.loads(self.invoke("history", "--repo", root,
                                                  "--json").stdout)), 3)
            blocked = self.invoke("run", "--agent", "--no-history", "--repo", root,
                                  "--cwd", root, "--", "true")
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("cannot disable history", blocked.stderr)
            grant = self.invoke("run", "--agent", "--tool-path", root, "--repo", root,
                                "--cwd", root, "--", "true")
            self.assertNotEqual(grant.returncode, 0)
            self.assertIn("configured outside", grant.stderr)
