# 08: Understand Rust projects

**What to build:** Make a Rust repository's packages, targets, and dependencies visible in the briefing and graph.

**Blocked by:** 05: Graph structure and dependencies.

**Status:** resolved

- [x] Rust manifests, packages, and likely executable or library targets are recognized with source evidence.
- [x] Declared dependencies are distinguished from source-level references inferred by inspection.
- [x] Known internal relationships appear in the graph; unresolved or external ones are labeled.
- [x] CLI-level integration tests verify briefing findings and graph edges in a small Rust project.

## Resolution

Added Cargo package, target, dependency, and source-reference analysis. Two focused installed-CLI tests pass.
