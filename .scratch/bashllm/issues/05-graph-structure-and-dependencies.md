# 05: Graph structure and dependencies

**What to build:** Show a compact architecture graph in the briefing and provide a detailed graph that a developer can render separately.

**Blocked by:** 04: Generate a basic preflight briefing.

**Status:** resolved

- [x] The briefing embeds a bounded Mermaid graph of directory, file, and known source-unit structure and dependencies.
- [x] A Graphviz DOT artifact contains every relationship found within the configured scan limits without requiring Graphviz to be installed.
- [x] External, unresolved, and uncertain relationships are visibly distinguished from resolved internal ones.
- [x] Dependency cycles and unresolved references appear in concise findings; large graphs are summarized in the briefing.
- [x] CLI-level integration tests verify graph syntax, representative edges, omissions, and cycle findings.

## Resolution

Implemented bounded Mermaid and DOT graph output, dependency status labels, and iterative cycle findings. Five graph integration tests pass, including a 1050-file cycle.
