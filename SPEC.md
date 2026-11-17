# bashllm: Repository Operations and Preflight Context

## Problem Statement

Coding agents repeat shell commands, spend tokens rediscovering repository structure, and begin work without a reliable map of code and dependencies. A new agent session needs a concise handoff grounded in the current checkout. This is especially difficult in unfamiliar or mixed-language repositories, including Fortran projects.

## Solution

Provide an installable `bashllm` CLI for macOS and Linux. It runs bounded Bash commands, records attempts, flags exact repeats, and offers focused code exploration. Before an LLM session, `bashllm inspect` statically analyzes a repository and writes `.bashllm/BRIEFING.md` plus a detailed Graphviz graph. `bashllm context` prints a compact, freshness-checked handoff that includes recent command history. The briefing embeds a small Mermaid structure and dependency graph. Inspection runs no project code and makes no LLM calls.

## User Stories

1. As a coding agent, I want to run Bash in a specified repository and working directory, so that commands execute in the intended context.
2. As a coding agent, I want command output and duration bounded by default, so that a command cannot consume the entire session.
3. As a coding agent, I want to adjust those limits explicitly, so that legitimate long tasks remain possible.
4. As a coding agent, I want concise human-readable output, so that routine results are easy to scan.
5. As a coding agent, I want JSON output for every command, so that I can parse results reliably.
6. As a coding agent, I want an exact-repeat warning before a command runs again, so that I avoid redundant attempts.
7. As a coding agent, I want the previous exit code and output summary on a blocked repeat, so that I can use the existing result.
8. As a coding agent, I want an explicit retry option, so that I can rerun a command after relevant changes.
9. As a coding agent, I want to see recent command attempts, so that I understand what has already been tried.
10. As a coding agent, I want an option to exclude a command from history, so that sensitive command text is not stored by this tool.
11. As a coding agent, I want bounded find, search, and read operations, so that common code exploration takes fewer shell pipelines.
12. As a developer, I want a preflight command that works before an LLM session, so that the agent starts with repository context.
13. As a developer, I want preflight to avoid executing project scripts or installing packages, so that inspection has predictable effects.
14. As a coding agent, I want a map of directories, source units, likely entry points, tests, and build commands, so that I can navigate the checkout quickly.
15. As a coding agent, I want declared and inferred dependencies distinguished, so that I can judge each finding's reliability.
16. As a coding agent, I want each important finding tied to source evidence, so that I can verify it.
17. As a coding agent, I want Python, JavaScript/TypeScript, Rust, Go, and Fortran projects recognized, so that the briefing covers common codebases.
18. As a coding agent, I want a basic file map for other languages, so that unsupported codebases still yield useful context.
19. As a Fortran developer, I want fixed and free form source, continuation lines, case-insensitive names, modules, and submodules recognized, so that legacy and modern projects are represented.
20. As a Fortran developer, I want common Fortran build files recognized, so that build targets and dependencies appear in the briefing.
21. As a coding agent, I want a compact Mermaid graph in the briefing, so that I can see code structure at a glance.
22. As a developer, I want a detailed Graphviz graph, so that I can render or inspect all relationships found within scan limits.
23. As a coding agent, I want unresolved and uncertain edges labeled, so that the graph does not present guesses as facts.
24. As a coding agent, I want dependency cycles highlighted, so that I can spot architectural constraints early.
25. As a coding agent, I want scan omissions reported, so that I know when the briefing is incomplete.
26. As a coding agent, I want a roughly 1,500-token default handoff with an adjustable limit, so that context usage stays controlled.
27. As a coding agent, I want a stale-briefing warning, so that I do not rely on an outdated map.

## Implementation Decisions

- Use Python 3.11 or later and the standard library for the first release; expose an installable `bashllm` command.
- Require an explicit repository root for every operation and an explicit working directory for Bash execution. Each run starts a fresh Bash process. The tool uses the caller's permissions and provides no sandbox.
- Default to a 60-second command timeout and capture at most 32 KiB from each output stream; allow callers to adjust both limits.
- Identify duplicates by exact command text and working directory within the repository. Block repeats unless the caller explicitly retries; return the prior result with a distinct not-executed status.
- Store local command history in SQLite with user-only file permissions. Support recent-history queries and a no-history execution option.
- Provide bounded `find`, `search`, and `read` operations with human-readable and JSON forms.
- Make inspection deterministic and static. Recognize common manifests and entry points for Python, JavaScript/TypeScript, Rust, Go, and Fortran, and provide a generic map for other languages.
- For Fortran, recognize legacy and modern source extensions, uppercase preprocessed variants, fixed and free form, continuation lines, `USE` and include relationships, programs, modules, and submodules. Inspect common package and build files.
- Model directories, files, modules, submodules, programs, and build targets with containment and dependency edges. Label intrinsic, external, unresolved, and uncertain relationships where applicable. Summarize cycles and unresolved references.
- Embed a bounded Mermaid graph in the Markdown briefing and generate a complete Graphviz DOT graph for all relationships found within configured scan limits. Report skipped files and other limits.
- Keep generated history and briefing state outside version control. The context command prints a compact briefing and recent-command summary, warns when inspected files or the eligible file set have changed, and accepts a larger output budget.

## Testing Decisions

- Use one primary test seam: invoke the installed CLI as a process against temporary repositories and assert its output, exit status, and generated artifacts. This tests observable behavior without coupling tests to parser or storage internals.
- Cover command execution, exact duplicates, explicit retries, previous-result reporting, no-history mode, timeouts, output limits, JSON, and private history storage.
- Cover preflight without project-code execution; evidence-backed findings, supported-language manifests, Fortran syntax and dependency cases, uncertain edges, cycles, scan limits, and both graph formats.
- Cover compact context output and stale-briefing detection after file edits, additions, and removals.
- The repository has no existing test suite or similar test seam to reuse.

## Out of Scope

- Windows support, a persistent interactive shell, command sandboxing, automatic retry after repository changes, and LLM-powered analysis.
- A complete compiler-grade parser or procedure-level call graph for any language.
- Rendering the DOT graph or installing Graphviz as a required dependency.

## Further Notes

The Markdown briefing is generated by an executable preflight command; the Markdown itself is not executable. Local Markdown is the configured issue tracker, with GitHub publication deferred until access is available.
