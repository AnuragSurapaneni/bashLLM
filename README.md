# bashllm

Coding assistants can spend a lot of tokens trying to understand a project. They may search for the same files, repeat commands, or read pages of error output before finding the useful line. `bashllm` gives them a short starting guide to your project, remembers what they have tried, and turns common command failures into smaller, more useful results.

Tokens are small pieces of text in an AI conversation. Using fewer of them leaves more room for the work you actually want the assistant to do.

You can use `bashllm` yourself in a terminal or connect it to a coding assistant. It works on macOS and Linux with Python 3.11 or newer.

## Get started

From this repository, install `bashllm` and ask it to look at your project:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/bashllm inspect --repo /path/to/your/project
.venv/bin/bashllm context --repo /path/to/your/project
```

Replace `/path/to/your/project` with the full path to the project you want to work on. `inspect` reads the project and writes a guide at `/path/to/your/project/.bashllm/BRIEFING.md`. `context` prints a shorter version that you can give to an assistant. If it says the guide is out of date, run `inspect` again. This step does not run your project's code.

If you update this `bashllm` checkout later, run `.venv/bin/python -m pip install .` again to install the new version.

## How it saves tokens

`bashllm` helps an assistant start with a project map instead of discovering the same facts through many searches. It remembers command attempts, so an exact repeat does not waste another run. When a command fails, the assistant gets a short error summary and can ask for more detail only when it needs it.

Here are estimated savings from seven repeatable tasks on a macOS development machine. “Before” models the previous, longer command response. For the Python tasks, it also includes separate commands to check the Python setup. The numbers are estimates based on response size, not counts from a specific AI model.

| Task | Before | Current `bashllm` | Tokens saved |
| --- | ---: | ---: | ---: |
| Find the wrong Python interpreter | 1,576 | 966 | 610 |
| Find a missing Python package | 1,571 | 1,013 | 558 |
| Check a package version conflict | 1,590 | 956 | 634 |
| Find a Python syntax error | 414 | 221 | 193 |
| Find a missing command | 209 | 181 | 28 |
| Understand a timed-out command | 180 | 175 | 5 |
| Handle very long output | 16,725 | 354 | 16,371 |

The measured savings depend on the task and its output. An [automated test](tests/test_mcp.py) also checks that a large failure saves at least 3,000 estimated tokens. It measured 4,339 on the development machine. You can see the setup and full results in the [benchmark notes](docs/agents/diagnostic-benchmark.md).

## Use it from the terminal

`inspect` makes a guide to the project's files and likely starting points. `context` prints a compact version with recent command history. `find`, `search`, and `read` help you look at specific files without a long chain of shell commands.

To run a command in your project, use `run`:

```bash
.venv/bin/bashllm run --repo /path/to/your/project --cwd . -- 'pwd'
```

The `--cwd .` part starts the command at the project root. `bashllm` records the attempt and stops you from running the exact same command there again by accident. Add `--retry` if you want to run it again. You can see earlier attempts with:

```bash
.venv/bin/bashllm history --repo /path/to/your/project
```

With `--json`, a failed run includes a short error summary and suggested next checks. For Python problems, `diagnose` can check which Python interpreter and packages are available. Use `--json` with `run` to get its `attempt_id`, then pass that number to `diagnose`:

```bash
.venv/bin/bashllm run --repo /path/to/your/project --cwd . --json -- 'python3 app.py'
.venv/bin/bashllm diagnose --repo /path/to/your/project --attempt-id 12 --json
```

Replace `12` with the `attempt_id` from your run. `diagnose` checks the environment as it is *now*, so it may differ from the environment at the time of an older failure. It does not install packages or rerun your command.

## Connect a coding assistant

`bashllm` can give the same tools directly to an assistant through MCP, a connection for assistant tools. Follow the [Codex guide](docs/agents/codex-demo.md) or [Claude Code guide](docs/agents/claude-demo.md) to set it up. The assistant can then ask for a short project guide, run a command with your approval, and check a failure without filling the conversation with raw output.

The assistant's app must ask for your approval before **every** command run or diagnostic check. `bashllm` cannot show that approval prompt itself. The setup guides explain how to require it.

Reading and inspecting files works without extra system setup. Running commands needs Bubblewrap on Linux or the system `sandbox-exec` tool on macOS. If that protection is unavailable, `bashllm` refuses to run the command. It does not fall back to an unrestricted run. The macOS protection is best effort; see the [macOS notes](docs/agents/macos-containment.md) for its limits.

## For contributors

Run the tests with:

```bash
python3 -m unittest discover -s tests -v
```
