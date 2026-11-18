# 03: Prove unsigned macOS execution profile

**What to build:** Demonstrate an unsigned `sandbox-exec` profile for finite native macOS Bash commands, recording the exact protections and limits before the CLI enables it.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] An unsigned `sandbox-exec` invocation runs a native macOS tool and child process with repository writes and private temporary files.
- [x] Repeatable probes record what happens when commands read and write outside the repository, follow external symlinks, inherit credentials, and attempt network connections.
- [x] The proof records host prerequisites, observed behavior, failure modes, deprecation, and limits without claiming robust isolation against hostile code.
- [x] No signing identity, signed helper, or Linux guest is needed.

## Comments

- 2026-11-18: A minimal ad hoc signed App Sandbox probe aborted, both as a bare executable and as an app bundle. The system reports no valid code-signing identities. Apple's [App Sandbox documentation](https://developer.apple.com/documentation/security/app-sandbox) and [helper guidance](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app) describe the supported packaging route. The user directed that macOS `run` remain disabled for now.
- 2026-11-18: The user changed scope and approved the deprecated unsigned `sandbox-exec` path with a narrower, explicitly best-effort guarantee. The earlier signing dependency is removed.
- 2026-11-18: Native installed-CLI tests passed on macOS outside the development sandbox. See `docs/agents/macos-containment.md` for the observed boundary and limits.
