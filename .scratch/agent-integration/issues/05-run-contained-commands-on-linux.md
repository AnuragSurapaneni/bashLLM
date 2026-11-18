# 05: Run contained commands on Linux

**What to build:** Let a developer run an approved finite Bash command on Linux through Bubblewrap with repository writes and private temporary files, while the rest of the host and the network remain outside the command's reach.

**Blocked by:** 02: Refuse uncontained command execution.

**Status:** ready-for-agent

- [ ] A capability check enables `run` only when Bubblewrap and usable user namespaces can establish the full boundary; failure leaves `run` refused.
- [ ] The command can use system programs, approved tool paths, the repository, and a disposable private temporary directory; repository changes persist.
- [ ] The command and its children cannot read unrelated private files, use undeclared home-directory tool paths, inherit credentials, or access the network.
- [ ] Native Linux installed-CLI tests cover allowed builds or tests, symlink and child-process escape attempts, output and timeout limits, and clear refusal when prerequisites are missing.
- [ ] Linux setup and tool-path grants are documented without making the backend a prerequisite for read-only CLI use.

## Comments

- 2026-11-18: A Bubblewrap launcher and fail-closed capability probe are implemented locally. Native Linux isolation tests remain outstanding; this macOS workspace has no running Linux container or host runner.
