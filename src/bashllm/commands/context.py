"""Print a compact, freshness-checked handoff for a new agent."""

import argparse
import json
from pathlib import Path

from bashllm import history as storage
from bashllm.context import SNAPSHOT_NAME, load_snapshot, read_state_file, snapshot


def register(commands: argparse._SubParsersAction) -> None:
    context = commands.add_parser("context", help="Print a compact repository handoff")
    context.add_argument("--repo", required=True, type=Path)
    context.add_argument("--max-tokens", type=int, default=1500)
    context.add_argument("--json", action="store_true")
    context.set_defaults(execute=execute)


def _recent_commands(repo: Path) -> str:
    database = repo / ".bashllm" / "history.sqlite3"
    if database.is_symlink():
        raise ValueError("history database must not be a symlink")
    if not database.exists():
        return "None recorded."
    connection = storage.connect(repo)
    try:
        entries = storage.recent(connection, 5)
    finally:
        connection.close()
    if not entries:
        return "None recorded."
    return "\n".join(
        f"- {entry['command'][:160]} ({entry.get('status', 'executed')}, exit {entry.get('exit_code', '?')})"
        for entry in entries
    )


def _fit(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    if limit <= 0:
        return "", True
    return text[:limit].rstrip() + "…", True


def execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.max_tokens <= 0:
        parser.error("max-tokens must be positive")
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error("repo must be an existing directory")
    state = repo / ".bashllm"
    if state.is_symlink():
        parser.error("generated state path must not be a symlink")
    if not (state / "BRIEFING.md").exists() or not (state / SNAPSHOT_NAME).exists():
        parser.error("no current briefing snapshot; run bashllm inspect --repo REPO")
    try:
        briefing = read_state_file(state, "BRIEFING.md")
        saved = load_snapshot(state)
        recent = _recent_commands(repo)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(f"cannot read briefing state: {error}")
    current = snapshot(repo, saved["max_depth"])
    before = saved["files"]
    after = current["files"]
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    edited = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
    stale = bool(added or removed or edited)
    warning = "Repository changed since inspection; run bashllm inspect --repo REPO again." if stale else ""
    scope_limited = bool(saved["scope_limited"] or current["scope_limited"])
    if scope_limited:
        warning += (" " if warning else "") + "Freshness check is limited by inspection depth or snapshot file/directory limits."

    # Approximate tokens as four characters, reserving room for recent attempts and status.
    character_budget = args.max_tokens * 4
    recent, recent_cut = _fit(recent, min(len(recent), max(40, character_budget // 4)))
    briefing, briefing_cut = _fit(briefing, max(0, character_budget - len(recent) - len(warning) - 100))
    truncated = recent_cut or briefing_cut
    payload = {
        "repo": str(repo), "briefing": briefing, "recent_commands": recent,
        "stale": stale, "stale_reasons": {
            "added": added[:20], "removed": removed[:20], "edited": edited[:20],
        }, "warning": warning, "scope_limited": scope_limited,
        "truncated": truncated,
    }
    if args.json:
        print(json.dumps(payload))
    else:
        print(briefing)
        print("\nRecent commands:\n" + recent)
        if warning:
            print("\nWarning: " + warning)
        print("\nTruncated: " + ("yes" if truncated else "no"))
    return 0
