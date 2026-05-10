#!/usr/bin/env python3
"""Audit workflow and asset candidates before production promotion.

The goal is to keep "accepted workflow evidence" separate from "production
promoted asset." The manifest records candidate status, required gameplay bands,
evidence files, and blockers. This script verifies references and writes a
human-readable audit table.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
MANIFEST = ROOT / "jobs/production_promotion_candidates.json"
OUT_JSON = ROOT / "docs/captures/review/production_promotion_audit.json"
OUT_MD = ROOT / "docs/PRODUCTION_PROMOTION_AUDIT_2026_05_10.md"


def repo_path(raw: str) -> Path:
    if not raw:
        return Path()
    if raw.startswith("res://"):
        return ROOT / raw.removeprefix("res://")
    if raw.startswith("world3/"):
        return REPO_ROOT / raw
    return REPO_ROOT / raw


def exists(raw: str) -> bool:
    if not raw:
        return True
    return repo_path(raw).exists()


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def audit_candidate(candidate: dict[str, Any], band_order: list[str]) -> dict[str, Any]:
    missing: list[str] = []
    required_capture_gaps: list[str] = []

    for field in ["source_doc", "scene"]:
        value = str(candidate.get(field, ""))
        if value and not exists(value):
            missing.append(f"{field}:{value}")

    for key, value in candidate.get("contract", {}).items():
        value = str(value)
        if value and not exists(value):
            missing.append(f"contract.{key}:{value}")

    captures: dict[str, str] = candidate.get("captures", {})
    for band, value in captures.items():
        value = str(value)
        if value and not exists(value):
            missing.append(f"capture.{band}:{value}")

    if candidate.get("type") == "workflow":
        for band in band_order:
            if band not in captures:
                required_capture_gaps.append(band)

    band_status: dict[str, str] = candidate.get("band_status", {})
    failed_bands = [band for band, status in band_status.items() if status == "fail"]
    conditional_bands = [band for band, status in band_status.items() if status == "conditional"]
    not_reviewed_bands = [band for band, status in band_status.items() if status == "not_reviewed"]

    if missing or required_capture_gaps:
        readiness = "blocked_missing_evidence"
    elif failed_bands:
        readiness = "blocked_failed_band"
    elif conditional_bands or not_reviewed_bands:
        readiness = "conditional"
    elif candidate.get("promotion_state") == "production_promoted":
        readiness = "production_promoted"
    elif candidate.get("promotion_state") == "production_candidate":
        readiness = "production_candidate_ready"
    else:
        readiness = "workflow_ready_not_production"

    return {
        "id": candidate.get("id", ""),
        "type": candidate.get("type", ""),
        "promotion_track": candidate.get("promotion_track", ""),
        "promotion_state": candidate.get("promotion_state", ""),
        "production_status": candidate.get("production_status", ""),
        "band_status": band_status,
        "missing_files": missing,
        "missing_required_captures": required_capture_gaps,
        "failed_bands": failed_bands,
        "conditional_bands": conditional_bands,
        "not_reviewed_bands": not_reviewed_bands,
        "readiness": readiness,
        "blockers": candidate.get("blockers", []),
        "source_doc": candidate.get("source_doc", ""),
        "scene": candidate.get("scene", ""),
    }


def collect() -> dict[str, Any]:
    manifest = load_manifest()
    band_order = list(manifest.get("band_order", ["close", "medium", "iso", "topdown"]))
    candidates = [
        audit_candidate(candidate, band_order)
        for candidate in manifest.get("candidates", [])
    ]
    return {
        "updated": date.today().isoformat(),
        "manifest": str(MANIFEST.relative_to(REPO_ROOT)),
        "candidate_count": len(candidates),
        "band_order": band_order,
        "readiness_counts": {
            readiness: sum(1 for c in candidates if c["readiness"] == readiness)
            for readiness in sorted({c["readiness"] for c in candidates})
        },
        "candidates": candidates,
    }


def band_cell(candidate: dict[str, Any], band_order: list[str]) -> str:
    statuses: dict[str, str] = candidate.get("band_status", {})
    return ", ".join(f"{band}:{statuses.get(band, '-')}" for band in band_order)


def markdown(report: dict[str, Any]) -> str:
    band_order = report["band_order"]
    lines = [
        "# Production Promotion Audit - 2026-05-10",
        "",
        "## Purpose",
        "",
        "This audit separates workflow acceptance from production promotion. A",
        "workflow can be accepted while still being blocked for production by close",
        "play quality, placeholder scatter, missing bands, or incomplete live review.",
        "",
        "## Summary",
        "",
        f"- Candidates tracked: `{report['candidate_count']}`.",
    ]
    for readiness, count in report["readiness_counts"].items():
        lines.append(f"- `{readiness}`: `{count}`.")

    lines.extend(
        [
            "",
            "## Candidate Table",
            "",
            "| Candidate | Track | State | Readiness | Bands | Missing Evidence |",
            "|-----------|-------|-------|-----------|-------|------------------|",
        ]
    )

    for c in report["candidates"]:
        missing = []
        missing.extend(c["missing_files"])
        if c["missing_required_captures"]:
            missing.append("missing captures: " + ", ".join(c["missing_required_captures"]))
        missing_text = "<br>".join(missing) if missing else "-"
        lines.append(
            "| `{id}` | `{track}` | `{state}` | `{ready}` | {bands} | {missing} |".format(
                id=c["id"],
                track=c["promotion_track"],
                state=c["promotion_state"],
                ready=c["readiness"],
                bands=band_cell(c, band_order),
                missing=missing_text,
            )
        )

    lines.extend(["", "## Blockers", ""])
    for c in report["candidates"]:
        blockers = c.get("blockers", [])
        if not blockers:
            continue
        lines.append(f"### {c['id']}")
        for blocker in blockers:
            lines.append(f"- {blocker}")
        lines.append("")

    lines.extend(
        [
            "## Gate Rule",
            "",
            "Production promotion requires all required gameplay bands to be `pass`, no",
            "missing evidence, and an explicit promotion-state change to",
            "`production_candidate` or `production_promoted`. Current accepted M10/M11/M12",
            "items are workflow evidence unless separately promoted.",
            "",
            "Regenerate:",
            "",
            "```powershell",
            "python world3/pipeline/audit_production_promotion_candidates.py",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    report = collect()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    OUT_MD.write_text(markdown(report), encoding="utf-8", newline="\n")
    print(OUT_MD.relative_to(ROOT))
    print(OUT_JSON.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
