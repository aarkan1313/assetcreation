"""Migrate flat library/w4_alpine_div_NN_slot_tag/ candidates into the
nested candidates/<biome>/<slot>/<NN>_<tag>/ tree.

Used once to absorb the original diversity_alpine.py batch outputs into
the new diversity_run.py layout. After running, the flat library dirs
can be deleted (set --delete-source).

Usage:
    python diversity_migrate.py --biome alpine
    python diversity_migrate.py --biome alpine --delete-source --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

LIBRARY = Path(r"D:\assets\world\textures\library")
BIOMES_DIR = Path(__file__).parent / "biomes"
CANDIDATES_ROOT = Path(r"D:\assets\world 4\the world 4\candidates")

# Old flat names looked like: w4_alpine_div_05_ground_old_drift
# Also _v0/_v1/_v2/_v3 variant siblings.
FLAT_RE = re.compile(r"^w4_(?P<biome>[a-z]+)_div_(?P<idx>\d+)_(?P<slot>[a-z]+)_(?P<tag>.+?)(?P<vsuffix>_v\d+)?$")


def _load_biome(biome: str) -> dict[str, Any]:
    return yaml.safe_load((BIOMES_DIR / f"{biome}.yaml").read_text(encoding="utf-8"))


def _tag_to_idx(spec: dict, slot: str, tag: str) -> int | None:
    cands = spec["slots"][slot]["candidates"]
    for i, c in enumerate(cands, start=1):
        if c["tag"] == tag:
            return i
    return None


def _prompt_for(spec: dict, slot: str, idx: int) -> str:
    cand = spec["slots"][slot]["candidates"][idx - 1]
    return spec.get("prompt_prefix", "") + cand["body"] + spec.get("prompt_suffix", "")


def migrate(biome: str, dry_run: bool, delete_source: bool) -> int:
    spec = _load_biome(biome)
    # group flat dirs by (slot, idx, tag) — collapse _v* variants under
    # their parent canonical dir.
    by_key: dict[tuple[str, int, str], dict[str, Path]] = {}
    for d in sorted(LIBRARY.iterdir()):
        if not d.is_dir():
            continue
        m = FLAT_RE.match(d.name)
        if not m:
            continue
        if m.group("biome") != biome:
            continue
        idx = int(m.group("idx"))
        slot = m.group("slot")
        tag = m.group("tag")
        vsuffix = m.group("vsuffix")
        key = (slot, idx, tag)
        # tag may itself end with _vN if FLAT_RE didn't peel one off
        # (the original driver produced both canonical and _vN siblings).
        # The "canonical" entry has no vsuffix.
        if vsuffix is None:
            by_key.setdefault(key, {})["canonical"] = d
        else:
            by_key.setdefault(key, {}).setdefault("variants", [])  # type: ignore[arg-type]
            by_key[key]["variants"].append(d)  # type: ignore[union-attr]

    print(f"[migrate] found {len(by_key)} distinct candidates for biome={biome}")

    index_by_slot: dict[str, dict[str, Any]] = {}
    moved = 0
    for (slot, idx, tag), parts in by_key.items():
        # Sanity: the yaml must know this (slot, tag) pair
        if slot not in spec["slots"]:
            print(f"  [skip] {slot}/{idx}_{tag}: slot not in yaml")
            continue
        canon_idx = _tag_to_idx(spec, slot, tag)
        if canon_idx is None:
            print(f"  [skip] {slot}/{idx}_{tag}: tag not in yaml")
            continue
        if canon_idx != idx:
            print(f"  [warn] {slot}/{tag}: yaml idx={canon_idx} != flat idx={idx}; using yaml idx")
        use_idx = canon_idx
        dst = CANDIDATES_ROOT / biome / slot / f"{use_idx:02d}_{tag}"
        print(f"  -> {dst.relative_to(CANDIDATES_ROOT)}")

        if dry_run:
            continue

        dst.mkdir(parents=True, exist_ok=True)

        # canonical maps + qa/
        canon = parts.get("canonical")
        if canon:
            for m in ("albedo", "normal", "roughness", "ao"):
                src = canon / f"{canon.name}_{m}.png"
                if src.exists():
                    shutil.copy2(src, dst / f"{m}.png")
            qa_src = canon / "qa"
            if qa_src.exists():
                qa_dst = dst / "qa"
                if qa_dst.exists():
                    shutil.rmtree(qa_dst)
                shutil.copytree(qa_src, qa_dst)
            # everything else into intermediates/
            intermediates = dst / "intermediates"
            intermediates.mkdir(exist_ok=True)
            for p in canon.iterdir():
                if not p.is_file():
                    continue
                if any(p.name == f"{canon.name}_{m}.png" for m in
                       ("albedo", "normal", "roughness", "ao")):
                    continue
                shutil.copy2(p, intermediates / p.name)

        # variant siblings -> intermediates/
        for variant_dir in parts.get("variants", []) or []:
            intermediates = dst / "intermediates"
            intermediates.mkdir(exist_ok=True)
            for p in variant_dir.iterdir():
                if p.is_file():
                    shutil.copy2(p, intermediates / p.name)

        # prompt.txt
        (dst / "prompt.txt").write_text(_prompt_for(spec, slot, use_idx),
                                        encoding="utf-8")

        # build index entry from QA json
        entry: dict[str, Any] = {
            "id": f"{use_idx:02d}_{tag}",
            "prompt": _prompt_for(spec, slot, use_idx),
            "size": 1024,  # original batch was 1024
            "status": "candidate",
            "promoted_to": None,
            "generated_at": None,
            "migrated_from_flat": True,
        }
        qa_json = dst / "qa" / "seam_score.json"
        if qa_json.exists():
            seam = json.loads(qa_json.read_text(encoding="utf-8"))
            entry["grade"] = seam.get("grade")
            checks = seam.get("checks", {})
            entry["metrics"] = {
                "periodic": checks.get("periodic_artifact", {}).get("peak_locality_ratio"),
                "edge": checks.get("edge_continuity", {}).get("overall_mse"),
                "junction": checks.get("junction_visibility", {}).get("ratio"),
                "richness": checks.get("richness", {}).get("score"),
            }
            reasons = [k for k, v in checks.items() if isinstance(v, dict) and v.get("passed") is False]
            entry["below_A_reason"] = ",".join(reasons) if reasons else None
            if entry["grade"] != "A":
                entry["status"] = "rejected_auto"
        else:
            entry["grade"] = None
            entry["metrics"] = None
            entry["below_A_reason"] = "no_qa_json"
            entry["status"] = "intermediates_only"

        index_by_slot.setdefault(slot, {"biome": biome, "slot": slot, "candidates": {}})
        index_by_slot[slot]["candidates"][f"{use_idx:02d}_{tag}"] = entry
        moved += 1

        if delete_source:
            if canon and canon.exists():
                shutil.rmtree(canon, ignore_errors=True)
            for vd in parts.get("variants", []) or []:
                shutil.rmtree(vd, ignore_errors=True)

    # save indexes
    if not dry_run:
        for slot, idx in index_by_slot.items():
            idx_path = CANDIDATES_ROOT / biome / slot / "_index.json"
            idx_path.parent.mkdir(parents=True, exist_ok=True)
            # merge with any existing index (in case some candidates were already there)
            if idx_path.exists():
                existing = json.loads(idx_path.read_text(encoding="utf-8"))
                existing.setdefault("candidates", {}).update(idx["candidates"])
                idx = existing
            idx_path.write_text(json.dumps(idx, indent=2), encoding="utf-8")
            print(f"  wrote {idx_path.relative_to(CANDIDATES_ROOT)}")

    print(f"[migrate] moved {moved} candidates" + (" (dry-run)" if dry_run else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--biome", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delete-source", action="store_true",
                    help="rm -rf library/<flat>/ after copying")
    args = ap.parse_args()
    return migrate(args.biome, args.dry_run, args.delete_source)


if __name__ == "__main__":
    raise SystemExit(main())
