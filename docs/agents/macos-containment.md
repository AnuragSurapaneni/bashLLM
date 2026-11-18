# macOS command profile

`bashllm run` uses the system `/usr/bin/sandbox-exec` on macOS. It creates a fresh private directory under `/private/tmp`, sets `HOME`, `TMPDIR`, and `XDG_CACHE_HOME` inside it, and removes inherited environment variables. It starts Bash through a temporary sandbox profile and removes that directory after the command. The profile needs no code signing.

The profile starts from `(allow default)`. It denies file reads from the current user's home, `/private/tmp`, and `/private/var/folders`, then allows the configured repository, the private run directory, and explicit read-only tool grants. It denies file writes by default, then allows writes inside the repository and private run directory. It denies network operations. The repository includes ignored files and `.bashllm` state, which a command can read and write. Other host reads and IPC may still be possible. This is a best-effort restriction, not a security boundary for hostile code.

The CLI verifies that the trusted system utility exists and that a profile-wrapped Bash process starts. If that check fails, `run` returns exit code 69 with `status: "backend_unavailable"` and does not launch the requested command. Read and inspection commands remain available. Apple's `sandbox-exec` and custom profiles are deprecated and unsupported for third-party use, so availability and behavior may change with macOS releases.

In local macOS installed-CLI tests, we observed repository writes, private temporary files and cleanup, native child processes, denied reads of a home-directory sentinel and an external symlink target, denied writes outside the repository, stripped inherited secrets, and denied loopback connections. These tests establish the behavior on the tested host; they do not guarantee resistance to a malicious process. The CI suite requires the backend with `BASHLLM_REQUIRE_MACOS_SANDBOX=1` on a `macos-15-intel` runner.

The profile permits execution of system tools and explicitly granted home-directory tools. A native tool may still expect access to files or caches that this profile denies; such commands can fail. Grant only the exact tool path needed through the owner-controlled tool grants file documented in the README.

Apple describes the deprecation in its [Developer Forums notice](https://developer.apple.com/forums/thread/661939).
