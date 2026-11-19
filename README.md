# bashllm

`bashllm` is a Python CLI for exploring a repository, preparing context for a coding agent, and running bounded Bash commands. It generates a static briefing, records command attempts, and blocks accidental exact repeats. A shared MCP server makes the same tools available to coding agents.

## Quick start

From the `bashllm` checkout, install the CLI and inspect a repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/bashllm inspect --repo /absolute/path/to/project
.venv/bin/bashllm context --repo /absolute/path/to/project
```

`inspect` creates `/absolute/path/to/project/.bashllm/BRIEFING.md` and `GRAPH.dot`. Run `inspect` again when `context` reports that files changed. These read and inspection commands work even if command containment is unavailable.

To run a command, first set up the platform backend described below, then use:

```bash
.venv/bin/bashllm run --repo /absolute/path/to/project --cwd . -- 'pwd'
.venv/bin/bashllm history --repo /absolute/path/to/project
```

`--cwd .` means the project root. The first command prints the command output and execution status; `history` shows the recorded attempt. Use `--json` on any command for structured output.

## Install

Requires Python 3.11 or later and Bash on macOS or Linux. Repository reading and inspection have no runtime dependencies. Contained execution requires a trusted system installation of Bubblewrap and usable user namespaces on Linux, or Apple's `sandbox-exec` on macOS. The macOS profile is a best-effort restriction through a deprecated utility; it is not a malicious-code isolation guarantee.

Install from the checkout as shown in Quick start. Re-run `.venv/bin/python -m pip install .` after updating the checkout so the installed entry points include the latest commands.

On Linux, install the distribution's system `bubblewrap` package and enable usable user namespaces. `bashllm` looks for a trusted `/usr/bin/bwrap` or `/bin/bwrap`; a copy installed elsewhere is not used. On macOS, `run` uses the system `/usr/bin/sandbox-exec`. The backend is checked when `run` starts, so installation alone does not establish that execution is available.

## Choose a command

| Command | Use it to |
| --- | --- |
| `inspect --repo REPO` | Generate a static briefing and dependency graph. |
| `context --repo REPO` | Get a compact handoff and recent attempts after `inspect`. |
| `find PATTERN --repo REPO` | Find files by glob. |
| `search TEXT --repo REPO` | Search repository text literally. |
| `read PATH --repo REPO` | Read a bounded repository file. |
| `history --repo REPO` | Review command attempts and outcomes. |
| `result --repo REPO --attempt-id ID` | Retrieve bounded output from a recorded attempt. |
| `diagnose --repo REPO --attempt-id ID` | Check a recorded failure in containment. |
| `run --repo REPO --cwd DIR -- 'COMMAND'` | Execute one bounded Bash command. |
| `agent-spec --json` | Get the versioned CLI contract for an agent harness. |

Run `.venv/bin/bashllm COMMAND --help` for each command's options. Paths supplied to `read` are relative to the repository. The read commands skip generated directories and limit their output.

## Run a command

```bash
.venv/bin/bashllm run --repo . --cwd . -- 'pwd'
.venv/bin/bashllm run --repo . --cwd . --json -- 'printf "hello\\n"'
```

Pass one Bash command string after `--`. `--repo` names the repository root, and `--cwd` names a directory inside it; a relative `--cwd` is resolved from the repository root. Each call starts a fresh Bash process only after the platform containment backend passes a capability check. If the backend is missing or fails to start, `run` refuses the command with exit code 69 and a `backend_unavailable` JSON status. It never falls back to unrestricted execution. The other commands continue to work.

On Linux, the backend exposes the repository for persistent reads and writes, a disposable private temporary directory, and the system runtime needed to launch Bash. It starts with a minimal environment and no network namespace. On macOS, `sandbox-exec` denies reads from the user's home and standard temporary locations except the repository and private run directory, while allowing metadata reads of repository ancestor directories for path resolution. It denies writes outside the repository and private run directory, and denies network operations. Diagnostic probes use a read-only repository mount or profile. The deprecated macOS profile permits other host reads and IPC, so it must not be used as a strong boundary against hostile commands. The entire repository is visible to the command, including ignored files. External tools installed under your home directory require an explicit read-only path grant. Human CLI users can pass `--tool-path PATH` on a run. An agent's grants must be configured in an owner-controlled `~/.config/bashllm/tool-grants.json` file as a JSON object mapping an absolute repository path to a list of absolute tool file or directory paths. Agent calls cannot pass `--tool-path` directly. Native containment tests run on each supported platform.

The default timeout is 60 seconds and each output stream retains at most 32 KiB. Use `--timeout SECONDS` and `--max-output BYTES` to adjust them. The CLI returns the command's exit code, or 124 on timeout. JSON output includes the exit code, duration, timeout status, and per-stream truncation flags.

Command attempts are saved privately under the repository's ignored `.bashllm/` directory. An exact repeat of the same executed command and working directory is blocked with the earlier result and a `not_executed` status. Use `--retry` to execute it again or `--no-history` to skip history lookup and storage for a human-invoked run. Agent runs use `--agent`, which records executions and refusals and rejects `--no-history`. The calling agent must request human approval for the exact command, repository, and working directory before each execution, including retries. Inspect recent attempts with:

```bash
.venv/bin/bashllm history --repo . --limit 10 --json
```

`run --json` reports `status: "executed"` for a launched command, `status: "not_executed"` with exit code 3 for a blocked repeat, or `status: "backend_unavailable"` with exit code 69 when containment cannot start. Agent attempts, including refusals and repeats, appear in history. A human CLI call can use `--no-history`; an agent call cannot.

Failed runs include a bounded `diagnostic` with an error category, evidence, uncertainty, and up to three next steps. A recorded run includes `attempt_id`. Use `result --repo REPO --attempt-id ID --max-bytes 4096 --json` to read bounded raw output later without rerunning the command. Use `diagnose --repo REPO --attempt-id ID --json` for a current check of the sanitized environment and Python interpreter. The check uses the same containment backend, reports declared dependency availability from package metadata, and never installs packages or retries the command. It is a separate process-launching action and requires its own human approval when exposed through an agent harness. `--group NAME` checks one declared optional dependency group; `--max-detail` adjusts the diagnostic detail budget. The reported Python search path comes from an isolated probe and can differ from a command that changed its own Python path.

The [MCP token-savings test](tests/test_mcp.py) generates a large failure and requires at least **3,000 estimated tokens saved** by the compact response. On the macOS development host it measured **4,339 estimated tokens saved**: 4,480 for a conservative baseline that counts only duplicated raw stderr, versus 141 for the compact response. The estimate uses UTF-8 bytes divided by four, not a model tokenizer. See the [diagnostic benchmark](docs/agents/diagnostic-benchmark.md) for seven reproducible scenarios and the measurement method.

## Agent integration

The versioned, harness-neutral command description is available from:

```bash
.venv/bin/bashllm agent-spec --json
```

Give this description to an agent harness as its tool contract. It explains when to use the read commands and `run`, how to parse JSON, and when to leave `bashllm` unused. For an MCP host, configure a stdio server with the installed executable and a fixed repository:

```json
{
  "command": "/absolute/path/to/bashLLM/.venv/bin/bashllm-mcp",
  "args": ["--repo", "/absolute/path/to/project"]
}
```

The host starts that executable and exposes fixed-repository `find`, `search`, `read`, `inspect`, `context`, `history`, `result`, `diagnose`, and `run` tools. The run tool requires the fixed repository path as a visible argument and rejects a mismatch. It always invokes the audited agent path for `run`. Failed MCP runs return a compact summary; `bashllm_result` retrieves bounded raw output by attempt ID. Configure the host to prompt a human for **every** `bashllm_run` and `bashllm_diagnose` call, including retries, and disable its generic shell tool when you need all command execution to pass through this boundary. The MCP server cannot verify that a host displayed or received human approval. See the [Codex CLI guide](docs/agents/codex-demo.md) and [Claude Code guide](docs/agents/claude-demo.md) for complete host configuration.

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
