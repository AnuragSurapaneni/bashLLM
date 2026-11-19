# 01: Summarize failed command attempts

**What to build:** Give a coding agent a stable attempt ID and a concise, evidence-backed failure summary in the first approved run result, without launching another command.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] A recorded run returns its attempt ID through the installed CLI and MCP tool, and the ID identifies that attempt in history.
- [x] A failed or timed-out run returns a bounded summary with the decisive output excerpt, exit or timeout state, truncation state, uncertainty, and no more than three next steps.
- [x] The summary is derived only from captured run data; it launches no diagnostic subprocess, installation, or retry.
- [x] A nonzero exit without useful error evidence does not receive a confident cause, and a blocked exact repeat does not claim a fresh execution.
- [x] Generated diagnostic excerpts redact credential-like values; existing raw run output remains accessible under the current contract.
- [x] Installed CLI and MCP process tests demonstrate the behavior against temporary repositories.
