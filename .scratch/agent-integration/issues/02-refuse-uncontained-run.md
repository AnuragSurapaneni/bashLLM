# 02: Refuse uncontained command execution

**What to build:** Make `run` clearly refuse a command whenever a verified containment backend is unavailable, while repository reading and inspection remain available.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] `run` never starts Bash with unrestricted caller permissions when containment cannot be established, including after backend startup failure.
- [x] Human-readable and JSON results distinguish a backend refusal from a command exit, timeout, and exact-repeat block.
- [x] The existing inspection, context, exploration, and history commands continue to work without an execution backend.
- [x] Installed-CLI tests prove refusal has no command side effect and cover the temporary unavailable state until platform backends are added.

## Resolution

Added fail-closed launcher selection and structured refusal with exit code 69. Installed-CLI tests on macOS verify no command side effect and continued read access. Native Linux backend verification remains in ticket 05.
