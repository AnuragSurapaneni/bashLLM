"""Static package and import analysis for JavaScript and TypeScript projects."""

import json
import posixpath
import re
from pathlib import Path


SOURCE_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
RESOLVE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".json")
STATIC_IMPORT = re.compile(
    r"^\s*(?:import|export)\s+(?:type\s+)?(?:[^'\"\n]*?\s+from\s+)?(?P<quote>['\"])(?P<name>[^'\"\n]+)(?P=quote)"
)
CALL_IMPORT = re.compile(r"\b(?:require|import)\s*\(\s*(['\"])([^'\"\n]+)\1\s*\)")


def _read(repo: Path, path: Path, max_file_bytes: int) -> str | None:
    try:
        source = repo / path
        if source.stat().st_size > max_file_bytes:
            return None
        return source.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _resolve(base: Path, specifier: str, available: set[Path]) -> Path | None:
    normalized = posixpath.normpath(posixpath.join(base.as_posix(), specifier))
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        return None
    candidate = Path(normalized)
    choices = [candidate]
    if candidate.suffix:
        if candidate.suffix == ".js":
            choices.extend(candidate.with_suffix(suffix) for suffix in (".ts", ".tsx"))
        elif candidate.suffix == ".mjs":
            choices.append(candidate.with_suffix(".mts"))
        elif candidate.suffix == ".cjs":
            choices.append(candidate.with_suffix(".cts"))
    else:
        choices.extend(Path(f"{normalized}{suffix}") for suffix in RESOLVE_SUFFIXES)
        choices.extend(candidate / f"index{suffix}" for suffix in RESOLVE_SUFFIXES)
    return next((path for path in choices if path in available), None)


def _entry_fields(manifest: dict):
    for field in ("main", "module", "browser", "types", "typings"):
        value = manifest.get(field)
        if isinstance(value, str):
            yield field, value
    binary = manifest.get("bin")
    if isinstance(binary, str):
        yield "bin", binary
    elif isinstance(binary, dict):
        for name, value in sorted(binary.items()):
            if isinstance(name, str) and isinstance(value, str):
                yield f"bin.{name}", value
    exports = manifest.get("exports")
    if isinstance(exports, str):
        yield "exports", exports
    elif isinstance(exports, dict):
        root = exports.get(".")
        if isinstance(root, str):
            yield "exports.", root
        elif isinstance(root, dict):
            for condition, value in sorted(root.items()):
                if isinstance(value, str):
                    yield f"exports..{condition}", value


def _imports(source: str):
    for line_number, line in enumerate(source.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("//", "/*", "*")):
            continue
        static = STATIC_IMPORT.search(line)
        if static:
            yield static.group("name"), line_number
        for match in CALL_IMPORT.finditer(line):
            yield match.group(2), line_number


def analyze(repo: Path, files: list[Path], max_file_bytes: int, graph) -> None:
    available = set(files)
    source_files = [path for path in files if path.suffix.lower() in SOURCE_SUFFIXES]
    manifests = [path for path in files if path.name == "package.json"]
    if not source_files and not manifests:
        return

    for path in manifests:
        raw = _read(repo, path, max_file_bytes)
        if raw is None:
            continue
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(manifest, dict):
            continue
        evidence = path.as_posix()
        name = manifest.get("name")
        package = f"file:{evidence}"
        if isinstance(name, str) and name:
            language = "TypeScript" if any(
                source.suffix.lower() in {".ts", ".tsx", ".mts", ".cts"}
                and source.is_relative_to(path.parent) for source in source_files
            ) else "JavaScript"
            package = graph.add_node("js-package", evidence, f"{language} package {name}")
            graph.add_edge(f"file:{evidence}", package, "defines", evidence=evidence)
            graph.add_finding(f"{language} package `{name}` — `{evidence}`.")
        for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            dependencies = manifest.get(field)
            if not isinstance(dependencies, dict):
                continue
            for dependency, version in sorted(dependencies.items()):
                if not isinstance(dependency, str) or not isinstance(version, str):
                    continue
                target = graph.add_node("dependency", dependency, dependency)
                detail = f"{evidence}:{field}.{dependency}"
                graph.add_edge(package, target, "depends on", "external", detail)
                graph.add_finding(f"Declared dependency `{dependency}@{version}` — `{detail}`.")
        scripts = manifest.get("scripts")
        if isinstance(scripts, dict):
            for script, command in sorted(scripts.items()):
                if not isinstance(script, str) or not isinstance(command, str):
                    continue
                target = graph.add_node("script", f"{evidence}:{script}", f"script {script}")
                detail = f"{evidence}:scripts.{script}"
                graph.add_edge(package, target, "declares", evidence=detail)
                graph.add_finding(f"Script `{script}` → `{command}` — `{detail}`.")
        for field, value in _entry_fields(manifest):
            detail = f"{evidence}:{field}"
            entry = graph.add_node("entry", detail, f"entry {field}")
            graph.add_edge(package, entry, "declares", evidence=detail)
            destination = _resolve(path.parent, value, available)
            if destination is None:
                target = graph.add_node("unresolved", f"{detail}:{value}", value)
                graph.add_edge(entry, target, "entry point", "unresolved", detail)
            else:
                graph.add_edge(entry, f"file:{destination.as_posix()}", "entry point",
                               evidence=detail)
            graph.add_finding(f"Entry point `{field}` → `{value}` — `{detail}`.")

    inferred = set()
    unresolved = set()
    for path in source_files:
        source = _read(repo, path, max_file_bytes)
        if source is None:
            continue
        for name, line_number in _imports(source):
            evidence = f"{path.as_posix()}:{line_number}: {name}"
            if name.startswith(("./", "../", "/")):
                destination = _resolve(path.parent, name, available)
                if destination is None:
                    target = graph.add_node("unresolved", name, name)
                    graph.add_edge(f"file:{path.as_posix()}", target, "imports", "unresolved", evidence)
                    if name not in unresolved:
                        graph.add_finding(f"Unresolved import `{name}` — `{path.as_posix()}:{line_number}`.")
                        unresolved.add(name)
                else:
                    graph.add_edge(f"file:{path.as_posix()}", f"file:{destination.as_posix()}",
                                   "imports", evidence=evidence)
            else:
                target = graph.add_node("external", name, name)
                graph.add_edge(f"file:{path.as_posix()}", target, "imports", "external", evidence)
                if name not in inferred:
                    graph.add_finding(f"Inferred import `{name}` — `{path.as_posix()}:{line_number}`.")
                    inferred.add(name)
