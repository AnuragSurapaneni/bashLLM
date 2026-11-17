# 12: Hand context to a new agent

**What to build:** Give a new coding agent one compact, current handoff that combines the briefing with recent command attempts.

**Blocked by:** 02: Remember command attempts; 05: Graph structure and dependencies.

**Status:** ready-for-agent

- [ ] The context command prints an existing briefing and a short recent-command summary with a roughly 1,500-token default budget and an adjustable limit.
- [ ] Human-readable and valid JSON forms identify when context was truncated.
- [ ] The command warns when inspected files or the eligible file set changed since the briefing was generated and directs the caller to inspect again.
- [ ] CLI-level integration tests cover compact output, budget adjustment, command history, and stale detection after edits, additions, and removals.
