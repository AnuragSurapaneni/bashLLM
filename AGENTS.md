# Repository Guidelines

This repository contains the `bashllm` CLI and static repository analyzers. `SPEC.md` records the product scope, and local Markdown tickets record implementation status.

## Project Structure & Module Organization

The installable Python package lives in `src/bashllm/`, with CLI commands under `commands/` and language analyzers under `analyzers/`; CLI-level integration tests live in `tests/`. `SPEC.md` records scope, `docs/agents/` holds agent workflow rules, and `.scratch/bashllm/issues/` holds local tickets. Generated build files and local runtime state are ignored by Git.

## Build, Test, and Development Commands

Use `python3 -m venv .venv` and `.venv/bin/python -m pip install .` to install locally. Run `.venv/bin/bashllm run --repo . --cwd . -- 'pwd'` for a smoke check and `.venv/bin/bashllm inspect --repo .` for a preflight briefing. Run `python3 -m unittest discover -s tests -v` for the integration suite.

## Coding Style & Naming Conventions

Use four spaces for Python indentation, `snake_case` for functions and variables, and `PascalCase` for classes. Keep runtime code compatible with Python 3.11 and its standard library. No formatter or linter is configured yet; keep changes consistent with adjacent code.

## Testing Guidelines

Tests use `unittest` and the `test_*.py` naming pattern. Test the installed CLI through subprocesses against temporary repositories. Add a behavioral test for each new command or bug fix. There is no coverage threshold.

## Commit & Pull Request Guidelines

Git history is sparse and mostly contains setup and merge commits. Use short, imperative commit subjects that describe the change, such as `Add command history`. Pull requests should explain the purpose, summarize key changes, list verification performed, and link a related issue when one exists. Include screenshots for visible interface changes.

## Agent skills

### Issue tracker

Local Markdown files are the active issue tracker; GitHub publication is deferred. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single root glossary and root ADR directory. See `docs/agents/domain.md`.
