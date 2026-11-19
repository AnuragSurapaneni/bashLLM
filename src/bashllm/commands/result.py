"""Retrieve bounded raw output for one recorded attempt."""

import argparse
import json
from pathlib import Path

from bashllm import history


def register(commands: argparse._SubParsersAction) -> None:
    result = commands.add_parser("result", help="Read a recorded command result")
    result.add_argument("--repo", required=True, type=Path)
    result.add_argument("--attempt-id", required=True, type=int)
    result.add_argument("--max-bytes", type=int, default=4096)
    result.add_argument("--json", action="store_true")
    result.set_defaults(execute=execute)


def execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.attempt_id <= 0 or not 0 <= args.max_bytes <= 32768:
        parser.error("attempt-id must be positive and max-bytes must be 0 through 32768")
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error("repo must be a directory")
    try:
        attempt = history.load_attempt(repo, args.attempt_id)
    except ValueError as error:
        print(json.dumps({"error": str(error)[:300], "attempt_id": args.attempt_id}))
        return 2
    if attempt is None:
        print(json.dumps({"error": "attempt not found", "attempt_id": args.attempt_id}))
        return 2
    payload = {"attempt_id": attempt["id"], "status": attempt.get("status", "executed"),
               "created_at": attempt["created_at"], "exit_code": attempt.get("exit_code")}
    for stream in ("stdout", "stderr"):
        raw = attempt.get(stream, "")
        encoded = raw.encode("utf-8")
        payload[stream] = encoded[:args.max_bytes].decode("utf-8", errors="replace")
        payload[f"{stream}_truncated"] = (len(encoded) > args.max_bytes or
                                          bool(attempt.get(f"{stream}_truncated")))
    if args.json:
        print(json.dumps(payload))
    else:
        print(json.dumps(payload, indent=2))
    return 0
