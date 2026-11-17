# 07: Understand JavaScript and TypeScript projects

**What to build:** Make a JavaScript or TypeScript repository's packages, entry points, and dependencies visible in the briefing and graph.

**Blocked by:** 05: Graph structure and dependencies.

**Status:** resolved

- [x] Common package manifests, scripts, and likely JavaScript and TypeScript entry points are recognized with source evidence.
- [x] Declared package dependencies are distinguished from imported modules inferred from source code.
- [x] Internal imports resolve where possible; external and unresolved references are labeled.
- [x] CLI-level integration tests verify findings and graph edges in representative JavaScript and TypeScript projects.

## Resolution

Added package, script, entry point, and import analysis, including modern module extensions. Three focused installed-CLI tests pass.
