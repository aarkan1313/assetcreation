"""Icon suggestion tool: match game_data records to UI icons by tag overlap.

For every validated game_data record (item / ability / npc) compute a
similarity score against every entry in ui/icons/manifest.json and emit the
top-K matches per record. Lets future game_data regens swap fictional icon
IDs for real ones from this catalogue, drying out the link_validator drift
the v2 catalogue still has.

Match score (deterministic, no model):
  raw  = |record.match_terms ∩ icon.match_terms|
  norm = raw / sqrt(|record| * |icon|)        (cosine on token sets)
  bonus = +0.5 if record.category/school/damage_type matches an icon-id token
          +0.2 if record.display_name shares >=2 distinct words with icon.display_name

Where match_terms include:
  record:  tags + category + school + damage_type + words(display_name)
  icon:    semantic_tags + words(display_name) + words(id minus 'ico_' prefix)

Outputs:
  ui/icons/suggestions.json    map of record_id -> top-K [{icon_id, score, reasons}]
  ui/icons/suggestions.md      human-readable per-record table

Optional --apply mode emits an `icon_id_patch.jsonl` listing the suggested
swaps; the game_data team's pickup is to merge those into the records (which
this tool deliberately does not write — that's their pipeline).

CLI:
  python suggest_icon_for_record.py
  python suggest_icon_for_record.py --top 5 --kind item,ability
  python suggest_icon_for_record.py --threshold 0.3 --apply
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ASSETS = Path(r"D:\assets")
ICONS_MANIFEST = ASSETS / "ui" / "icons" / "manifest.json"
GAME_DATA = ASSETS / "game_data" / "validated"
SUGGESTIONS_JSON = ASSETS / "ui" / "icons" / "suggestions.json"
SUGGESTIONS_MD = ASSETS / "ui" / "icons" / "suggestions.md"
PATCH_OUT = ASSETS / "ui" / "icons" / "icon_id_patch.jsonl"


_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "to", "in", "on", "for",
    "with", "from", "by", "is", "are", "was", "were", "be", "been",
    "ico", "icon",
}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


def _icon_terms(icon: dict) -> set[str]:
    bag = set(icon.get("semantic_tags", []) or [])
    bag |= _tokens(icon.get("display_name", ""))
    iid = icon.get("id", "")
    if iid.startswith("ico_"):
        iid = iid[4:]
    bag |= _tokens(iid)
    return bag


def _record_terms(rec: dict) -> set[str]:
    bag: set[str] = set()
    for k in ("tags",):
        v = rec.get(k) or []
        bag |= {t.lower() for t in v if isinstance(t, str)}
    for k in ("category", "school", "damage_type", "kind", "shape"):
        v = rec.get(k)
        if isinstance(v, str) and v:
            bag.add(v.lower())
    bag |= _tokens(rec.get("display_name", ""))
    bag |= _tokens(rec.get("id", ""))
    bag.discard("none")
    bag.discard("default")
    return bag


def _category_bonus(rec: dict, icon: dict) -> float:
    """+0.5 if record category/school/damage_type appears in the icon id."""
    iid = icon.get("id", "").lower().removeprefix("ico_")
    iid_words = set(iid.split("_"))
    for k in ("category", "school", "damage_type"):
        v = rec.get(k)
        if isinstance(v, str) and v.lower() in iid_words:
            return 0.5
    return 0.0


def _name_bonus(rec: dict, icon: dict) -> float:
    rn = _tokens(rec.get("display_name", ""))
    inn = _tokens(icon.get("display_name", ""))
    overlap = rn & inn
    return 0.2 if len(overlap) >= 2 else 0.0


def score(rec: dict, icon: dict) -> tuple[float, list[str]]:
    rt = _record_terms(rec)
    it = _icon_terms(icon)
    if not rt or not it:
        return 0.0, []
    raw = len(rt & it)
    if raw == 0:
        return 0.0, []
    cos = raw / math.sqrt(len(rt) * len(it))
    cb = _category_bonus(rec, icon)
    nb = _name_bonus(rec, icon)
    s = cos + cb + nb
    reasons = []
    overlap = sorted(rt & it)
    if overlap:
        reasons.append("overlap=[" + ",".join(overlap[:6]) + "]")
    if cb:
        reasons.append("category-in-id+0.5")
    if nb:
        reasons.append("name-overlap+0.2")
    return s, reasons


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError as e:
            print(f"  [warn] {path}: bad JSON line: {e}", file=sys.stderr)
    return out


_PLURAL_OVERRIDES = {
    "ability": "abilities",
    "abilities": "abilities",
    "lore_term": "lore_terms",
    "lore_terms": "lore_terms",
    "faction": "factions",
}


def _pluralize(kind: str) -> str:
    if kind in _PLURAL_OVERRIDES:
        return _PLURAL_OVERRIDES[kind]
    if kind.endswith("s"):
        return kind
    if kind.endswith("y") and not kind.endswith(("ay", "ey", "iy", "oy", "uy")):
        return kind[:-1] + "ies"
    return kind + "s"


def load_records(kinds: list[str]) -> dict[str, list[dict]]:
    out = {}
    for kind in kinds:
        plural = _pluralize(kind)
        out[plural] = load_jsonl(GAME_DATA / f"{plural}.jsonl")
    return out


def topk(rec: dict, icons: list[dict], k: int = 5,
         min_score: float = 0.0) -> list[dict]:
    cands = []
    for icon in icons:
        s, reasons = score(rec, icon)
        if s <= min_score:
            continue
        cands.append({"icon_id": icon["id"], "score": round(s, 4),
                      "reasons": reasons,
                      "current_icon_id": rec.get("icon_id")})
    cands.sort(key=lambda c: -c["score"])
    return cands[:k]


def write_md(report: dict, out_path: Path) -> None:
    lines = ["# Icon suggestions for game_data records", "",
             "Auto-generated by `pipelines/ui/suggest_icon_for_record.py`. "
             "Match scores are cosine on token sets + category/name bonuses. "
             "Top suggestion per record below; full top-K in `suggestions.json`.",
             ""]
    for plural, results in report["by_kind"].items():
        if not results:
            continue
        lines.append(f"## {plural}")
        lines.append("")
        lines.append("| Record | Current `icon_id` | Suggested | Score | Reasons |")
        lines.append("|---|---|---|---|---|")
        for r in results:
            top = r["matches"][0] if r["matches"] else None
            lines.append(
                f"| `{r['record_id']}` ({r.get('display_name','')}) | "
                f"`{r.get('current_icon_id','-')}` | "
                f"`{top['icon_id'] if top else '-'}` | "
                f"{top['score'] if top else '-'} | "
                f"{', '.join(top['reasons']) if top else '-'} |"
            )
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--icons", type=Path, default=ICONS_MANIFEST)
    ap.add_argument("--game-data", type=Path, default=GAME_DATA)
    ap.add_argument("--kind", default="item,ability,npc",
                    help="Comma-separated kinds to match. Default: items, "
                         "abilities, npcs.")
    ap.add_argument("--top", type=int, default=5,
                    help="Number of suggestions per record.")
    ap.add_argument("--threshold", type=float, default=0.0,
                    help="Skip suggestions below this score.")
    ap.add_argument("--out-json", type=Path, default=SUGGESTIONS_JSON)
    ap.add_argument("--out-md", type=Path, default=SUGGESTIONS_MD)
    ap.add_argument("--apply", action="store_true",
                    help="Also write an icon_id_patch.jsonl listing the "
                         "suggested swap per record (the game_data team's "
                         "pickup; this tool does NOT mutate validated/*.jsonl).")
    ap.add_argument("--patch-out", type=Path, default=PATCH_OUT)
    args = ap.parse_args()

    if not args.icons.exists():
        print(f"[suggest_icon] ERROR: icons manifest not found: {args.icons}",
              file=sys.stderr)
        return 2
    icons = json.loads(args.icons.read_text(encoding="utf-8")).get("icons", [])
    if not icons:
        print("[suggest_icon] ERROR: no icons in manifest", file=sys.stderr)
        return 2

    kinds = [k.strip() for k in args.kind.split(",") if k.strip()]
    records = load_records(kinds)
    total = sum(len(v) for v in records.values())
    print(f"[suggest_icon] icons={len(icons)} records={total} "
          f"({', '.join(f'{k}={len(v)}' for k,v in records.items())})")

    by_kind: dict[str, list[dict]] = {}
    for plural, recs in records.items():
        by_kind[plural] = []
        for rec in recs:
            matches = topk(rec, icons, k=args.top, min_score=args.threshold)
            by_kind[plural].append({
                "record_id": rec["id"],
                "display_name": rec.get("display_name", ""),
                "current_icon_id": rec.get("icon_id"),
                "matches": matches,
            })

    report = {
        "icons_manifest": str(args.icons),
        "game_data_root": str(args.game_data),
        "kinds": kinds,
        "top_k": args.top,
        "threshold": args.threshold,
        "total_records": total,
        "by_kind": by_kind,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_md(report, args.out_md)
    print(f"[suggest_icon] suggestions -> {args.out_json}")
    print(f"[suggest_icon]              -> {args.out_md}")

    if args.apply:
        # Emit JSONL of {record_id, suggested_icon_id, score} for the highest match
        rows = []
        for plural, results in by_kind.items():
            for r in results:
                if not r["matches"]:
                    continue
                rows.append({
                    "kind": plural,
                    "record_id": r["record_id"],
                    "current_icon_id": r["current_icon_id"],
                    "suggested_icon_id": r["matches"][0]["icon_id"],
                    "score": r["matches"][0]["score"],
                    "reasons": r["matches"][0]["reasons"],
                })
        args.patch_out.parent.mkdir(parents=True, exist_ok=True)
        with args.patch_out.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        print(f"[suggest_icon] patch     -> {args.patch_out} ({len(rows)} rows)")

    # Quick stdout summary
    coverage = 0
    weak = 0
    for plural, results in by_kind.items():
        for r in results:
            if r["matches"]:
                top = r["matches"][0]
                if top["score"] >= 0.3:
                    coverage += 1
                else:
                    weak += 1
    print(f"[suggest_icon] coverage strong={coverage} weak={weak} (threshold 0.3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
