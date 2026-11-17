# 03: Explore repository files

**What to build:** Give a coding agent focused file discovery, text search, and file reading commands that return bounded results without hand-written shell pipelines.

**Blocked by:** 01: Run bounded Bash commands.

**Status:** ready-for-agent

- [ ] Find lists matching repository files, search returns matching text with file locations, and read returns requested file content.
- [ ] Each operation limits its output and reports when results were truncated.
- [ ] Each operation supports human-readable and valid JSON output.
- [ ] CLI-level integration tests cover matches, no matches, excluded generated content, and result limits.
