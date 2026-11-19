"""Process-level checks for the stdio MCP adapter."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class McpProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.install_dir = tempfile.TemporaryDirectory()
        venv_path = Path(cls.install_dir.name) / "venv"
        venv.create(venv_path, with_pip=True, system_site_packages=True)
        python = venv_path / "bin" / "python"
        subprocess.run(
            [python, "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(ROOT)],
            check=True, capture_output=True, text=True,
        )
        cls.mcp = venv_path / "bin" / "bashllm-mcp"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.install_dir.cleanup()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        (self.repo / "hello.txt").write_text("hello from mcp\n", encoding="utf-8")
        self.process = subprocess.Popen(
            [self.mcp, "--repo", str(self.repo)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self._stop)

    def _stop(self) -> None:
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()

    def exchange(self, identifier: int, method: str, params: dict | None = None) -> dict:
        request = {"jsonrpc": "2.0", "id": identifier, "method": method}
        if params is not None:
            request["params"] = params
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        answer = self.process.stdout.readline()
        self.assertTrue(answer, "MCP server exited without a response")
        return json.loads(answer)

    def initialize(self) -> None:
        answer = self.exchange(1, "initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        })
        self.assertEqual(answer["result"]["protocolVersion"], "2025-11-25")
        self.process.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        self.process.stdin.flush()

    def call(self, identifier: int, name: str, arguments: dict) -> dict:
        return self.exchange(identifier, "tools/call", {"name": name, "arguments": arguments})["result"]

    def test_tools_require_initialization_and_have_fixed_schemas(self) -> None:
        self.assertEqual(self.exchange(1, "tools/list")["error"]["code"], -32000)
        self.initialize()
        tools = self.exchange(2, "tools/list")["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], [
            "bashllm_find", "bashllm_search", "bashllm_read", "bashllm_inspect",
            "bashllm_context", "bashllm_history", "bashllm_diagnose", "bashllm_result", "bashllm_run",
        ])
        self.assertEqual(tools[-1]["inputSchema"]["required"], ["repo", "command"])
        self.assertEqual(tools[-1]["inputSchema"]["properties"]["repo"]["const"], str(self.repo.resolve()))
        self.assertFalse(tools[-1]["annotations"]["readOnlyHint"])
        self.assertTrue(tools[-1]["_meta"]["anthropic/requiresUserInteraction"])
        self.assertNotIn("tool_path", tools[-1]["inputSchema"]["properties"])
        self.assertTrue(tools[-3]["_meta"]["anthropic/requiresUserInteraction"])

    def test_read_and_search_use_fixed_repository(self) -> None:
        self.initialize()
        read = self.call(2, "bashllm_read", {"path": "hello.txt"})
        self.assertFalse(read["isError"])
        self.assertEqual(read["structuredContent"]["content"], "hello from mcp\n")
        search = self.call(3, "bashllm_search", {"query": "from mcp"})
        self.assertEqual(search["structuredContent"]["matches"][0]["path"], "hello.txt")
        outside = self.call(4, "bashllm_read", {"path": "../outside.txt"})
        self.assertTrue(outside["isError"])
        override = self.call(5, "bashllm_find", {"pattern": "--repo=/tmp"})
        self.assertFalse(override["isError"])
        self.assertEqual(override["structuredContent"]["files"], [])

    def test_run_rejects_escape_arguments_before_subprocess(self) -> None:
        self.initialize()
        self.assertTrue(self.call(2, "bashllm_run", {"command": "pwd"})["isError"])
        for arguments in (
            {"repo": None, "command": "pwd"},
            {"command": "pwd", "no_history": True},
            {"command": "pwd", "tool_path": "/tmp"},
            {"command": "pwd", "repo": "/tmp"},
            {"command": "pwd", "cwd": ".."},
            {"command": "pwd", "cwd": "/tmp"},
            {"command": "pwd", "timeout_seconds": 600},
            {"command": "pwd\0echo bad"},
        ):
            with self.subTest(arguments=arguments):
                result = self.call(2, "bashllm_run", {"repo": str(self.repo.resolve()), **arguments})
                self.assertTrue(result["isError"])
        self.assertFalse((self.repo / ".bashllm" / "history.sqlite3").exists())

    def test_run_is_agent_audited_even_if_backend_refuses(self) -> None:
        self.initialize()
        result = self.call(2, "bashllm_run", {
            "repo": str(self.repo.resolve()), "command": "pwd", "timeout_seconds": 2,
        })
        self.assertIn("structuredContent", result, result)
        payload = result["structuredContent"]
        self.assertIn(payload["status"], {"executed", "backend_unavailable"})
        self.assertEqual(payload["command"], "pwd")
        self.assertGreater(payload["attempt_id"], 0)
        self.assertTrue((self.repo / ".bashllm" / "history.sqlite3").exists())
        history = self.call(3, "bashllm_history", {"limit": 5})
        self.assertFalse(history["isError"])
        self.assertEqual(history["structuredContent"]["entries"][0]["command"], "pwd")

    def test_diagnostic_and_result_use_recorded_attempt(self) -> None:
        self.initialize()
        run = self.call(2, "bashllm_run", {
            "repo": str(self.repo.resolve()), "command": "python3 -c 'import absent_test_package'",
        })["structuredContent"]
        attempt_id = run["attempt_id"]
        detail = self.call(3, "bashllm_result", {"attempt_id": attempt_id, "max_bytes": 500})
        self.assertFalse(detail["isError"])
        self.assertEqual(detail["structuredContent"]["attempt_id"], attempt_id)
        diagnosis = self.call(4, "bashllm_diagnose", {"attempt_id": attempt_id})
        self.assertIn("structuredContent", diagnosis)
        self.assertEqual(diagnosis["structuredContent"]["recorded_attempt"]["id"], attempt_id)
        if run["status"] == "executed":
            self.assertNotIn("stderr", run)
            self.assertIn("diagnostic", run)
        history = self.call(5, "bashllm_history", {})["structuredContent"]["entries"]
        self.assertEqual(len(history), 1)

    def test_compact_failure_saves_estimated_tokens(self) -> None:
        self.initialize()
        command = (
            "for i in {1..256}; do "
            "printf 'error %03d: dependency check failed\\n' \"$i\" >&2; "
            "done; exit 1"
        )
        run = self.call(2, "bashllm_run", {
            "repo": str(self.repo.resolve()), "command": command,
        })
        summary = run["structuredContent"]
        if summary["status"] == "backend_unavailable":
            self.skipTest("contained command execution is unavailable on this host")
        self.assertEqual(summary["status"], "executed")
        detail = self.call(3, "bashllm_result", {
            "attempt_id": summary["attempt_id"], "max_bytes": 32768,
        })["structuredContent"]
        raw_stderr_bytes = len(detail["stderr"].encode("utf-8"))
        self.assertGreater(raw_stderr_bytes, 8000)

        # The previous MCP response copied full JSON into text and structured
        # content. Counting stderr alone makes this a conservative baseline.
        baseline_estimated_tokens = (2 * raw_stderr_bytes + 3) // 4
        compact_bytes = (len(run["content"][0]["text"].encode("utf-8")) +
                         len(json.dumps(summary, ensure_ascii=False).encode("utf-8")))
        compact_estimated_tokens = (compact_bytes + 3) // 4
        saved_estimated_tokens = baseline_estimated_tokens - compact_estimated_tokens
        self.assertGreaterEqual(
            saved_estimated_tokens, 3000,
            f"saved {saved_estimated_tokens} estimated tokens "
            f"({baseline_estimated_tokens} baseline, {compact_estimated_tokens} compact)",
        )
        print(f"estimated token saving: {saved_estimated_tokens} "
              f"({baseline_estimated_tokens} baseline, {compact_estimated_tokens} compact)")

    def test_unknown_attempt_does_not_create_history(self) -> None:
        self.initialize()
        invalid = self.call(2, "bashllm_diagnose", {"attempt_id": 0})
        self.assertTrue(invalid["isError"])
        self.assertIn("error", invalid["structuredContent"])
        diagnosis = self.call(2, "bashllm_diagnose", {"attempt_id": 999})
        self.assertTrue(diagnosis["isError"])
        self.assertEqual(diagnosis["structuredContent"]["error"], "attempt not found")
        self.assertFalse((self.repo / ".bashllm").exists())

    def test_oversized_request_does_not_break_following_calls(self) -> None:
        self.process.stdin.write("x" * 1_000_001 + "\n")
        self.process.stdin.flush()
        self.assertEqual(json.loads(self.process.stdout.readline())["error"]["code"], -32700)
        self.initialize()
        self.assertEqual(self.exchange(2, "ping")["result"], {})


if __name__ == "__main__":
    unittest.main()
