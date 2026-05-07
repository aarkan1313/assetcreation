"""SFX suggestion tool: match game_data records to audio sfx by tag overlap.

Same shape as `pipelines/ui/suggest_icon_for_record.py`. For every validated
ability / item / npc record compute a similarity score against every entry
in `audio/sfx_manifest.json` and emit the top-K matches per record. Lets
future game_data regens stop emitting fictional sfx IDs by first looking
up real ones from the catalogue.

Two distinct suggestion lanes (a single record can produce both):

  cast_sfx     : the sound played when an ability is *cast*. Matches against
                 sfx whose tags include "cast" + the ability's school or
                 damage_type (e.g. spell_fire_cast for a fire ability).
  impact_sfx   : the sound played when an ability *hits*. Matches against
                 sfx whose tags include "impact" + same.

For items (potions / weapons), we use a single "item_sfx" lane which biases
toward UI sfx (potions -> ui_pickup, swords -> impact_metal, etc).

Match score (deterministic, no model):

  raw  = |record.match_terms ∩ sfx.match_terms|
  norm = raw / sqrt(|record| * |sfx|)        (cosine on token sets)
  bonus = +0.5 if record.school appears as a sfx-id token (e.g. fire->spell_fire_cast)
        + 0.3 if the lane keyword (cast / impact / pickup) appears in the sfx id
        + 0.2 if the record category lines up with sfx category

Where match_terms include:
  record:  tags + category + school + damage_type + words(display_name)
  sfx:     cue.tags + words(id minus prefix) + category

Outputs:
  audio/suggestions.json    map of record_id -> top-K [{sfx_id, score, reasons}]
  audio/suggestions.md      human-readable per-record table

Optional --apply emits an `sfx_id_patch.jsonl` of suggested swaps; the
game_data team's pickup is to merge those in (this tool deliberately does
not write to validated/*.jsonl).

CLI:
  python suggest_sfx_for_record.py
  python suggest_sfx_for_record.py --top 5 --kind ability
  python suggest_sfx_for_record.py --threshold 0.3 --apply
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ASSETS = Path(r"D:\assets")
SFX_MANIFEST = ASSETS / "audio" / "sfx_manifest.json"
GAME_DATA = ASSETS / "game_data" / "validated"
SUGGESTIONS_JSON = ASSETS / "audio" / "suggestions.json"
SUGGESTIONS_MD = ASSETS / "audio" / "suggestions.md"
PATCH_OUT = ASSETS / "audio" / "sfx_id_patch.jsonl"


_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "to", "in", "on", "for",
    "with", "from", "by", "is", "are", "was", "were", "be", "been",
}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


def _sfx_terms(snd: dict) -> set[str]:
    cue = snd.get("cue") or {}
    bag: set[str] = set()
    for t in (cue.get("tags") or snd.get("tags") or []):
        if isinstance(t, str):
            bag.add(t.lower())
    bag |= _tokens(snd.get("id", ""))
    if cue.get("preset"):
        bag |= _tokens(cue["preset"])
    if snd.get("category"):
        bag.add(str(snd["category"]).lower())
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


def _category_bonus(rec: dict, snd: dict) -> tuple[float, list[str]]:
    """+0.5 if record school/damage_type appears in sfx id."""
    sid = snd.get("id", "").lower()
    sid_words = set(re.split(r"[_\s]+", sid))
    reasons = []
    for k in ("school", "damage_type"):
        v = rec.get(k)
        if isinstance(v, str) and v.lower() in sid_words:
            reasons.append(f"{k}-in-id+0.5")
            return 0.5, reasons
    return 0.0, reasons


def _lane_bonus(snd: dict, lane: str) -> tuple[float, list[str]]:
    """+0.3 if the lane keyword appears in the sfx id.
    lane = 'cast' | 'impact' | 'pickup' | 'item'
    """
    sid = snd.get("id", "").lower()
    if lane in ("cast", "impact"):
        if lane in sid:
            return 0.3, [f"lane-{lane}+0.3"]
        return 0.0, []
    if lane == "item":
        # Item lane matches UI/pickup sounds preferentially
        if any(t in sid for t in ("pickup", "purchase", "ui_")):
            return 0.3, ["lane-item+0.3"]
        return 0.0, []
    return 0.0, []


def _category_match_bonus(rec: dict, snd: dict) -> tuple[float, list[str]]:
    """+0.2 if record category lines up with sfx category."""
    rc = str(rec.get("category") or "").lower()
    cc = str(snd.get("category") or (snd.get("cue") or {}).get("category") or "").lower()
    if rc and cc and rc == cc:
        return 0.2, ["category-match+0.2"]
    return 0.0, []


def score(rec: dict, snd: dict, lane: str) -> tuple[float, list[str]]:
    rt = _record_terms(rec)
    st = _sfx_terms(snd)
    if not rt or not st:
        return 0.0, []
    raw = len(rt & st)
    if raw == 0:
        return 0.0, []
    cos = raw / math.sqrt(len(rt) * len(st))
    cb, cb_r = _category_bonus(rec, snd)
    lb, lb_r = _lane_bonus(snd, lane)
    cm, cm_r = _category_match_bonus(rec, snd)
    s = cos + cb + lb + cm
    reasons = []
    overlap = sorted(rt & st)
    if overlap:
        reasons.append("overlap=[" + ",".join(overlap[:6]) + "]")
    reasons += cb_r + lb_r + cm_r
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
    "ability": "abilities", "abilities": "abilities",
    "item": "items", "items": "items",
    "npc": "npcs", "npcs": "npcs",
}


def _pluralize(kind: str) -> str:
    if kind in _PLURAL_OVERRIDES:
        return _PLURAL_OVERRIDES[kind]
    if kind.endswith("s"):
        return kind
    return kind + "s"


def topk(rec: dict, sounds: list[dict], lane: str, k: int = 5,
         min_score: float = 0.0, current_id: str | None = None) -> list[dict]:
    cands = []
    for snd in sounds:
        s, reasons = score(rec, snd, lane=lane)
        if s <= min_score:
            continue
        cands.append({"sfx_id": snd["id"], "score": round(s, 4),
                      "reasons": reasons,
                      "current_sfx_id": current_id})
    cands.sort(key=lambda c: -c["score"])
    return cands[:k]


def suggest_for_record(rec: dict, kind: str, sounds: list[dict],
                       k: int, min_score: float) -> dict:
    """For an ability we suggest TWO lanes (cast + impact). For items / npcs
    we suggest one (item)."""
    out: dict = {
        "record_id": rec["id"],
        "display_name": rec.get("display_name", ""),
        "kind": kind,
    }
    if kind == "abilities":
        out["lanes"] = {
            "cast_sfx_id": {
                "current": rec.get("cast_sfx_id") or rec.get("sfx_id"),
                "matches": topk(rec, sounds, lane="cast", k=k,
                                min_score=min_score,
                                current_id=rec.get("cast_sfx_id") or rec.get("sfx_id")),
            },
            "impact_sfx_id": {
                "current": rec.get("impact_sfx_id"),
                "matches": topk(rec, sounds, lane="impact", k=k,
                                min_score=min_score,
                                current_id=rec.get("impact_sfx_id")),
            },
        }
    else:
        out["lanes"] = {
            "sfx_id": {
                "current": rec.get("sfx_id"),
                "matches": topk(rec, sounds, lane="item", k=k,
                                min_score=min_score,
                                current_id=rec.get("sfx_id")),
            },
        }
    return out


def write_md(report: dict, out_path: Path) -> None:
    lines = ["# SFX suggestions for game_data records", "",
             "Auto-generated by `pipelines/audio/suggest_sfx_for_record.py`. "
             "Match scores are cosine on token sets + school/lane/category "
             "bonuses. Top suggestion per lane below; full top-K in "
             "`suggestions.json`.", ""]
    for plural, results in report["by_kind"].items():
        if not results:
            continue
        lines.append(f"## {plural}")
        lines.append("")
        if plural == "abilities":
            lines.append("| Record | Lane | Current | Suggested | Score | Reasons |")
            lines.append("|---|---|---|---|---|---|")
            for r in results:
                for lane_key, lane_info in r["lanes"].items():
                    top = lane_info["matches"][0] if lane_info["matches"] else None
                    lines.append(
                        f"| `{r['record_id']}` ({r.get('display_name','')}) | "
                        f"`{lane_key}` | "
                        f"`{lane_info.get('current','-')}` | "
                        f"`{top['sfx_id'] if top else '-'}` | "
                        f"{top['score'] if top else '-'} | "
                        f"{', '.join(top['reasons']) if top else '-'} |"
                    )
        else:
            lines.append("| Record | Current | Suggested | Score | Reasons |")
            lines.append("|---|---|---|---|---|")
            for r in results:
                lane = r["lanes"].get("sfx_id", {})
                top = lane.get("matches", [None])[0] if lane.get("matches") else None
                lines.append(
                    f"| `{r['record_id']}` ({r.get('display_name','')}) | "
                    f"`{lane.get('current','-')}` | "
                    f"`{top['sfx_id'] if top else '-'}` | "
                    f"{top['score'] if top else '-'} | "
                    f"{', '.join(top['reasons']) if top else '-'} |"
                )
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=SFX_MANIFEST)
    ap.add_argument("--game-data", type=Path, default=GAME_DATA)
    ap.add_argument("--kind", default="ability,item,npc",
                    help="Comma-separated kinds.")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=0.0)
    ap.add_argument("--out-json", type=Path, default=SUGGESTIONS_JSON)
    ap.add_argument("--out-md", type=Path, default=SUGGESTIONS_MD)
    ap.add_argument("--apply", action="store_true",
                    help="Also write an sfx_id_patch.jsonl of suggested swaps.")
    ap.add_argument("--patch-out", type=Path, default=PATCH_OUT)
    args = ap.parse_args()

    if not args.manifest.exists():
        print(f"[suggest_sfx] ERROR: manifest not found: {args.manifest}",
              file=sys.stderr)
        return 2
    sounds = json.loads(args.manifest.read_text(encoding="utf-8")).get("sounds", [])
    if not sounds:
        print("[suggest_sfx] ERROR: no sounds in manifest", file=sys.stderr)
        return 2

    kinds = [k.strip() for k in args.kind.split(",") if k.strip()]
    by_kind: dict[str, list[dict]] = {}
    total = 0
    for kind in kinds:
        plural = _pluralize(kind)
        recs = load_jsonl(args.game_data / f"{plural}.jsonl")
        total += len(recs)
        by_kind[plural] = [
            suggest_for_record(r, plural, sounds, args.top, args.threshold)
            for r in recs
        ]

    print(f"[suggest_sfx] sounds={len(sounds)} records={total} "
          f"({', '.join(f'{k}={len(v)}' for k,v in by_kind.items())})")

    report = {
        "manifest": str(args.manifest),
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
    print(f"[suggest_sfx] suggestions -> {args.out_json}")
    print(f"[suggest_sfx]              -> {args.out_md}")

    if args.apply:
        rows = []
        for plural, results in by_kind.items():
            for r in results:
                for lane_key, lane in r["lanes"].items():
                    if not lane["matches"]:
                        continue
                    rows.append({
                        "kind": plural,
                        "record_id": r["record_id"],
                        "lane": lane_key,
                        "current": lane.get("current"),
                        "suggested": lane["matches"][0]["sfx_id"],
                        "score": lane["matches"][0]["score"],
                        "reasons": lane["matches"][0]["reasons"],
                    })
        args.patch_out.parent.mkdir(parents=True, exist_ok=True)
        with args.patch_out.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        print(f"[suggest_sfx] patch     -> {args.patch_out} ({len(rows)} rows)")

    # Quick stdout summary
    strong = weak = 0
    for plural, results in by_kind.items():
        for r in results:
            for lane in r["lanes"].values():
                if lane["matches"]:
                    top = lane["matches"][0]
                    if top["score"] >= 0.3:
                        strong += 1
                    else:
                        weak += 1
    print(f"[suggest_sfx] coverage strong={strong} weak={weak} (threshold 0.3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
