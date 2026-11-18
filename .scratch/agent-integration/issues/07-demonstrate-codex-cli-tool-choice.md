# 07: Demonstrate Codex CLI tool choice

**What to build:** Show a Codex CLI agent using the common `bashllm` CLI when repository context or an approved command helps, and skipping it when the task is unrelated.

**Blocked by:** None.

**Status:** ready-for-agent

- [x] Codex CLI receives the shared MCP tools with no unrestricted generic shell execution in the demonstration.
- [x] For a repository-understanding task, the agent voluntarily selects appropriate inspection, context, or exploration commands and uses their JSON results.
- [ ] For a command task, the agent shows the exact command, repository, and working directory, obtains human confirmation, then invokes contained `run`; a retry asks again.
- [x] An unrelated task prompts no `bashllm` call, and local history matches the demonstrated command attempts.
- [x] The setup and observed results are repeatable and documented without changing the common CLI contract.

## Comments

- 2026-11-18: A noninteractive Codex demo used `bashllm_find` and `bashllm_read` for a repository question and no tool for arithmetic. A proposed run did not execute because no human approval was available. An interactive approved run and retry remain to be observed. See `docs/agents/codex-demo.md`.
