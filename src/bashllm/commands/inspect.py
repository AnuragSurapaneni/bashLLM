"""Static repository inspection command."""

import argparse
import json
import os
from pathlib import Path

from bashllm.context import SNAPSHOT_NAME, snapshot
from bashllm.inspection import build_briefing


def register(commands: argparse._SubParsersAction) -> None:
    inspect = commands.add_parser("inspect", help="Generate a static repository briefing")
    inspect.add_argument("--repo", required=True, type=Path)
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--max-files", type=int, default=2000)
    inspect.add_argument("--max-directories", type=int, default=1000)
    inspect.add_argument("--max-depth", type=int, default=8)
    inspect.add_argument("--max-file-bytes", type=int, default=65536)
    inspect.set_defaults(execute=execute)


def execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error("repo must be an existing directory")
    if args.max_files <= 0 or args.max_directories < 0 or args.max_depth < 0 or args.max_file_bytes <= 0:
        parser.error("max-files and max-file-bytes must be positive; max-directories and max-depth must be nonnegative")
    briefing, summary, graph_dot = build_briefing(repo, args.max_files, args.max_directories,
                                                  args.max_depth, args.max_file_bytes)
    output = repo / ".bashllm" / "BRIEFING.md"
    graph_output = output.parent / "GRAPH.dot"
    snapshot_output = output.parent / SNAPSHOT_NAME
    if (output.parent.is_symlink() or output.is_symlink() or graph_output.is_symlink()
            or snapshot_output.is_symlink()):
        parser.error("generated state path must not be a symlink")
    inspection_snapshot = snapshot(repo, args.max_depth)
    try:
        output.parent.mkdir(mode=0o700, exist_ok=True)
        directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            file_fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                              0o600, dir_fd=directory_fd)
            with os.fdopen(file_fd, "w", encoding="utf-8") as stream:
                stream.write(briefing)
            graph_fd = os.open(graph_output.name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                               0o600, dir_fd=directory_fd)
            with os.fdopen(graph_fd, "w", encoding="utf-8") as stream:
                stream.write(graph_dot)
            snapshot_fd = os.open(snapshot_output.name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                                  0o600, dir_fd=directory_fd)
            with os.fdopen(snapshot_fd, "w", encoding="utf-8") as stream:
                json.dump(inspection_snapshot, stream, sort_keys=True)
        finally:
            os.close(directory_fd)
    except OSError as error:
        parser.error(f"cannot write briefing: {error}")
    payload = {"repo": str(repo), "briefing": str(output), "graph": str(graph_output), **summary}
    if args.json:
        print(json.dumps(payload))
    else:
        print(f"Wrote {output} ({summary['files_scanned']} files scanned; "
              f"{sum(summary['omission_counts'].values())} omissions)")
    return 0
