#!/usr/bin/env python3
"""Build the M14 close-play terrain-quality board.

M14 turns the earlier M8 organic material queue into a post-parity production
quality lane. This report keeps the generator bakeoff, visual veto, gameplay
bands, and M13 promotion gate in one place.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
QUEUE = ROOT / "jobs/comfy_texture_regen_candidates.json"
PLAN = ROOT / "jobs/m14_texture_bakeoff_plan.json"
OUT_JSON = ROOT / "docs/M14_CLOSE_PLAY_QUALITY_BOARD.json"
OUT_MD = ROOT / "docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md"


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify(candidate: dict[str, Any]) -> tuple[str, str]:
    latest = candidate.get("latest_tested_candidate")
    material_id = str(candidate.get("material_id", ""))
    if not latest:
        return (
            "queued_for_bakeoff",
            "Run FLUX/Aura/SD batches, then visual-veto before terrain staging.",
        )

    trial = latest.get("m14_runtime_trial")
    if trial:
        return (
            str(trial.get("status", "m14_runtime_trial_recorded")),
            "Keep sidecar-only; use M14 bakeoff lanes for stronger close-play candidates.",
        )

    prompt_review = latest.get("m14_prompt_bakeoff_review")
    if prompt_review:
        return (
            str(prompt_review.get("status", "m14_prompt_review_recorded")),
            str(prompt_review.get("next_action", "Use M14 review findings for the next prompt pass.")),
        )

    status = str(latest.get("status", ""))
    if status == "terrain_context_candidate_pass_not_promoted":
        return (
            "sidecar_needs_m14_runtime_trials",
            "Run M4/M7-style close/medium/iso/topdown rerenders before any promotion.",
        )
    if status == "visual_rejected_no_sidecar_stage":
        return (
            "prompt_rework_before_bakeoff",
            "Revise prompt from the best failed direction, then rerun active model lanes.",
        )
    return (
        status or "status_unknown",
        f"Inspect latest metadata for {material_id} and assign a concrete M14 gate.",
    )


def latest_label(candidate: dict[str, Any]) -> str:
    latest = candidate.get("latest_tested_candidate") or {}
    if latest.get("id"):
        return str(latest["id"])
    prompt_review = latest.get("m14_prompt_bakeoff_review") or {}
    prompt_attempts = prompt_review.get("attempts") or []
    if prompt_attempts:
        return f"{len(prompt_attempts)} M14 attempts through {prompt_attempts[-1].get('id', 'unknown')}"
    attempts = latest.get("attempts") or []
    if attempts:
        return f"{len(attempts)} attempts through {attempts[-1].get('id', 'unknown')}"
    return "-"


def build_rows(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in queue.get("candidates", []):
        status, next_action = classify(candidate)
        rows.append(
            {
                "material_id": candidate.get("material_id", ""),
                "regen_id": candidate.get("regen_id", ""),
                "current_source_asset_id": candidate.get("current_source_asset_id", ""),
                "failure_mode": candidate.get("failure_mode", ""),
                "latest": latest_label(candidate),
                "m14_status": status,
                "next_action": next_action,
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"total": len(rows)}
    for row in rows:
        status = str(row["m14_status"])
        counts[status] = counts.get(status, 0) + 1
    return counts


def collect() -> dict[str, Any]:
    queue = load_json(QUEUE)
    plan = load_json(PLAN)
    rows = build_rows(queue)
    return {
        "updated": date.today().isoformat(),
        "source_queue": repo_rel(QUEUE),
        "bakeoff_plan": repo_rel(PLAN),
        "view_contract": plan["view_contract"],
        "promotion_gate": plan["promotion_gate"],
        "active_model_lanes": plan["active_model_lanes"],
        "parked_model_lanes": plan["parked_model_lanes"],
        "rejected_model_lanes": plan["rejected_model_lanes"],
        "candidate_gate": plan["candidate_gate"],
        "summary": summarize(rows),
        "rows": rows,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M14 Close-Play Quality Board - 2026-05-10",
        "",
        "## Purpose",
        "",
        "M14 is the production-facing terrain-quality lane after M13. It does not",
        "promote assets by itself; it feeds candidates into the M13 gate after",
        "close, medium, iso, and topdown review.",
        "",
        "## Summary",
        "",
        f"- Materials tracked: `{report['summary']['total']}`.",
    ]
    for key, value in sorted(report["summary"].items()):
        if key == "total":
            continue
        lines.append(f"- `{key}`: `{value}`.")

    lines.extend(
        [
            "",
            "## Active Model Lanes",
            "",
            "| Lane | Status | Role | Variants | Prompt Policy |",
            "|------|--------|------|----------|---------------|",
        ]
    )
    for lane in report["active_model_lanes"]:
        lines.append(
            "| `{id}` | `{status}` | {role} | `{variants}` | {policy} |".format(
                id=lane["id"],
                status=lane["status"],
                role=lane["role"],
                variants=lane["variants_per_material"],
                policy=lane["prompt_policy"],
            )
        )

    lines.extend(
        [
            "",
            "## Material Board",
            "",
            "| Material | Status | Latest | Next Action | Failure Mode |",
            "|----------|--------|--------|-------------|--------------|",
        ]
    )
    for row in report["rows"]:
        lines.append(
            "| `{material}` | `{status}` | `{latest}` | {next_action} | {failure} |".format(
                material=row["material_id"],
                status=row["m14_status"],
                latest=row["latest"],
                next_action=row["next_action"],
                failure=row["failure_mode"],
            )
        )

    lines.extend(["", "## Candidate Gate", ""])
    for gate in report["candidate_gate"]:
        lines.append(f"- {gate}")

    lines.extend(
        [
            "",
            "## Parked Or Rejected Lanes",
            "",
            "| Lane | Status | Reason |",
            "|------|--------|--------|",
        ]
    )
    for lane in report["parked_model_lanes"] + report["rejected_model_lanes"]:
        lines.append(f"| `{lane['id']}` | `{lane['status']}` | {lane['reason']} |")

    lines.extend(
        [
            "",
            "## Next Move",
            "",
            "1. Run close/medium/iso/topdown runtime trials for",
            "   any future sidecar candidates before M13 promotion.",
            "2. Convert `grass` from a monolithic plant-photo tile target into a",
            "   layered substrate/detail target, then rerun the active FLUX/Aura/SD",
            "   lanes only against that corrected brief.",
            "3. Generate first bakeoff batches for `temperate_forest_grass`,",
            "   `tundra_moss`, and `tundra_lichen` in queue order.",
            "4. Feed survivors back into `production_promotion_candidates.json` only",
            "   after the M14 board and gameplay-band captures support them.",
            "",
            "Regenerate:",
            "",
            "```powershell",
            "python world3/pipeline/build_m14_close_play_quality_board.py",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    report = collect()
    write_lf(OUT_JSON, json.dumps(report, indent=2) + "\n")
    write_lf(OUT_MD, markdown(report))
    print(repo_rel(OUT_JSON))
    print(repo_rel(OUT_MD))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
