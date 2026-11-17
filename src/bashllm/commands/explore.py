"""Bounded discovery, text search, and reading inside a repository."""

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path


EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".bashllm", ".venv", "venv",
    "__pycache__", "node_modules", "build", "dist", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "target", "coverage", ".coverage",
}
EXCLUDED_FILES = {".DS_Store"}


def register(commands: argparse._SubParsersAction) -> None:
    find = commands.add_parser("find", help="Find repository files by glob")
    _common_options(find)
    find.add_argument("pattern", help="Glob matched against file names and relative paths")
    find.add_argument("--max-results", type=int, default=200)
    find.set_defaults(execute=_execute_find)

    search = commands.add_parser("search", help="Search repository text")
    _common_options(search)
    search.add_argument("query", help="Literal text to search for")
    search.add_argument("--glob", default="*", help="Limit files by glob")
    search.add_argument("--max-results", type=int, default=200)
    search.add_argument("--max-bytes", type=int, default=32768,
                        help="Maximum bytes of returned match text")
    search.set_defaults(execute=_execute_search)

    read = commands.add_parser("read", help="Read a repository file")
    _common_options(read)
    read.add_argument("path", type=Path)
    read.add_argument("--max-bytes", type=int, default=32768)
    read.set_defaults(execute=_execute_read)


def _common_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--repo", required=True, type=Path)
    command.add_argument("--json", action="store_true")


def _repo(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Path:
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error("repo must be a directory")
    return repo


def _nonnegative(value: int, name: str, parser: argparse.ArgumentParser) -> None:
    if value < 0:
        parser.error(f"{name} must be zero or greater")


def _eligible_files(repo: Path):
    for directory, dirnames, filenames in os.walk(repo, followlinks=False):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in EXCLUDED_DIRS and not (Path(directory) / name).is_symlink()
        )
        for name in sorted(filenames):
            path = Path(directory) / name
            if name in EXCLUDED_FILES or path.is_symlink() or not path.is_file():
                continue
            yield path, path.relative_to(repo).as_posix()


def _matches(relative: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(
        relative.rsplit("/", 1)[-1], pattern
    )


def _emit(args: argparse.Namespace, payload: dict, lines: list[str]) -> int:
    if args.json:
        print(json.dumps(payload))
    else:
        for line in lines:
            print(line)
        if payload["truncated"]:
            print("results truncated", file=sys.stderr)
    return 0


def _execute_find(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    repo = _repo(args, parser)
    _nonnegative(args.max_results, "max-results", parser)
    files = []
    truncated = False
    for _, relative in _eligible_files(repo):
        if _matches(relative, args.pattern):
            if len(files) >= args.max_results:
                truncated = True
                break
            files.append(relative)
    return _emit(args, {"files": files, "truncated": truncated}, files)


def _matching_lines(stream, needle: bytes, capture_limit: int):
    """Scan bounded chunks, retaining only the start of each matching line."""
    number = 1
    prefix = bytearray()
    tail = b""
    found = False
    overflow = False
    line_started = False
    while chunk := stream.readline(8192):
        ends_line = chunk.endswith(b"\n")
        content = chunk[:-1] if ends_line else chunk
        line_started = True
        window = tail + content
        found = found or needle in window
        tail = window[-(len(needle) - 1):] if len(needle) > 1 else b""
        remaining = capture_limit - len(prefix)
        prefix.extend(content[:remaining])
        overflow = overflow or len(content) > remaining
        if ends_line:
            if found:
                yield number, bytes(prefix).rstrip(b"\r"), overflow
            number += 1
            prefix.clear()
            tail = b""
            found = False
            overflow = False
            line_started = False
    if line_started and found:
        yield number, bytes(prefix).rstrip(b"\r"), overflow


def _execute_search(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    repo = _repo(args, parser)
    _nonnegative(args.max_results, "max-results", parser)
    _nonnegative(args.max_bytes, "max-bytes", parser)
    if not args.query:
        parser.error("query must not be empty")
    needle = args.query.encode("utf-8")
    matches = []
    used_bytes = 0
    truncated = False
    for path, relative in _eligible_files(repo):
        if not _matches(relative, args.glob):
            continue
        try:
            with path.open("rb") as stream:
                if b"\0" in stream.read(4096):
                    continue
                stream.seek(0)
                for number, prefix, overflow in _matching_lines(
                    stream, needle, args.max_bytes + 1
                ):
                    if len(matches) >= args.max_results:
                        truncated = True
                        break
                    available = args.max_bytes - used_bytes
                    encoded = prefix.decode("utf-8", errors="replace").encode("utf-8")
                    shown = encoded[:available].decode("utf-8", errors="ignore")
                    matches.append({"path": relative, "line": number, "text": shown})
                    used_bytes += len(shown.encode("utf-8"))
                    if overflow or len(encoded) > available:
                        truncated = True
                        break
        except (OSError, UnicodeError):
            continue
        if truncated:
            break
    lines = [f"{item['path']}:{item['line']}:{item['text']}" for item in matches]
    return _emit(args, {"matches": matches, "truncated": truncated}, lines)


def _execute_read(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    repo = _repo(args, parser)
    _nonnegative(args.max_bytes, "max-bytes", parser)
    path = (repo / args.path).resolve()
    if not path.is_relative_to(repo) or not path.is_file():
        parser.error("path must be a file inside repo")
    relative = path.relative_to(repo)
    if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):
        parser.error("path is excluded generated content")
    try:
        with path.open("rb") as stream:
            data = stream.read(args.max_bytes + 1)
    except OSError as error:
        parser.error(str(error))
    truncated = len(data) > args.max_bytes
    content = data[:args.max_bytes].decode("utf-8", errors="replace")
    if args.json:
        return _emit(args, {"path": relative.as_posix(), "content": content,
                            "truncated": truncated}, [])
    sys.stdout.write(content)
    if truncated:
        print("content truncated", file=sys.stderr)
    return 0
