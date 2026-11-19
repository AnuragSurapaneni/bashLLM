"""Compare legacy and compact MCP response sizes for fixed failure scenarios."""

import json
import math
import subprocess
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def cli(executable: Path, *arguments: str) -> tuple[int, dict]:
    process = subprocess.run([executable, *arguments], capture_output=True, text=True)
    try:
        return process.returncode, json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(process.stderr or process.stdout) from error


def tokens(payload: dict) -> int:
    # The previous MCP adapter presented full JSON in both content fields.
    return math.ceil(2 * len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) / 4)


def mcp_tokens(result: dict) -> int:
    visible = result["content"][0]["text"]
    structured = json.dumps(result.get("structuredContent", {}), ensure_ascii=False)
    return math.ceil((len(visible.encode("utf-8")) + len(structured.encode("utf-8"))) / 4)


def legacy(payload: dict) -> dict:
    return {key: value for key, value in payload.items()
            if key not in {"attempt_id", "diagnostic", "previous_diagnostic", "previous_attempt_id"}}


class McpClient:
    def __init__(self, executable: Path, repo: Path) -> None:
        self.process = subprocess.Popen([executable, "--repo", str(repo)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                    "clientInfo": {"name": "benchmark", "version": "1"}})

    def request(self, method: str, params: dict) -> dict:
        request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(self.process.stderr.read())
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["result"]

    def call(self, name: str, arguments: dict) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        self.process.stdin.close()
        self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        install = base / "install"
        venv.create(install, with_pip=True, system_site_packages=True)
        python = install / "bin/python"
        subprocess.run([python, "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(ROOT)],
                       check=True, capture_output=True, text=True)
        executable = install / "bin/bashllm"
        repo = base / "repo"
        repo.mkdir()
        repo = repo.resolve()
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "sample"\nversion = "1"\n'
            'dependencies = ["absent_demo_package>=1"]\n', encoding="utf-8")
        (repo / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
        venv.create(repo / ".venv", with_pip=False)
        cases = [
            ("wrong interpreter", "/usr/bin/python3 -c 'import absent_demo_package'", None, True),
            ("missing distribution", "python3 -c 'import absent_demo_package'", None, True),
            ("version conflict", "python3 -c 'raise RuntimeError(\"VersionConflict: requires 2 but you have 1\")'", None, True),
            ("syntax error", "python3 broken.py", None, False),
            ("missing executable", "no_such_tool_123", None, False),
            ("timeout", "sleep 2", 1, False),
            ("truncated output", "python3 -c 'print(\"x\" * 40000); exit(1)'", None, False),
        ]
        print("scenario,baseline_calls,diagnostic_calls,baseline_tokens,diagnostic_tokens")
        client = McpClient(install / "bin/bashllm-mcp", repo)
        try:
            for name, command, timeout, deep in cases:
                options = ["--retry"]
                if timeout:
                    options += ["--timeout", str(timeout)]
                code, run = cli(executable, "run", "--agent", "--repo", str(repo),
                                "--cwd", str(repo), "--json", *options, "--", command)
                if code == 69:
                    raise RuntimeError("containment unavailable; benchmark cannot run")
                arguments = {"repo": str(repo), "command": command, "retry": True}
                if timeout:
                    arguments["timeout_seconds"] = timeout
                new_run = client.call("bashllm_run", arguments)
                legacy_tokens = tokens(legacy(run))
                diagnostic_tokens = mcp_tokens(new_run)
                baseline_calls = diagnostic_calls = 1
                if deep:
                    _, baseline_probe = cli(executable, "run", "--agent", "--repo", str(repo),
                                            "--cwd", str(repo), "--json", "--retry", "--",
                                            "python3 -c 'import sys; print(sys.executable); print(sys.version)'")
                    _, baseline_package = cli(executable, "run", "--agent", "--repo", str(repo),
                                              "--cwd", str(repo), "--json", "--retry", "--",
                                              "python3 -c 'import importlib.metadata as m; print(m.version(\"absent_demo_package\"))'")
                    diagnosis = client.call("bashllm_diagnose", {
                        "attempt_id": new_run["structuredContent"]["attempt_id"]})
                    legacy_tokens += tokens(legacy(baseline_probe)) + tokens(legacy(baseline_package))
                    diagnostic_tokens += mcp_tokens(diagnosis)
                    baseline_calls += 2
                    diagnostic_calls += 1
                print(f"{name},{baseline_calls},{diagnostic_calls},{legacy_tokens},{diagnostic_tokens}")
        finally:
            client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
