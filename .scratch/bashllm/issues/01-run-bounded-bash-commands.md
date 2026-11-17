# 01: Run bounded Bash commands

**What to build:** Give a coding agent an installable CLI that executes a Bash command in an explicit repository and working directory and returns a concise, bounded result.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] A fresh installation exposes the CLI on macOS and Linux with Python 3.11 or later and no required runtime packages.
- [x] A command runs in the requested working directory in a fresh Bash process and reports its exit code.
- [x] Execution defaults to a 60-second timeout and captures at most 32 KiB per output stream; both limits can be adjusted.
- [x] Results are available in human-readable and valid JSON forms, including timeout and truncation status.
- [x] CLI-level integration tests exercise success, failure, timeout, output limits, and working directory selection.

## Resolution

Implemented the installable `run` command and verified it with five CLI-level integration tests on macOS. Linux compatibility follows the POSIX process APIs used here but has not been run in this workspace.
