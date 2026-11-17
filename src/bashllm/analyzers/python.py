"""Static Python package, manifest, entry point, and import analysis."""

import ast
import configparser
import re
import tomllib
from pathlib import Path


DEPENDENCY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _read(repo: Path, path: Path, max_file_bytes: int) -> str | None:
    try:
        source = repo / path
        if source.stat().st_size > max_file_bytes:
            return None
        return source.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _manifest(repo: Path, path: Path, max_file_bytes: int):
    source = _read(repo, path, max_file_bytes)
    if source is None:
        return None
    try:
        if path.name == "pyproject.toml":
            project = tomllib.loads(source).get("project", {})
            if not isinstance(project, dict):
                return None
            scripts = {}
            for section in ("scripts", "gui-scripts"):
                values = project.get(section, {})
                if isinstance(values, dict):
                    scripts.update({key: value for key, value in values.items()
                                    if isinstance(key, str) and isinstance(value, str)})
            dependencies = project.get("dependencies", [])
            if not isinstance(dependencies, list):
                dependencies = []
            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for values in optional.values():
                    if isinstance(values, list):
                        dependencies = [*dependencies, *values]
            return project.get("name"), dependencies, scripts
        if path.name == "setup.cfg":
            config = configparser.ConfigParser()
            config.read_string(source)
            name = config.get("metadata", "name", fallback=None)
            dependencies = config.get("options", "install_requires", fallback="").splitlines()
            scripts = {}
            for section in ("console_scripts", "gui_scripts"):
                for line in config.get("options.entry_points", section, fallback="").splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        scripts[key.strip()] = value.strip()
            return name, dependencies, scripts
        if path.name == "setup.py":
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (isinstance(node.func, ast.Name) and node.func.id == "setup"):
                    continue
                values = {}
                for keyword in node.keywords:
                    try:
                        values[keyword.arg] = ast.literal_eval(keyword.value)
                    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                        pass
                scripts = {}
                entry_points = values.get("entry_points", {})
                if isinstance(entry_points, dict):
                    for section in ("console_scripts", "gui_scripts"):
                        for line in entry_points.get(section, []):
                            if isinstance(line, str) and "=" in line:
                                key, value = line.split("=", 1)
                                scripts[key.strip()] = value.strip()
                return values.get("name"), values.get("install_requires", []), scripts
    except (tomllib.TOMLDecodeError, configparser.Error, SyntaxError, ValueError):
        return None
    return None


def _module_names(path: Path):
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    names = [".".join(parts)]
    if parts and parts[0] == "src":
        names.append(".".join(parts[1:]))
    return [name for name in names if name]


def _resolve(name: str, modules: dict[str, Path]) -> Path | None:
    return modules.get(name)


def _imports(tree: ast.AST, path: Path, module: str):
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]

    def visit(node, uncertain=False):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, False, uncertain, node.lineno, None
            return
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                keep = len(parts) - node.level + 1
                prefix = ".".join(parts[:keep]) if keep >= 0 else ""
                base = ".".join(filter(None, (prefix, node.module)))
                relative = True
            else:
                base = node.module or ""
                relative = False
            for alias in node.names:
                if alias.name == "*":
                    yield base, relative, uncertain, node.lineno, None
                else:
                    yield ".".join(filter(None, (base, alias.name))), relative, uncertain, node.lineno, (
                        base if node.module else None)
            return
        child_uncertain = uncertain or isinstance(
            node, (ast.If, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef,
                   ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)
        )
        for child in ast.iter_child_nodes(node):
            yield from visit(child, child_uncertain)

    yield from visit(tree)


def analyze(repo: Path, files: list[Path], max_file_bytes: int, graph) -> None:
    python_files = [path for path in files if path.suffix == ".py"]
    manifest_paths = [path for path in files if path.name in {"pyproject.toml", "setup.cfg", "setup.py"}]
    requirement_paths = [path for path in files if path.name.startswith("requirements") and path.suffix == ".txt"]
    if not python_files and not manifest_paths and not requirement_paths:
        return

    modules = {}
    for path in python_files:
        for name in _module_names(path):
            modules.setdefault(name, path)
        if path.name == "__init__.py":
            name = _module_names(path)[-1] if _module_names(path) else path.parent.as_posix()
            package = graph.add_node("package", name, f"Python package {name}")
            graph.add_edge(f"file:{path.as_posix()}", package, "defines", evidence=path.as_posix())
            graph.add_finding(f"Python package `{name}` — `{path.as_posix()}`.")

    for path in manifest_paths:
        parsed = _manifest(repo, path, max_file_bytes)
        if parsed is None:
            continue
        name, dependencies, scripts = parsed
        manifest = f"file:{path.as_posix()}"
        if isinstance(name, str) and name:
            project = graph.add_node("project", name, f"Python project {name}")
            graph.add_edge(manifest, project, "defines", evidence=path.as_posix())
            graph.add_finding(f"Python project `{name}` — `{path.as_posix()}`.")
        else:
            project = manifest
        if isinstance(dependencies, list):
            for dependency in dependencies:
                _dependency(graph, project, dependency, path.as_posix())
        for script, target in sorted(scripts.items()):
            entry = graph.add_node("entry", f"{path}:{script}", f"Python script {script}")
            graph.add_edge(manifest, entry, "declares", evidence=path.as_posix())
            target_module = target.split(":", 1)[0].strip()
            destination = _resolve(target_module, modules)
            if destination is not None:
                graph.add_edge(entry, f"file:{destination.as_posix()}", "entry point",
                               evidence=f"{path.as_posix()}: {script} = {target}")
            else:
                missing = graph.add_node("unresolved", target_module, target_module)
                graph.add_edge(entry, missing, "entry point", "unresolved",
                               f"{path.as_posix()}: {script} = {target}")
            graph.add_finding(f"Python script `{script}` → `{target}` — `{path.as_posix()}`.")

    for path in requirement_paths:
        source = _read(repo, path, max_file_bytes)
        if source is None:
            continue
        for line_number, line in enumerate(source.splitlines(), 1):
            dependency = line.split("#", 1)[0].strip()
            if dependency and not dependency.startswith(("-", ".", "/")):
                _dependency(graph, f"file:{path.as_posix()}", dependency,
                            f"{path.as_posix()}:{line_number}")

    inferred = set()
    for path in python_files:
        source = _read(repo, path, max_file_bytes)
        if source is None:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        source_id = f"file:{path.as_posix()}"
        module = _module_names(path)[-1] if _module_names(path) else ""
        for name, relative, uncertain, line_number, fallback in _imports(tree, path, module):
            destination = _resolve(name, modules)
            if destination is None and fallback:
                destination = _resolve(fallback, modules)
                if destination is not None:
                    uncertain = True
            evidence = f"{path.as_posix()}:{line_number}"
            if destination is not None:
                graph.add_edge(source_id, f"file:{destination.as_posix()}", "imports",
                               "uncertain" if uncertain else "internal", evidence)
            else:
                status = "uncertain" if uncertain else "unresolved" if relative else "external"
                target = graph.add_node(status, name or "?", name or "?")
                graph.add_edge(source_id, target, "imports", status, evidence)
                if status == "external" and name not in inferred:
                    inferred.add(name)
                    graph.add_finding(f"Inferred import `{name}` — `{evidence}`.")

def _dependency(graph, source: str, value, evidence: str) -> None:
    if not isinstance(value, str):
        return
    requirement = value.strip()
    match = DEPENDENCY_NAME.match(requirement)
    if not match:
        return
    name = match.group().lower().replace("_", "-")
    target = graph.add_node("dependency", name, name)
    graph.add_edge(source, target, "depends on", "external", evidence)
    graph.add_finding(f"Declared dependency `{requirement}` — `{evidence}`.")
