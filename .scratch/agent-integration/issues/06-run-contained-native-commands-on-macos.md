# 06: Run contained native commands on macOS

**What to build:** Let a developer run an approved finite native macOS Bash command through the verified helper, with the same observable containment and failure behavior promised for `run`.

**Blocked by:** 02: Refuse uncontained command execution; 03: Prove native macOS containment.

**Status:** ready-for-agent

- [ ] The installed CLI uses a verified native macOS backend and refuses execution if the helper, signing, entitlement, or boundary check fails.
- [ ] Native build or test tools can read required runtime paths, use explicitly granted home-directory tool paths, write within the repository, and use private temporary files.
- [ ] The command and its children cannot reach unrelated private files, inherited credentials, or the network, including through symlinks.
- [ ] Native macOS installed-CLI tests verify allowed effects, denied effects, timeouts, output limits, and backend failure without an unrestricted fallback.
- [ ] Packaging and setup instructions explain how to install and verify the helper while preserving read-only CLI use without it.
