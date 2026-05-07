"""Validate NPC dialogue_start references against Yarn Spinner files.

Supported Yarn subset:
  title: NodeName
  ---
  body
  [[Choice text|TargetNode]]
  <<jump TargetNode>>
  ===

The parser is intentionally conservative. It catches missing start nodes,
missing jump/option targets, and unreachable nodes from NPC entry points.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

GAME_DATA = Path(r"D:\assets\game_data")
VALIDATED = GAME_DATA / "validated"
DEFAULT_DIALOGUE_DIR = GAME_DATA / "source" / "dialogue"
REPORTS = GAME_DATA / "reports"

TITLE_RE = re.compile(r"^title:\s*(?P<title>[A-Za-z0-9_.:-]+)\s*$")
JUMP_RE = re.compile(r"<<\s*jump\s+(?P<target>[A-Za-z0-9_.:-]+)\s*>>")
OPTION_RE = re.compile(r"\[\[[^\]|]+(?:\|(?P<target>[A-Za-z0-9_.:-]+))?\]\]")


def parse_yarn_file(path: Path) -> dict[str, set[str]]:
    text = path.read_text(encoding="utf-8")
    nodes: dict[str, set[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        title = TITLE_RE.match(line)
        if title:
            current = title.group("title")
            nodes.setdefault(current, set())
            continue
        if current is None:
            continue
        if line == "===":
            current = None
            continue
        for match in JUMP_RE.finditer(line):
            nodes[current].add(match.group("target"))
        for match in OPTION_RE.finditer(line):
            target = match.group("target")
            if target:
                nodes[current].add(target)
    return nodes


def load_yarn_graph(dialogue_dir: Path) -> tuple[dict[str, set[str]], list[str]]:
    graph: dict[str, set[str]] = {}
    warnings: list[str] = []
    if not dialogue_dir.exists():
        return graph, [f"dialogue directory does not exist: {dialogue_dir}"]
    for path in sorted(dialogue_dir.rglob("*.yarn")):
        try:
            parsed = parse_yarn_file(path)
        except OSError as exc:
            warnings.append(f"{path}: {exc}")
            continue
        for node, edges in parsed.items():
            if node in graph:
                warnings.append(f"duplicate Yarn node title: {node} in {path}")
            graph.setdefault(node, set()).update(edges)
    return graph, warnings


def load_npcs(validated: Path) -> list[dict[str, Any]]:
    path = validated / "npcs.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reachable_nodes(graph: dict[str, set[str]], starts: set[str]) -> set[str]:
    seen: set[str] = set()
    q: deque[str] = deque(starts)
    while q:
        node = q.popleft()
        if node in seen or node not in graph:
            continue
        seen.add(node)
        for target in graph[node]:
            if target not in seen:
                q.append(target)
    return seen


def validate_dialogue(validated: Path = VALIDATED, dialogue_dir: Path = DEFAULT_DIALOGUE_DIR) -> dict[str, Any]:
    graph, warnings = load_yarn_graph(dialogue_dir)
    npcs = load_npcs(validated)
    starts = {npc["dialogue_start"] for npc in npcs if npc.get("dialogue_start")}

    missing_starts = sorted(start for start in starts if start not in graph)
    missing_targets = []
    for node, targets in graph.items():
        for target in sorted(targets):
            if target not in graph:
                missing_targets.append({"source": node, "target": target})

    reachable = reachable_nodes(graph, starts)
    unreachable = sorted(set(graph) - reachable) if starts else sorted(set(graph))

    return {
        "schema": "yarn_link_report.v1",
        "dialogue_dir": str(dialogue_dir),
        "npc_count": len(npcs),
        "npc_dialogue_starts": sorted(starts),
        "node_count": len(graph),
        "edge_count": sum(len(v) for v in graph.values()),
        "missing_starts": missing_starts,
        "missing_targets": missing_targets,
        "unreachable_nodes": unreachable,
        "warnings": warnings,
        "ok": not missing_starts and not missing_targets,
    }


def write_report(report: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Yarn Link Report",
        "",
        f"- dialogue_dir: `{report['dialogue_dir']}`",
        f"- npc_count: {report['npc_count']}",
        f"- npc_dialogue_starts: {len(report['npc_dialogue_starts'])}",
        f"- node_count: {report['node_count']}",
        f"- edge_count: {report['edge_count']}",
        f"- ok: {report['ok']}",
        "",
        "## Missing NPC Start Nodes",
        "",
    ]
    lines.extend([f"- `{node}`" for node in report["missing_starts"]] or ["(none)"])
    lines.extend(["", "## Missing Yarn Targets", ""])
    lines.extend([f"- `{row['source']}` -> `{row['target']}`" for row in report["missing_targets"]] or ["(none)"])
    lines.extend(["", "## Unreachable Nodes", ""])
    lines.extend([f"- `{node}`" for node in report["unreachable_nodes"]] or ["(none)"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in report["warnings"]] or ["(none)"])
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validated", type=Path, default=VALIDATED)
    ap.add_argument("--dialogue-dir", type=Path, default=DEFAULT_DIALOGUE_DIR)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=REPORTS / "yarn_link_report.md")
    args = ap.parse_args()

    report = validate_dialogue(args.validated, args.dialogue_dir)
    write_report(report, args.report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[yarn_link] nodes={report['node_count']} starts={len(report['npc_dialogue_starts'])} "
          f"missing_starts={len(report['missing_starts'])} missing_targets={len(report['missing_targets'])}")
    print(f"[yarn_link] report -> {args.report}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

