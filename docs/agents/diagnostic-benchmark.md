# Diagnostic workflow comparison

Run `python3 scripts/benchmark_diagnostics.py` from the repository root on a host where the containment backend is available. The script installs the package into a temporary virtual environment, starts its MCP server as a process, creates a temporary Python project, and runs seven fixed failures. It prints CSV with tool-call counts and estimated returned tokens for two workflows.

The baseline models the previous MCP adapter: the full run JSON appears in both text and structured content. For Python environment questions, the baseline then makes separate interpreter and package-metadata shell calls. The diagnostic workflow measures the actual compact MCP run response and one diagnostic MCP response. Both workflows execute the same initial failure in separate attempts. The package lookup deliberately fails when its distribution is absent; that unsuccessful exploratory call is part of the baseline being measured. Token estimates are `ceil(UTF-8 response bytes / 4)` for model-visible MCP content, not counts from a model tokenizer. The old adapter's response shape is reconstructed from an installed CLI result; the script does not run an old binary.

Observed on the macOS development host on 2026-11-19:

| Scenario | Baseline calls | Diagnostic calls | Baseline estimated tokens | Diagnostic estimated tokens |
| --- | ---: | ---: | ---: | ---: |
| Wrong interpreter | 3 | 2 | 1,576 | 966 |
| Missing distribution | 3 | 2 | 1,571 | 1,013 |
| Version conflict | 3 | 2 | 1,590 | 956 |
| Syntax error | 1 | 1 | 414 | 221 |
| Missing executable | 1 | 1 | 209 | 181 |
| Timeout | 1 | 1 | 180 | 175 |
| Truncated output | 1 | 1 | 16,725 | 354 |

The fixed Python workflow saves one exploratory call. Compact responses reduce the estimated returned tokens in these scenarios, especially when raw output is truncated. Actual agent choices, output content, platform paths, and host handling of MCP text and structured content can change these numbers. This comparison measures response cost and tool calls, not task completion quality or model reasoning tokens.
