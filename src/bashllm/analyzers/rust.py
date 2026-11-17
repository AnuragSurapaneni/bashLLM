"""Bounded static inspection of Cargo packages and Rust source references."""

import re
import tomllib
from pathlib import Path


DEPENDENCY_SECTIONS = ("dependencies", "dev-dependencies", "build-dependencies")
USE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+(?:::)?([A-Za-z_][A-Za-z_0-9]*)\b")
EXTERN = re.compile(r"^\s*(?:pub\s+)?extern\s+crate\s+([A-Za-z_][A-Za-z_0-9]*)\b")
MODULE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+([A-Za-z_][A-Za-z_0-9]*)\s*;")


def _evidence(path: Path, line: int | None = None) -> str:
    return f"{path.as_posix()}:{line}" if line is not None else path.as_posix()


def _manifest(repo: Path, path: Path, max_file_bytes: int):
    try:
        absolute = repo / path
        if absolute.stat().st_size > max_file_bytes:
            return None
        with absolute.open("rb") as stream:
            data = tomllib.load(stream)
        return data if isinstance(data, dict) else None
    except (OSError, tomllib.TOMLDecodeError):
        return None


def _target_source(manifest: Path, value: str) -> Path | None:
    source = manifest.parent / value
    if source.is_absolute() or ".." in source.parts:
        return None
    return source


def _targets(manifest: Path, data: dict, files: set[Path], name: str):
    base = manifest.parent
    normalized = name.replace("-", "_")
    result = []
    explicit = set()
    library = data.get("lib")
    if isinstance(library, dict):
        source = _target_source(manifest, library.get("path", "src/lib.rs")) if isinstance(library.get("path", "src/lib.rs"), str) else None
        if source in files:
            result.append(("library", str(library.get("name", normalized)), source))
            explicit.add(source)
    elif base / "src/lib.rs" in files:
        result.append(("library", normalized, base / "src/lib.rs"))
    for item in data.get("bin", []):
        if not isinstance(item, dict):
            continue
        target_name = item.get("name")
        if not isinstance(target_name, str):
            continue
        raw_path = item.get("path", f"src/bin/{target_name}.rs")
        source = _target_source(manifest, raw_path) if isinstance(raw_path, str) else None
        if source in files:
            result.append(("binary", target_name, source))
            explicit.add(source)
    package = data.get("package", {})
    autobins = package.get("autobins", True) if isinstance(package, dict) else True
    if autobins:
        main = base / "src/main.rs"
        if main in files and main not in explicit:
            result.append(("binary", name, main))
        binary_dir = base / "src/bin"
        for source in sorted(files):
            if source.parent == binary_dir and source.suffix == ".rs" and source not in explicit:
                result.append(("binary", source.stem, source))
            elif source.parent.parent == binary_dir and source.name == "main.rs" and source not in explicit:
                result.append(("binary", source.parent.name, source))
    return result


def analyze(repo: Path, files: list[Path], max_file_bytes: int, graph) -> None:
    scanned = set(files)
    manifests = {}
    packages = {}
    for path in files:
        if path.name != "Cargo.toml":
            continue
        data = _manifest(repo, path, max_file_bytes)
        if data is None:
            continue
        manifests[path] = data
        package = data.get("package")
        if not isinstance(package, dict) or not isinstance(package.get("name"), str):
            continue
        name = package["name"]
        node = graph.add_node("package", f"rust:{path.as_posix()}", f"Rust package {name}")
        graph.add_edge(f"file:{path.as_posix()}", node, "defines", evidence=_evidence(path))
        graph.add_finding(f"Rust package `{name}` — `{path.as_posix()}`.")
        packages[path] = (name, node)

    source_package = {}
    declared = {}
    for path, (name, package_node) in packages.items():
        data = manifests[path]
        for kind, target_name, source in _targets(path, data, scanned, name):
            node = graph.add_node("target", f"rust:{path.as_posix()}:{kind}:{target_name}",
                                  f"Rust {kind} {target_name}")
            graph.add_edge(package_node, node, "defines", evidence=_evidence(path))
            graph.add_edge(node, f"file:{source.as_posix()}", "entry point", evidence=_evidence(source))
            graph.add_finding(f"Rust {kind} target `{target_name}` — `{source.as_posix()}`.")
        for source in files:
            if source.suffix == ".rs" and source.is_relative_to(path.parent) and (
                path.parent == Path(".") or not any(
                    source.is_relative_to(other.parent) and len(other.parent.parts) > len(path.parent.parts)
                    for other in packages if other != path
                )
            ):
                source_package[source] = path

    for path, (name, package_node) in packages.items():
        data = manifests[path]
        for section in DEPENDENCY_SECTIONS:
            entries = data.get(section, {})
            if not isinstance(entries, dict):
                continue
            for alias, spec in sorted(entries.items()):
                if not isinstance(alias, str):
                    continue
                spec_base = path.parent
                inherited_missing = False
                if isinstance(spec, dict) and spec.get("workspace") is True:
                    inherited = None
                    for workspace_path, workspace_data in sorted(
                        manifests.items(), key=lambda item: len(item[0].parent.parts), reverse=True
                    ):
                        workspace = workspace_data.get("workspace")
                        if not path.parent.is_relative_to(workspace_path.parent) or not isinstance(workspace, dict):
                            continue
                        workspace_dependencies = workspace.get("dependencies", {})
                        if isinstance(workspace_dependencies, dict) and alias in workspace_dependencies:
                            inherited = workspace_dependencies[alias]
                            spec_base = workspace_path.parent
                            break
                    if inherited is None:
                        inherited_missing = True
                    else:
                        spec = inherited
                dependency_name = spec.get("package", alias) if isinstance(spec, dict) else alias
                dependency_name = str(dependency_name)
                internal = None
                if inherited_missing:
                    status = "unresolved"
                elif isinstance(spec, dict) and isinstance(spec.get("path"), str):
                    candidate = spec_base / spec["path"] / "Cargo.toml"
                    for other in packages:
                        if (repo / candidate).resolve() == (repo / other).resolve():
                            internal = other
                            break
                    status = "internal" if internal else "unresolved"
                else:
                    status = "external"
                if internal:
                    target = packages[internal][1]
                else:
                    target = graph.add_node(status, f"rust:{path.as_posix()}:{alias}", dependency_name)
                graph.add_edge(package_node, target, "depends on", status,
                               f"{path.as_posix()}: [{section}].{alias}")
                graph.add_finding(
                    f"Declared Rust dependency `{alias}` ({status}) — "
                    f"`{path.as_posix()}` [{section}]."
                )
                declared[(path, alias.replace("-", "_"))] = (target, status)

    for source, package_path in sorted(source_package.items()):
        try:
            absolute = repo / source
            if absolute.stat().st_size > max_file_bytes:
                continue
            lines = absolute.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for number, line in enumerate(lines, 1):
            stripped = line.split("//", 1)[0]
            module = MODULE.match(stripped)
            if module:
                name = module.group(1)
                candidates = (source.parent / f"{name}.rs", source.parent / name / "mod.rs")
                destination = next((item for item in candidates if item in scanned), None)
                if destination:
                    graph.add_edge(f"file:{source.as_posix()}", f"file:{destination.as_posix()}",
                                   "imports", evidence=f"{_evidence(source, number)}: {stripped.strip()}")
                else:
                    target = graph.add_node("unresolved", f"rust:module:{source}:{name}", name)
                    graph.add_edge(f"file:{source.as_posix()}", target, "imports", "unresolved",
                                   f"{_evidence(source, number)}: {stripped.strip()}")
                continue
            reference = USE.match(stripped) or EXTERN.match(stripped)
            if reference is None:
                continue
            name = reference.group(1)
            if name in {"self", "super", "crate"}:
                target = packages[package_path][1]
                status = "internal"
            elif name in {"std", "core", "alloc"}:
                target = graph.add_node("intrinsic", f"rust:{name}", name)
                status = "intrinsic"
            elif (package_path, name) in declared:
                target, status = declared[(package_path, name)]
            else:
                target = graph.add_node("unresolved", f"rust:reference:{package_path}:{name}", name)
                status = "unresolved"
            graph.add_edge(f"file:{source.as_posix()}", target, "uses", status,
                           f"{_evidence(source, number)}: {stripped.strip()}")
            graph.add_finding(f"Inferred Rust reference `{name}` ({status}) — `{_evidence(source, number)}`.")
