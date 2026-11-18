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
```

Start `codex -C /ABS/REPO` interactively with that `CODEX_HOME`. The `bashllm_run` approval should show the tool arguments, including the command and `cwd`; the server fixes the repository path in its launch arguments. Check those values before approving each call, including retries. The `prompt` approval mode is documented in [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp), and `features.shell_tool` is documented in the [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

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
  --json 'Identify the Python module that implements the MCP server.'
```

## Observed on 2026-11-18

Three ephemeral `codex exec --json` sessions used the configuration above, with the built-in shell disabled:

| Prompt | Observed tool activity | Result |
| --- | --- | --- |
| Identify the Python MCP module and a function from its contents | `bashllm_find` for `*mcp*.py`, then `bashllm_read` for `src/bashllm/mcp_server.py` | Answered with the correct path and `main()` |
| Call `bashllm_run` for `pwd` in `cwd=.` | No MCP call | Codex said it could not obtain approval in the noninteractive session; no command ran |
| Compute `17 × 19` | No MCP call | Answered `323` |

The noninteractive `exec` check establishes voluntary read-tool choice, no tool use for an unrelated question, and no silent execution when approval is unavailable. It does not establish a completed human-approved run or retry; test those in the interactive CLI before marking ticket 07 complete. No `bashllm_run` attempt reached the server during these three sessions, so they added no command-history entry.
