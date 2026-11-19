# 07: Verify token savings

**What to build:** Demonstrate whether the completed diagnostic workflow reduces an agent's exploratory tool calls and returned output tokens for representative failures, and document how to use it.

**Blocked by:** 02: Recognize actionable error patterns; 05: Check declared Python dependencies; 06: Keep MCP results compact.

**Status:** resolved

- [x] Reproducible scenarios cover wrong interpreter, missing distribution, version conflict, syntax error, missing executable, timeout, and truncated output.
- [x] Each scenario records tool-call counts and returned output-token estimates for the existing workflow and the diagnostic workflow, with the measurement method stated.
- [x] Results identify scenarios where the feature helps or does not help; no universal savings claim is made.
- [x] Agent contract and MCP host guidance explain the compact run result, separately approved diagnostic call, detail retrieval, and unchanged approval boundary.
- [x] The installed CLI and MCP process suite passes with the completed workflow.
