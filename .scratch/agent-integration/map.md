# Agent integration effort

Status: ready-for-agent

Blocked by: None.

- [Specification](spec.md): harness-neutral agent integration and contained command execution.

## Tickets

| Ticket | Blocked by |
| --- | --- |
| [01: Agent uses repository context](issues/01-agent-uses-repository-context.md) | Resolved |
| [02: Refuse uncontained command execution](issues/02-refuse-uncontained-run.md) | Resolved |
| [03: Prove native macOS containment](issues/03-prove-native-macos-containment.md) | Signing identity and packaging proof |
| [04: Record every agent run attempt](issues/04-record-agent-run-attempts.md) | 02 |
| [05: Run contained commands on Linux](issues/05-run-contained-commands-on-linux.md) | 02 |
| [06: Run contained native commands on macOS](issues/06-run-contained-native-commands-on-macos.md) | 02, 03 |
| [07: Demonstrate Codex CLI tool choice](issues/07-demonstrate-codex-cli-tool-choice.md) | 01, 04, 06 |
| [08: Demonstrate Claude Code tool choice](issues/08-demonstrate-claude-code-tool-choice.md) | 01, 04, 06 |

The current agent frontier is 04 and 05. Ticket 03 awaits a macOS signing identity, and 06 through 08 remain blocked. Tickets 07 and 08 do not require Linux ticket 05 because the local demonstrations run on macOS. The full milestone requires every ticket.
