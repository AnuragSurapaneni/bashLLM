# 09: Understand Go projects

**What to build:** Make a Go repository's modules, packages, entry points, and dependencies visible in the briefing and graph.

**Blocked by:** 05: Graph structure and dependencies.

**Status:** ready-for-agent

- [ ] Go module declarations, packages, and likely executable entry points are recognized with source evidence.
- [ ] Declared module dependencies are distinguished from imports inferred from source code.
- [ ] Internal package relationships resolve where possible; external and unresolved imports are labeled.
- [ ] CLI-level integration tests verify briefing findings and graph edges in a small Go project.
