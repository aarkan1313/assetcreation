"""UI icon validator — strict-icons gating wrapper around link_validator.

Wraps `pipelines/_meta/link_validator.py` to add UI-specific gating that the
base validator deliberately reports as informational. This is the **ship
readiness** check for the icon catalogue.

Three checks beyond the base:

  unused_icons        manifest entries no game_data record references at all.
                      v3 catalogue has 130+ icons; 8 referenced by current
                      synthetic data. Threshold-based: --max-unused-fraction
                      defaults to 0.95 (95% unused is fine until catalogue
                      breadth is wired into game_data; 100% would break).

  mismatched_icons    records whose current icon_id is referencing a real
                      manifest entry, BUT suggest_icon_for_record.py finds
                      a strictly better match with a delta over --mismatch-margin.
                      Default 0.20 — only fires when there's a clearly better
                      icon available. Avoids false positives on near-ties.

  missing_tags        manifest entries whose `semantic_tags` is empty/missing.
                      First-party synth icons currently lack tags; freelib +
                      ui-lib entries have them. Strict mode requires every
                      icon to have at least one semantic_tag for the
                      suggester to reason over it.

Output:
  ui/icons/strict_report.json   machine-readable
  ui/icons/strict_report.md     human-readable

Exit codes:
  0   pass (no gating issues, or all under thresholds)
  1   gating fail (one or more checks tripped)
  2   bad invocation (manifest missing, etc.)

CLI:
  python icon_validator.py
  python icon_validator.py --strict
  python icon_validator.py --strict --max-unused-fraction 0.50 --mismatch-margin 0.10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ASSETS = Path(r"D:\assets")
ICONS_MANIFEST = ASSETS / "ui" / "icons" / "manifest.json"
SUGGESTIONS_JSON = ASSETS / "ui" / "icons" / "suggestions.json"
STRICT_REPORT_JSON = ASSETS / "ui" / "icons" / "strict_report.json"
STRICT_REPORT_MD = ASSETS / "ui" / "icons" / "strict_report.md"

# Import the base validator without modifying its source.
sys.path.insert(0, str(ASSETS / "pipelines" / "_meta"))
try:
    import link_validator as _lv  # type: ignore
except ImportError as e:  # pragma: no cover - defensive
    raise SystemExit(
        f"icon_validator: cannot import link_validator from "
        f"{ASSETS / 'pipelines' / '_meta'}: {e}")


def _load_manifest() -> dict:
    if not ICONS_MANIFEST.exists():
        raise SystemExit(f"icon_validator: manifest not found: {ICONS_MANIFEST}")
    return json.loads(ICONS_MANIFEST.read_text(encoding="utf-8"))


def _load_suggestions() -> dict | None:
    """Optional. If suggestions.json is missing or stale, the mismatch check
    is skipped — we don't auto-run the suggester here to keep this tool
    deterministic and side-effect-free."""
    if not SUGGESTIONS_JSON.exists():
        return None
    return json.loads(SUGGESTIONS_JSON.read_text(encoding="utf-8"))


def check_unused_icons(base_report: dict, total_icons: int,
                       max_unused_fraction: float) -> dict:
    unused_ids = base_report["unused"].get("icon", [])
    fraction = (len(unused_ids) / total_icons) if total_icons else 0.0
    return {
        "name": "unused_icons",
        "unused_count": len(unused_ids),
        "total_icons": total_icons,
        "unused_fraction": round(fraction, 4),
        "threshold": max_unused_fraction,
        "passes": fraction <= max_unused_fraction,
        "unused_ids_sample": unused_ids[:20],
    }


def check_mismatched_icons(suggestions: dict | None,
                           min_score: float,
                           margin: float) -> dict:
    if not suggestions:
        return {
            "name": "mismatched_icons",
            "skipped": True,
            "reason": "suggestions.json not found; run "
                      "`pipelines/ui/suggest_icon_for_record.py` first.",
            "passes": True,
        }
    by_kind = suggestions.get("by_kind", {})
    mismatches: list[dict] = []
    for kind, results in by_kind.items():
        for entry in results:
            top = (entry.get("matches") or [None])[0]
            if not top:
                continue
            current = entry.get("current_icon_id")
            if not current:
                continue
            top_score = top.get("score", 0.0)
            if top_score < min_score:
                continue
            if top["icon_id"] == current:
                continue
            # Find the score the current icon would get if it appears in the
            # suggestion list (it might rank lower, or not appear at all).
            current_score = next(
                (s.get("score", 0.0)
                 for s in entry.get("suggestions", [])
                 if s["icon_id"] == current),
                0.0,
            )
            if (top_score - current_score) >= margin:
                mismatches.append({
                    "kind": kind,
                    "record_id": entry.get("record_id"),
                    "display_name": entry.get("display_name"),
                    "current_icon_id": current,
                    "current_score": round(current_score, 4),
                    "suggested_icon_id": top["icon_id"],
                    "suggested_score": round(top_score, 4),
                    "delta": round(top_score - current_score, 4),
                })
    return {
        "name": "mismatched_icons",
        "min_score": min_score,
        "margin": margin,
        "mismatches": mismatches,
        "passes": len(mismatches) == 0,
    }


def check_missing_tags(manifest: dict) -> dict:
    missing: list[str] = []
    for icon in manifest.get("icons", []):
        tags = icon.get("semantic_tags") or []
        if not tags:
            missing.append(icon["id"])
    return {
        "name": "missing_tags",
        "missing_count": len(missing),
        "total": len(manifest.get("icons", [])),
        "missing_ids_sample": missing[:30],
        "passes": len(missing) == 0,
    }


def write_md(report: dict, out_path: Path) -> None:
    lines = ["# UI strict-icons report", ""]
    summary = report.get("summary", {})
    lines.append(f"- **strict mode:** {report.get('strict')}")
    lines.append(f"- **total_icons:** {summary.get('total_icons')}")
    lines.append(f"- **base validator OK:** {report.get('base_ok')}")
    lines.append(f"- **strict OK:** {report.get('strict_ok')}")
    lines.append("")
    for c in report["checks"]:
        lines.append(f"## {c['name']}")
        lines.append("")
        if c.get("skipped"):
            lines.append(f"_skipped: {c.get('reason')}_")
            lines.append("")
            continue
        for k, v in c.items():
            if k == "name":
                continue
            if isinstance(v, list) and v:
                lines.append(f"- **{k}** ({len(v)}):")
                for item in v[:10]:
                    lines.append(f"  - `{item}`")
                if len(v) > 10:
                    lines.append(f"  - … and {len(v) - 10} more")
            else:
                lines.append(f"- **{k}:** `{v}`")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=ASSETS)
    ap.add_argument("--strict", action="store_true",
                    help="Fail with exit 1 if any gating check trips.")
    ap.add_argument("--max-unused-fraction", type=float, default=0.95,
                    help="Max acceptable fraction of unused icons. Default 0.95 "
                         "(catalogue breadth currently outpaces game_data).")
    ap.add_argument("--mismatch-min-score", type=float, default=0.4)
    ap.add_argument("--mismatch-margin", type=float, default=0.20)
    ap.add_argument("--require-tags", action="store_true",
                    help="Strict mode: fail if any icon lacks semantic_tags.")
    ap.add_argument("--out-json", type=Path, default=STRICT_REPORT_JSON)
    ap.add_argument("--out-md", type=Path, default=STRICT_REPORT_MD)
    args = ap.parse_args()

    base_report = _lv.validate(args.repo, strict=False)
    manifest = _load_manifest()
    suggestions = _load_suggestions()

    total_icons = base_report["counts"]["assets"].get("icon", 0)
    unused_check = check_unused_icons(
        base_report, total_icons, args.max_unused_fraction)
    mismatch_check = check_mismatched_icons(
        suggestions, args.mismatch_min_score, args.mismatch_margin)
    tags_check = check_missing_tags(manifest)
    if not args.require_tags:
        # When not strictly required, missing_tags is informational only.
        tags_check["passes"] = True
        tags_check["informational"] = True

    checks = [unused_check, mismatch_check, tags_check]
    base_ok = base_report["ok"]
    strict_ok = base_ok and all(c["passes"] for c in checks)

    summary = {"total_icons": total_icons,
               "base_missing": {k: len(v) for k, v in base_report["missing"].items()
                                if v},
               "base_unused_icon": len(base_report["unused"].get("icon", [])),
               "manifest_total": len(manifest.get("icons", [])),
               "suggestions_loaded": suggestions is not None}

    full = {
        "strict": args.strict,
        "base_ok": base_ok,
        "strict_ok": strict_ok,
        "summary": summary,
        "checks": checks,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(full, indent=2), encoding="utf-8")
    write_md(full, args.out_md)

    print(f"[icon_validator] icons={total_icons} "
          f"base_ok={base_ok} strict_ok={strict_ok}")
    for c in checks:
        if c.get("skipped"):
            print(f"  - {c['name']}: SKIPPED ({c.get('reason')})")
        else:
            tag = "PASS" if c["passes"] else "FAIL"
            extra = ""
            if c["name"] == "unused_icons":
                extra = f" {c['unused_count']}/{c['total_icons']} ({c['unused_fraction']:.2f})"
            elif c["name"] == "mismatched_icons":
                extra = f" mismatches={len(c.get('mismatches', []))}"
            elif c["name"] == "missing_tags":
                extra = f" missing={c['missing_count']}/{c['total']}"
            print(f"  - {c['name']}: {tag}{extra}")
    print(f"[icon_validator] report -> {args.out_md}")

    if args.strict and not strict_ok:
        return 1
    if not base_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
