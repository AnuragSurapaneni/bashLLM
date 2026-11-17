"""Deterministic, bounded, static repository briefing."""

import json
import os
from pathlib import Path

from bashllm.graph import build_graph


SKIP_DIRECTORIES = {
    ".git", ".bashllm", ".venv", "venv", "node_modules", "target",
    "build", "dist", "__pycache__", ".pytest_cache",
}
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".mts", ".cts", ".rs", ".go",
    ".f", ".for", ".f77", ".f90", ".f95", ".f03", ".f08",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".java", ".rb",
    ".sh", ".swift", ".kt", ".scala", ".jl", ".lua",
}
MANIFESTS = {
    "pyproject.toml", "setup.py", "requirements.txt", "package.json",
    "Cargo.toml", "go.mod", "fpm.toml", "Makefile", "makefile",
    "CMakeLists.txt", "meson.build", "build.gradle", "pom.xml",
}
MAX_OMISSION_DETAILS = 20
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".mts": "TypeScript", ".cts": "TypeScript", ".rs": "Rust",
    ".go": "Go", ".f": "Fortran", ".for": "Fortran",
    ".f77": "Fortran", ".f90": "Fortran", ".f95": "Fortran",
    ".f03": "Fortran", ".f08": "Fortran",
}


def _source(path: Path) -> bool:
    return path.suffix.lower() in SOURCE_SUFFIXES


def _test(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return ("tests" in parts or "test" in parts or name.startswith("test_")
            or name.endswith("_test.py") or name.endswith(".test.js")
            or name.endswith(".test.ts") or name.endswith(".spec.js")
            or name.endswith(".spec.ts"))


def _entry(path: Path) -> bool:
    name = path.name.lower()
    return (name in {"main.py", "__main__.py", "app.py", "manage.py", "main.js",
                     "index.js", "main.ts", "index.ts", "main.rs", "main.go",
                     "main.f90", "main.f", "main.for"}
            or (len(path.parts) >= 2 and path.parts[-2] == "bin"))


def _add_omission(omissions: list[str], counts: dict[str, int], relative: str, reason: str) -> None:
    counts[reason] = counts.get(reason, 0) + 1
    if len(omissions) < MAX_OMISSION_DETAILS:
        omissions.append(f"{relative}: {reason}")


def _scan(repo: Path, max_files: int, max_directories: int, max_depth: int):
    directories = []
    files = []
    omissions = []
    omission_counts = {}
    for current, child_dirs, child_files in os.walk(repo, topdown=True, followlinks=False):
        relative_dir = Path(current).relative_to(repo)
        depth = len(relative_dir.parts)
        kept = []
        for name in sorted(child_dirs):
            relative = (relative_dir / name).as_posix()
            child = Path(current) / name
            if name == ".bashllm":
                continue
            if name in SKIP_DIRECTORIES:
                _add_omission(omissions, omission_counts, f"{relative}/", "ignored directory")
            elif child.is_symlink():
                _add_omission(omissions, omission_counts, f"{relative}/", "symbolic link")
            elif depth >= max_depth:
                _add_omission(omissions, omission_counts, f"{relative}/", "depth limit")
            elif len(directories) >= max_directories:
                _add_omission(omissions, omission_counts, f"{relative}/", "directory limit")
            else:
                kept.append(name)
                directories.append(f"{relative}/")
        child_dirs[:] = kept
        for name in sorted(child_files):
            relative = (relative_dir / name).as_posix()
            path = Path(current) / name
            if path.is_symlink():
                _add_omission(omissions, omission_counts, relative, "symbolic link")
            elif len(files) >= max_files:
                _add_omission(omissions, omission_counts, relative, "file limit")
            elif path.is_file():
                files.append(Path(relative))
    return sorted(directories), sorted(files, key=lambda path: path.as_posix()), omissions, omission_counts


def _commands(repo: Path, files: list[Path], max_file_bytes: int):
    entries = []
    names = {path.name for path in files}
    for path in files:
        name = path.name
        evidence = path.as_posix()
        if name == "pyproject.toml" or name == "setup.py":
            entries.append(("python3 -m pip install .", evidence))
        elif name == "Cargo.toml":
            entries.extend((("cargo build", evidence), ("cargo test", evidence)))
        elif name == "go.mod":
            entries.append(("go test ./...", evidence))
        elif name == "fpm.toml":
            entries.extend((("fpm build", evidence), ("fpm test", evidence)))
        elif name in {"Makefile", "makefile"}:
            entries.append(("make", evidence))
        elif name == "CMakeLists.txt":
            entries.append(("cmake -S . -B build", evidence))
        elif name == "package.json":
            package = repo / path
            if package.stat().st_size > max_file_bytes:
                continue
            try:
                scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
            except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
                scripts = {}
            if isinstance(scripts, dict):
                for script in sorted(scripts):
                    if script in {"build", "test", "check", "lint"}:
                        entries.append((f"npm run {script}", evidence + f" (scripts.{script})"))
    if "pyproject.toml" in names and any(_test(path) for path in files):
        entries.append(("python3 -m unittest discover -s tests", "pyproject.toml; tests/ (suggested)"))
    return sorted(set(entries))


def build_briefing(repo: Path, max_files: int, max_directories: int,
                   max_depth: int, max_file_bytes: int):
    directories, files, omissions, omission_counts = _scan(repo, max_files, max_directories, max_depth)
    sources = [path for path in files if _source(path)]
    tests = [path for path in sources if _test(path)]
    entries = [path for path in sources if _entry(path) and path not in tests]
    manifests = [path for path in files if path.name in MANIFESTS]
    suffixes = {path.suffix.lower() for path in sources}
    languages = sorted({LANGUAGES[suffix] for suffix in suffixes if suffix in LANGUAGES})
    if sources and not languages:
        languages = ["Other or unrecognized"]
    for path in files:
        if not (_source(path) or path.name in MANIFESTS or path.name == "setup.cfg"
                or (path.name.startswith("requirements") and path.suffix == ".txt")):
            continue
        try:
            oversized = (repo / path).stat().st_size > max_file_bytes
        except OSError:
            continue
        if oversized:
            _add_omission(omissions, omission_counts, path.as_posix(), "content limit")
    commands = _commands(repo, files, max_file_bytes)
    graph = build_graph(repo, directories, files, max_file_bytes)

    def section(title: str, items: list[str]) -> list[str]:
        return [f"## {title}", "", *(f"- {item}" for item in items or ["None found within scan limits."]), ""]

    lines = ["# Repository briefing", "", f"Repository: `{repo}`", "",
             "Static inspection only. Commands below are reported, not run.", "",
             f"Files scanned: {len(files)}; maximum: {max_files}. Directories scanned: {len(directories)}; "
             f"maximum: {max_directories}; maximum depth: {max_depth}.", ""]
    lines += section("Languages", languages)
    lines += section("Directories", [f"`{item}` (directory path)" for item in directories])
    lines += section("Source files", [f"`{path.as_posix()}`" for path in sources])
    lines += section("Likely entry points", [f"`{path.as_posix()}` (filename clue)" for path in entries])
    lines += section("Tests", [f"`{path.as_posix()}` (path or filename clue)" for path in tests])
    lines += section("Build and test commands", [f"`{command}` — `{evidence}`" for command, evidence in commands])
    lines += section("Manifests and build files", [f"`{path.as_posix()}`" for path in manifests])
    other = [path for path in files if path not in sources and path not in manifests]
    lines += section("Other files", [f"`{path.as_posix()}`" for path in other])
    lines += ["## Architecture graph", "", graph.mermaid(), "",
              f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} relationships. "
              "See `.bashllm/GRAPH.dot` for the complete graph.", ""]
    lines += section("Graph findings", graph.findings())
    units = {"file limit": "files", "directory limit": "directories",
             "depth limit": "directories", "ignored directory": "directories",
             "content limit": "files", "symbolic link": "paths"}
    lines += section("Omission counts", [
        f"{count} {units.get(reason, 'paths')} skipped by {reason}"
        for reason, count in sorted(omission_counts.items())
    ])
    omitted_detail_count = sum(omission_counts.values()) - len(omissions)
    detail = [f"`{item}`" for item in omissions]
    if omitted_detail_count:
        detail.append(f"{omitted_detail_count} additional omission details not shown.")
    lines += section("Omissions", detail)
    return "\n".join(lines), {
        "files_scanned": len(files), "directories_scanned": len(directories),
        "omissions": omissions, "omission_counts": omission_counts, "languages": languages,
    }, graph.dot()
