# 08: Demonstrate Claude Code tool choice

**What to build:** Show a Claude Code agent making the same voluntary tool choices and using the same `bashllm` CLI contract as the Codex CLI demonstration.

**Blocked by:** 01: Agent uses repository context; 04: Record every agent run attempt; 06: Run contained native commands on macOS.

**Status:** ready-for-agent

- [ ] Claude Code receives the common versioned command description without a `bashllm`-specific protocol adapter and has no unrestricted generic shell execution in the demonstration.
- [ ] For a repository-understanding task, the agent voluntarily uses the relevant inspection, context, or exploration result.
- [ ] For a command task, the agent shows the exact command, repository, and working directory, obtains human confirmation, then invokes contained `run`; a retry asks again.
- [ ] An unrelated task prompts no `bashllm` call, and local history matches the demonstrated command attempts.
- [ ] The setup and observed results are repeatable and documented without changing the common CLI contract.
