# 01: Agent uses repository context

**What to build:** Give an agent a versioned, harness-neutral description of the installed CLI so it can choose and use repository inspection, context handoff, exploration, and history when those capabilities help its task.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The installed CLI exposes a machine-readable versioned description of the relevant commands, arguments, JSON results, failure states, and usage guidance.
- [x] A consumer using only that description can obtain a briefing, refresh stale context, locate and read a file, and inspect recent command history through the CLI.
- [x] Guidance leaves tool choice to the agent and explains when an unrelated task needs no `bashllm` call.
- [x] Installed-CLI tests verify the description and the read-only user journey without requiring a harness-specific protocol.

## Resolution

Added a versioned agent command description to the installed CLI, documented its use, and verified repository inspection, context, exploration, and history through subprocess tests.
