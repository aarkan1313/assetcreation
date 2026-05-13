"""Overnight queue — chains multiple diversity batches + experiments.

The plan (estimated ~8 hours total at current ComfyUI throughput):

  STAGE A — Palette-lock validation (cheap, runs first; fails fast if broken):
    Run tx_family.py against 5 existing _review/ candidates (one per
    biome). Validates the palette-lock approach with empirical data
    before the rest of the queue burns hours generating siblings.

  STAGE B — Sibling batches (~3.75h, the biggest piece):
    alpine_siblings  (30 ground prompts)
    desert_siblings  (30 mid prompts)
    rocky_siblings   (30 ground prompts)
    wetland_siblings (30 mid prompts)
    forest_siblings  (30 mid prompts)

  STAGE C — New biome batches (~2.5h):
    volcanic  (51 prompts)
    tundra    (51 prompts)

  STAGE D — Mip-ladder experiment (~0.75h):
    Auto-pick top 10 winners by composite score (across all existing
    biomes' kept _review/ sets). Re-generate at size=2048 with the
    ladder flag set. Measures whether 2048 buys real detail or just
    upscale.

Each stage runs continue-on-fail — if one batch dies, the queue logs
it and moves on. Total candidates ~262, plus the experiments.

Outputs:
  the world 4/candidates/<biome>/ — for diversity batches
  the world 4/candidates/_pipeline_review/palette_lock/ — for stage A
  the world 4/candidates/_pipeline_review/mip_ladder/ — for stage D
  D:/tmp/overnight_queue.log — full log
  D:/tmp/overnight_queue_summary.json — per-stage outcomes
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(r"D:/assets/world 4")
PY = r"C:\Program Files\Python312\python.exe"
LOG_DIR = Path(r"D:/tmp/overnight_queue_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH = LOG_DIR / "summary.json"


@dataclass
class StageResult:
    name: str
    started_at: str = ""
    completed_at: str = ""
    duration_s: float = 0.0
    returncode: Optional[int] = None
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(cmd: list[str], log_path: Path, name: str) -> StageResult:
    """Run a subprocess, tee stdout to a per-stage log file, return result."""
    r = StageResult(name=name, started_at=_now())
    t = time.time()
    print(f"\n{'='*72}\n=== STAGE: {name}\n=== cmd: {' '.join(cmd)}\n{'='*72}",
          flush=True)
    with log_path.open("w", encoding="utf-8", buffering=1) as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT)
    r.returncode = proc.returncode
    r.duration_s = round(time.time() - t, 1)
    r.completed_at = _now()
    if proc.returncode != 0:
        r.error = f"returncode {proc.returncode}; see {log_path}"
    print(f"=== {name} done rc={proc.returncode} duration={r.duration_s:.0f}s",
          flush=True)
    return r


def _save_summary(results: list[StageResult]) -> None:
    SUMMARY_PATH.write_text(
        json.dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8")


# ---------- STAGE A — palette-lock validation ----------

PALETTE_LOCK_TARGETS = [
    # (label, variants_dir under candidates/)
    ("alpine_firn_dense",
     ROOT / "the world 4/candidates/alpine/ground/_review/03_firn_dense/variants"),
    ("desert_rock_fragments_sand",
     ROOT / "the world 4/candidates/desert/mid/03_rock_fragments_sand/variants"),
    ("rocky_mossy_scree",
     ROOT / "the world 4/candidates/rocky/ground/06_mossy_scree/variants"),
    ("wetland_skunk_cabbage",
     ROOT / "the world 4/candidates/wetland/mid/08_skunk_cabbage/variants"),
    ("forest_lichen_on_rock_brown",
     ROOT / "the world 4/candidates/forest/mid/01_lichen_on_rock_brown/variants"),
]


def stage_palette_lock() -> StageResult:
    r = StageResult(name="palette_lock_validation", started_at=_now())
    t = time.time()
    out_root = ROOT / "the world 4/candidates/_pipeline_review/palette_lock"
    out_root.mkdir(parents=True, exist_ok=True)
    per_target = {}
    for label, vdir in PALETTE_LOCK_TARGETS:
        if not vdir.exists():
            per_target[label] = {"skipped": True, "reason": f"not found: {vdir}"}
            continue
        target_out = out_root / label
        log_path = LOG_DIR / f"palette_lock_{label}.log"
        cmd = [
            PY, str(ROOT / "pipeline/textures/tx_family.py"),
            "--variants", str(vdir),
            "--out", str(target_out),
            "--anchor", "0",
        ]
        sub = _run(cmd, log_path, f"palette_lock/{label}")
        report_path = target_out / "family_report.json"
        if report_path.exists():
            try:
                rep = json.loads(report_path.read_text(encoding="utf-8"))
                per_target[label] = {
                    "ok": True,
                    "improvement_factor": rep["palette_dist_to_anchor"]["improvement_factor"],
                    "pre_mean": rep["palette_dist_to_anchor"]["mean_pre"],
                    "post_mean": rep["palette_dist_to_anchor"]["mean_post"],
                }
            except Exception as e:
                per_target[label] = {"ok": False, "error": str(e)}
        else:
            per_target[label] = {"ok": False, "error": "no report"}
    r.duration_s = round(time.time() - t, 1)
    r.completed_at = _now()
    r.returncode = 0
    r.extra = {"per_target": per_target}
    # also compute aggregate improvement
    factors = [v["improvement_factor"] for v in per_target.values()
               if isinstance(v, dict) and v.get("ok") and "improvement_factor" in v]
    if factors:
        r.extra["mean_improvement_factor"] = round(sum(factors) / len(factors), 2)
    return r


# ---------- STAGE B + C — diversity batches ----------

SIBLING_BATCHES = [
    "alpine_siblings",
    "desert_siblings",
    "rocky_siblings",
    "wetland_siblings",
    "forest_siblings",
]
NEW_BIOME_BATCHES = ["volcanic", "tundra"]


def stage_diversity_batch(biome: str) -> StageResult:
    log_path = LOG_DIR / f"diversity_{biome}.log"
    cmd = [
        PY, str(ROOT / "pipeline/diversity_run.py"),
        "--biome", biome,
    ]
    return _run(cmd, log_path, f"diversity/{biome}")


# ---------- STAGE D — mip-ladder experiment ----------

def _find_top_winners(n: int = 10) -> list[Path]:
    """Auto-pick top-N candidates by composite score across all biome
    _review/ sets. Reads each candidate's variants/ranking.json and
    sorts by best variant's composite score."""
    biome_root = ROOT / "the world 4/candidates"
    scored: list[tuple[float, Path]] = []
    for index_path in biome_root.rglob("_index.json"):
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        subdir = idx.get("candidate_subdir")
        base = index_path.parent / subdir if subdir else index_path.parent
        for cid, entry in idx.get("candidates", {}).items():
            if entry.get("grade") != "A":
                continue
            cand_dir = base / cid
            ranking_path = cand_dir / "variants" / "ranking.json"
            if not ranking_path.exists():
                continue
            try:
                ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            best = next((r for r in ranking if "composite" in r), None)
            if best:
                scored.append((best["composite"], cand_dir))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [p for _, p in scored[:n]]


def stage_mip_ladder() -> StageResult:
    r = StageResult(name="mip_ladder_2048", started_at=_now())
    t = time.time()
    winners = _find_top_winners(10)
    out_root = ROOT / "the world 4/candidates/_pipeline_review/mip_ladder"
    out_root.mkdir(parents=True, exist_ok=True)
    per_target = {}
    for winner_dir in winners:
        # Read prompt + category from its manifest
        manifest = winner_dir / "manifest.json"
        if not manifest.exists():
            per_target[winner_dir.name] = {"skipped": True, "reason": "no manifest"}
            continue
        m = json.loads(manifest.read_text(encoding="utf-8"))
        prompt = m.get("prompt", "")
        category = m.get("settings", {}).get("category", "Rock")
        # Identify biome from path
        biome = winner_dir.parts[-4] if "candidates" in winner_dir.parts else "?"
        slot = winner_dir.parts[-3]
        cid = winner_dir.name
        label = f"{biome}_{slot}_{cid}"
        target_out = out_root / label
        log_path = LOG_DIR / f"mip_ladder_{label}.log"
        # Run at size=2048 to test the upscale-vs-real-detail claim
        cmd = [
            PY, str(ROOT / "pipeline/textures/tx_pipeline.py"),
            "--prompt", prompt,
            "--id", f"mipladder_{label}",
            "--out-dir", str(target_out),
            "--category", category,
            "--variants", "1",
            "--size", "2048",
        ]
        sub = _run(cmd, log_path, f"mip_ladder/{label}")
        per_target[label] = {
            "winner_dir": str(winner_dir),
            "size": 2048,
            "rc": sub.returncode,
            "duration_s": sub.duration_s,
        }
    r.duration_s = round(time.time() - t, 1)
    r.completed_at = _now()
    r.returncode = 0
    r.extra = {"n_targets": len(winners), "per_target": per_target}
    return r


# ---------- main ----------

def main() -> int:
    print(f"\n[overnight_queue] starting at {_now()}\n", flush=True)
    results: list[StageResult] = []

    # Stage A: palette-lock validation (fails fast if module is broken)
    print("\n>>> STAGE A: palette-lock validation\n", flush=True)
    r = stage_palette_lock()
    results.append(r)
    _save_summary(results)
    print(f"  mean improvement factor: "
          f"{r.extra.get('mean_improvement_factor', '?')}x\n", flush=True)

    # Stage B: sibling batches
    print("\n>>> STAGE B: sibling batches (5 × ~45min)\n", flush=True)
    for biome in SIBLING_BATCHES:
        r = stage_diversity_batch(biome)
        results.append(r)
        _save_summary(results)

    # Stage C: new biomes
    print("\n>>> STAGE C: new biome batches (2 × ~75min)\n", flush=True)
    for biome in NEW_BIOME_BATCHES:
        r = stage_diversity_batch(biome)
        results.append(r)
        _save_summary(results)

    # Stage D: mip-ladder experiment
    print("\n>>> STAGE D: mip-ladder 2048 experiment (10 × ~4min)\n", flush=True)
    r = stage_mip_ladder()
    results.append(r)
    _save_summary(results)

    # Final summary
    print(f"\n{'='*72}\n=== overnight queue done at {_now()}\n{'='*72}", flush=True)
    total_s = sum(r.duration_s for r in results)
    print(f"  total wall time: {total_s/60:.0f} min")
    print(f"  stages: {len(results)}")
    print(f"  failures: {sum(1 for r in results if r.error)}")
    print(f"  summary: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
