# 09: Expose bashllm through a shared MCP adapter

**What to build:** Let Codex CLI and Claude Code call the same typed repository and execution tools without giving the agent a generic shell or unrestricted CLI passthrough.

**Blocked by:** 01: Agent uses repository context; 04: Record every agent run attempt.

**Status:** resolved

- [x] One MCP stdio server exposes typed inspection, context, exploration, history, and execution tools that call the installed CLI and return structured results.
- [x] The execution tool always uses the audited agent path and cannot accept a history opt-out, arbitrary CLI arguments, or direct tool-path grants.
- [x] Invalid tool names and inputs produce structured errors without launching a command.
- [x] Process-level MCP tests cover initialization, discovery, tool calls, refusal, and shutdown.
- [x] Setup guidance shows how both harnesses can expose the same server while disabling generic shell access and requiring human approval for each execution.
