# 06: Keep MCP results compact

**What to build:** Give a coding agent a short default MCP failure response that avoids repeating full raw output, while allowing bounded detail when the summary is insufficient.

**Blocked by:** 01: Summarize failed command attempts.

**Status:** resolved

- [x] A failed run's default model-visible MCP response contains the compact diagnostic without duplicating raw stdout and stderr across text and structured content.
- [x] The agent can explicitly request additional bounded detail, including the recorded raw output, without re-executing the command.
- [x] The compact response preserves the attempt ID, outcome, evidence limitations, and enough context to request diagnosis.
- [x] Detail requests enforce a documented output budget and redact generated excerpts; ordinary run semantics and audit history remain intact.
- [x] MCP process tests compare default and detailed responses and verify that detail retrieval does not create a new command attempt.
