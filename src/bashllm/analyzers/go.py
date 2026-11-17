"""Bounded static inspection of Go modules, packages, and imports."""

import re
from pathlib import Path


MODULE = re.compile(r"^\s*module\s+(\S+)")
REQUIRE = re.compile(r"^\s*require\s+(\S+)\s+(\S+)")
PACKAGE = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z_0-9]*)\b")
MAIN = re.compile(r"^\s*func\s+main\s*\(")
IMPORT = re.compile(r'^\s*import\s+(?:[.\w]+\s+)?"([^"]+)"')
IMPORT_ITEM = re.compile(r'^\s*(?:[.\w]+\s+)?"([^"]+)"')


def _lines(repo: Path, path: Path, max_file_bytes: int) -> list[str] | None:
    try:
        absolute = repo / path
        if absolute.stat().st_size > max_file_bytes:
            return None
        return absolute.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None


def analyze(repo: Path, files: list[Path], max_file_bytes: int, graph) -> None:
    manifests = {}
    declared = {}
    for path in files:
        if path.name != "go.mod":
            continue
        lines = _lines(repo, path, max_file_bytes)
        if lines is None:
            continue
        module = next(((number, match.group(1)) for number, line in enumerate(lines, 1)
                       if (match := MODULE.match(line.split("//", 1)[0]))), None)
        if module is None:
            continue
        number, name = module
        node = graph.add_node("module", f"go:{path.as_posix()}", f"Go module {name}")
        graph.add_edge(f"file:{path.as_posix()}", node, "defines", evidence=f"{path}:{number}")
        graph.add_finding(f"Go module `{name}` — `{path}:{number}`.")
        manifests[path] = (name, node, lines)

    for path, (name, node, lines) in manifests.items():
        in_require = False
        for number, raw in enumerate(lines, 1):
            line = raw.split("//", 1)[0].strip()
            if line == "require (":
                in_require = True
                continue
            if in_require and line == ")":
                in_require = False
                continue
            match = REQUIRE.match(line if not in_require else "require " + line)
            if match is None:
                continue
            dependency = match.group(1)
            internal = next((entry[1] for other, entry in manifests.items()
                             if other != path and entry[0] == dependency), None)
            status = "internal" if internal else "external"
            target = internal or graph.add_node("external", f"go:dependency:{path}:{dependency}", dependency)
            graph.add_edge(node, target, "depends on", status, f"{path}:{number}: {raw.strip()}")
            graph.add_finding(f"Declared Go dependency `{dependency}` ({status}) — `{path}:{number}`.")
            declared[(path, dependency)] = target

    packages = {}
    sources = {}
    source_packages = {}
    for path in files:
        if path.suffix != ".go":
            continue
        lines = _lines(repo, path, max_file_bytes)
        if lines is None:
            continue
        package = next(((number, match.group(1)) for number, line in enumerate(lines, 1)
                        if (match := PACKAGE.match(line.split("//", 1)[0]))), None)
        if package is None:
            continue
        number, name = package
        unit = graph.add_node("package", f"go:{path.parent.as_posix()}:{name}",
                              f"Go package {name} ({path.parent.as_posix()})")
        graph.add_edge(f"file:{path}", unit, "defines", evidence=f"{path}:{number}")
        graph.add_finding(f"Go package `{name}` — `{path}:{number}`.")
        sources[path] = lines
        source_packages[path] = unit
        if name == "main":
            for main_number, line in enumerate(lines, 1):
                if MAIN.match(line.split("//", 1)[0]):
                    graph.add_edge(unit, f"file:{path}", "entry point", evidence=f"{path}:{main_number}")
                    graph.add_finding(f"Go entry point `{path}:{main_number}`.")
                    break
        containing = [manifest for manifest in manifests if path.is_relative_to(manifest.parent)]
        if containing:
            manifest = max(containing, key=lambda item: len(item.parent.parts))
            graph.add_edge(manifests[manifest][1], unit, "contains", evidence=f"{path}:{number}")
            import_path = manifests[manifest][0]
            relative = path.parent.relative_to(manifest.parent).as_posix()
            if relative != ".":
                import_path += "/" + relative
            packages[import_path] = unit

    for path, lines in sources.items():
        containing = [manifest for manifest in manifests if path.is_relative_to(manifest.parent)]
        manifest = max(containing, key=lambda item: len(item.parent.parts)) if containing else None
        in_import = False
        for number, raw in enumerate(lines, 1):
            line = raw.split("//", 1)[0]
            if re.match(r"^\s*import\s*\(", line):
                in_import = True
                continue
            if in_import and line.strip() == ")":
                in_import = False
                continue
            match = (IMPORT_ITEM if in_import else IMPORT).match(line)
            if match is None:
                continue
            imported = match.group(1)
            if imported in packages:
                target, status = packages[imported], "internal"
            elif manifest is not None and any(
                imported == name or imported.startswith(name + "/")
                for name, _, _ in manifests.values()
            ):
                target = graph.add_node("unresolved", f"go:import:{imported}", imported)
                status = "unresolved"
            elif manifest is not None and (dependency := next((dependency for owner, dependency in declared
                    if owner == manifest and (imported == dependency or imported.startswith(dependency + "/"))), None)):
                target = graph.add_node("external", f"go:import:{imported}", imported)
                status = "external"
            elif "." not in imported.split("/", 1)[0] or imported == "C":
                target = graph.add_node("intrinsic", f"go:import:{imported}", imported)
                status = "intrinsic"
            else:
                target = graph.add_node("unresolved", f"go:import:{imported}", imported)
                status = "unresolved"
            evidence = f"{path}:{number}: {raw.strip()}"
            graph.add_edge(f"file:{path}", target, "imports", status, evidence)
            if status == "internal":
                graph.add_edge(source_packages[path], target, "imports", status, evidence)
            graph.add_finding(f"Inferred Go import `{imported}` ({status}) — `{path}:{number}`.")
