# 07: Demonstrate Codex CLI tool choice

**What to build:** Show a Codex CLI agent using the common `bashllm` CLI when repository context or an approved command helps, and skipping it when the task is unrelated.

**Blocked by:** 01: Agent uses repository context; 04: Record every agent run attempt; 06: Run contained native commands on macOS.

**Status:** ready-for-agent

- [ ] Codex CLI receives the versioned command description without a `bashllm`-specific protocol adapter and has no unrestricted generic shell execution in the demonstration.
- [ ] For a repository-understanding task, the agent voluntarily selects appropriate inspection, context, or exploration commands and uses their JSON results.
- [ ] For a command task, the agent shows the exact command, repository, and working directory, obtains human confirmation, then invokes contained `run`; a retry asks again.
- [ ] An unrelated task prompts no `bashllm` call, and local history matches the demonstrated command attempts.
- [ ] The setup and observed results are repeatable and documented without changing the common CLI contract.
