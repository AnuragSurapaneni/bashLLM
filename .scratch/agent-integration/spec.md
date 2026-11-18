# Harness-neutral agent integration and contained command execution

Status: ready-for-agent

Blocked by: None.

## Problem Statement

A coding agent can use `bashllm` today only if its harness happens to know the CLI and when each command is useful. The CLI already returns JSON for repository exploration, preflight inspection, context handoff, history, and bounded Bash execution, but it has no versioned agent-facing contract or demonstrated use across agent harnesses. More seriously, `run` currently starts Bash with the caller's permissions. A human approving an agent's command cannot rely on `bashllm` to confine that command, especially when an unfamiliar repository's scripts or dependencies may actively seek files outside the checkout.

## Solution

Give coding agents one versioned description of the CLI and JSON interface and a shared MCP adapter with typed tools, so Codex CLI and Claude Code can invoke `bashllm` without exposing a generic shell tool. Keep the agent responsible for choosing whether to use it and the harness responsible for obtaining human confirmation of the exact command and working directory before every execution, including retries. On Linux, `run` uses the verified Bubblewrap boundary. On macOS, use an unsigned `sandbox-exec` profile for a narrower, best-effort boundary that permits native commands, repository writes, and private temporary files while denying home-directory and standard temporary-directory reads, non-repository writes, and network operations. Other host reads and IPC remain possible. Both paths fail closed if their backend cannot start or pass its probe. macOS does not claim robust isolation against hostile code. Preserve repo inspection and reading when an execution backend is unavailable. Demonstrate voluntary tool selection in Codex CLI and Claude Code.

## User Stories

1. As a coding agent, I want to discover what `bashllm` can do from a versioned description, so that I can decide when it helps my task.
2. As a coding agent, I want command arguments and JSON results described consistently, so that I can call the CLI without guessing at its contract.
3. As a harness integrator, I want one portable command description and shared MCP adapter, so that I can expose the same capabilities in different agent harnesses.
4. As a developer, I want the installed CLI to remain the execution backend, so that agent tool calls follow the same repository behavior and limits.
5. As a coding agent, I want to choose whether to call `bashllm` for each task, so that unrelated work does not incur unnecessary calls.
6. As a coding agent, I want guidance on when to request a preflight briefing, so that I can orient myself in an unfamiliar repository.
7. As a coding agent, I want to know when a context handoff is missing or stale, so that I can refresh inspection before relying on it.
8. As a coding agent, I want to use bounded find, search, and read operations when locating code, so that I can retrieve focused evidence.
9. As a coding agent, I want to inspect recent command attempts, so that I can avoid repeating work already done.
10. As a coding agent, I want exact-repeat blocking to remain visible in JSON, so that I can distinguish a reused result from a fresh execution.
11. As a coding agent, I want to request a retry explicitly, so that I can rerun a command when circumstances justify it.
12. As a human reviewer, I want the agent to show the exact command, repository, and working directory before execution, so that I know what I am approving.
13. As a human reviewer, I want a separate approval for each retry, so that an earlier approval cannot authorize later side effects.
14. As a coding agent, I want a confirmed command to run in the requested working directory, so that its effects land in the intended checkout.
15. As a developer, I want a command's changes inside the repository to persist, so that approved formatters and generators remain useful.
16. As a developer, I want commands to have a private temporary directory, so that ordinary builds and tests can create temporary files.
17. As a developer, I want ordinary finite builds, tests, and formatters to work in containment, so that the tool remains useful for common agent work.
18. As a developer, I want native macOS toolchains to run on macOS, so that containment does not silently change the execution platform.
19. As a developer, I want Linux commands to run with a verified Bubblewrap backend, so that filesystem and network access can be constrained.
20. As a developer, I want an unavailable containment backend reported clearly, so that I do not mistake an unconfined run for a contained one.
21. As a developer, I want find, search, read, inspect, context, and history to remain usable without an execution backend, so that a platform limitation does not block repository understanding.
22. As a repository owner, I want Linux scripts and dependencies barred from unrelated private files, so that unfamiliar code cannot read my home-directory credentials through `run`.
23. As a repository owner, I want Linux `run` without network access and macOS `run` with a tested network-denying profile, so that command execution follows each platform's stated boundary.
24. As a repository owner, I want inherited credentials and tokens excluded from the command environment, so that subprocesses do not receive them implicitly.
25. As a repository owner, I want tools installed under my home directory inaccessible until I explicitly grant their paths, so that installing a tool does not expose all home files.
26. As a repository owner, I want to understand that files inside the repository, including ignored files, remain visible to contained commands, so that I can manage repo-local secrets accordingly.
27. As a repository owner, I want Linux child processes and symlinks to obey the same boundary and macOS limitations stated clearly, so that I can judge what a command may reach.
28. As a human reviewer, I want every agent-initiated run attempt recorded in private repository history, so that I can inspect executions and refusals afterward.
29. As a human reviewer, I want agents unable to disable that history, so that the agent-facing execution path remains auditable.
30. As a coding agent, I want structured failure results for backend errors and denied execution, so that I can report the reason instead of silently retrying elsewhere.
31. As a developer, I want to install the Python package without installing an execution backend, so that read capabilities remain easy to adopt.
32. As a developer, I want backend prerequisites and explicit tool-path grants documented, so that I can set up contained execution deliberately.
33. As a maintainer, I want security checks on both supported platforms, so that containment is verified against hostile scripts rather than assumed from configuration.
34. As a maintainer, I want a Codex CLI demonstration where the agent chooses `bashllm` for repository understanding and an approved command, so that the integration is demonstrated in a real harness.
35. As a maintainer, I want the same demonstration in Claude Code, so that the interface is shown to work across harnesses.
36. As a maintainer, I want each demonstration to include an unrelated task where the agent skips `bashllm`, so that “as needed” means actual tool choice.

## Implementation Decisions

- The installed CLI and its JSON output remain the backend contract. Publish one versioned, machine-readable description of command arguments, result shapes, failure states, and usage guidance. Add one shared MCP stdio adapter that exposes typed operations for both demonstration harnesses. The adapter does not offer a raw CLI or shell argument passthrough; agent execution uses `run --agent`.
- The agent-facing guidance gives conditions for using repository inspection, context handoff, exploration, history, and execution. It does not require a `bashllm` call on every task. Inspection remains static; `context` still depends on a prior inspection and reports staleness.
- The calling agent or harness obtains human confirmation for the exact Bash command, repository, and working directory before each execution, including retries. `bashllm` enforces containment but does not verify that human approval occurred. The containment guarantee applies to commands launched through `bashllm run`; other agent tools remain the harness's responsibility.
- Preserve the existing single Bash command string, fresh process, bounded timeout and output, JSON result, and exact-repeat behavior unless a security requirement requires a clearly documented change. Persistent or interactive programs are outside the first milestone.
- `run` must fail closed when a verified backend is absent or cannot establish the required boundary. It must not fall back to the caller's unrestricted permissions. Read and inspection commands continue to work in this state.
- Linux execution requires Bubblewrap and usable user namespaces. Runtime capability checks determine availability; installation alone is insufficient.
- macOS execution runs native macOS commands through an unsigned `sandbox-exec` profile. This tool and its profile language are deprecated, so the macOS boundary is explicitly best-effort and makes no malicious-code isolation guarantee. Probe the profile's expected denials and fail closed if the utility or probe is unavailable. No code-signing identity or Linux guest is required.
- A contained command can read and write the repository and use a disposable private temporary directory. Its changes inside the repository persist. Files within the repository, including ignored files, are within the accessible data boundary. Symlink and subprocess behavior must not expose unrelated host paths.
- Provide only the minimum read-only host runtime paths needed for system programs and libraries. A tool under the user's home directory requires an explicit path grant; the grant must not imply access to the rest of the home directory.
- Start commands with a minimal environment that omits inherited credentials and tokens. Disable network access with no override in this milestone.
- Every agent-initiated run request, including a refusal or blocked repeat, must leave a local history record with an outcome. The agent-facing execution path must not offer a history opt-out. The existing human-facing no-history behavior is a compatibility issue to resolve without weakening the agent path.
- Keep installation of the Python package possible without a sandbox backend. Execution prerequisites are installed and verified separately; unsupported or unconfigured systems receive a structured error.
- The two demonstration harnesses are Codex CLI and Claude Code. Their demonstration configurations expose the shared MCP tools and no unrestricted generic shell execution; approved command execution flows through `bashllm run --agent`. Both harnesses use the same CLI backend contract.
- This feature extends the original product scope, whose first-release spec explicitly excluded sandboxing. Update the main product documentation and any conflicting claims when implementation lands.

## Testing Decisions

- Use the highest existing seam: install the package and invoke the CLI as a subprocess against temporary repositories, then assert exit status, JSON output, history, and observable filesystem and network effects. Avoid tests tied to internal parser or backend functions.
- Reuse the repository's CLI integration-test pattern for run limits, duplicate handling, retries, history, inspection, context staleness, and exploration. Extend those behavioral tests for the agent-facing description, structured errors, mandatory agent history, and backend availability.
- Run native containment tests on macOS and Linux, rather than relying only on mocks. Probe reading and writing outside the repository, home-directory secrets, symlink escapes, child processes, inherited environment variables, and network access. Verify allowed repository writes, private temporary files, native tool execution, output limits, and timeouts. On macOS, these tests establish observed behavior of the deprecated profile on tested releases; they do not turn it into a supported adversarial security boundary.
- Test backend failure and missing prerequisites as observable CLI behavior: `run` refuses execution and records the outcome while read and inspection commands continue to work. Do not describe a backend as supported until its adversarial tests pass on that platform.
- Validate agent choice end to end in Codex CLI and Claude Code using the same published command description. In each harness, give the agent a repository-understanding task, a task needing a confirmed command, and an unrelated task. Observe voluntary use or non-use, the approval prompt, and the resulting history. Keep generic shell execution unavailable during these demonstrations.
- Test the shared MCP server as a subprocess through initialization, tool listing, tool calls, malformed inputs, and clean shutdown. Verify that read tools reach the installed CLI and that agent execution cannot disable history or grant arbitrary host paths.
- Good tests assert behavior at the user boundary, including what files were touched and what the agent selected. They do not assert the exact internal sandbox command line, parser layout, or incidental wording in generated guidance.

## Out of Scope

- Protocol adapters other than the shared MCP stdio server, harness-specific feature behavior, and an LLM inside `bashllm`.
- Network-enabled command execution or a network override.
- Windows execution support.
- Persistent shells, interactive programs, long-running servers, and daemon management.
- Hiding ignored files or other secrets located inside the repository.
- A robust macOS malicious-code sandbox, code signing, and a durable guarantee that deprecated `sandbox-exec` remains available on future macOS versions.
- Containing unrelated tools exposed by an agent harness or verifying the harness's human-approval event inside `bashllm`.
- Replacing the existing repository analyzers or expanding language coverage.

## Further Notes

- The user revised the macOS scope to avoid signing and approved `sandbox-exec` despite its deprecation. The macOS path must be labelled best-effort; if its required checks fail on a host, `run` remains unavailable there.
- The user later approved a shared MCP adapter because the installed Codex CLI and Claude Code cannot expose a plain CLI command to the agent while removing their generic shell tool.
- Backend research starting points: [Bubblewrap](https://github.com/containers/bubblewrap), Apple's [App Sandbox](https://developer.apple.com/documentation/security/app-sandbox) and [sandboxed helper guidance](https://developer.apple.com/documentation/Xcode/embedding-a-helper-tool-in-a-sandboxed-app), and the [`sandbox-exec` deprecation notice](https://keith.github.io/xcode-man-pages/sandbox-exec.1.html).
- The original first-release spec and README describe `run` as unsandboxed. That description is accurate for the current implementation and must change only when contained execution is shipped.
- Local Markdown is the active issue tracker. This spec's `ready-for-agent` status marks it ready for implementation planning; it does not claim that either platform backend has already passed verification.

## Comments

- Synthesized from the confirmed agent-integration design discussion.
