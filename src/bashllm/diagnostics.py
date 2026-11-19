"""Bounded, conservative summaries of captured command failures."""

import re


SECRET = re.compile(r"(?i)\b([A-Z_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL)[A-Z_]*)\s*[:=]\s*([^\s,;]+)")
URL_CREDENTIALS = re.compile(r"(https?://)[^\s/@]+:[^\s/@]+@")
BEARER = re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/-]+")
QUERY_SECRET = re.compile(r"(?i)([?&](?:token|api_key|secret|password)=)[^\s&#]+")
FLAG_SECRET = re.compile(r"(?i)(--(?:password|token|api[-_]?key|secret|credential)(?:=|\s+))(?:'[^']*'|\"[^\"]*\"|\S+)")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
LOCATION = re.compile(r'File ["\']([^"\']+)["\'], line (\d+)')
PATTERNS = (
    ("missing_module", re.compile(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"),
     "Check that the package is installed for the selected Python interpreter."),
    ("import_error", re.compile(r"(?:ImportError|cannot import name):[^\n]*"),
     "Check package versions and the selected Python interpreter."),
    ("syntax_error", re.compile(r"(?:SyntaxError|IndentationError|TabError):[^\n]*"),
     "Inspect the reported source file and line."),
    ("version_conflict", re.compile(r"(?:VersionConflict|DistributionNotFound|requires [^\n]* but you have|incompatible version)[^\n]*", re.I),
     "Compare the declared requirement with installed package metadata."),
    ("missing_executable", re.compile(r"(?:^|\n)(?:bash|/bin/bash):[^\n]*(?:command not found|No such file or directory)", re.I),
     "Check the executable path inside the run environment."),
    ("python_traceback", re.compile(r"Traceback \(most recent call last\):[\s\S]*?\n([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):[^\n]*)"),
     "Inspect the final exception and its reported source location."),
)


def redact(value: str) -> str:
    value = ANSI.sub("", value)
    value = SECRET.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    value = URL_CREDENTIALS.sub(r"\1[REDACTED]@", value)
    value = BEARER.sub(r"\1 [REDACTED]", value)
    value = FLAG_SECRET.sub(r"\1[REDACTED]", value)
    return QUERY_SECRET.sub(r"\1[REDACTED]", value)


def summarize(result: dict) -> dict | None:
    if result.get("exit_code") == 0 and not result.get("timed_out"):
        return None
    output = (result.get("stderr") or "") + "\n" + (result.get("stdout") or "")
    category = "unclassified"
    evidence = ""
    next_steps: list[str] = []
    location = None
    for name, pattern, step in PATTERNS:
        match = pattern.search(output)
        if match:
            category = name
            lines = output.splitlines()
            line = next((item for item in lines if match.group(0) in item), match.group(0))
            evidence = redact((match.group(1) if category == "python_traceback" else line).strip())[:400]
            next_steps.append(step)
            if category in {"syntax_error", "missing_module", "import_error", "python_traceback"}:
                matches = LOCATION.findall(output)
                if matches:
                    path, line_number = matches[-1]
                    location = {"path": redact(path)[:200], "line": int(line_number)}
            break
    if not evidence:
        lines = [redact(line.strip()) for line in output.splitlines() if line.strip()]
        evidence = (lines[-1] if lines else "No error output was captured.")[:400]
    if result.get("timed_out"):
        next_steps.append("Check whether the command needs more time or is waiting for input.")
    if result.get("stdout_truncated") or result.get("stderr_truncated"):
        next_steps.append("Request bounded detail; the captured output was truncated.")
    summary = {
        "category": category,
        "confidence": "evidence" if category != "unclassified" else "unknown",
        "evidence": evidence,
        "exit_code": result.get("exit_code"),
        "timed_out": bool(result.get("timed_out")),
        "stdout_truncated": bool(result.get("stdout_truncated")),
        "stderr_truncated": bool(result.get("stderr_truncated")),
        "next_steps": next_steps[:3],
    }
    if location is not None:
        summary["location"] = location
    return summary
