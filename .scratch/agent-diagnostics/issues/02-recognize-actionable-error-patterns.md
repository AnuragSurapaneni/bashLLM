# 02: Recognize actionable error patterns

**What to build:** Let a coding agent recognize common Python and shell failures from a compact run summary and see evidence-based next checks without guessing from an exit code alone.

**Blocked by:** 01: Summarize failed command attempts.

**Status:** resolved

- [x] Python tracebacks, missing module or import errors, syntax errors, and supported version-conflict messages receive bounded categories and relevant evidence.
- [x] Missing executable errors receive a category and a concrete next check.
- [x] A timeout, truncated output, or uncertain pattern is labeled accordingly; unsupported failures remain unclassified instead of receiving a fabricated cause.
- [x] Suggested actions remain advisory and never install packages, change the environment, or retry the command.
- [x] Process-level scenarios cover each supported pattern and an ordinary nonzero exit that is not a diagnosed failure.
