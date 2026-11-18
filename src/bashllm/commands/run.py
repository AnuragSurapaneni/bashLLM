"""Bounded Bash execution."""

import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

from bashllm import history
from bashllm.sandbox import BackendUnavailable, agent_tool_grants, launch_command


def _run_bounded(argv: list[str], cwd: Path, timeout: float, max_output: int,
                 environment: dict[str, str]) -> dict:
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    timed_out = False
    deadline = started + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    try:
        while selector.get_map():
            now = time.monotonic()
            if now >= deadline:
                if not timed_out:
                    timed_out = True
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    deadline = now + 1.0
                else:
                    break
            for key, _ in selector.select(max(0.0, deadline - time.monotonic())):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                stream = key.data
                available = max_output - len(buffers[stream])
                buffers[stream].extend(chunk[:available])
                if len(chunk) > available:
                    truncated[stream] = True
    finally:
        selector.close()
        for pipe in (process.stdout, process.stderr):
            if not pipe.closed:
                pipe.close()
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()

    return {
        "exit_code": 124 if timed_out else process.returncode,
        "stdout": buffers["stdout"].decode("utf-8", errors="replace"),
        "stderr": buffers["stderr"].decode("utf-8", errors="replace"),
        "stdout_truncated": truncated["stdout"],
        "stderr_truncated": truncated["stderr"],
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def _refuse(args: argparse.Namespace, connection, repo: Path, cwd: Path,
            command: str, error: str) -> int:
    payload = {
        "repo": str(repo), "cwd": str(cwd), "command": command,
        "status": "backend_unavailable", "error": error, "exit_code": 69,
    }
    if args.agent and connection:
        history.record(connection, str(cwd), command, {
            "status": payload["status"], "error": error, "exit_code": 69,
        })
    if connection:
        connection.close()
    if args.json:
        print(json.dumps(payload))
    else:
        print(f"run refused: {error}", file=sys.stderr)
    return 69


def register(commands: argparse._SubParsersAction) -> None:
    run = commands.add_parser("run", help="Run a Bash command in a repository")
    run.add_argument("--repo", required=True, type=Path)
    run.add_argument("--cwd", required=True, type=Path)
    run.add_argument("--json", action="store_true")
    run.add_argument("--retry", action="store_true", help="Execute even when this command was attempted before")
    run.add_argument("--no-history", action="store_true", help="Do not consult or record history")
    run.add_argument("--agent", action="store_true", help="Require an audit record for every run request")
    run.add_argument("--tool-path", action="append", type=Path, default=[],
                     help="Grant read-only access to a tool file or directory outside the repository")
    run.add_argument("--timeout", type=float, default=60.0, help="Timeout in seconds (default: 60)")
    run.add_argument("--max-output", type=int, default=32768, help="Bytes retained per output stream (default: 32768)")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(execute=execute)


def execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.timeout <= 0:
        parser.error("timeout must be greater than zero")
    if args.max_output < 0:
        parser.error("max-output must be zero or greater")
    if args.agent and args.no_history:
        parser.error("agent runs cannot disable history")
    if args.agent and args.tool_path:
        parser.error("agent tool paths must be configured outside the repository")

    command_parts = args.command[1:] if args.command[:1] == ["--"] else args.command
    if len(command_parts) != 1:
        parser.error("run requires one Bash command string after --")
    repo = args.repo.resolve()
    cwd = (repo / args.cwd).resolve() if not args.cwd.is_absolute() else args.cwd.resolve()
    if not repo.is_dir() or not cwd.is_dir() or not cwd.is_relative_to(repo):
        parser.error("repo and cwd must be directories, with cwd inside repo")

    try:
        connection = None if args.no_history else history.connect(repo)
    except ValueError as error:
        parser.error(str(error))
    command = command_parts[0]
    prior = history.previous(connection, str(cwd), command) if connection else None
    if prior is not None and not args.retry:
        payload = {
            "repo": str(repo),
            "cwd": str(cwd),
            "command": command,
            "status": "not_executed",
            "previous_exit_code": prior["exit_code"],
            "previous_stdout": prior["stdout"],
            "previous_stderr": prior["stderr"],
            "previous_stdout_truncated": prior["stdout_truncated"],
            "previous_stderr_truncated": prior["stderr_truncated"],
            "previous_timed_out": prior["timed_out"],
        }
        if args.json:
            print(json.dumps(payload))
        else:
            print(
                f"not executed: exact repeat of {command!r} in {cwd}; "
                f"previous_exit_code={prior['exit_code']}\n"
                f"previous_stdout={prior['stdout']!r}\nprevious_stderr={prior['stderr']!r}",
                file=sys.stderr,
            )
        if args.agent:
            history.record(connection, str(cwd), command, {"status": "not_executed", "exit_code": 3})
        connection.close()
        return 3

    try:
        tool_paths = agent_tool_grants(repo) if args.agent else args.tool_path
        argv, environment, cleanup = launch_command(repo, cwd, command, tool_paths)
    except BackendUnavailable as error:
        return _refuse(args, connection, repo, cwd, command, str(error))

    try:
        result = _run_bounded(argv, cwd, args.timeout, args.max_output, environment)
    except OSError as error:
        return _refuse(args, connection, repo, cwd, command,
                       f"containment launcher failed to start: {error}")
    finally:
        cleanup()

    payload = {
        "repo": str(repo),
        "cwd": str(cwd),
        "command": command,
        "status": "executed",
        **result,
    }
    if connection:
        history.record(connection, str(cwd), command, {
            key: payload[key] for key in (
                "exit_code", "stdout", "stderr", "stdout_truncated", "stderr_truncated",
                "timed_out", "duration_seconds",
            )
        } | {"status": "executed"})
        connection.close()
    if args.json:
        print(json.dumps(payload))
    else:
        sys.stdout.write(payload["stdout"])
        sys.stderr.write(payload["stderr"])
        print(
            f"exit_code={payload['exit_code']} timed_out={str(payload['timed_out']).lower()} "
            f"stdout_truncated={str(payload['stdout_truncated']).lower()} "
            f"stderr_truncated={str(payload['stderr_truncated']).lower()}",
            file=sys.stderr,
        )
    return payload["exit_code"]
