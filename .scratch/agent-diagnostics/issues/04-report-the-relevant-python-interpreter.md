# 04: Report the relevant Python interpreter

**What to build:** Show a coding agent which Python interpreter a recorded failed command explicitly used, or show available candidates when that cannot be determined, with enough environment detail to investigate mismatches.

**Blocked by:** 03: Diagnose a recorded run safely.

**Status:** resolved

- [x] An unambiguous interpreter explicitly named in the recorded command is checked inside the approved containment boundary.
- [x] When the command does not identify one unambiguously, the result reports bounded discoverable candidates without presenting a guess as the selected interpreter.
- [x] For a selected interpreter, the result includes its path, version, virtual environment status, and bounded relevant `sys.path` entries.
- [x] Repository virtual environments and configured external tool grants are respected; unavailable or inaccessible interpreters are reported as unverified.
- [x] Checks do not import project modules or run project scripts, and tests demonstrate explicit, ambiguous, virtual-environment, and unavailable cases through the process seam.
