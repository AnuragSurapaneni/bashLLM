"""Approved, contained diagnostics for a recorded command attempt."""

import argparse
import json
import re
import shlex
import shutil
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from bashllm import history
from bashllm.analyzers.python import _manifest
from bashllm.commands.run import _run_bounded
from bashllm.diagnostics import redact, summarize
from bashllm.sandbox import BackendUnavailable, agent_tool_grants, launch_command


NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$")
SIMPLE_SPEC = re.compile(r"^\s*(==|!=|>=|<=|>|<)\s*(\d+(?:\.\d+)*)\s*$")
PYTHON = re.compile(r"^python(?:\d+(?:\.\d+)?)?$", re.I)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PROBE = """import importlib.metadata as m, json, platform, sys
names = json.loads(%(names)r)
packages = {}
for name in names:
    try:
        packages[name] = m.version(name)
    except m.PackageNotFoundError:
        packages[name] = None
print(json.dumps({"executable": sys.executable, "version": platform.python_implementation() + " " + platform.python_version(), "prefix": sys.prefix, "base_prefix": sys.base_prefix, "sys_path": sys.path[:12], "packages": packages}))
"""


def register(commands: argparse._SubParsersAction) -> None:
    diagnose = commands.add_parser("diagnose", help="Check a recorded failure in containment")
    diagnose.add_argument("--repo", required=True, type=Path)
    diagnose.add_argument("--attempt-id", nargs="?", const="")
    diagnose.add_argument("--group", default="")
    diagnose.add_argument("--max-detail", type=int, default=1600)
    diagnose.add_argument("--json", action="store_true")
    diagnose.set_defaults(execute=execute)


def _eligible_manifest(path: Path, repo: Path) -> bool:
    try:
        return path.is_file() and path.resolve().is_relative_to(repo) and path.stat().st_size <= 65536
    except OSError:
        return False


def _declared(repo: Path, cwd: Path, group: str, command: str) -> tuple[list[str], list[str]]:
    requirements: list[str] = []
    groups: list[str] = []
    directories = [cwd, *[parent for parent in cwd.parents if parent.is_relative_to(repo)]]
    for directory in directories:
        project_file = directory / "pyproject.toml"
        if _eligible_manifest(project_file, repo):
            try:
                project = tomllib.loads(project_file.read_text(encoding="utf-8")).get("project", {})
                if isinstance(project, dict):
                    core = project.get("dependencies", [])
                    if isinstance(core, list):
                        requirements.extend(value for value in core if isinstance(value, str))
                    optional = project.get("optional-dependencies", {})
                    if isinstance(optional, dict):
                        groups.extend(key for key in optional if isinstance(key, str))
                        selected = group or next((name for name in groups if f"[{name}]" in command), "")
                        if selected and isinstance(optional.get(selected), list):
                            requirements.extend(value for value in optional[selected] if isinstance(value, str))
            except (OSError, UnicodeError, ValueError, tomllib.TOMLDecodeError):
                pass
        for name in ("setup.cfg", "setup.py"):
            path = directory / name
            if _eligible_manifest(path, repo):
                parsed = _manifest(repo, path.relative_to(repo), 65536)
                if parsed is not None and isinstance(parsed[1], list):
                    requirements.extend(value for value in parsed[1] if isinstance(value, str))
        for path in directory.glob("requirements*.txt"):
            if not _eligible_manifest(path, repo):
                continue
            if path.name != "requirements.txt":
                suffix = path.stem.removeprefix("requirements").lstrip("-_")
                if suffix:
                    groups.append(suffix)
                    if group != suffix and f"[{suffix}]" not in command:
                        continue
            try:
                requirements.extend(line.split("#", 1)[0].strip()
                                    for line in path.read_text(encoding="utf-8").splitlines()
                                    if line.strip() and not line.lstrip().startswith(("#", "-", ".", "/")))
            except (OSError, UnicodeError):
                pass
    groups = sorted(set(groups))[:30]
    return list(dict.fromkeys(requirements))[:40], groups


def _python_command(command: str) -> tuple[str, list[str], bool]:
    """Recognize a simple leading Python invocation without interpreting Bash."""
    if "\n" in command or "\r" in command:
        return "", [], False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return "", [], False
    if any(word in {";", "&&", "||", "|", "&"} for word in words):
        return "", [], False
    index = 0
    changed_path = False
    if words and words[0] in {"env", "/usr/bin/env"}:
        index += 1
        while index < len(words) and words[index].startswith("-"):
            if words[index] == "-u" and index + 1 < len(words):
                index += 2
            elif words[index] in {"-i", "--ignore-environment"}:
                changed_path = True
                index += 1
            else:
                return "", [], False
    while index < len(words) and ASSIGNMENT.match(words[index]):
        changed_path |= words[index].startswith("PATH=")
        index += 1
    if index >= len(words) or not PYTHON.fullmatch(Path(words[index]).name):
        return "", [], False
    return words[index], words[index + 1:], changed_path


def _interpreter(command: str, cwd: Path, repo: Path,
                 grants: list[Path]) -> tuple[str | None, list[str]]:
    candidates = [path for path in (repo / ".venv/bin/python", repo / "venv/bin/python",
                                     Path("/usr/bin/python3"), Path("/bin/python3")) if path.is_file()]
    first, _, changed_path = _python_command(command)
    if first:
        if "/" in first:
            selected = (cwd / first).resolve() if not Path(first).is_absolute() else Path(first).resolve()
            return str(selected), [str(path) for path in candidates][:8]
        if changed_path:
            return None, [str(path) for path in candidates][:8]
        grant_path = ":".join(str(path if path.is_dir() else path.parent) for path in grants)
        found = shutil.which(first, path=grant_path + ":/usr/bin:/bin")
        return found, [str(path) for path in candidates][:8]
    return None, [str(path) for path in candidates][:8]


def _search_path(command: str, cwd: Path, probe_paths: list[str]) -> list[str]:
    _, arguments, _ = _python_command(command)
    if "-I" in arguments or "--isolated" in arguments:
        return probe_paths
    if arguments and arguments[0] not in {"-c", "-m"} and not arguments[0].startswith("-"):
        source = Path(arguments[0])
        first = str((cwd / source).resolve().parent) if not source.is_absolute() else str(source.parent)
    else:
        first = str(cwd)
    return list(dict.fromkeys([first, *probe_paths]))[:12]


def _version_tuple(value: str) -> tuple[int, ...] | None:
    if not re.fullmatch(r"\d+(?:\.\d+)*", value):
        return None
    return tuple(int(part) for part in value.split("."))


def _packages(requirements: list[str], installed: dict[str, str | None]) -> list[dict]:
    checks = []
    for requirement in requirements:
        match = NAME.match(requirement)
        if not match:
            checks.append({"requirement": requirement[:120], "status": "unverified"})
            continue
        name, spec = match.groups()
        normalized = name.lower().replace("_", "-").replace(".", "-")
        version = installed.get(normalized)
        simple = SIMPLE_SPEC.fullmatch(spec) if spec.strip() else None
        if spec.strip() and simple is None:
            status = "unverified"
        else:
            status = "missing" if version is None else "installed"
        if version is not None and simple is not None:
            operator, expected = simple.groups()
            actual_tuple, expected_tuple = _version_tuple(version), _version_tuple(expected)
            if actual_tuple is None or expected_tuple is None:
                status = "unverified"
            else:
                width = max(len(actual_tuple), len(expected_tuple))
                actual_tuple += (0,) * (width - len(actual_tuple))
                expected_tuple += (0,) * (width - len(expected_tuple))
                compare = {"==": actual_tuple == expected_tuple, "!=": actual_tuple != expected_tuple,
                           ">=": actual_tuple >= expected_tuple, "<=": actual_tuple <= expected_tuple,
                           ">": actual_tuple > expected_tuple, "<": actual_tuple < expected_tuple}
                status = "installed" if compare[operator] else "incompatible"
        checks.append({"requirement": requirement[:120], "installed_version": version, "status": status})
    return checks


def _bound(payload: dict, budget: int) -> dict:
    """Keep a useful core while bounding the serialized diagnostic."""
    while len(json.dumps(payload)) > budget:
        python = payload["python"]
        recorded = payload["recorded_attempt"]
        if python.get("candidates"):
            python["candidates"].pop()
        elif len(python.get("sys_path", [])) > 1:
            python["sys_path"].pop()
            python["sys_path_omitted"] = True
        elif payload["optional_groups"]:
            payload["optional_groups"].pop()
            payload["optional_groups_omitted"] = True
        elif len(payload["dependencies"]) > 1:
            payload["dependencies"].pop()
            payload["dependencies_omitted"] = payload.get("dependencies_omitted", 0) + 1
        elif any(len(value) > 40 for value in payload["environment"].values()):
            payload["environment"] = {key: value[:40] for key, value in payload["environment"].items()}
        elif any(len(recorded.get(key, "")) > 80 for key in ("command", "stdout_excerpt", "stderr_excerpt")):
            recorded["command"] = recorded.get("command", "")[:80]
            recorded["stdout_excerpt"] = recorded.get("stdout_excerpt", "")[:40]
            recorded["stderr_excerpt"] = recorded.get("stderr_excerpt", "")[-80:]
            recorded["detail_truncated"] = True
        elif payload["dependencies"] and len(payload["dependencies"][0]["requirement"]) > 40:
            payload["dependencies"][0]["requirement"] = payload["dependencies"][0]["requirement"][:40]
            payload["dependencies_omitted"] = payload.get("dependencies_omitted", 0) + 1
        elif python.get("sys_path"):
            python["sys_path"].pop()
            payload["python"]["sys_path_omitted"] = True
        elif payload["dependencies"]:
            payload["dependencies"].pop()
            payload["dependencies_omitted"] = payload.get("dependencies_omitted", 0) + 1
        else:
            return {"recorded_attempt": {"id": recorded["id"], "status": recorded["status"],
                                          "created_at": recorded["created_at"]},
                    "checked_at": payload["checked_at"], "status": payload.get("status", "unverified"),
                    "detail_truncated": True}
    return payload


def _emit(payload: dict, args: argparse.Namespace, code: int) -> int:
    def scrub(value):
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if isinstance(value, dict):
            return {key: scrub(item) for key, item in value.items()}
        return value

    print(json.dumps(_bound(scrub(payload), args.max_detail)))
    return code


def execute(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        args.attempt_id = int(args.attempt_id)
        if args.attempt_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        print(json.dumps({"error": "attempt-id must be a positive integer"}))
        return 2
    if not 800 <= args.max_detail <= 4000:
        parser.error("max-detail must be 800 through 4000")
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error("repo must be a directory")
    try:
        attempt = history.load_attempt(repo, args.attempt_id)
    except ValueError as error:
        print(json.dumps({"error": str(error)[:300], "attempt_id": args.attempt_id}))
        return 2
    if attempt is None:
        print(json.dumps({"error": "attempt not found", "attempt_id": args.attempt_id}))
        return 2
    cwd = Path(attempt["cwd"])
    if not cwd.is_dir() or not cwd.resolve().is_relative_to(repo):
        print(json.dumps({"error": "recorded working directory is unavailable", "attempt_id": args.attempt_id}))
        return 2
    summary = summarize(attempt)
    recorded = {"id": attempt["id"], "created_at": attempt["created_at"],
                "status": attempt.get("status", "executed"),
                "exit_code": attempt.get("exit_code"),
                "command": redact(attempt["command"])[:160],
                "cwd": str(cwd)[:160],
                "stdout_excerpt": redact(attempt.get("stdout", ""))[-120:],
                "stderr_excerpt": redact(attempt.get("stderr", ""))[-160:],
                "error_excerpt": summary["evidence"] if summary else "",
                "stdout_truncated": bool(attempt.get("stdout_truncated")),
                "stderr_truncated": bool(attempt.get("stderr_truncated")),
                "timed_out": bool(attempt.get("timed_out"))}
    recorded["detail_truncated"] = (len(attempt["command"]) > 160 or len(str(cwd)) > 160 or
                                     len(attempt.get("stdout", "")) > 120 or
                                     len(attempt.get("stderr", "")) > 160)
    payload = {"recorded_attempt": recorded,
               "checked_at": datetime.now(timezone.utc).isoformat(), "environment": {},
               "python": {"status": "unverified"}, "dependencies": [], "optional_groups": []}
    if attempt.get("status") != "executed":
        payload["status"] = "attempt_not_executed"
        return _emit(payload, args, 0)
    try:
        grants = agent_tool_grants(repo)
    except BackendUnavailable as error:
        payload["status"] = "backend_unavailable"
        payload["error"] = str(error)[:300]
        return _emit(payload, args, 69)
    selected, candidates = _interpreter(attempt["command"], cwd, repo, grants)
    payload["python"] = {"status": "ambiguous" if selected is None else "unverified",
                         "candidates": candidates}
    requirements, groups = _declared(repo, cwd, args.group, attempt["command"])
    error_text = (attempt.get("stderr", "") + " " + attempt.get("stdout", "")).lower()
    requirements.sort(key=lambda value: 0 if (match := NAME.match(value))
                      and match.group(1).lower().replace("-", "_") in error_text.replace("-", "_") else 1)
    payload["optional_groups"] = groups
    if args.group and args.group not in groups:
        payload["warning"] = "requested optional group is not declared"
    probe_names = []
    for requirement in requirements:
        match = NAME.match(requirement)
        if match:
            probe_names.append(match.group(1).lower().replace("_", "-").replace(".", "-"))
    script = PROBE % {"names": json.dumps(probe_names)}
    command = (shlex.quote(selected) + " -I -c " + shlex.quote(script)) if selected else ":"
    try:
        argv, environment, cleanup = launch_command(repo, cwd, command, grants, read_only_repo=True)
    except BackendUnavailable as error:
        payload["status"] = "backend_unavailable"
        payload["error"] = str(error)[:300]
        return _emit(payload, args, 69)
    payload["environment"] = {key: redact(value)[:120] for key, value in environment.items()
                              if key in {"PATH", "HOME", "TMPDIR", "XDG_CACHE_HOME", "LC_ALL"}}
    try:
        result = _run_bounded(argv, cwd, 20, 8192, environment)
    except OSError as error:
        payload["status"] = "probe_unverified"
        payload["error"] = str(error)[:300]
        payload["dependencies"] = [{"requirement": value[:120], "status": "unverified"}
                                   for value in requirements]
        return _emit(payload, args, 1)
    finally:
        cleanup()
    if selected is None and result["exit_code"] == 0:
        payload["status"] = "interpreter_ambiguous"
        payload["dependencies"] = [{"requirement": value[:120], "status": "unverified"}
                                   for value in requirements]
    elif result["exit_code"] != 0 or result["stdout_truncated"]:
        payload["status"] = "probe_unverified"
        payload["error"] = redact(result["stderr"])[-300:]
        payload["dependencies"] = [{"requirement": value[:120], "status": "unverified"}
                                   for value in requirements]
    else:
        try:
            observed = json.loads(result["stdout"])
            payload["python"] = {"status": "checked", "executable": observed["executable"],
                                 "version": observed["version"],
                                 "virtual_environment": observed["prefix"] != observed["base_prefix"],
                                 "sys_path": _search_path(attempt["command"], cwd, observed["sys_path"]),
                                 "sys_path_inferred": True, "isolated_probe": True,
                                 "candidates": candidates}
            payload["dependencies"] = _packages(requirements, observed["packages"])
            payload["status"] = "checked"
        except (KeyError, ValueError, TypeError):
            payload["status"] = "probe_unverified"
            payload["dependencies"] = [{"requirement": value[:120], "status": "unverified"}
                                       for value in requirements]
    code = 0 if payload["status"] in {"checked", "interpreter_ambiguous"} else 1
    return _emit(payload, args, code)
