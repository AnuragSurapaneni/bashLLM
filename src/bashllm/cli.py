"""Command-line interface for bashllm."""

import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path


def _run_bounded(command: str, cwd: Path, timeout: float, max_output: int) -> dict:
    started = time.monotonic()
    process = subprocess.Popen(
        ["bash", "-c", command],
        cwd=cwd,
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
                    deadline = now + 1.0  # Drain output from the killed process.
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="bashllm")
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("run", help="Run a Bash command in a repository")
    run.add_argument("--repo", required=True, type=Path)
    run.add_argument("--cwd", required=True, type=Path)
    run.add_argument("--json", action="store_true")
    run.add_argument("--timeout", type=float, default=60.0, help="Timeout in seconds (default: 60)")
    run.add_argument("--max-output", type=int, default=32768, help="Bytes retained per output stream (default: 32768)")
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("timeout must be greater than zero")
    if args.max_output < 0:
        parser.error("max-output must be zero or greater")

    command_parts = args.command[1:] if args.command[:1] == ["--"] else args.command
    if len(command_parts) != 1:
        parser.error("run requires one Bash command string after --")
    repo = args.repo.resolve()
    cwd = (repo / args.cwd).resolve() if not args.cwd.is_absolute() else args.cwd.resolve()
    if not repo.is_dir() or not cwd.is_dir() or not cwd.is_relative_to(repo):
        parser.error("repo and cwd must be directories, with cwd inside repo")

    payload = {
        "repo": str(repo),
        "cwd": str(cwd),
        "command": command_parts[0],
        **_run_bounded(command_parts[0], cwd, args.timeout, args.max_output),
    }
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


if __name__ == "__main__":
    raise SystemExit(main())
