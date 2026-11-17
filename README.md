# bashllm

`bashllm` is a Python CLI for bounded Bash operations in a repository. This first ticket provides the `run` command. Command history, code exploration, and preflight briefings are planned in later tickets.

## Install

Requires Python 3.11 or later and Bash on macOS or Linux. The package has no runtime dependencies.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

## Run a command

```bash
.venv/bin/bashllm run --repo . --cwd . -- 'pwd'
.venv/bin/bashllm run --repo . --cwd . --json -- 'printf "hello\\n"'
```

Pass one Bash command string after `--`. `--repo` names the repository root, and `--cwd` names a directory inside it; a relative `--cwd` is resolved from the repository root. Each call starts a fresh Bash process with the caller's permissions. This command is not a sandbox.

The default timeout is 60 seconds and each output stream retains at most 32 KiB. Use `--timeout SECONDS` and `--max-output BYTES` to adjust them. The CLI returns the command's exit code, or 124 on timeout. JSON output includes the exit code, duration, timeout status, and per-stream truncation flags.

## Test

```bash
python3 -m unittest discover -s tests -v
```

The tests install the package in a temporary virtual environment and invoke the installed CLI.
