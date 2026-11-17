"""Bounded static analysis of Fortran source and common build descriptions."""

import re
import tomllib
from pathlib import Path


FREE_FORM_SUFFIXES = {".f90", ".f95", ".f03", ".f08"}
FIXED_FORM_SUFFIXES = {".f", ".for", ".f77"}
INTRINSIC_MODULES = {
    "iso_c_binding", "iso_fortran_env", "ieee_arithmetic", "ieee_exceptions",
    "ieee_features",
}
PROCEDURE_PREFIXES = {
    "elemental", "impure", "non_recursive", "procedure", "pure",
    "recursive", "subroutine", "function",
}
NAME = r"[a-z][a-z0-9_]*"
UNIT = re.compile(rf"^(program|module)\s+({NAME})\b", re.IGNORECASE)
SUBMODULE = re.compile(
    rf"^submodule\s*\(\s*({NAME})(?:\s*:\s*({NAME}))?\s*\)\s*({NAME})\b",
    re.IGNORECASE,
)
USE = re.compile(
    rf"^use\b\s*(?:,\s*(intrinsic|non_intrinsic)\s*::\s*|::\s*)?({NAME})\b",
    re.IGNORECASE,
)
END_UNIT = re.compile(r"^end\s*(program|module|submodule)\b", re.IGNORECASE)
INCLUDE = re.compile(r"^include\s*(['\"])([^'\"]+)\1", re.IGNORECASE)
CPP_INCLUDE = re.compile(r"^#\s*include\s*(['\"<])([^'\">]+)['\">]", re.IGNORECASE)


def _without_comment(line: str) -> str:
    """Discard comments while preserving exclamation marks inside strings."""
    quote = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == quote:
                if index + 1 < len(line) and line[index + 1] == quote:
                    index += 2
                    continue
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "!":
            return line[:index]
        index += 1
    return line


def _statements(source: str, fixed: bool = False, preprocessed: bool = False):
    """Yield logical statements, first line, and preprocessing uncertainty."""
    parts = []
    start = 0
    conditional_depth = 0
    uncertain = False

    def emit():
        joined = "".join(parts)
        for statement in joined.split(";"):
            statement = statement.strip()
            if statement:
                yield statement, start, uncertain

    for number, raw in enumerate(source.splitlines(), 1):
        if raw.lstrip().startswith("#"):
            if parts:
                yield from emit()
                parts = []
            directive = raw.strip()
            if directive.lower().startswith(("#if ", "#if(", "#ifdef", "#ifndef")):
                conditional_depth += 1
            yield directive, number, True
            if directive.lower().startswith("#endif"):
                conditional_depth = max(0, conditional_depth - 1)
            continue
        if fixed:
            if raw and raw[0] in "cC*!":
                continue
            continuation = len(raw) >= 6 and raw[5] not in " 0"
            line = _without_comment(raw[6:72]).rstrip() if len(raw) > 6 else ""
            if not continuation and parts:
                yield from emit()
                parts = []
            if not line.strip():
                continue
            if not parts:
                start = number
                uncertain = preprocessed or bool(conditional_depth)
            parts.append(line.strip())
            continue
        line = _without_comment(raw).rstrip()
        if not line.strip():
            continue
        if not parts:
            start = number
            uncertain = preprocessed or bool(conditional_depth)
        segment = line.lstrip()
        if parts and segment.startswith("&"):
            segment = segment[1:]
        continued = segment.endswith("&")
        if continued:
            segment = segment[:-1]
        parts.append(segment)
        if continued:
            continue
        yield from emit()
        parts = []
    if parts:
        yield from emit()


def _build_files(repo: Path, files: list[Path], max_file_bytes: int, graph) -> None:
    """Add conservative targets and declared dependencies from build files."""
    by_name = {path.as_posix(): path for path in files}

    def target(name, path, line):
        node = graph.add_node("build target", f"fortran:{path}:{name}", name)
        evidence = f"{path}:{line}: {name}"
        graph.add_edge(f"file:{path}", node, "defines", evidence=evidence)
        graph.add_finding(f"Fortran build target {name} — {path}:{line}.")
        return node

    def dependency(source, name, path, line, declared=True):
        destination = by_name.get(name)
        if destination is not None:
            node, status = f"file:{destination.as_posix()}", "internal"
        else:
            node = graph.add_node("build dependency", f"fortran:build:{name}", name)
            status = "external" if declared else "unresolved"
        graph.add_edge(source, node, "depends on", status, f"{path}:{line}: {name}")
        if status != "internal":
            graph.add_finding(f"Fortran build dependency {name} ({status}) — {path}:{line}.")

    for path in files:
        if path.name not in {"fpm.toml", "CMakeLists.txt", "Makefile", "makefile"}:
            continue
        try:
            absolute = repo / path
            if absolute.stat().st_size > max_file_bytes:
                continue
            source = absolute.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        label = path.as_posix()
        lines = source.splitlines()
        if path.name == "fpm.toml":
            try:
                data = tomllib.loads(source)
            except tomllib.TOMLDecodeError:
                continue
            package = data.get("name")
            if isinstance(package, str):
                line = next((i for i, text in enumerate(lines, 1)
                             if re.match(r"\s*name\s*=", text)), 1)
                package_node = target(package, label, line)
            else:
                package_node = f"file:{label}"
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                dependencies = data.get(section, {})
                if isinstance(dependencies, dict):
                    for name in dependencies:
                        line = next((i for i, text in enumerate(lines, 1)
                                     if re.match(rf"\s*{re.escape(name)}\s*=", text)), 1)
                        dependency(package_node, name, label, line)
            for section in ("executable", "test", "example", "library"):
                values = data.get(section, [])
                if isinstance(values, dict):
                    values = [values]
                if not isinstance(values, list):
                    continue
                for value in values:
                    if not isinstance(value, dict) or not isinstance(value.get("name"), str):
                        continue
                    name = value["name"]
                    line = next((i for i, text in enumerate(lines, 1)
                                 if re.match(rf'\s*name\s*=\s*["\']{re.escape(name)}["\']', text)), 1)
                    target(name, label, line)
            continue
        if path.name == "CMakeLists.txt":
            targets = {}
            links = []
            commands = re.finditer(
                r"^[ \t]*(add_library|add_executable|target_link_libraries)"
                r"[ \t]*\(([^)]*)\)", source, re.I | re.M | re.S,
            )
            for match in commands:
                line = source.count("\n", 0, match.start()) + 1
                command = match.group(1).lower()
                items = match.group(2).split()
                if not items:
                    continue
                name = items[0]
                if command in {"add_library", "add_executable"}:
                    node = target(name, label, line)
                    targets[name] = node
                    for item in items[1:]:
                        if item.upper() in {"STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE", "EXCLUDE_FROM_ALL"}:
                            continue
                        if item in by_name:
                            dependency(node, item, label, line)
                else:
                    links.append((line, name, items[1:]))
            for line, name, items in links:
                source_node = targets.get(name)
                if source_node is None:
                    continue
                for item in items:
                    if item.upper() in {"PRIVATE", "PUBLIC", "INTERFACE"}:
                        continue
                    if item in targets:
                        graph.add_edge(source_node, targets[item], "depends on", evidence=f"{label}:{line}: {item}")
                    else:
                        dependency(source_node, item, label, line)
            continue
        targets = {}
        rules = []
        for line, raw in enumerate(lines, 1):
            if raw.startswith("\t") or raw.lstrip().startswith("#"):
                continue
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", raw)
            if match:
                name, prerequisites = match.groups()
                targets[name] = target(name, label, line)
                rules.append((line, name, prerequisites.split("#", 1)[0].split()))
        for line, name, prerequisites in rules:
            for item in prerequisites:
                if item in targets:
                    graph.add_edge(targets[name], targets[item], "depends on", evidence=f"{label}:{line}: {item}")
                else:
                    dependency(targets[name], item, label, line, declared=False)


def analyze(repo: Path, files: list[Path], max_file_bytes: int, graph) -> None:
    sources = {}
    scanned = {path.as_posix() for path in files}
    for path in files:
        suffix = path.suffix.lower()
        if suffix not in FREE_FORM_SUFFIXES | FIXED_FORM_SUFFIXES:
            continue
        absolute = repo / path
        try:
            if absolute.stat().st_size > max_file_bytes:
                continue
            sources[path] = list(_statements(
                absolute.read_text(encoding="utf-8"),
                fixed=suffix in FIXED_FORM_SUFFIXES,
                preprocessed=path.suffix != suffix,
            ))
        except (OSError, UnicodeError):
            continue

    modules = {}
    submodules = {}
    units_by_path = {}
    all_units = []
    for path, statements in sources.items():
        units = []
        for statement, line, uncertain in statements:
            lowered = statement.lower()
            submodule = SUBMODULE.match(lowered)
            if submodule:
                ancestor, parent, name = submodule.groups()
                key = f"fortran:{ancestor}:{parent or ''}:{name}"
                node = graph.add_node("submodule", key, f"submodule {name}")
                submodules[(ancestor, name)] = node
                units.append((line, "submodule", node))
                all_units.append(("submodule", name, path, line))
                graph.add_edge(f"file:{path.as_posix()}", node, "defines",
                               "uncertain" if uncertain else "internal",
                               evidence=f"{path.as_posix()}:{line}: {statement}")
                continue
            unit = UNIT.match(lowered)
            if not unit or (unit.group(1) == "module" and
                            unit.group(2) in PROCEDURE_PREFIXES):
                continue
            kind, name = unit.groups()
            key = f"fortran:{name}" if kind == "module" else f"fortran:{path.as_posix()}:{name}"
            node = graph.add_node(kind, key, f"{kind} {name}")
            if kind == "module":
                modules[name] = node
            units.append((line, kind, node))
            all_units.append((kind, name, path, line))
            graph.add_edge(f"file:{path.as_posix()}", node, "defines",
                           "uncertain" if uncertain else "internal",
                           evidence=f"{path.as_posix()}:{line}: {statement}")
        units_by_path[path] = units

    for path, statements in sources.items():
        active = f"file:{path.as_posix()}"
        units = {line: node for line, _, node in units_by_path[path]}
        for statement, line, uncertain in statements:
            if line in units:
                active = units[line]
            if END_UNIT.match(statement):
                active = f"file:{path.as_posix()}"
                continue
            include = INCLUDE.match(statement) or CPP_INCLUDE.match(statement)
            if include or statement.lower().startswith("#include"):
                if include:
                    name = include.group(2)
                    candidate = (path.parent / name).as_posix()
                    if candidate not in scanned and name in scanned:
                        candidate = name
                    if candidate in scanned:
                        destination = f"file:{candidate}"
                        status = "uncertain" if uncertain else "internal"
                    else:
                        destination = graph.add_node("unresolved", f"fortran:include:{name}", name)
                        status = "uncertain" if uncertain else "unresolved"
                else:
                    name = statement.split(None, 1)[-1].strip() or "?"
                    destination = graph.add_node("unresolved", f"fortran:include:{name}", name)
                    status = "uncertain"
                evidence = f"{path.as_posix()}:{line}: {statement}"
                graph.add_edge(active, destination, "includes", status, evidence)
                if status != "internal":
                    graph.add_finding(f"Fortran include {name} ({status}) — {evidence}.")
                continue
            match = USE.match(statement)
            if not match:
                continue
            qualifier, name = match.groups()
            name = name.lower()
            qualifier = qualifier.lower() if qualifier else None
            if qualifier == "intrinsic" or (qualifier != "non_intrinsic" and name in INTRINSIC_MODULES):
                status = "intrinsic"
                target = graph.add_node("intrinsic", f"fortran:{name}", name)
            elif name in modules:
                status = "internal"
                target = modules[name]
            else:
                status = "unresolved" if qualifier == "non_intrinsic" else "external"
                target = graph.add_node(status, f"fortran:{name}", name)
            evidence = f"{path.as_posix()}:{line}: {statement}"
            edge_status = "uncertain" if uncertain else status
            graph.add_edge(active, target, "uses", edge_status, evidence)
            if status != "internal":
                graph.add_finding(f"Fortran USE {name} ({edge_status}) — {evidence}.")

    for path, statements in sources.items():
        for statement, line, uncertain in statements:
            match = SUBMODULE.match(statement)
            if not match:
                continue
            ancestor, parent, name = (part.lower() if part else None for part in match.groups())
            source = submodules[(ancestor, name)]
            destination = submodules.get((ancestor, parent)) if parent else modules.get(ancestor)
            if destination is None:
                status = "unresolved"
                destination = graph.add_node("unresolved", f"fortran:{ancestor}:{parent or ''}",
                                             f"{ancestor}:{parent}" if parent else ancestor)
            else:
                status = "internal"
            evidence = f"{path.as_posix()}:{line}: {statement}"
            graph.add_edge(source, destination, "extends",
                           "uncertain" if uncertain else status, evidence)
            if status == "unresolved":
                graph.add_finding(f"Fortran submodule parent unresolved — {evidence}.")

    for kind, name, path, line in all_units[:20]:
        graph.add_finding(f"Fortran {kind} {name} — {path.as_posix()}:{line}.")
    if len(all_units) > 20:
        graph.add_finding(f"{len(all_units) - 20} more Fortran units; see GRAPH.dot.")
    if sources or any(path.name == "fpm.toml" for path in files):
        _build_files(repo, files, max_file_bytes, graph)
