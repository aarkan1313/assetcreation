"""Audio-breadth strict linter.

Same pattern as `pipelines/ui/lint_icons.py` (UI v3): wraps
`pipelines/_meta/link_validator.py` (which is owned by another lane and not
edited from the audio pipeline) and adds audio-specific gating checks on top.

Checks:

  (a) UNUSED SFX        : any sfx_manifest entry that no validated record
                          references via cast_sfx_id / impact_sfx_id /
                          ambient_sfx_id / sfx_id. Catches catalogue bloat.
                          Currently ~36 of 39 sounds (catalogue ahead of
                          game_data wiring; expected until real TLTE seeds
                          land).

  (b) ABILITY ↔ SFX MISMATCH : record points at a sfx whose tags contradict
                          the record's school / damage_type. Heuristic
                          (NEGATIVE_TOKENS); catches the worst drift like
                          a `cold` ability bound to a `fire`-tagged sfx.

  (c) BUS ASSIGNMENT SANITY : sounds whose id starts with `ui_*` should map
                          to the UI bus, `step_*` to SFX bus, `spell_*`
                          impact/cast to the SFX bus, `amb_*` to Ambience.
                          Verify the cue.tags or category line up. Reports
                          mismatches so the export_godot.py side can be
                          audited.

  (d) AMBIENCE COVERAGE : every biome registered in
                          art_lab/biomes/biome_texture_registry.json should
                          have a recipe entry in
                          pipelines/audio/recipes/biome_ambience.json AND
                          a built ambience pack at audio/ambience/<biome>/.
                          Catches drift after a new biome ships.

Outputs `audio/lint_audio_report.json` + a stdout summary.

Exit-code semantics (parallels lint_icons.py):
  0 -> all checks pass (or warnings only with --warn-only)
  1 -> at least one strict check failed
  2 -> setup/IO error

CLI:
  # Informational (always exits 0)
  python lint_audio.py --warn-only

  # Strict (exits 1 if any of (a)-(c) trip; (d) is informational always)
  python lint_audio.py --strict

  # Whitelist intentionally-unused sfx
  python lint_audio.py --strict --allow-unused amb_drone_lava,amb_drone_ice

  # Reuse a previous link_validator JSON
  python lint_audio.py --link-validator-json reports/link_validator.json --strict
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
SFX_MANIFEST = ASSETS / "audio" / "sfx_manifest.json"
GAME_DATA = ASSETS / "game_data" / "validated"
AMBIENCE_RECIPE = ASSETS / "pipelines" / "audio" / "recipes" / "biome_ambience.json"
AMBIENCE_SUMMARY = ASSETS / "audio" / "ambience" / "ambience_summary.json"
BIOME_REGISTRY = ASSETS / "art_lab" / "biomes" / "biome_texture_registry.json"
DEFAULT_REPORT = ASSETS / "audio" / "lint_audio_report.json"


# Negative tokens per record-school: a sfx whose cue.tags contains any of
# these tokens but the record's school is the LHS of the row is a mismatch.
NEGATIVE_TOKENS = {
    "fire":      {"ice", "frost", "snow", "frozen", "water", "rain"},
    "cold":      {"fire", "ember", "flame", "magma", "lava", "burn"},
    "ice":       {"fire", "ember", "flame", "magma", "lava", "burn"},
    "frost":     {"fire", "ember", "flame", "magma", "lava", "burn"},
    "lightning": {"water", "ice", "frost"},
    "shadow":    {"holy", "divine", "sun"},
    "holy":      {"shadow", "skull", "death", "void"},
    "nature":    {"shadow", "void", "skull", "death"},
    "arcane":    set(),  # broad-spectrum; no easy mismatches
}

# Bus expectations by id prefix. Mismatch is informational (the export step
# might use a different bus mapping) but worth flagging.
BUS_EXPECTATIONS = {
    "ui_":     "UI",
    "step_":   "SFX",
    "spell_":  "SFX",
    "impact_": "SFX",
    "amb_":    "Ambience",
}


_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    if not s:
        return set()
    return set(_WORD.findall(s.lower()))


def _sfx_token_bag(snd: dict) -> set[str]:
    cue = snd.get("cue") or {}
    bag: set[str] = set()
    for t in (cue.get("tags") or snd.get("tags") or []):
        if isinstance(t, str):
            bag.add(t.lower())
    bag |= _tokens(snd.get("id", ""))
    if cue.get("preset"):
        bag |= _tokens(cue["preset"])
    return bag


def _expected_bus(sfx_id: str) -> str | None:
    for prefix, bus in BUS_EXPECTATIONS.items():
        if sfx_id.startswith(prefix):
            return bus
    return None


def _actual_bus(snd: dict) -> str | None:
    """Best-effort bus inference from manifest. Falls back to category."""
    cue = snd.get("cue") or {}
    tags = [t.lower() for t in (cue.get("tags") or snd.get("tags") or [])
            if isinstance(t, str)]
    if "ui" in tags:
        return "UI"
    if "ambience" in tags or "ambient" in tags:
        return "Ambience"
    if "voice" in tags or "tts" in tags:
        return "Voice"
    cat = (snd.get("category") or cue.get("category") or "sfx").lower()
    if cat == "ui":
        return "UI"
    if cat in ("ambience", "ambient"):
        return "Ambience"
    return "SFX"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_link_validator(report_path: Path | None = None) -> dict:
    args = [sys.executable, str(LINK_VALIDATOR)]
    if report_path:
        args += ["--json", str(report_path)]
    out = subprocess.run(args, capture_output=True, text=True)
    if report_path and report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    return {"counts": {}, "missing": {}, "unused": {},
            "ok": out.returncode == 0, "_stdout_only": True}


# ---------- checks ----------

# Records can reference sfx via several keys. Be permissive: any key
# matching one of these patterns is treated as an sfx reference.
_SFX_KEY_PATTERNS = (
    "sfx_id", "sound_id", "audio_id",
)
_SFX_KEY_LIST_PATTERNS = (
    "sfx_ids", "sound_ids",
)


def _collect_sfx_refs() -> set[str]:
    """Walk validated records and return every (record_id, sfx_id) pair."""
    refs: set[str] = set()
    for plural in ("items", "abilities", "npcs", "factions", "lore_terms"):
        for rec in load_jsonl(GAME_DATA / f"{plural}.jsonl"):
            for k, v in rec.items():
                kl = str(k).lower()
                if isinstance(v, str) and any(kl == p or kl.endswith("_" + p) for p in _SFX_KEY_PATTERNS):
                    if v:
                        refs.add(v)
                if isinstance(v, list) and any(kl == p or kl.endswith("_" + p) for p in _SFX_KEY_LIST_PATTERNS):
                    for x in v:
                        if isinstance(x, str) and x:
                            refs.add(x)
    return refs


def check_unused(manifest: dict, allow: set[str]) -> list[str]:
    sfx_ids = {s["id"] for s in manifest.get("sounds", [])}
    referenced = _collect_sfx_refs()
    return sorted(sfx_ids - referenced - allow)


def check_ability_mismatch(manifest: dict) -> list[dict]:
    by_id = {s["id"]: s for s in manifest.get("sounds", [])}
    out: list[dict] = []
    for plural in ("items", "abilities"):
        for rec in load_jsonl(GAME_DATA / f"{plural}.jsonl"):
            for key in ("cast_sfx_id", "impact_sfx_id", "sfx_id",
                       "ambient_sfx_id", "sound_id"):
                ref = rec.get(key)
                if not isinstance(ref, str) or not ref or ref not in by_id:
                    continue
                bag = _sfx_token_bag(by_id[ref])
                triggers = []
                for k in ("school", "damage_type"):
                    v = rec.get(k)
                    if not isinstance(v, str):
                        continue
                    neg = NEGATIVE_TOKENS.get(v.lower(), set())
                    hit = neg & bag
                    if hit:
                        triggers.append(f"record.{k}={v} ↯ sfx[{','.join(sorted(hit))}]")
                if triggers:
                    out.append({"record_id": rec.get("id", "?"),
                                "kind": plural, "key": key,
                                "sfx_id": ref, "triggers": triggers})
    return out


def check_bus_sanity(manifest: dict) -> list[dict]:
    out: list[dict] = []
    for snd in manifest.get("sounds", []):
        sid = snd["id"]
        expected = _expected_bus(sid)
        if not expected:
            continue
        actual = _actual_bus(snd)
        if actual and actual != expected:
            out.append({
                "sfx_id": sid, "expected_bus": expected, "actual_bus": actual,
                "category": snd.get("category"),
                "tags": (snd.get("cue") or {}).get("tags") or snd.get("tags") or [],
            })
    return out


def check_ambience_coverage() -> dict:
    """Every biome in the registry must (1) be in the recipe and (2) have a
    built pack on disk. Returns a dict with the per-biome verdict."""
    if not BIOME_REGISTRY.exists():
        return {"ok": True, "registered": 0, "missing_recipe": [],
                "missing_pack": [], "extra_recipe": []}
    reg = json.loads(BIOME_REGISTRY.read_text(encoding="utf-8"))
    biomes = list((reg.get("biomes") or {}).keys())
    recipe = (json.loads(AMBIENCE_RECIPE.read_text(encoding="utf-8"))
              if AMBIENCE_RECIPE.exists() else {"biomes": {}})
    summary = (json.loads(AMBIENCE_SUMMARY.read_text(encoding="utf-8"))
               if AMBIENCE_SUMMARY.exists() else {"biomes": {}})
    recipe_biomes = set(recipe.get("biomes", {}).keys())
    summary_biomes = set(summary.get("biomes", {}).keys())
    missing_recipe = sorted(b for b in biomes if b not in recipe_biomes)
    missing_pack = sorted(b for b in biomes if b not in summary_biomes)
    extra_recipe = sorted(b for b in recipe_biomes if b not in biomes)
    return {
        "registered": len(biomes),
        "recipe_biomes": sorted(recipe_biomes),
        "pack_biomes": sorted(summary_biomes),
        "missing_recipe": missing_recipe,
        "missing_pack": missing_pack,
        "extra_recipe": extra_recipe,
        "ok": not (missing_recipe or missing_pack),
    }


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=SFX_MANIFEST)
    ap.add_argument("--link-validator-json", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 if any of (a) unused / (b) mismatch / "
                         "(c) bus-sanity trip. (d) coverage is informational.")
    ap.add_argument("--warn-only", action="store_true",
                    help="Always exit 0 even if strict checks trip.")
    ap.add_argument("--allow-unused", default="",
                    help="Comma-separated sfx IDs to whitelist as "
                         "intentionally unused.")
    args = ap.parse_args()

    if not args.manifest.exists():
        print(f"[lint_audio] ERROR: manifest not found: {args.manifest}",
              file=sys.stderr)
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    # Run / parse link_validator. We ignore its exit code; lint_audio is
    # additive — link_validator's own pass/fail is its concern.
    if args.link_validator_json and args.link_validator_json.exists():
        lv_report = json.loads(args.link_validator_json.read_text(encoding="utf-8"))
    else:
        scratch = ASSETS / "audio" / "_lv_scratch.json"
        lv_report = _run_link_validator(scratch)

    allow = {s.strip() for s in args.allow_unused.split(",") if s.strip()}

    unused = check_unused(manifest, allow)
    mismatches = check_ability_mismatch(manifest)
    bus_issues = check_bus_sanity(manifest)
    coverage = check_ambience_coverage()

    report = {
        "manifest": str(args.manifest),
        "sfx_count": len(manifest.get("sounds", [])),
        "unused_count": len(unused),
        "mismatch_count": len(mismatches),
        "bus_sanity_count": len(bus_issues),
        "coverage": coverage,
        "unused": unused,
        "mismatches": mismatches,
        "bus_sanity": bus_issues,
        "link_validator_summary": {
            "missing": lv_report.get("missing", {}),
            "ok": lv_report.get("ok"),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[lint_audio] sfx_count={report['sfx_count']} "
          f"unused={report['unused_count']} "
          f"mismatch={report['mismatch_count']} "
          f"bus_sanity={report['bus_sanity_count']}")
    if unused[:5]:
        print(f"[lint_audio] sample unused : {', '.join(unused[:5])}"
              + (" ..." if len(unused) > 5 else ""))
    for m in mismatches[:5]:
        print(f"[lint_audio] MISMATCH {m['record_id']}.{m['key']} -> "
              f"{m['sfx_id']}: {'; '.join(m['triggers'])}")
    for b in bus_issues[:5]:
        print(f"[lint_audio] BUS {b['sfx_id']}: expected {b['expected_bus']} "
              f"got {b['actual_bus']}")
    cov = report["coverage"]
    print(f"[lint_audio] coverage registered={cov['registered']} "
          f"missing_recipe={len(cov['missing_recipe'])} "
          f"missing_pack={len(cov['missing_pack'])} "
          f"extra_recipe={len(cov['extra_recipe'])}")
    if cov["missing_recipe"]:
        print(f"[lint_audio] MISSING recipe entries for: "
              f"{', '.join(cov['missing_recipe'])}")
    if cov["missing_pack"]:
        print(f"[lint_audio] MISSING ambience packs for: "
              f"{', '.join(cov['missing_pack'])}")

    print(f"[lint_audio] report -> {args.report}")

    if args.warn_only:
        return 0
    if args.strict:
        ok = (not unused) and (not mismatches) and (not bus_issues)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
