# Claude Code demonstration

Claude Code can use the shared `bashllm` MCP server without exposing its built-in Bash tool. This recipe uses an explicitly supplied server, Manual permissions, and one-time human approval for `bashllm_run`.

## Start an isolated session

Install the current checkout first, then set `REPO` to its absolute path. Keep the MCP server name `bashllm`; the permission rule depends on it.

```bash
REPO=/absolute/path/to/bashLLM
python3 -m venv "$REPO/.venv"
"$REPO/.venv/bin/python" -m pip install "$REPO"
```

Create two temporary JSON files outside the repository. Replace `/absolute/path/to/bashLLM` in both files with `REPO`'s value. The absolute installed entry point avoids dependence on the caller's `PATH`.

`bashllm.mcp.json`:

```json
{
  "mcpServers": {
    "bashllm": {
      "type": "stdio",
      "command": "/absolute/path/to/bashLLM/.venv/bin/bashllm-mcp",
      "args": ["--repo", "/absolute/path/to/bashLLM"]
    }
  }
}
```

`bashllm.settings.json`:

```json
{
  "permissions": {
    "ask": ["mcp__bashllm__bashllm_run"],
    "deny": ["Bash"]
  }
}
```

Launch interactively from `REPO`:

```bash
cd "$REPO"
claude --restricted --strict-mcp-config \
  --mcp-config /path/to/bashllm.mcp.json \
  --settings /path/to/bashllm.settings.json \
  --permission-mode manual
```

`--restricted` removes built-in command and code execution tools, including Bash. `--strict-mcp-config` limits MCP configuration to the explicitly supplied file. Do not use `--dangerously-skip-permissions`, `--permission-mode auto`, or a standing allow rule for the run tool. The MCP server advertises `bashllm_run` as requiring user interaction on every call, including retries; the `ask` rule and Manual mode make that intent visible in the host setup. Inspect `/mcp` to confirm the server is connected and `/permissions` to confirm the rule. Choose the one-time approval option for each run, after reading its `command` and `cwd` arguments; `--repo` is fixed in the MCP configuration.

## Exercise tool choice

Give Claude these prompts separately in the interactive session and record the tool transcript:

1. `Identify the repository entry points and explain which files support your answer. Use available tools when useful.` Expect a `bashllm_inspect`, `bashllm_context`, or exploration call when the agent finds the static briefing useful. Record the actual choice; no particular call is guaranteed.
2. `Run pwd in the repository and tell me its output.` Expect a proposed `bashllm_run` call with `command: "pwd"`, `cwd: "."`, and a one-time permission prompt. Approve only after inspecting the call. Ask for an exact retry and verify a second prompt. Check `bashllm history --repo "$REPO" --json` against both attempts.
3. `What is 2 + 2?` Expect a direct answer without a `bashllm` call.

These are observations to collect, rather than promises about model behavior. A real demonstration meets ticket 08 only when the transcript shows voluntary use for the repository task, a separate human approval for each contained run, no generic shell capability, and no `bashllm` call for the unrelated task.

## Observed on this machine

On 2026-11-18, Claude Code 2.1.284 accepted the `--restricted`, `--strict-mcp-config`, `--mcp-config`, `--settings`, and Manual flags in a noninteractive probe with the local MCP server configured. The probe stopped before model inference with `Not logged in · Please run /login` (`claude auth status` reported `loggedIn: false`). It made zero tool calls and spent zero API tokens. Therefore, voluntary tool selection and permission prompts remain unverified here.

The shared adapter's process tests separately verify MCP initialization, tool discovery, fixed-repository reads, input rejection, and audited run attempts. They do not substitute for Claude's host permission prompt.

References: [Claude Code MCP configuration and per-call approval](https://code.claude.com/docs/en/mcp), [Claude Code permission rules and modes](https://code.claude.com/docs/en/permissions).
