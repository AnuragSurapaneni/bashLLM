# 04: Generate a basic preflight briefing

**What to build:** Let a developer run static inspection before an LLM session and get an evidence-backed Markdown map of an unfamiliar repository.

**Blocked by:** 01: Run bounded Bash commands.

**Status:** resolved

- [x] Inspection reports directories, source files, likely entry points, tests, and available build or test commands with supporting file locations.
- [x] An unfamiliar language still produces a useful basic file map.
- [x] Inspection neither executes project code nor installs dependencies or calls an LLM.
- [x] Scan limits are configurable, and the briefing reports skipped files or other omissions.
- [x] Generated state is excluded from version control; CLI-level tests verify the briefing and absence of project-code execution.

## Resolution

Implemented static, bounded briefing generation. Four installed-CLI tests pass, including output-path symlink protection and large-repository omissions.
