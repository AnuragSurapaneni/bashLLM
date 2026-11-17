# 09: Understand Go projects

**What to build:** Make a Go repository's modules, packages, entry points, and dependencies visible in the briefing and graph.

**Blocked by:** 05: Graph structure and dependencies.

**Status:** resolved

- [x] Go module declarations, packages, and likely executable entry points are recognized with source evidence.
- [x] Declared module dependencies are distinguished from imports inferred from source code.
- [x] Internal package relationships resolve where possible; external and unresolved imports are labeled.
- [x] CLI-level integration tests verify briefing findings and graph edges in a small Go project.

## Resolution

Added Go module, package, entry point, declared dependency, and import analysis. Three focused installed-CLI tests pass.
