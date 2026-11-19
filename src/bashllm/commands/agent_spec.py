"""Portable command contract for coding-agent harnesses."""

import argparse
import json


COMMANDS = [
    {
        "name": "inspect", "when": "Start work in an unfamiliar repository or refresh stale context.",
        "arguments": {"required": ["--repo"], "optional": ["--max-files", "--max-directories", "--max-depth", "--max-file-bytes"]},
        "result": ["repo", "briefing", "graph", "files_scanned", "omission_counts"],
    },
    {
        "name": "context", "when": "Get a compact briefing and recent attempts after inspect; rerun inspect if stale.",
        "arguments": {"required": ["--repo"], "optional": ["--max-tokens"]},
        "result": ["repo", "briefing", "recent_commands", "stale", "stale_reasons", "warning", "truncated"],
    },
    {
        "name": "find", "when": "Locate repository files by glob.",
        "arguments": {"required": ["--repo", "pattern"], "optional": ["--max-results"]},
        "result": ["files", "truncated"],
    },
    {
        "name": "search", "when": "Find literal text in repository files.",
        "arguments": {"required": ["--repo", "query"], "optional": ["--glob", "--max-results", "--max-bytes"]},
        "result": ["matches", "truncated"],
    },
    {
        "name": "read", "when": "Read a bounded repository file after locating it.",
        "arguments": {"required": ["--repo", "path"], "optional": ["--max-bytes"]},
        "result": ["path", "content", "truncated"],
    },
    {
        "name": "history", "when": "Check previous command attempts before suggesting another run.",
        "arguments": {"required": ["--repo"], "optional": ["--limit"]},
        "result_container": "array",
        "result": ["id", "cwd", "command", "created_at", "status", "exit_code"],
    },
    {
        "name": "result", "when": "Retrieve bounded raw output for a recorded attempt without rerunning it.",
        "arguments": {"required": ["--repo", "--attempt-id"], "optional": ["--max-bytes"]},
        "result": ["attempt_id", "status", "created_at", "exit_code", "stdout", "stderr",
                   "stdout_truncated", "stderr_truncated"],
    },
    {
        "name": "diagnose", "when": "After separate human approval, check a recorded failure in containment.",
        "arguments": {"required": ["--repo", "--attempt-id"],
                      "optional": ["--group", "--max-detail"]},
        "result": ["recorded_attempt", "checked_at", "status", "environment", "python",
                   "dependencies", "optional_groups"],
        "approval": "The harness must obtain human confirmation before every diagnostic check. bashllm does not verify approval.",
    },
    {
        "name": "run", "when": "Execute one finite Bash command only after human approval of its exact text, repository, and working directory; approve each retry again.",
        "arguments": {"required": ["--agent", "--repo", "--cwd", "--", "command"],
                      "optional": ["--retry", "--timeout", "--max-output"],
                      "forbidden": ["--no-history", "--tool-path"]},
        "result": ["repo", "cwd", "command", "status", "attempt_id", "exit_code", "stdout", "stderr", "timed_out", "duration_seconds", "diagnostic"],
        "result_by_status": {
            "executed": ["repo", "cwd", "command", "status", "attempt_id", "exit_code", "stdout", "stderr", "timed_out", "duration_seconds", "stdout_truncated", "stderr_truncated", "diagnostic"],
            "not_executed": ["repo", "cwd", "command", "status", "attempt_id", "previous_attempt_id", "previous_exit_code", "previous_stdout", "previous_stderr", "previous_timed_out", "previous_diagnostic"],
            "backend_unavailable": ["repo", "cwd", "command", "status", "attempt_id", "error", "exit_code"],
        },
        "statuses": ["executed", "not_executed", "backend_unavailable"],
        "approval": "The harness must obtain human confirmation before every execution, including retries. bashllm does not verify approval.",
    },
]


def register(commands: argparse._SubParsersAction) -> None:
    agent_spec = commands.add_parser("agent-spec", help="Describe the CLI to agent harnesses")
    agent_spec.add_argument("--json", action="store_true")
    agent_spec.set_defaults(execute=execute)


def execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    payload = {
        "schema_version": 2,
        "interface": "bashllm CLI",
        "invocation": "bashllm COMMAND --json ...",
        "policy": [
            "Choose commands only when they help the current task.",
            "Read and inspection commands do not require execution approval; diagnose does.",
            "Generic shell tools remain the harness's responsibility; disable them when claiming agent command containment.",
            "A contained command can read every file in its repository, including ignored files.",
            "If run reports backend_unavailable, do not execute the command through an uncontained fallback.",
        ],
        "commands": COMMANDS,
    }
    if args.json:
        print(json.dumps(payload))
    else:
        print("bashllm agent contract v2\n")
        for command in COMMANDS:
            print(f"{command['name']}: {command['when']}")
        print("\nRequest approval for every run and diagnose call.")
    return 0
