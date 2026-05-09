#!/usr/bin/env python3
"""Build an M8 organic texture regeneration queue status report."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DEFAULT_QUEUE = ROOT / "jobs/comfy_texture_regen_candidates.json"
DEFAULT_JSON = ROOT / "docs/M8_ORGANIC_REGEN_QUEUE_STATUS.json"
DEFAULT_MD = ROOT / "docs/M8_ORGANIC_REGEN_QUEUE_STATUS_2026_05_08.md"


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def classify(candidate: dict[str, Any]) -> tuple[str, str]:
    latest = candidate.get("latest_tested_candidate")
    if not latest:
        return (
            "queued_untested",
            "Generate the first candidate, then run seam/PBR QA, visual veto, noise audit, and terrain-context review.",
        )
    status = str(latest.get("status", ""))
    if status == "terrain_context_candidate_pass_not_promoted":
        return (
            "sidecar_candidate_needs_runtime_trials",
            "Keep quarantined; run M4/M7 rerender trials and only promote if terrain context stays clean.",
        )
    if status == "visual_rejected_no_sidecar_stage":
        return (
            "visual_rejected",
            "Do not stage; revise prompt and require visual landmark/object veto before any sidecar material.",
        )
    return (
        status or "latest_status_unknown",
        "Review latest candidate metadata and assign a concrete next gate.",
    )


def row_for(candidate: dict[str, Any]) -> dict[str, Any]:
    status, next_action = classify(candidate)
    latest = candidate.get("latest_tested_candidate", {})
    attempts = latest.get("attempts", [])
    latest_candidate_id = latest.get("id", "")
    if not latest_candidate_id and attempts:
        latest_candidate_id = "%d rejected attempts through %s" % (
            len(attempts),
            attempts[-1].get("id", "unknown"),
        )
    return {
        "material_id": candidate["material_id"],
        "regen_id": candidate["regen_id"],
        "current_source_asset_id": candidate["current_source_asset_id"],
        "status": status,
        "failure_mode": candidate["failure_mode"],
        "next_action": next_action,
        "latest_candidate_id": latest_candidate_id,
        "latest_review_doc": latest.get("review_doc", latest.get("terrain_context_review", {}).get("doc", "")),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
    keys = [
        "sidecar_candidate_needs_runtime_trials",
        "visual_rejected",
        "queued_untested",
        "latest_status_unknown",
    ]
    counts = {key: 0 for key in keys}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    counts["total"] = len(rows)
    return counts


def write_markdown(queue: dict[str, Any], rows: list[dict[str, Any]], summary: dict[str, int], out_md: Path) -> None:
    lines = [
        "# M8 Organic Regeneration Queue Status",
        "",
        f"Date: {date.today().isoformat()}",
        "",
        "This is the current execution board for the M8 ComfyUI/`aaa_texture.py`",
        "organic source-material cleanup lane. It turns the queue JSON into an",
        "explicit status report so we do not treat strict texture QA as visual",
        "promotion.",
        "",
        "## Summary",
        "",
        f"- Total blockers: `{summary['total']}`",
        f"- Sidecar candidates needing runtime trials: `{summary.get('sidecar_candidate_needs_runtime_trials', 0)}`",
        f"- Visual rejected: `{summary.get('visual_rejected', 0)}`",
        f"- Queued untested: `{summary.get('queued_untested', 0)}`",
        "",
        "## Gate",
        "",
    ]
    for gate in queue.get("shared_gate", []):
        lines.append(f"- {gate}")
    lines.extend(
        [
            "",
            "Organic-specific hard rule:",
            "",
            "- A candidate may pass seam/PBR QA and still fail if it contains",
            "  object-like plants, landmark blotches, boxy sod panels, bright patch",
            "  islands, or visible repeated leaf/grass clumps.",
            "",
            "## Queue",
            "",
            "| Material | Status | Latest | Next Action |",
            "|----------|--------|--------|-------------|",
        ]
    )
    for row in rows:
        latest = row["latest_candidate_id"] or "-"
        lines.append(
            f"| `{row['material_id']}` | `{row['status']}` | `{latest}` | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Next Execution Order",
            "",
            "1. Run M4/M7 runtime trials for `m8_grassland_grass_calm_v3` while it",
            "   remains sidecar-only.",
            "2. Retry `grass` only after a prompt revision explicitly suppresses",
            "   patch islands, box panels, dark landmarks, and individual plant objects.",
            "3. Generate the untested blockers in queue order:",
            "   `temperate_forest_grass`, `tundra_moss`, then `tundra_lichen`.",
            "4. Rebuild this report after every candidate attempt.",
            "",
            "## Command",
            "",
            "```powershell",
            "python world3/pipeline/build_m8_regen_queue_status.py",
            "```",
        ]
    )
    write_lf(out_md, "\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--out-json", default=str(DEFAULT_JSON))
    ap.add_argument("--out-md", default=str(DEFAULT_MD))
    args = ap.parse_args()

    queue_path = Path(args.queue)
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    rows = [row_for(candidate) for candidate in queue.get("candidates", [])]
    summary = summarize(rows)
    out = {
        "version": 1,
        "updated": date.today().isoformat(),
        "kind": "m8_organic_regen_queue_status",
        "source_queue": repo_rel(queue_path),
        "summary": summary,
        "rows": rows,
    }
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    write_lf(out_json, json.dumps(out, indent=2) + "\n")
    write_markdown(queue, rows, summary, out_md)
    print(f"wrote {repo_rel(out_json)}")
    print(f"wrote {repo_rel(out_md)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
