# 05: Check declared Python dependencies

**What to build:** Let a coding agent compare the selected interpreter's installed distributions with the repository's declared Python dependencies in one approved diagnostic, without importing package code.

**Blocked by:** 04: Report the relevant Python interpreter.

**Status:** resolved

- [x] Core dependencies from supported project declarations are compared with installed distribution metadata for the selected interpreter, with missing and incompatible versions reported separately.
- [x] Optional groups are listed but checked only when the recorded command clearly selects one or the diagnostic caller explicitly requests it.
- [x] Package checks use metadata rather than importing every dependency or executing project code.
- [x] Unsupported declarations, unresolved version constraints, and inaccessible package data are labeled unverified rather than missing.
- [x] Output remains bounded and separates recorded failure evidence from current package observations.
- [x] Installed CLI and MCP process tests cover core, optional, missing, incompatible, and unverified outcomes.
