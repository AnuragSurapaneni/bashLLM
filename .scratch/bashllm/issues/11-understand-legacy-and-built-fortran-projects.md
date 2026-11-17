# 11: Understand legacy and built Fortran projects

**What to build:** Extend Fortran inspection to legacy source forms, preprocessing uncertainty, includes, and common build descriptions.

**Blocked by:** 10: Understand modern Fortran projects.

**Status:** resolved

- [x] Fixed form and uppercase preprocessed Fortran source extensions are recognized, including their continuation rules.
- [x] Include relationships and common Fortran build files contribute evidence-backed findings and graph edges.
- [x] Edges affected by conditional compilation or unresolved preprocessing are marked uncertain.
- [x] CLI-level integration tests verify fixed form, includes, preprocessing uncertainty, and representative package or build files.

## Resolution

Extended Fortran inspection to fixed form, preprocessing uncertainty, includes, and fpm/CMake/Make relationships. Nine modern and legacy Fortran CLI tests pass.
