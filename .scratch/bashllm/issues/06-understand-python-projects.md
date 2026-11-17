# 06: Understand Python projects

**What to build:** Make a Python repository's entry points and dependencies visible in the preflight briefing and graph.

**Blocked by:** 05: Graph structure and dependencies.

**Status:** resolved

- [x] Common Python project manifests, scripts, packages, and likely entry points are recognized with source evidence.
- [x] Declared dependencies are distinguished from imports inferred from source code.
- [x] Internal imports resolve to repository nodes where possible; unresolved or external imports are labeled.
- [x] CLI-level integration tests use a small Python project and verify both briefing findings and graph edges.

## Resolution

Added static Python package, manifest, script, dependency, and import analysis. Eight focused CLI graph and Python tests pass.
