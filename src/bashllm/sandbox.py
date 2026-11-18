"""Fail-closed platform launchers for bounded Bash commands."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


class BackendUnavailable(Exception):
    """A command cannot be launched inside a verified containment backend."""


def agent_tool_grants(repo: Path) -> list[Path]:
    """Read tool grants from owner-controlled configuration outside the repository."""
    configuration = Path.home() / ".config" / "bashllm" / "tool-grants.json"
    if not configuration.exists():
        return []
    try:
        descriptor = os.open(configuration, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(descriptor)
            if metadata.st_uid != os.getuid() or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise BackendUnavailable("tool grants must be owned by the user and not writable by others")
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                descriptor = -1
                settings = json.load(stream)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not isinstance(settings, dict):
            raise ValueError("tool grants must map repositories to path lists")
        paths = settings.get(str(repo), [])
        if (not isinstance(paths, list) or
                not all(isinstance(path, str) and Path(path).is_absolute() for path in paths)):
            raise ValueError("repository grants must be a list of absolute paths")
        return [Path(path) for path in paths]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise BackendUnavailable(f"cannot read trusted tool grants: {error}") from error


def _minimal_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp/bashllm-home",
        "TMPDIR": "/tmp",
        "XDG_CACHE_HOME": "/tmp/bashllm-cache",
        "LC_ALL": "C",
    }


def _trusted_bubblewrap() -> Path:
    for candidate in (Path("/usr/bin/bwrap"), Path("/bin/bwrap")):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        metadata = resolved.stat()
        if metadata.st_uid != 0 or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise BackendUnavailable("Bubblewrap must be a root-owned, non-writable system binary")
        return resolved
    raise BackendUnavailable("Bubblewrap is not installed in a trusted system location")


def _runtime_mounts() -> list[str]:
    arguments: list[str] = []
    for name in ("/usr", "/bin", "/lib", "/lib64", "/sbin"):
        path = Path(name)
        if path.is_symlink():
            arguments.extend(("--symlink", os.readlink(path), name))
        elif path.is_dir():
            arguments.extend(("--ro-bind", name, name))
    for name in ("/etc/ld.so.cache", "/etc/ld.so.conf", "/etc/ld.so.conf.d", "/etc/nsswitch.conf", "/etc/passwd", "/etc/group"):
        if Path(name).exists():
            arguments.extend(("--ro-bind", name, name))
    return arguments


def _tool_mounts(paths: list[Path], repo: Path) -> tuple[list[str], list[str]]:
    arguments: list[str] = []
    path_entries: list[str] = []
    home = Path.home().resolve()
    for requested in paths:
        path = requested.expanduser().resolve(strict=True)
        if not path.is_file() and not path.is_dir():
            raise BackendUnavailable(f"tool path is neither a file nor a directory: {path}")
        if path == home or home.is_relative_to(path):
            raise BackendUnavailable("a tool path cannot grant the whole home directory")
        if path.is_relative_to(repo):
            continue
        arguments.extend(("--ro-bind", str(path), str(path)))
        path_entries.append(str(path if path.is_dir() else path.parent))
    return arguments, path_entries


def _linux_argv(repo: Path, cwd: Path, command: str, tool_paths: list[Path]) -> tuple[list[str], dict[str, str]]:
    bwrap = _trusted_bubblewrap()
    mounts, path_entries = _tool_mounts(tool_paths, repo)
    environment = _minimal_environment()
    environment["PATH"] = ":".join(path_entries + [environment["PATH"]])
    arguments = [
        str(bwrap), "--unshare-user", "--unshare-pid", "--unshare-net",
        "--unshare-ipc", "--unshare-uts", "--die-with-parent", "--new-session",
        "--clearenv", "--tmpfs", "/tmp", "--dir", "/tmp/bashllm-home",
        "--dir", "/tmp/bashllm-cache", "--proc", "/proc", "--dev", "/dev",
        *_runtime_mounts(), *mounts, "--bind", str(repo), str(repo),
    ]
    for key, value in environment.items():
        arguments.extend(("--setenv", key, value))
    arguments.extend(("--chdir", str(cwd), "/bin/bash", "-c", command))
    return arguments, environment


def launch_command(repo: Path, cwd: Path, command: str, tool_paths: list[Path]) -> tuple[list[str], dict[str, str]]:
    """Return a contained launcher, after verifying it can start on this host."""
    if sys.platform != "linux":
        if sys.platform == "darwin":
            raise BackendUnavailable("native macOS containment helper is not installed or verified")
        raise BackendUnavailable("contained execution is supported only on Linux and macOS")
    try:
        arguments, environment = _linux_argv(repo, cwd, command, tool_paths)
        probe = [*arguments[:-1], ":"]
        check = subprocess.run(probe, capture_output=True, text=True, timeout=5, env=environment)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise BackendUnavailable(f"Bubblewrap capability check failed: {error}") from error
    if check.returncode:
        reason = check.stderr.strip()[:300] or f"exit {check.returncode}"
        raise BackendUnavailable(f"Bubblewrap capability check failed: {reason}")
    return arguments, environment
