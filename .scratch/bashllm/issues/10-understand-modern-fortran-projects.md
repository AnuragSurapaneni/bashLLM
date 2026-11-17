# 10: Understand modern Fortran projects

**What to build:** Make modern Fortran programs, modules, submodules, and `USE` dependencies visible in the briefing and graph.

**Blocked by:** 05: Graph structure and dependencies.

**Status:** ready-for-agent

- [ ] Common free form Fortran source extensions are recognized, with case-insensitive names and continuation lines handled.
- [ ] Programs, modules, submodules, and `USE` relationships appear with source evidence.
- [ ] Internal module references resolve where possible; intrinsic, external, and unresolved targets are labeled appropriately.
- [ ] CLI-level integration tests verify mixed-case, multiline, module, and submodule examples in briefing and graph output.
