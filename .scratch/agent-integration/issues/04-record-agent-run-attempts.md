# 04: Record every agent run attempt

**What to build:** Give agent-initiated command execution an auditable CLI path that records executions and refusals without allowing the agent to disable history.

**Blocked by:** 02: Refuse uncontained command execution.

**Status:** resolved

- [x] Agent-initiated runs record the requested command, repository, working directory, and outcome for executions, retries, exact-repeat blocks, and backend refusals.
- [x] The agent-facing invocation cannot opt out of history; any existing human-facing no-history behavior is handled without weakening this guarantee.
- [x] Stored history remains private to the repository owner, and `history` reports the new outcomes through its normal CLI interface.
- [x] Installed-CLI tests cover both executed and refused attempts, repeat blocking, explicit retry, and the history opt-out boundary.

## Comments

- 2026-11-18: The agent-facing CLI path now rejects history opt-out and records backend refusals, including repeated and retry requests. Executed-command and blocked-repeat audit cases still need a verified Linux backend to complete behavioral testing.

## Resolution

The native Linux installed-CLI suite now verifies agent execution, blocked-repeat, and retry records alongside the fail-closed refusal tests. GitHub Actions run 44276840573 passed.
