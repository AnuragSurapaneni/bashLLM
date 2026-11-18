"""Small, dependency-free MCP stdio facade for one configured repository.

The server exposes fixed bashllm operations, never a general process runner.
The host must require human approval for every bashllm_run tool call.
"""

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = "2025-11-25"
SERVER_VERSION = "0.1.0"
MAX_MESSAGE_BYTES = 1_000_000


def _string(description: str, max_length: int = 4096) -> dict[str, Any]:
    return {"type": "string", "description": description, "maxLength": max_length}


def _integer(description: str, minimum: int, maximum: int) -> dict[str, Any]:
    return {"type": "integer", "description": description, "minimum": minimum, "maximum": maximum}


def _tool(name: str, description: str, properties: dict[str, Any],
          required: list[str], *, read_only: bool = True) -> dict[str, Any]:
    return {
        "name": f"bashllm_{name}",
        "description": description,
        "inputSchema": {"type": "object", "properties": properties,
                        "required": required, "additionalProperties": False},
        "annotations": {"readOnlyHint": read_only, "destructiveHint": not read_only,
                        "openWorldHint": False},
    }


TOOLS = [
    _tool("find", "Find repository files by glob.",
          {"pattern": _string("File name or relative-path glob", 512),
           "max_results": _integer("Maximum files", 0, 200)}, ["pattern"]),
    _tool("search", "Search repository text for a literal string.",
          {"query": _string("Literal search text", 4096),
           "glob": _string("Optional file glob", 512),
           "max_results": _integer("Maximum matches", 0, 200),
           "max_bytes": _integer("Maximum returned match bytes", 0, 32768)}, ["query"]),
    _tool("read", "Read a bounded repository file; generated and external files are excluded.",
          {"path": _string("Path relative to the configured repository", 4096),
           "max_bytes": _integer("Maximum returned bytes", 0, 32768)}, ["path"]),
    _tool("inspect", "Build the static repository briefing and graph.", {}, [], read_only=False),
    _tool("context", "Read the freshness-checked repository briefing.",
          {"max_tokens": _integer("Approximate context token limit", 1, 4000)}, []),
    _tool("history", "List recent bashllm command attempts.",
          {"limit": _integer("Maximum entries", 0, 50)}, []),
    _tool("run", "Run one bounded Bash command in the configured repository. "
          "Requires human approval on every invocation in the MCP host.",
          {"repo": _string("Fixed repository path shown for human approval", 4096),
           "command": _string("Single Bash command string to execute", 4096),
           "cwd": _string("Working directory relative to the repository", 4096),
           "timeout_seconds": _integer("Execution timeout", 1, 60),
           "retry": {"type": "boolean", "description": "Explicitly repeat a prior exact command"}},
          ["repo", "command"], read_only=False),
]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOLS}
TOOL_BY_NAME["bashllm_run"]["_meta"] = {"anthropic/requiresUserInteraction": True}


class InvalidArguments(ValueError):
    pass


def _validate(tool: dict[str, Any], arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise InvalidArguments("arguments must be an object")
    schema = tool["inputSchema"]
    unknown = arguments.keys() - schema["properties"].keys()
    if unknown:
        raise InvalidArguments(f"unsupported argument: {sorted(unknown)[0]}")
    for name in schema["required"]:
        if name not in arguments:
            raise InvalidArguments(f"missing argument: {name}")
    for name, value in arguments.items():
        field = schema["properties"][name]
        expected = field["type"]
        if expected == "string":
            if not isinstance(value, str) or not value or "\0" in value or len(value) > field["maxLength"]:
                raise InvalidArguments(f"{name} must be a nonempty bounded string")
        elif expected == "integer":
            if type(value) is not int or not field["minimum"] <= value <= field["maximum"]:
                raise InvalidArguments(f"{name} is outside its permitted integer range")
        elif expected == "boolean" and type(value) is not bool:
            raise InvalidArguments(f"{name} must be a boolean")
    return arguments


def _command(name: str, args: dict[str, Any], repo: Path) -> list[str]:
    command = [sys.executable, "-m", "bashllm.cli", name, "--repo", str(repo), "--json"]
    if name == "find":
        command += ["--max-results", str(args.get("max_results", 200))]
        command += ["--", args["pattern"]]
    elif name == "search":
        command += [f"--glob={args.get('glob', '*')}", "--max-results",
                    str(args.get("max_results", 200)), "--max-bytes",
                    str(args.get("max_bytes", 32768))]
        command += ["--", args["query"]]
    elif name == "read":
        command += ["--max-bytes", str(args.get("max_bytes", 32768)), "--", args["path"]]
    elif name == "context":
        command += ["--max-tokens", str(args.get("max_tokens", 1500))]
    elif name == "history":
        command += ["--limit", str(args.get("limit", 10))]
    elif name == "run":
        cwd = Path(args.get("cwd", "."))
        if cwd.is_absolute() or ".." in cwd.parts or not (repo / cwd).resolve().is_relative_to(repo):
            raise InvalidArguments("cwd must stay inside the configured repository")
        command += [f"--cwd={cwd}", "--agent", "--timeout",
                    str(args.get("timeout_seconds", 60)), "--max-output", "32768"]
        if args.get("retry", False):
            command.append("--retry")
        command += ["--", args["command"]]
    return command


def _call(name: str, arguments: Any, repo: Path) -> dict[str, Any]:
    tool = TOOL_BY_NAME.get(name)
    if tool is None:
        raise InvalidArguments(f"unknown tool: {name}")
    args = _validate(tool, arguments)
    if name == "bashllm_run" and args["repo"] != str(repo):
        raise InvalidArguments("repo must match the configured repository")
    command = _command(name.removeprefix("bashllm_"), args, repo)
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=75,
                                 stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"content": [{"type": "text", "text": f"bashllm failed: {error}"}], "isError": True}
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        detail = process.stderr.strip() or process.stdout.strip() or "no output"
        return {"content": [{"type": "text", "text": detail[:4096]}], "isError": True}
    structured = payload if isinstance(payload, dict) else {"entries": payload}
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "structuredContent": structured,
            "isError": process.returncode != 0}


def _response(request_id: Any, *, result: Any = None,
              error: dict[str, Any] | None = None) -> dict[str, Any]:
    message = {"jsonrpc": "2.0", "id": request_id}
    message["error" if error is not None else "result"] = error if error is not None else result
    return message


def _dispatch(message: Any, repo: Path, initialized: bool) -> tuple[dict[str, Any] | None, bool]:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _response(None, error={"code": -32600, "message": "Invalid Request"}), initialized
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None, initialized
    if method == "notifications/cancelled":
        return None, initialized
    if "id" not in message:
        return None, initialized
    if method == "initialize":
        params = message.get("params")
        version = params.get("protocolVersion") if isinstance(params, dict) else None
        if not isinstance(version, str):
            return _response(request_id, error={"code": -32602, "message": "Missing protocolVersion"}), initialized
        return _response(request_id, result={"protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "bashllm", "version": SERVER_VERSION},
                    "instructions": "Approve every bashllm_run invocation in the host. "
                                    "The server confines runs but cannot enforce host approval."}), True
    if not initialized:
        return _response(request_id, error={"code": -32000, "message": "Initialize first"}), initialized
    if method == "ping":
        return _response(request_id, result={}), initialized
    if method == "tools/list":
        tools = copy.deepcopy(TOOLS)
        tools[-1]["inputSchema"]["properties"]["repo"]["const"] = str(repo)
        return _response(request_id, result={"tools": tools}), initialized
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _response(request_id, error={"code": -32602, "message": "Invalid tool call"}), initialized
        try:
            result = _call(params["name"], params.get("arguments", {}), repo)
        except InvalidArguments as error:
            result = {"content": [{"type": "text", "text": str(error)}], "isError": True}
        return _response(request_id, result=result), initialized
    return _response(request_id, error={"code": -32601, "message": "Method not found"}), initialized


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve bashllm tools over MCP stdio")
    parser.add_argument("--repo", required=True, type=Path,
                        help="Fixed repository available to this server")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error("repo must be an existing directory")
    initialized = False
    while True:
        line = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
        if not line:
            break
        if len(line) > MAX_MESSAGE_BYTES:
            while line and not line.endswith(b"\n"):
                line = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
            answer = _response(None, error={"code": -32700, "message": "Message too large"})
        else:
            try:
                message = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                answer = _response(None, error={"code": -32700, "message": "Parse error"})
            else:
                answer, initialized = _dispatch(message, repo, initialized)
        if answer is not None:
            sys.stdout.write(json.dumps(answer, separators=(",", ":"), ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
