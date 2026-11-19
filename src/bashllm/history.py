"""Private, repository-local command attempt history."""

import json
import os
import sqlite3
from pathlib import Path


def connect(repo: Path) -> sqlite3.Connection:
    state = repo / ".bashllm"
    if state.is_symlink():
        raise ValueError("history state directory must not be a symlink")
    state.mkdir(mode=0o700, exist_ok=True)
    database = state / "history.sqlite3"
    directory_fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchmod(directory_fd, 0o700)
        if database.is_symlink():
            raise ValueError("history database must not be a symlink")
        descriptor = os.open(
            database.name,
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        try:
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
    finally:
        os.close(directory_fd)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE IF NOT EXISTS attempts ("
        "id INTEGER PRIMARY KEY, cwd TEXT NOT NULL, command TEXT NOT NULL, "
        "result TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS attempts_match ON attempts (cwd, command, id)"
    )
    return connection


def previous(connection: sqlite3.Connection, cwd: str, command: str) -> dict | None:
    rows = connection.execute(
        "SELECT id, result FROM attempts WHERE cwd = ? AND command = ? ORDER BY id DESC",
        (cwd, command),
    )
    for row in rows:
        result = json.loads(row["result"])
        if result.get("status", "executed") == "executed":
            return {"id": row["id"], **result}
    return None


def record(connection: sqlite3.Connection, cwd: str, command: str, result: dict) -> int:
    with connection:
        cursor = connection.execute(
            "INSERT INTO attempts (cwd, command, result) VALUES (?, ?, ?)",
            (cwd, command, json.dumps(result)),
        )
    return cursor.lastrowid


def attempt(connection: sqlite3.Connection, attempt_id: int) -> dict | None:
    row = connection.execute(
        "SELECT id, cwd, command, result, created_at FROM attempts WHERE id = ?",
        (attempt_id,),
    ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "cwd": row["cwd"], "command": row["command"],
            "created_at": row["created_at"], **json.loads(row["result"])}


def load_attempt(repo: Path, attempt_id: int) -> dict | None:
    """Load an existing attempt without creating history for a missing store."""
    if not (repo / ".bashllm/history.sqlite3").is_file():
        return None
    connection = connect(repo)
    try:
        return attempt(connection, attempt_id)
    finally:
        connection.close()


def recent(connection: sqlite3.Connection, limit: int) -> list[dict]:
    rows = connection.execute(
        "SELECT id, cwd, command, result, created_at FROM attempts ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "cwd": row["cwd"],
            "command": row["command"],
            "created_at": row["created_at"],
            **json.loads(row["result"]),
        }
        for row in rows
    ]
