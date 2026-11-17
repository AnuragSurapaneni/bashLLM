# 05: Graph structure and dependencies

**What to build:** Show a compact architecture graph in the briefing and provide a detailed graph that a developer can render separately.

**Blocked by:** 04: Generate a basic preflight briefing.

**Status:** ready-for-agent

- [ ] The briefing embeds a bounded Mermaid graph of directory, file, and known source-unit structure and dependencies.
- [ ] A Graphviz DOT artifact contains every relationship found within the configured scan limits without requiring Graphviz to be installed.
- [ ] External, unresolved, and uncertain relationships are visibly distinguished from resolved internal ones.
- [ ] Dependency cycles and unresolved references appear in concise findings; large graphs are summarized in the briefing.
- [ ] CLI-level integration tests verify graph syntax, representative edges, omissions, and cycle findings.
