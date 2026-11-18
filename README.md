# bashllm

`bashllm` is a Python CLI for bounded Bash operations and static repository exploration. It records command attempts, helps agents avoid exact repeats, and generates a Markdown briefing before an LLM starts work.

## Install

Requires Python 3.11 or later and Bash on macOS or Linux. Repository reading and inspection have no runtime dependencies. Contained execution currently requires a trusted system installation of Bubblewrap and usable user namespaces on Linux. Native macOS execution remains unavailable until a signed containment helper is verified.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

## Run a command

```bash
.venv/bin/bashllm run --repo . --cwd . -- 'pwd'
.venv/bin/bashllm run --repo . --cwd . --json -- 'printf "hello\\n"'
```

Pass one Bash command string after `--`. `--repo` names the repository root, and `--cwd` names a directory inside it; a relative `--cwd` is resolved from the repository root. Each call starts a fresh Bash process only after the platform containment backend passes a capability check. If the backend is missing or fails to start, `run` refuses the command with exit code 69 and a `backend_unavailable` JSON status. It never falls back to unrestricted execution. The other commands continue to work.

On Linux, the backend exposes the repository for persistent reads and writes, a disposable private temporary directory, and the system runtime needed to launch Bash. It starts with a minimal environment and no network namespace. The entire repository is visible to the command, including ignored files. External tools installed under your home directory require an explicit read-only path grant. Human CLI users can pass `--tool-path PATH` on a run. An agent's grants must be configured in an owner-controlled `~/.config/bashllm/tool-grants.json` file as a JSON object mapping an absolute repository path to a list of absolute tool file or directory paths. Agent calls cannot pass `--tool-path` directly. Native Linux adversarial tests are included in the suite and must pass on a Linux host before this backend is treated as verified.

The default timeout is 60 seconds and each output stream retains at most 32 KiB. Use `--timeout SECONDS` and `--max-output BYTES` to adjust them. The CLI returns the command's exit code, or 124 on timeout. JSON output includes the exit code, duration, timeout status, and per-stream truncation flags.

Command attempts are saved privately under the repository's ignored `.bashllm/` directory. An exact repeat of the same executed command and working directory is blocked with the earlier result and a `not_executed` status. Use `--retry` to execute it again or `--no-history` to skip history lookup and storage for a human-invoked run. Agent runs use `--agent`, which records executions and refusals and rejects `--no-history`. The calling agent must request human approval for the exact command, repository, and working directory before each execution, including retries. Inspect recent attempts with:

```bash
.venv/bin/bashllm history --repo . --limit 10 --json
```

## Agent integration

The versioned, harness-neutral command description is available from:

```bash
.venv/bin/bashllm agent-spec --json
```

Give this description to an agent harness as its tool contract. It explains when to use the read commands and `run`, how to parse JSON, and when to leave `bashllm` unused. An agent must call `run` with `--agent`; a harness claiming command containment must not expose an unrestricted shell tool alongside it. `bashllm` enforces its own execution boundary but cannot verify that a harness obtained human approval.

## Explore files

```bash
.venv/bin/bashllm find '*.py' --repo .
.venv/bin/bashllm search 'TODO' --repo . --glob '*.py'
.venv/bin/bashllm read src/bashllm/cli.py --repo . --max-bytes 4096
```

These commands skip generated directories and support `--json`. `find` and `search` accept `--max-results`; `search` and `read` accept `--max-bytes`. Truncation is reported in both output formats.

## Generate a preflight briefing

```bash
.venv/bin/bashllm inspect --repo .
```

The static scan writes `.bashllm/BRIEFING.md` and `.bashllm/GRAPH.dot`. The briefing maps files, likely entry points, tests, build commands, and evidence paths; it embeds a compact Mermaid dependency graph. The DOT artifact holds the full graph within scan limits. Analysis recognizes Python, JavaScript/TypeScript, Rust, Go, and Fortran projects and produces a basic file map for other languages. It does not run project code. Use `--max-files`, `--max-directories`, `--max-depth`, and `--max-file-bytes` to adjust scan limits; the briefing reports omissions.

## Hand context to an agent

```bash
.venv/bin/bashllm context --repo .
.venv/bin/bashllm context --repo . --max-tokens 3000 --json
```

`context` prints a compact briefing plus recent command attempts. It warns when file paths, sizes, or modification times have changed since `inspect`; rerun `inspect` after that warning. The default output budget approximates 1,500 tokens, and JSON reports truncation and stale reasons. Generated state stays in the ignored `.bashllm/` directory.

## Test

```bash
python3 -m unittest discover -s tests -v
```

The tests install the package in a temporary virtual environment and invoke the installed CLI.
