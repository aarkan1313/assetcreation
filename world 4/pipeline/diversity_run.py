"""W4 diversity batch driver — biome-aware, nested-layout edition.

Replaces the flat ``diversity_alpine.py`` with a per-biome yaml-driven
pipeline that produces a nested candidate tree:

    candidates/<biome>/<slot>/<NN>_<tag>/
        albedo.png  normal.png  roughness.png  ao.png
        qa/             — seam_score.json + previews
        intermediates/  — all _v0..v3 raw FLUX + pre-delight + variant_select.json
        prompt.txt      — exact prompt used

Plus per-slot:
    candidates/<biome>/<slot>/_index.json — prompt + grade + score + status
                                            per candidate
    candidates/<biome>/<slot>/_contact_sheet.png — review at-a-glance grid

This driver still calls aaa_texture.py underneath (so the rest of the
texture infra works unchanged); the new layer happens *after* aaa_texture
finishes — outputs are pulled out of library/<id>/ and reshaped into the
nested layout.

Usage:
    python diversity_run.py --biome alpine
    python diversity_run.py --biome alpine --slots ground
    python diversity_run.py --biome alpine --only ground/fresh_powder ground/windpack
    python diversity_run.py --biome alpine --size 512   # default; pass 1024 to override
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PY = r"C:\Program Files\Python312\python.exe"
AAA = r"D:\assets\pipelines\textures\aaa_texture.py"
LIBRARY = Path(r"D:\assets\world\textures\library")
BIOMES_DIR = Path(__file__).parent / "biomes"
CANDIDATES_ROOT = Path(r"D:\assets\world 4\the world 4\candidates")

UNET = "flux-2-klein-9b-fp8.safetensors"
CLIP = "qwen_3_8b_fp8mixed.safetensors"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_biome(biome: str) -> dict[str, Any]:
    p = BIOMES_DIR / f"{biome}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"biome yaml not found: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _candidate_dir(biome: str, slot: str, idx: int, tag: str) -> Path:
    return CANDIDATES_ROOT / biome / slot / f"{idx:02d}_{tag}"


def _index_path(biome: str, slot: str) -> Path:
    return CANDIDATES_ROOT / biome / slot / "_index.json"


def _load_index(biome: str, slot: str) -> dict[str, Any]:
    p = _index_path(biome, slot)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"biome": biome, "slot": slot, "candidates": {}}


def _save_index(biome: str, slot: str, index: dict[str, Any]) -> None:
    p = _index_path(biome, slot)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(index, indent=2), encoding="utf-8")


def _aaa_id(biome: str, slot: str, idx: int, tag: str) -> str:
    """The id passed to aaa_texture.py — stays unique within library/."""
    return f"w4_div_{biome}_{slot}_{idx:02d}_{tag}"


def _already_done(biome: str, slot: str, idx: int, tag: str) -> bool:
    d = _candidate_dir(biome, slot, idx, tag)
    return all((d / f"{m}.png").exists()
               for m in ("albedo", "normal", "roughness", "ao"))


def _run_aaa_texture(slot_id: str, full_prompt: str, category: str,
                     size: int) -> int:
    cmd = [
        PY, AAA,
        "--prompt", full_prompt,
        "--id", slot_id,
        "--category", category,
        "--quality", "default",
        "--size", str(size),
        "--unet", UNET,
        "--clip", CLIP,
        "--no-gate",  # gate decision happens at our index level, after promote
    ]
    print(f"  cmd: aaa_texture --id {slot_id} --size {size}")
    return subprocess.run(cmd).returncode


def _promote_to_candidate_dir(slot_id: str, biome: str, slot: str,
                              idx: int, tag: str, prompt: str,
                              size: int) -> dict[str, Any]:
    """Move outputs from library/<slot_id>/ into candidates/<biome>/<slot>/<NN>_<tag>/
    Returns the index entry built from the QA report."""
    src = LIBRARY / slot_id
    if not src.exists():
        raise FileNotFoundError(f"aaa_texture produced no output dir: {src}")

    dst = _candidate_dir(biome, slot, idx, tag)
    dst.mkdir(parents=True, exist_ok=True)

    # canonical maps (rename: w4_div_alpine_ground_01_fresh_powder_albedo.png -> albedo.png)
    maps_found = []
    for m in ("albedo", "normal", "roughness", "ao"):
        s = src / f"{slot_id}_{m}.png"
        if s.exists():
            shutil.copy2(s, dst / f"{m}.png")
            maps_found.append(m)
    # qa/ folder
    qa_src = src / "qa"
    qa_dst = dst / "qa"
    if qa_src.exists():
        if qa_dst.exists():
            shutil.rmtree(qa_dst)
        shutil.copytree(qa_src, qa_dst)
    # intermediates: pre_delight, variant_select.json, aaa_pipeline.json
    intermediates_dst = dst / "intermediates"
    intermediates_dst.mkdir(exist_ok=True)
    for name in os.listdir(src):
        p = src / name
        if not p.is_file():
            continue
        if name == "qa":
            continue
        # skip the canonical map files (already copied)
        is_canonical_map = any(name == f"{slot_id}_{m}.png"
                               for m in ("albedo", "normal", "roughness", "ao"))
        if is_canonical_map:
            continue
        shutil.copy2(p, intermediates_dst / name)
    # also pull in the _v0..v3 variant siblings if they exist
    for variant_dir in LIBRARY.glob(f"{slot_id}_v*"):
        for vp in variant_dir.iterdir():
            if vp.is_file():
                shutil.copy2(vp, intermediates_dst / vp.name)

    # prompt.txt
    (dst / "prompt.txt").write_text(prompt, encoding="utf-8")

    # build the index entry from the QA report
    qa_json = qa_dst / "seam_score.json"
    entry: dict[str, Any] = {
        "id": f"{idx:02d}_{tag}",
        "prompt": prompt,
        "size": size,
        "maps_found": maps_found,
        "generated_at": _now_iso(),
        "status": "candidate",
        "promoted_to": None,
    }
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
        reasons = []
        for k, v in checks.items():
            if isinstance(v, dict) and v.get("passed") is False:
                reasons.append(k)
        entry["below_A_reason"] = ",".join(reasons) if reasons else None
        if entry["grade"] != "A":
            entry["status"] = "rejected_auto"
    else:
        entry["grade"] = None
        entry["metrics"] = None
        entry["below_A_reason"] = "no_qa_json"
        entry["status"] = "intermediates_only"

    return entry


def _cleanup_library_traces(slot_id: str) -> None:
    """Remove the flat library/<slot_id>/ and library/<slot_id>_v*/ siblings
    once we've copied everything into the nested tree."""
    for d in list(LIBRARY.glob(f"{slot_id}")) + list(LIBRARY.glob(f"{slot_id}_v*")):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


def run_candidate(biome: str, slot: str, slot_yaml: dict, idx: int,
                  cand: dict, prefix: str, suffix: str, size: int,
                  skip_existing: bool, no_cleanup: bool) -> dict | None:
    tag = cand["tag"]
    body = cand["body"]
    if skip_existing and _already_done(biome, slot, idx, tag):
        print(f"[skip] {biome}/{slot}/{idx:02d}_{tag} — already has 4 maps")
        return None
    full_prompt = prefix + body + suffix
    slot_id = _aaa_id(biome, slot, idx, tag)
    category = slot_yaml.get("category", "Rock")
    print(f"\n========== {biome}/{slot}/{idx:02d}_{tag} ==========")
    print(f"  prompt: {full_prompt}")
    rc = _run_aaa_texture(slot_id, full_prompt, category, size)
    if rc != 0:
        print(f"  !! FAILED rc={rc}")
        return {
            "id": f"{idx:02d}_{tag}",
            "prompt": full_prompt,
            "size": size,
            "status": "failed",
            "rc": rc,
            "generated_at": _now_iso(),
        }
    entry = _promote_to_candidate_dir(slot_id, biome, slot, idx, tag,
                                      full_prompt, size)
    if not no_cleanup:
        _cleanup_library_traces(slot_id)
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--biome", required=True, help="biome name (matches biomes/<biome>.yaml)")
    ap.add_argument("--slots", nargs="*", help="restrict to specific slots (default: all in yaml)")
    ap.add_argument("--only", nargs="*", default=[],
                    help="space-separated 'slot/tag' filters; e.g. ground/fresh_powder")
    ap.add_argument("--size", type=int, default=512,
                    help="FLUX generation size (default: 512). Pass 1024 to test 1024.")
    ap.add_argument("--no-skip", action="store_true",
                    help="re-run even if candidate already has 4 maps")
    ap.add_argument("--no-cleanup", action="store_true",
                    help="keep library/<slot_id>/ + _v* siblings after promoting")
    args = ap.parse_args()

    spec = _load_biome(args.biome)
    slots_spec = spec["slots"]
    prefix = spec.get("prompt_prefix", "")
    suffix = spec.get("prompt_suffix", "")

    if args.slots:
        slots_to_run = [s for s in args.slots if s in slots_spec]
    else:
        slots_to_run = list(slots_spec.keys())

    only_pairs = set()
    for f in args.only:
        if "/" in f:
            only_pairs.add(f)

    total = sum(len(slots_spec[s]["candidates"]) for s in slots_to_run)
    print(f"[diversity_run] biome={args.biome} slots={slots_to_run} size={args.size} total={total}")

    failures: list[str] = []
    for slot in slots_to_run:
        slot_yaml = slots_spec[slot]
        cands = slot_yaml["candidates"]
        index = _load_index(args.biome, slot)
        for i, cand in enumerate(cands, start=1):
            if only_pairs and f"{slot}/{cand['tag']}" not in only_pairs:
                continue
            entry = run_candidate(args.biome, slot, slot_yaml, i, cand,
                                  prefix, suffix, args.size,
                                  skip_existing=not args.no_skip,
                                  no_cleanup=args.no_cleanup)
            if entry is not None:
                index["candidates"][f"{i:02d}_{cand['tag']}"] = entry
                _save_index(args.biome, slot, index)
                if entry.get("status") not in ("candidate", "rejected_auto"):
                    failures.append(f"{slot}/{cand['tag']}")

    print(f"\n[diversity_run] done. failures={len(failures)}")
    for f in failures:
        print(f"  - {f}")

    # Print summary by grade per slot
    print("\n[diversity_run] grade summary:")
    for slot in slots_to_run:
        index = _load_index(args.biome, slot)
        by_grade: dict[str, int] = {}
        for e in index.get("candidates", {}).values():
            by_grade[e.get("grade") or "-"] = by_grade.get(e.get("grade") or "-", 0) + 1
        cnts = " ".join(f"{g}={n}" for g, n in sorted(by_grade.items()))
        print(f"  {args.biome}/{slot}: {cnts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
