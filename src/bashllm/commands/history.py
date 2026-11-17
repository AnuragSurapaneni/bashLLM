"""List recent command attempts."""

import argparse
import json
from pathlib import Path

from bashllm import history as storage


def register(commands: argparse._SubParsersAction) -> None:
    history = commands.add_parser("history", help="List recent command attempts")
    history.add_argument("--repo", required=True, type=Path)
    history.add_argument("--limit", type=int, default=10)
    history.add_argument("--json", action="store_true")
    history.set_defaults(execute=execute)


def execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.limit < 0:
        parser.error("limit must be zero or greater")
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error("repo must be a directory")
    try:
        connection = storage.connect(repo)
    except ValueError as error:
        parser.error(str(error))
    entries = storage.recent(connection, args.limit)
    connection.close()
    if args.json:
        print(json.dumps(entries))
    else:
        for entry in entries:
            print(
                f"{entry['created_at']} cwd={entry['cwd']} exit_code={entry['exit_code']} "
                f"command={entry['command']!r}"
            )
    return 0
