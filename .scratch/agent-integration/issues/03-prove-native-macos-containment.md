# 03: Prove native macOS containment

**What to build:** Establish a verifiable native macOS containment approach for finite Bash commands before the CLI advertises contained macOS execution.

**Blocked by:** A valid Apple Developer code-signing identity and a native helper packaging path.

**Status:** ready-for-human

- [ ] A signed helper or other supported macOS backend runs a native macOS tool and a child process while keeping the command tree inside the proposed boundary.
- [ ] A repeatable proof shows repository writes and private temporary files work while unrelated private files, inherited credentials, and network access are unavailable.
- [ ] The proof attempts symlink and subprocess escapes and records observed results, backend prerequisites, packaging requirements, and remaining limitations.
- [ ] The proof uses neither a Linux guest nor deprecated `sandbox-exec` as the basis of the promised boundary.

## Comments

- 2026-11-18: A minimal ad hoc signed App Sandbox probe aborted, both as a bare executable and as an app bundle. The system reports no valid code-signing identities. Apple's [App Sandbox documentation](https://developer.apple.com/documentation/security/app-sandbox) and [helper guidance](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app) describe the supported packaging route. The user directed that macOS `run` remain disabled for now.
