# Repository Guidelines

This repository is currently a blank starting point. Add project-specific details here as the first implementation and tooling are introduced.

## Project Structure & Module Organization

There is no source tree, test suite, or asset directory yet. Keep new code in a clearly named top-level directory such as `src/`, place related tests in `tests/`, and store non-code assets in `assets/` if the project needs them. Group files by feature or responsibility, and document any different layout in this guide.

## Build, Test, and Development Commands

No build system, package manager, or run command is configured. When adding one, provide a single documented command for each common task and record it here, for example `make build`, `make test`, and `make run`. Commit the configuration those commands depend on so another contributor can run them from a fresh checkout.

## Coding Style & Naming Conventions

No language or formatter has been chosen. Follow the conventions of the language and framework introduced by the project, use consistent indentation within each file, and choose descriptive names. Add formatter and linter configuration alongside the first substantial code change; document the commands here. Prefer names that reveal a file's purpose over generic names such as `utils` or `misc`.

## Testing Guidelines

No testing framework or coverage threshold exists yet. Add tests with new behavior and bug fixes, using the naming convention supported by the chosen framework. Keep tests close to the behavior they verify, either beside source files or under `tests/`. Once a test runner is configured, list its command in the section above.

## Commit & Pull Request Guidelines

There is no Git history from which to infer a commit convention. Use short, imperative commit subjects that describe the change, such as `Add command parser`. Pull requests should explain the purpose, summarize key changes, list verification performed, and link a related issue when one exists. Include screenshots for visible interface changes.

## Agent skills

### Issue tracker

Local Markdown files are the active issue tracker; GitHub publication is deferred. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single root glossary and root ADR directory. See `docs/agents/domain.md`.
