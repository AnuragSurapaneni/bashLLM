# 04: Generate a basic preflight briefing

**What to build:** Let a developer run static inspection before an LLM session and get an evidence-backed Markdown map of an unfamiliar repository.

**Blocked by:** 01: Run bounded Bash commands.

**Status:** ready-for-agent

- [ ] Inspection reports directories, source files, likely entry points, tests, and available build or test commands with supporting file locations.
- [ ] An unfamiliar language still produces a useful basic file map.
- [ ] Inspection neither executes project code nor installs dependencies or calls an LLM.
- [ ] Scan limits are configurable, and the briefing reports skipped files or other omissions.
- [ ] Generated state is excluded from version control; CLI-level tests verify the briefing and absence of project-code execution.
