# 01: Run bounded Bash commands

**What to build:** Give a coding agent an installable CLI that executes a Bash command in an explicit repository and working directory and returns a concise, bounded result.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A fresh installation exposes the CLI on macOS and Linux with Python 3.11 or later and no required runtime packages.
- [ ] A command runs in the requested working directory in a fresh Bash process and reports its exit code.
- [ ] Execution defaults to a 60-second timeout and captures at most 32 KiB per output stream; both limits can be adjusted.
- [ ] Results are available in human-readable and valid JSON forms, including timeout and truncation status.
- [ ] CLI-level integration tests exercise success, failure, timeout, output limits, and working directory selection.
