#!/usr/bin/env python3
"""Audit source-stack review scenes for M12 view-mode parity.

M12 is about making walk/close, medium, iso, and topdown evidence use the same
terrain/source/material contract instead of drifting into separate pipelines.
This script inventories review scenes and capture wrappers so the roadmap can
track parity as data.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCENE_DIR = ROOT / "scenes/review"
OUT_JSON = ROOT / "docs/captures/review/m12_view_mode_parity_audit.json"
OUT_MD = ROOT / "docs/M12_VIEW_MODE_PARITY_AUDIT_2026_05_10.md"

RE_EXT = re.compile(r'^\[ext_resource .*path="([^"]+)".*id="([^"]+)".*\]$')
RE_ASSIGN = re.compile(r"^([A-Za-z0-9_]+)\s*=\s*(.+)$")
RE_QUOTED = re.compile(r'^"(.+)"$')

REQUIRED_BANDS = ["close", "medium", "iso", "topdown"]


def parse_value(raw: str) -> str:
    raw = raw.strip()
    match = RE_QUOTED.match(raw)
    if match:
        return match.group(1)
    return raw


def parse_scene(path: Path) -> dict[str, Any]:
    ext_resources: dict[str, str] = {}
    assignments: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        ext = RE_EXT.match(line)
        if ext:
            ext_resources[ext.group(2)] = ext.group(1)
            continue
        assign = RE_ASSIGN.match(line)
        if assign:
            assignments[assign.group(1)] = parse_value(assign.group(2))
    return {"path": path, "ext_resources": ext_resources, "assignments": assignments}


def band_for(path: Path, output_path: str) -> str:
    name = f"{path.stem} {output_path}".lower()
    if "topdown" in name:
        return "topdown"
    if "iso" in name:
        return "iso"
    if "close" in name:
        return "close"
    if "medium" in name:
        return "medium"
    if "_3d" in name or "3d_" in name:
        return "medium"
    return "unknown"


def workflow_id_from_scene(scene_path: str) -> str:
    stem = Path(scene_path).stem
    if stem.startswith("source_stack_"):
        stem = stem.removeprefix("source_stack_")
    if stem.endswith("_tour"):
        stem = stem.removesuffix("_tour")
    return stem


def collect() -> dict[str, Any]:
    workflows: dict[str, dict[str, Any]] = {}
    capture_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in sorted(SCENE_DIR.glob("source_stack*_tour.tscn")):
        parsed = parse_scene(path)
        assignments = parsed["assignments"]
        workflow_id = workflow_id_from_scene(path.name)
        workflows[workflow_id] = {
            "id": workflow_id,
            "scene": "res://scenes/review/" + path.name,
            "tour_profile": assignments.get("tour_profile", "standard"),
            "material_path": assignments.get("material_path", ""),
            "heightmap_path": assignments.get("heightmap_path", ""),
            "meta_path": assignments.get("meta_path", ""),
            "splat_weights_path": assignments.get("splat_weights_path", ""),
            "source_macro_albedo_override_path": assignments.get("source_macro_albedo_override_path", ""),
            "source_macro_valid_mask_override_path": assignments.get("source_macro_valid_mask_override_path", ""),
            "transition_rule_id": assignments.get("transition_rule_id", ""),
            "captures": [],
        }

    for path in sorted(SCENE_DIR.glob("capture_source_stack*.tscn")):
        parsed = parse_scene(path)
        assignments = parsed["assignments"]
        scene_res = parsed["ext_resources"].get("scene", "")
        workflow_id = workflow_id_from_scene(scene_res)
        output_path = assignments.get("output_path", "")
        capture = {
            "scene": "res://scenes/review/" + path.name,
            "target_scene": scene_res,
            "output_path": output_path,
            "band": band_for(path, output_path),
            "initial_tour_index": assignments.get("initial_tour_index", assignments.get("initial_view_index", "")),
        }
        capture_map[workflow_id].append(capture)

    for workflow_id, workflow in workflows.items():
        captures = capture_map.get(workflow_id, [])
        workflow["captures"] = captures
        bands = sorted({cap["band"] for cap in captures if cap["band"] != "unknown"})
        missing = [band for band in REQUIRED_BANDS if band not in bands]
        workflow["capture_bands"] = bands
        workflow["missing_bands"] = missing
        workflow["has_source_stack_contract"] = bool(
            workflow["material_path"]
            and workflow["heightmap_path"]
            and workflow["meta_path"]
            and workflow["source_macro_albedo_override_path"]
        )
        workflow["has_runtime_splat_weights"] = bool(workflow["splat_weights_path"])
        workflow["parity_status"] = "full_capture_set" if not missing else "missing_" + "_".join(missing)

    return {
        "updated": date.today().isoformat(),
        "purpose": "M12 view-mode parity audit",
        "required_bands": REQUIRED_BANDS,
        "workflows": [workflows[key] for key in sorted(workflows)],
    }


def markdown(report: dict[str, Any]) -> str:
    workflows = report["workflows"]
    full = [w for w in workflows if not w["missing_bands"]]
    with_contract = [w for w in workflows if w["has_source_stack_contract"]]
    with_splat = [w for w in workflows if w["has_runtime_splat_weights"]]
    runtime_proof = next((w for w in workflows if w["id"] == "m12_runtime_fourway"), None)

    if runtime_proof:
        status_lines = [
            "M12 runtime parity checkpoint. The audit now includes a representative",
            "runtime proof that uses one source/material/height/splat contract across",
            "true walk close/medium bands and gallery-style iso/topdown bands.",
            "",
            "This is stronger than the initial camera-template audit, but it does not",
            "retrofit every historical gallery script. `RegionGalleryCapture.gd` remains",
            "a legacy bulk-region tool until we decide it needs source-stack promotion.",
        ]
    else:
        status_lines = [
            "Initial M12 audit. This is an inventory, not closure.",
            "",
            "M12 starts from the accepted M10/M11 workflow scenes and asks whether the",
            "same terrain/material/source decision can be reviewed in close, medium, iso,",
            "and topdown bands without switching pipelines.",
        ]

    lines = [
        "# M12 View-Mode Parity Audit - 2026-05-10",
        "",
        "## Status",
        "",
        *status_lines,
        "",
        "## Summary",
        "",
        f"- Source-stack tour scenes: `{len(workflows)}`.",
        f"- Scenes with complete close/medium/iso/topdown captures: `{len(full)}`.",
        f"- Scenes with source-stack macro contract: `{len(with_contract)}`.",
        f"- Scenes with runtime splat weights: `{len(with_splat)}`.",
        "",
        "## Workflow Inventory",
        "",
        "| Workflow | Profile | Bands | Missing | Runtime splat | Notes |",
        "|----------|---------|-------|---------|---------------|-------|",
    ]
    for w in workflows:
        bands = ", ".join(w["capture_bands"]) if w["capture_bands"] else "-"
        missing = ", ".join(w["missing_bands"]) if w["missing_bands"] else "none"
        splat = "yes" if w["has_runtime_splat_weights"] else "no"
        notes = []
        if not w["has_source_stack_contract"]:
            notes.append("missing source-stack macro override")
        if not w["captures"]:
            notes.append("tour only")
        if w["id"] in {"m11_fourway_corner", "m11_junction", "ecotone_layer", "real_procedural"}:
            notes.append("current workflow evidence")
        lines.append(
            f"| `{w['id']}` | `{w['tour_profile']}` | {bands} | {missing} | {splat} | "
            + ("; ".join(notes) if notes else "-")
            + " |"
        )

    lines.extend(
        [
            "",
            "## Findings",
            "",
            "- The newest M10/M11 proof scenes already have the capture shape M12 wants:",
            "  close, medium, iso, and topdown review bands.",
            "- Older cross-source and seam-integration proofs often have only one 3D",
            "  capture, which is acceptable as historical evidence but not parity closure.",
            "- `RegionGalleryCapture.gd` still uses per-mode whole-kit material swaps, so",
            "  the old bulk gallery remains a legacy path rather than parity evidence.",
            "",
            "## M12 Parity Template",
            "",
            "`source_stack_m12_parity_fourway_tour.tscn` now exposes the accepted",
            "four-way M11 proof through named camera bands: close play, medium play,",
            "iso/tactical, and topdown/map. It uses the same source/material/height/splat",
            "contract for every band.",
            "",
        ]
    )

    if runtime_proof:
        lines.extend(
            [
                "## M12 Runtime Parity Proof",
                "",
                "`source_stack_m12_runtime_fourway_tour.tscn` instantiates the accepted",
                "four-way proof through the runtime path: a `CharacterBody3D` with",
                "`Walker.gd`, streamed `ChunkLoader` chunks, collision chunks, the accepted",
                "four-way material, source macro/mask overrides, and runtime splat weights.",
                "",
                "Its close and medium captures are true walk-runtime bands. Its iso and",
                "topdown captures are gallery-style review bands over the same loaded",
                "runtime contract, not per-mode kit material swaps.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "- Walk-mode parity is not solved by capture wrappers alone. The next real",
                "  M12 implementation step is to bind the same material/source stack into",
                "  a walk scene and capture close/medium bands from that path.",
                "",
            ]
        )

    next_lines = [
        "## Next M12 Step",
        "",
    ]
    if runtime_proof:
        next_lines.extend(
            [
                "Use the runtime parity proof for live review. If it passes, M12 can close",
                "as representative parity and the full `RegionGalleryCapture.gd` retrofit",
                "can become follow-up bulk-gallery work instead of a milestone blocker.",
            ]
        )
    else:
        next_lines.extend(
            [
                "Use the parity template as the control scene, then bring one true",
                "walk-mode scene and one gallery/region view onto the same",
                "source-stack/splat contract. That is the remaining path divergence M12",
                "needs to resolve.",
            ]
        )
    lines.extend(
        next_lines
        + [
            "",
            "Regenerate:",
            "",
            "```powershell",
            "python world3/pipeline/audit_m12_view_mode_parity.py",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    report = collect()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(markdown(report), encoding="utf-8")
    print(OUT_MD.relative_to(ROOT))
    print(OUT_JSON.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
