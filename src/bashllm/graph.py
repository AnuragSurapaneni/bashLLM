"""Static architecture graph and extension point for language analyzers.

Analyzers in ``bashllm.analyzers`` may define
``analyze(repo, files, max_file_bytes, graph)``. ``files`` contains scanned
repository-relative Paths. Add nodes with ``graph.add_node(kind, key, label)``
and relationships with ``graph.add_edge(source, target, relation, status,
evidence)``; source and target are node IDs returned by add_node. Edges with
the same endpoints, relation, and status are deduplicated. Analyzers can call
``graph.add_finding(text)`` to add a concise, evidence-backed briefing finding.
"""

import importlib
import json
import pkgutil
from collections import defaultdict
from pathlib import Path


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self._extra_findings = []

    def add_node(self, kind: str, key: str, label: str) -> str:
        node_id = f"{kind}:{key}"
        self.nodes[node_id] = (kind, label)
        return node_id

    def add_edge(self, source: str, target: str, relation: str,
                 status: str = "internal", evidence: str | None = None) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError("graph edge refers to an unknown node")
        key = (source, target, relation, status)
        if key not in self.edges or (self.edges[key] is None and evidence):
            self.edges[key] = evidence

    def add_finding(self, text: str) -> None:
        if text not in self._extra_findings:
            self._extra_findings.append(text)

    def dot(self) -> str:
        identifiers = {node: f"n{index}" for index, node in enumerate(sorted(self.nodes))}
        lines = ["digraph bashllm {", "  rankdir=LR;"]
        for node in sorted(self.nodes):
            kind, label = self.nodes[node]
            lines.append(f"  {identifiers[node]} [label={json.dumps(label, ensure_ascii=True)}, "
                         f"shape={('folder' if kind == 'directory' else 'box' if kind == 'file' else 'ellipse')}];")
        for (source, target, relation, status), evidence in sorted(self.edges.items()):
            label = relation if status == "internal" else f"{relation} ({status})"
            attributes = [f"label={json.dumps(label, ensure_ascii=True)}"]
            if status != "internal":
                attributes.append("style=dashed")
                attributes.append(f"color={json.dumps({'external': 'blue', 'unresolved': 'red', 'uncertain': 'orange', 'intrinsic': 'purple'}.get(status, 'gray'))}")
            if evidence:
                attributes.append(f"tooltip={json.dumps(evidence, ensure_ascii=True)}")
            lines.append(f"  {identifiers[source]} -> {identifiers[target]} [{', '.join(attributes)}];")
        return "\n".join([*lines, "}", ""])

    def mermaid(self, max_nodes: int = 24, max_edges: int = 30) -> str:
        dependency_relations = {"imports", "depends on", "uses", "includes"}
        selected_set = set()
        selected_edges = []
        ordered_edges = sorted(self.edges, key=lambda edge: (
            edge[2] not in dependency_relations, edge[3] != "internal", edge))
        for edge in ordered_edges:
            if len(selected_edges) >= max_edges:
                break
            source, target = edge[:2]
            if len(selected_set | {source, target}) > max_nodes:
                continue
            selected_set.update((source, target))
            selected_edges.append(edge)
        for node in sorted(self.nodes):
            if len(selected_set) >= max_nodes:
                break
            selected_set.add(node)
        selected = sorted(selected_set)
        identifiers = {node: f"n{index}" for index, node in enumerate(selected)}
        lines = ["```mermaid", "flowchart LR"]
        for node in selected:
            label = self.nodes[node][1].replace("&", "&amp;").replace('"', "&quot;")
            label = label.replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")
            lines.append(f'    {identifiers[node]}["{label}"]')
        for source, target, relation, status in selected_edges:
            label = relation if status == "internal" else f"{relation}: {status}"
            lines.append(f"    {identifiers[source]} -->|{label}| {identifiers[target]}")
        return "\n".join([*lines, "```"])

    def findings(self) -> list[str]:
        findings = []
        for status in ("external", "unresolved", "uncertain"):
            edges = [edge for edge in self.edges if edge[3] == status]
            if edges:
                targets = sorted({self.nodes[edge[1]][1] for edge in edges})
                examples = ", ".join(targets[:5])
                if len(targets) > 5:
                    examples += f", and {len(targets) - 5} more"
                findings.append(f"{len(edges)} {status} relationship(s): {examples}.")
        cycles = self._cycles()
        for cycle in cycles[:5]:
            labels = ", ".join(self.nodes[node][1] for node in cycle[:8])
            if len(cycle) > 8:
                labels += f", and {len(cycle) - 8} more nodes"
            findings.append(f"Dependency cycle: {labels}.")
        if len(cycles) > 5:
            findings.append(f"{len(cycles) - 5} additional dependency cycles; see GRAPH.dot.")
        findings.extend(self._extra_findings)
        return findings

    def _cycles(self) -> list[list[str]]:
        adjacency = defaultdict(set)
        reverse = defaultdict(set)
        for source, target, relation, status in self.edges:
            if relation in {"imports", "depends on", "uses", "includes"} and status == "internal":
                adjacency[source].add(target)
                reverse[target].add(source)
        seen = set()
        finished = []
        for start in sorted(set(adjacency) | set(reverse)):
            if start in seen:
                continue
            seen.add(start)
            stack = [(start, iter(sorted(adjacency[start])))]
            while stack:
                node, neighbors = stack[-1]
                target = next(neighbors, None)
                if target is None:
                    finished.append(node)
                    stack.pop()
                elif target not in seen:
                    seen.add(target)
                    stack.append((target, iter(sorted(adjacency[target]))))
        cycles = []
        assigned = set()
        for start in reversed(finished):
            if start in assigned:
                continue
            component = []
            pending = [start]
            assigned.add(start)
            while pending:
                node = pending.pop()
                component.append(node)
                for source in sorted(reverse[node]):
                    if source not in assigned:
                        assigned.add(source)
                        pending.append(source)
            if len(component) > 1 or start in adjacency[start]:
                cycles.append(sorted(component))
        return sorted(cycles)


def build_graph(repo: Path, directories: list[str], files: list[Path],
                max_file_bytes: int) -> Graph:
    graph = Graph()
    root = graph.add_node("directory", ".", ".")
    for directory in directories:
        key = directory.rstrip("/")
        node = graph.add_node("directory", key, directory)
        parent = Path(key).parent.as_posix()
        graph.add_edge(f"directory:{parent}" if parent != "." else root, node, "contains")
    for path in files:
        key = path.as_posix()
        node = graph.add_node("file", key, key)
        parent = path.parent.as_posix()
        graph.add_edge(f"directory:{parent}" if parent != "." else root, node, "contains")
    _language_analyzers(repo, files, max_file_bytes, graph)
    return graph


def _language_analyzers(repo: Path, files: list[Path], max_file_bytes: int,
                        graph: Graph) -> None:
    try:
        package = importlib.import_module("bashllm.analyzers")
    except ModuleNotFoundError as error:
        if error.name == "bashllm.analyzers":
            return
        raise
    for module_info in sorted(pkgutil.iter_modules(package.__path__), key=lambda item: item.name):
        module = importlib.import_module(f"bashllm.analyzers.{module_info.name}")
        analyze = getattr(module, "analyze", None)
        if analyze is not None:
            analyze(repo, files, max_file_bytes, graph)
