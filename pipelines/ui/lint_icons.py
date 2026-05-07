"""Icon-breadth strict linter.

Wraps `pipelines/_meta/link_validator.py` (which is owned by another lane and
must not be edited from the UI pipeline) and adds icon-specific gating
checks on top:

  (a) UNUSED ICONS  : any manifest entry that no validated record references.
                       Catches catalogue bloat / dead-weight icons.
  (b) MISSING TAGS  : any manifest entry with empty `semantic_tags`.
                       Without tags, suggest_icon_for_record.py can't match
                       records to icons -> drift on every game_data regen.
  (c) ID->RECORD MISMATCH : record points at an icon whose tokens contradict
                       the record's category/school/damage_type. Heuristic
                       (false-positive-tolerant); catches the worst drift
                       like a fireball ability pointing at `ico_axe`.
  (d) RTL FLAG MISSING : asymmetric icons (chevrons/arrows/etc) with
                       `rtl_mirror=false` flagged for review by the i18n
                       reviewer.

Outputs a `lint_icons_report.json` + a stdout summary with exit-code semantics:
  exit 0  -> all four checks pass (or warnings only with --warn-only)
  exit 1  -> at least one strict check failed
  exit 2  -> setup/IO error

CLI:
  # Informational (always exits 0, prints findings)
  python lint_icons.py --warn-only

  # Strict (exits 1 if any of (a)-(d) trip)
  python lint_icons.py --strict

  # Strict but allow specific icon IDs to be unused (whitelist):
  python lint_icons.py --strict --allow-unused ico_lucide_circle,ico_phosphor_circle

  # Pull link_validator's JSON output if you already ran it elsewhere
  python lint_icons.py --link-validator-json reports/link_validator.json --strict

Run after any change to ui/icons/manifest.json or game_data/validated/*.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ASSETS = Path(r"D:\assets")
LINK_VALIDATOR = ASSETS / "pipelines" / "_meta" / "link_validator.py"
ICONS_MANIFEST = ASSETS / "ui" / "icons" / "manifest.json"
GAME_DATA = ASSETS / "game_data" / "validated"
DEFAULT_REPORT = ASSETS / "ui" / "icons" / "lint_icons_report.json"


# Tokens that disqualify an icon for a given record category/school. The set
# is intentionally narrow: only obvious mismatches. Spell-school keywords are
# the most reliable signal because they're enum-bounded in the schema.
NEGATIVE_TOKENS = {
    "fire":     {"ice", "frost", "snow", "frozen", "icicle", "water"},
    "ice":      {"fire", "ember", "flame", "magma"},
    "frost":    {"fire", "ember", "flame", "magma"},
    "cold":     {"fire", "ember", "flame", "magma"},
    "lightning":{"water", "ice", "frost"},
    "shadow":   {"holy", "divine", "sun"},
    "holy":     {"shadow", "skull", "death", "void"},
    "nature":   {"shadow", "void", "skull", "death"},
    "weapon":   {"potion", "elixir", "scroll"},
    "potion":   {"sword", "axe", "mace"},
}


_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    if not s:
        return set()
    return set(_WORD.findall(s.lower()))


def _icon_token_bag(icon: dict) -> set[str]:
    bag = set(icon.get("semantic_tags", []) or [])
    bag |= _tokens(icon.get("display_name", ""))
    iid = icon.get("id", "").removeprefix("ico_")
    bag |= _tokens(iid)
    return bag


def _record_token_bag(rec: dict) -> set[str]:
    bag = {t.lower() for t in (rec.get("tags") or []) if isinstance(t, str)}
    for k in ("category", "school", "damage_type", "kind"):
        v = rec.get(k)
        if isinstance(v, str) and v:
            bag.add(v.lower())
    bag |= _tokens(rec.get("display_name", ""))
    return bag


# ---------- pulls ----------

def _run_link_validator(report_path: Path | None = None) -> dict:
    args = [sys.executable, str(LINK_VALIDATOR)]
    if report_path:
        args += ["--json", str(report_path)]
    out = subprocess.run(args, capture_output=True, text=True)
    # link_validator returns 1 when references missing; we still parse the JSON.
    if report_path and report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    # Fallback: parse stdout-printed counts only (no rich JSON)
    return {"counts": {}, "missing": {}, "unused": {}, "ok": out.returncode == 0,
            "_stdout_only": True}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------- checks ----------

def check_unused(manifest: dict, lv_report: dict, allow: set[str]) -> list[str]:
    icon_ids = {e["id"] for e in manifest["icons"]}
    referenced = set()
    for plural in ("items", "abilities", "npcs", "factions", "lore_terms"):
        for rec in load_jsonl(GAME_DATA / f"{plural}.jsonl"):
            ico = rec.get("icon_id")
            if isinstance(ico, str) and ico:
                referenced.add(ico)
    unused = sorted(icon_ids - referenced - allow)
    return unused


def check_missing_tags(manifest: dict) -> list[str]:
    return sorted(e["id"] for e in manifest["icons"]
                  if not (e.get("semantic_tags") or []))


def check_record_mismatch(manifest: dict) -> list[dict]:
    """Heuristic: record points at an icon whose tokens are in NEGATIVE_TOKENS
    for the record's category/school/damage_type."""
    by_id = {e["id"]: e for e in manifest["icons"]}
    out: list[dict] = []
    for plural in ("items", "abilities"):
        for rec in load_jsonl(GAME_DATA / f"{plural}.jsonl"):
            ico_id = rec.get("icon_id")
            if not ico_id or ico_id not in by_id:
                continue
            icon_bag = _icon_token_bag(by_id[ico_id])
            triggers = []
            for k in ("category", "school", "damage_type"):
                v = rec.get(k)
                if not isinstance(v, str):
                    continue
                neg = NEGATIVE_TOKENS.get(v.lower(), set())
                hit = neg & icon_bag
                if hit:
                    triggers.append(f"record.{k}={v} ↯ icon[{','.join(sorted(hit))}]")
            if triggers:
                out.append({"record_id": rec["id"], "icon_id": ico_id,
                            "kind": plural, "triggers": triggers})
    return out


def check_rtl_flag(manifest: dict) -> list[str]:
    """Asymmetric icons (left/right/up/down/chevron/caret/arrow tokens) that
    don't have rtl_mirror=true. Just lists candidates for human review."""
    out: list[str] = []
    asym_tokens = {"left", "right", "up", "down", "chevron", "caret", "arrow",
                   "back", "forward", "next", "prev"}
    for e in manifest["icons"]:
        if e.get("rtl_mirror"):
            continue
        bag = _icon_token_bag(e)
        if bag & asym_tokens:
            out.append(e["id"])
    return sorted(out)


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ICONS_MANIFEST)
    ap.add_argument("--link-validator-json", type=Path, default=None,
                    help="Existing link_validator JSON output. If omitted, "
                         "run link_validator first.")
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 if any of unused / missing-tags / record-"
                         "mismatch trip. RTL is informational always.")
    ap.add_argument("--warn-only", action="store_true",
                    help="Always exit 0 even with strict failures (for CI "
                         "preview runs).")
    ap.add_argument("--allow-unused", default="",
                    help="Comma-separated icon IDs to whitelist as "
                         "intentionally unused (e.g. fallbacks, "
                         "future-content placeholders).")
    args = ap.parse_args()

    if not args.manifest.exists():
        print(f"[lint_icons] ERROR: manifest not found: {args.manifest}",
              file=sys.stderr)
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    lv_report: dict
    if args.link_validator_json and args.link_validator_json.exists():
        lv_report = json.loads(args.link_validator_json.read_text(encoding="utf-8"))
    else:
        # Run link_validator and collect JSON
        scratch = ASSETS / "ui" / "icons" / "_lv_scratch.json"
        lv_report = _run_link_validator(scratch)

    allow = {s.strip() for s in args.allow_unused.split(",") if s.strip()}

    unused = check_unused(manifest, lv_report, allow)
    missing_tags = check_missing_tags(manifest)
    mismatches = check_record_mismatch(manifest)
    rtl_candidates = check_rtl_flag(manifest)

    report = {
        "manifest": str(args.manifest),
        "icon_count": len(manifest["icons"]),
        "unused_count": len(unused),
        "missing_tags_count": len(missing_tags),
        "mismatch_count": len(mismatches),
        "rtl_candidates_count": len(rtl_candidates),
        "unused": unused,
        "missing_tags": missing_tags,
        "mismatches": mismatches,
        "rtl_candidates_for_review": rtl_candidates,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[lint_icons] icon_count={report['icon_count']} "
          f"unused={report['unused_count']} "
          f"missing_tags={report['missing_tags_count']} "
          f"mismatch={report['mismatch_count']} "
          f"rtl_review={report['rtl_candidates_count']}")
    if unused[:5]:
        print(f"[lint_icons] sample unused : {', '.join(unused[:5])}"
              + (" ..." if len(unused) > 5 else ""))
    if missing_tags[:5]:
        print(f"[lint_icons] sample no-tags: {', '.join(missing_tags[:5])}"
              + (" ..." if len(missing_tags) > 5 else ""))
    for m in mismatches[:5]:
        print(f"[lint_icons] MISMATCH {m['record_id']} -> {m['icon_id']}: "
              f"{'; '.join(m['triggers'])}")
    if rtl_candidates[:3]:
        print(f"[lint_icons] rtl review : {', '.join(rtl_candidates[:3])}"
              + (" ..." if len(rtl_candidates) > 3 else ""))

    print(f"[lint_icons] report -> {args.report}")

    if args.warn_only:
        return 0
    if args.strict:
        ok = (not unused) and (not missing_tags) and (not mismatches)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
