# Compact command failure and Python environment diagnostics

Status: resolved

Blocked by: None.

## Problem Statement

After a command fails, a coding agent often has to read a large stdout or stderr payload, guess which lines matter, and run several exploratory Bash commands to discover the active Python interpreter, missing dependencies, or relevant environment settings. Those retries consume context and approval time without necessarily moving the task forward. The existing MCP adapter returns bounded raw command results and repository inspection, but it does not summarize failures or verify the Python environment in which an approved command ran.

## Solution

When an approved `bashllm_run` attempt fails, return a compact, evidence-backed diagnostic derived from its captured result without executing another process. Give the agent a separately approved `bashllm_diagnose` tool that accepts the run's history ID and performs one bounded check of the sanitized execution environment, selected Python interpreter, virtual environment, and declared package availability inside the same containment boundary. Keep the original result available, distinguish recorded evidence from current checks, state uncertainty and omissions, and suggest at most three concrete next actions. Measure whether the workflow reduces tool calls and output tokens across representative failures.

## User Stories

1. As a coding agent, I want a concise failure summary in the first run result, so that I can identify the important error without reading all captured output.
2. As a coding agent, I want the summary to use only the captured run result, so that it does not silently execute another command.
3. As a coding agent, I want the decisive stdout or stderr excerpt, so that I can see the evidence behind a diagnosis.
4. As a coding agent, I want the exit code, timeout, and truncation state in the summary, so that I can judge how complete the evidence is.
5. As a coding agent, I want recognized Python tracebacks summarized, so that I can locate the failing frame and exception quickly.
6. As a coding agent, I want missing module and import errors identified, so that I can investigate the relevant interpreter and dependency.
7. As a coding agent, I want syntax errors identified with their reported file and line, so that I can inspect the right source.
8. As a coding agent, I want dependency version conflicts identified when the output supports them, so that I can compare installed and required versions.
9. As a coding agent, I want missing executable errors identified, so that I can check the tool path rather than retry the same command.
10. As a coding agent, I want timeout and output truncation called out explicitly, so that I do not assume the visible excerpt is the whole failure.
11. As a coding agent, I want diagnoses based on weak signals labeled as possibilities, so that I do not treat a nonzero exit code alone as a known cause.
12. As a coding agent, I want a prior run ID in the result, so that I can request a deeper check without copying the command or error text.
13. As a coding agent, I want to diagnose a run by its history ID, so that the check uses the recorded command and working directory.
14. As a human reviewer, I want each process-launching diagnostic to require its own approval, so that approval of the original command does not authorize later checks.
15. As a coding agent, I want the deeper check to report the sanitized run environment, so that I can reason about variables the command could actually see.
16. As a repository owner, I want environment values restricted to an allowlist and credential-like data redacted, so that diagnostic output does not reveal secrets.
17. As a coding agent, I want the interpreter explicitly named in the failed command selected for checks, so that the report matches the failed process.
18. As a coding agent, I want available interpreters reported when the command does not identify one, so that I can choose deliberately rather than trust a guess.
19. As a coding agent, I want the interpreter path and version, so that I can detect an unexpected Python installation.
20. As a coding agent, I want virtual environment status and relevant `sys.path` entries, so that I can understand where Python searches for packages.
21. As a coding agent, I want declared core dependencies compared with installed package metadata, so that I can spot missing or incompatible distributions without importing package code.
22. As a coding agent, I want optional dependency groups identified but checked only when relevant or selected, so that expected omissions are not reported as failures.
23. As a coding agent, I want an explicit unverifiable result when a package or interpreter is inaccessible in containment, so that I do not mistake absence of evidence for a missing dependency.
24. As a coding agent, I want the recorded failure time separated from the current check time, so that changed repository or environment state does not masquerade as the earlier cause.
25. As a coding agent, I want up to three evidence-based next checks or fixes by default, so that I can act without reading a long troubleshooting guide.
26. As a coding agent, I want an explicit way to request more diagnostic detail, so that the default result can remain small.
27. As a human reviewer, I want installation, environment changes, and retries to remain separate approved actions, so that diagnosis does not make changes on its own.
28. As a coding agent, I want prior raw output to remain accessible, so that I can inspect context when the compact summary is insufficient.
29. As a maintainer, I want to compare tool calls and output tokens against the existing workflow, so that the feature's token-efficiency claim is testable.
30. As a coding agent, I want the default MCP failure response to avoid duplicating raw output in text and structured content, so that a useful summary actually saves context.

## Implementation Decisions

- Extend the agent-facing CLI contract and shared MCP adapter with a diagnostic operation. Keep the installed CLI as the MCP backend and the repository fixed by server configuration. The diagnostic tool accepts a history attempt ID and an optional detail budget or mode; it does not accept arbitrary shell text, repository overrides, tool-path grants, or a history opt-out.
- Add a stable attempt ID to the run result when history records an attempt. A diagnostic request retrieves the exact recorded attempt, including command, working directory, result status, output, flags, and timestamp. Invalid or missing IDs return bounded structured errors. An attempt that never executed is identified as such.
- Add a compact diagnostic object to failed run results. Build it only from captured output, exit code, timeout, and truncation flags. Do not launch a follow-up process as part of `run`. Preserve the existing raw result fields and exact-repeat behavior. A blocked repeat can refer to its previous recorded failure without claiming a fresh execution.
- Recognize Python traceback, `ModuleNotFoundError`, `ImportError`, syntax error, version conflict, and missing executable patterns. Use a conservative category and confidence/uncertainty field; do not infer a cause from a nonzero exit code alone. Include a bounded evidence excerpt and at most three next steps by default. State when recognized error text is absent or output is truncated.
- The deeper diagnostic uses the same fail-closed containment backend and minimal environment as agent runs. Any check that launches a process follows the existing per-call host approval requirement. Advertise the diagnostic MCP tool as requiring user interaction and document the host's responsibility to prompt for each call. If containment is unavailable, report that state without an unrestricted fallback.
- Report only allowlisted settings from the sanitized execution environment. Redact credential-like values in all generated diagnostic excerpts, including excerpts taken from command output. Keep bounds on field lengths, list lengths, and total diagnostic output. Raw captured run output remains available under the existing contract.
- For Python commands, select an interpreter explicitly identified in the recorded command where the selection is unambiguous; otherwise report discoverable candidates without asserting which one the project uses. Respect repository-relative virtual environments and the sandbox's configured external tool grants. Report the selected interpreter path, version, virtual environment status, and bounded `sys.path` evidence.
- Use static project declarations already recognized by inspection to identify core and optional Python dependencies. Check installed distribution metadata for the selected interpreter without importing every dependency or running project code. Check optional groups only when the failed command clearly selects them or the diagnostic caller names a group. Report unsupported declarations and inaccessible packages as unverified.
- A diagnostic result separates historical run evidence from current environment and dependency observations, including timestamps. It does not claim that current observations caused an earlier failure when state may have changed.
- Suggested next steps are advisory. The diagnostic operation never installs packages, mutates the repository or environment, automatically retries a command, or invokes a dependency's import code as a broad health check.
- Keep human-readable and structured JSON results aligned. The model-visible MCP failure response defaults to compact diagnostic fields rather than echoing the full raw output twice; preserve bounded raw output through an explicit detail request or the recorded result. Update agent guidance and MCP host setup guidance so agents can discover the new tool and hosts require approval for it.

## Testing Decisions

- Use the existing highest process seam: install the package, invoke the CLI and MCP stdio server as processes against temporary repositories, and assert observable JSON, tool discovery, approval metadata, history, output bounds, and filesystem effects. Avoid tests of private parser helpers or exact prose.
- Extend the existing installed CLI and MCP process tests rather than adding a lower-level diagnostic seam. Assert that a failed run returns an attempt ID and compact summary without launching extra checks, while a diagnostic call uses the recorded ID and receives its own execution approval metadata.
- Cover wrong interpreter, missing distribution, version conflict, Python syntax error, missing executable, timeout, and truncated output. Include ordinary nonzero exits that do not justify a confident error category.
- Cover interpreter selection when explicit, ambiguity when absent, virtual environment reporting, sanitized environment values, optional dependency groups, metadata-only package checks, unverified states, and changed state between failure and diagnosis.
- Cover invalid IDs, blocked repeats, backend refusal, bounded detail requests, redaction of credential-like values in generated excerpts, and absence of automatic installation or retry. Reuse the repository's containment tests where platform behavior is material.
- Compare representative agent workflows with and without diagnostics using tool-call counts and returned output tokens. Keep the scenarios and measurement method reproducible; treat lower counts as a validation target, not a guarantee for every failure.

## Out of Scope

- Automatic package installation, environment repair, command retry, or arbitrary troubleshooting command generation.
- Reading inherited host environment variables or secrets outside the sanitized execution environment.
- Importing every declared package, executing project code for inspection, or building a complete dependency solver.
- Broad language-specific environment probes beyond the agreed Python checks; generic error extraction may still recognize non-Python command failures.
- Network access, new containment privileges, a generic shell passthrough, or bypassing host approval.
- Persistent interactive sessions or an LLM-powered diagnosis engine.

## Further Notes

- The current adapter exposes find, search, read, inspect, context, history, and run. It sends full JSON in both text and structured MCP content, so response duplication is part of the token-cost problem this feature must address.
- Current Python inspection reads project manifests, requirements files, and imports, but does not probe interpreter or installed distributions. Current agent execution clears inherited variables and supplies a minimal environment.
- No root glossary or relevant ADR was present when this spec was written. The agreed test seam is the installed CLI and MCP process boundary, following existing integration tests.
- The local Markdown issue tracker is the source of truth. The spec and its seven tickets are resolved after implementation and verification.
