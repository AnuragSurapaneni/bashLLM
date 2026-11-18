# 06: Run native commands with unsigned macOS profile

**What to build:** Let a developer run an approved finite native macOS Bash command through the tested unsigned `sandbox-exec` profile, with clearly labelled best-effort restrictions and fail-closed startup behavior.

**Blocked by:** 02: Refuse uncontained command execution; 03: Prove native macOS containment.

**Status:** resolved

- [x] The installed CLI uses the tested unsigned profile and refuses execution if `sandbox-exec` or its probe fails; it never falls back to unrestricted Bash.
- [x] Native commands can read system runtime paths, write within the repository, and use private temporary files; explicit tool grants are supported.
- [x] The tested profile restricts outside private file access, inherited credentials, and network connections for the observed command and child-process cases; the CLI describes this as best-effort.
- [x] Native macOS installed-CLI tests verify allowed effects, denied effects, timeouts, output limits, and backend failure without an unrestricted fallback.
- [x] Documentation explains the profile's deprecation, exact tested limits, and continued read-only CLI use when it is unavailable.
