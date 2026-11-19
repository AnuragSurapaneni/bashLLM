# 03: Diagnose a recorded run safely

**What to build:** Let a coding agent request one separately approved, bounded diagnostic for a prior run by ID and see the sanitized execution environment that applies now alongside the recorded failure evidence.

**Blocked by:** 01: Summarize failed command attempts.

**Status:** resolved

- [x] The installed CLI and MCP adapter accept a recorded attempt ID and reject missing, invalid, or inaccessible attempts with bounded structured errors.
- [x] The diagnostic MCP tool is marked as requiring human interaction, and host guidance requires approval for every process-launching diagnostic call.
- [x] The check uses the recorded repository and working directory, the same fail-closed containment boundary, and the minimal agent-run environment; no unrestricted fallback runs when containment is unavailable.
- [x] The result separates the recorded attempt and its timestamp from current checks and their timestamp, and identifies attempts that never executed.
- [x] Only allowlisted environment settings appear, with bounded and redacted values; the diagnostic neither mutates state nor retries the prior command.
- [x] CLI and MCP process tests cover approval metadata, fixed repository, valid and invalid IDs, sanitized values, and backend refusal.
