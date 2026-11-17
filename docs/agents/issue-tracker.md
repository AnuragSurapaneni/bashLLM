# Issue tracker: Local Markdown

Specs and issues live under `.scratch/<feature-slug>/`. Local files are the source of truth until GitHub access is available.

## Conventions

- Store each spec as `spec.md` in its feature directory.
- Store each ticket in its own numbered Markdown file under `issues/`.
- Record triage state in a `Status:` line and dependencies in a `Blocked by:` line.
- Append discussion under `## Comments`.

When a skill says to publish, create the appropriate local file. When it says to fetch an issue, read that file. For wayfinding, use one `map.md` per effort and numbered child tickets; a ticket is ready when its blockers are resolved and it is unclaimed.

## GitHub

The intended repository is `AnuragSurapaneni/bashLLM`. Publish or mirror local issues there only after access is available. Record GitHub links in the local files; do not describe an issue as published until its GitHub issue exists.
