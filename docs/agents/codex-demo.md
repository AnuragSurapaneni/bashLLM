# Codex CLI MCP demonstration

This setup gives Codex the shared `bashllm` MCP tools while removing its generic shell tool. It fixes the repository at server launch. A person must approve every `bashllm_run` call in an interactive Codex session. The MCP server cannot enforce a host prompt by itself.

## Setup

Install `bashllm` in a Python 3.11+ environment, then put the following in `config.toml` for a dedicated `CODEX_HOME` containing no other executable MCP servers or plugins. Replace `/ABS/REPO` with the repository's absolute path. Sign in to that Codex home before starting the demo. Do not enable automatic review or an approval bypass.

```toml
approval_policy = "on-request"
approvals_reviewer = "user"
sandbox_mode = "read-only"

[features]
shell_tool = false

[mcp_servers.bashllm]
command = "/ABS/REPO/.venv/bin/bashllm-mcp"
args = ["--repo", "/ABS/REPO"]
required = true
tool_timeout_sec = 75

[mcp_servers.bashllm.tools.bashllm_run]
approval_mode = "prompt"

[mcp_servers.bashllm.tools.bashllm_diagnose]
approval_mode = "prompt"
```

Start `codex -C /ABS/REPO` interactively with that `CODEX_HOME`. The `bashllm_run` approval should show the command, `cwd`, and `repo`. The server fixes the repository at launch, advertises its resolved path as a required constant tool argument, and rejects a different path. Check all three values before approving each call, including retries. The `prompt` approval mode is documented in [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp), and `features.shell_tool` is documented in the [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

After a failed run, the agent can read its compact diagnostic and request `bashllm_result` for bounded raw output. `bashllm_diagnose` launches a separate contained check for the recorded attempt ID; inspect its arguments and approve that call separately. It does not install dependencies or retry the command.

For a disposable read-only check without changing user configuration, the installed Codex CLI 0.169.0 also accepted `codex exec --ignore-user-config --disable shell_tool --sandbox read-only` with `-c` overrides for `approval_policy`, `approvals_reviewer`, and the MCP server table above. In the local check, the server command was `.venv/bin/python` with arguments `-m bashllm.mcp_server --repo /ABS/REPO` and `PYTHONPATH=/ABS/REPO/src`, because the new entry point was not yet installed in the development virtual environment. Use the installed entry point for normal setup. For example:

```bash
codex exec --ignore-user-config --strict-config --ephemeral \
  --disable shell_tool --sandbox read-only -C /ABS/REPO \
  -c 'approval_policy="on-request"' -c 'approvals_reviewer="user"' \
  -c 'mcp_servers.bashllm.command="/ABS/REPO/.venv/bin/bashllm-mcp"' \
  -c 'mcp_servers.bashllm.args=["--repo","/ABS/REPO"]' \
  -c 'mcp_servers.bashllm.required=true' \
  -c 'mcp_servers.bashllm.tool_timeout_sec=75' \
  -c 'mcp_servers.bashllm.tools.bashllm_run.approval_mode="prompt"' \
  -c 'mcp_servers.bashllm.tools.bashllm_diagnose.approval_mode="prompt"' \
  --json 'Identify the Python module that implements the MCP server.'
```

## Observed on 2026-11-18

Three ephemeral `codex exec --json` sessions used the configuration above, with the built-in shell disabled:

| Prompt | Observed tool activity | Result |
| --- | --- | --- |
| Identify the Python MCP module and a function from its contents | `bashllm_find` for `*mcp*.py`, then `bashllm_read` for `src/bashllm/mcp_server.py` | Answered with the correct path and `main()` |
| Call `bashllm_run` for `pwd` in `cwd=.` | No MCP call | Codex said it could not obtain approval in the noninteractive session; no command ran |
| Compute `17 × 19` | No MCP call | Answered `323` |

The noninteractive `exec` check establishes voluntary read-tool choice, no tool use for an unrelated question, and no silent execution when approval is unavailable. No `bashllm_run` attempt reached the server during those three sessions, so they added no command-history entry.

An interactive `codex --no-alt-screen --no-daemon` session with `features.shell_tool=false` and the same fixed MCP server then called `bashllm_run` with `command: pwd` and `cwd: .`. The host showed an “Allow” or “Cancel” dialog. The user approved that exact call in the parent conversation, and the operator submitted “Allow” in the Codex terminal. The server returned `status: executed`, exit code 0, and `/Users/anurag/Desktop/bashLLM` on stdout.

Codex was then asked to retry the same command. It called `bashllm_run` with `command: pwd`, `cwd: .`, and `retry: true`. The host displayed a fresh approval dialog that included `retry: true`. The user approved this separate call in the parent conversation; the operator submitted “Allow” again. The result was another successful execution. The configured repository was `/Users/anurag/Desktop/bashLLM`; its path was fixed in the server launch configuration, while the dialogs displayed the tool arguments. `bashllm history --repo . --json` showed two `executed` entries for `pwd` in that repository and working directory, each with exit code 0. The interactive session was then closed normally.

After the adapter began requiring its fixed repository path as an explicit argument, a second interactive Codex session reached a dialog showing `command: pwd`, `cwd: .`, and `repo: /Users/anurag/Desktop/bashLLM`. The operator chose “Cancel”; no third history entry appeared. This verifies that the full execution target is visible to the human before approval.
