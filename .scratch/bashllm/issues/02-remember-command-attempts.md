# 02: Remember command attempts

**What to build:** Let a coding agent see prior command attempts and avoid repeating the exact same command accidentally while retaining an explicit way to retry it.

**Blocked by:** 01: Run bounded Bash commands.

**Status:** ready-for-agent

- [ ] Commands are recorded in local SQLite history with user-only access permissions, and recent attempts can be listed.
- [ ] The same command text and working directory within one repository is blocked on a subsequent attempt.
- [ ] A blocked attempt clearly says it was not executed and returns the prior exit code and bounded output summary.
- [ ] An explicit retry executes the command again; a no-history option runs without recording the command.
- [ ] CLI-level integration tests cover exact matching, different working directories, retry, history lookup, and no-history mode.
