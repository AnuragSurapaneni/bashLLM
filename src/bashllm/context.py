"""Freshness snapshot for a static repository briefing."""

import json
import os
from pathlib import Path

from bashllm.inspection import _scan


SNAPSHOT_NAME = "inspection.json"
SNAPSHOT_FILE_LIMIT = 100000
SNAPSHOT_DIRECTORY_LIMIT = 10000


def snapshot(repo: Path, max_depth: int) -> dict:
    """Record eligible paths without reading or running repository code."""
    _, files, _, omissions = _scan(
        repo, SNAPSHOT_FILE_LIMIT, SNAPSHOT_DIRECTORY_LIMIT, max_depth,
    )
    signatures = {}
    for relative in files:
        path = repo / relative
        if path.is_symlink():
            continue
        try:
            stat = path.stat(follow_symlinks=False)
        except OSError:
            continue
        signatures[relative.as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return {
        "files": signatures,
        "max_depth": max_depth,
        "scope_limited": any(omissions.get(reason, 0) for reason in
                             ("file limit", "directory limit", "depth limit")),
    }


def read_state_file(state: Path, name: str) -> str:
    if state.is_symlink() or (state / name).is_symlink():
        raise ValueError("generated state path must not be a symlink")
    directory_fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        with os.fdopen(file_fd, "r", encoding="utf-8") as stream:
            return stream.read()
    finally:
        os.close(directory_fd)


def load_snapshot(state: Path) -> dict:
    return json.loads(read_state_file(state, SNAPSHOT_NAME))
