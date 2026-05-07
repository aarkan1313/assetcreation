"""Variation sweep — one recipe + parameter ranges -> N sibling props.

Per J2 §7.1: consumes a `prop_sweep.v1` JSON spec describing a family,
parameter distributions, render_class, collision policy, and LOD ladder.
For each seed in [base_seed .. base_seed+count), it:

  1. Samples params from declared distributions (deterministic on seed).
  2. Runs proc_generate.py with --kind, --id (prefixed), --seed, --params.
  3. Runs lod_chain.py to author LOD1..LOD3 GLBs.
  4. Optionally runs collision_decompose.py per render_class policy.
  5. Optionally runs billboard_bake.py (separate item).

The recipe-side change: proc_props.py factories already accept a `params` dict
(JSON string on the CLI) and use sampled values where declared. Factories
without params declared in the sweep fall back to current defaults.

Sweep spec schema (sweeps/<file>.json):
{
  "schema": "prop_sweep.v1",
  "family": "rock_small",
  "kit": "first_party_proc",
  "count": 8,
  "id_prefix": "rock_small_a",
  "id_start_index": 1,
  "base_seed": 100,
  "render_class": "scatter_multimesh",
  "collision": "none",
  "params": {
    "displacement_magnitude": {"type": "float_range", "min": 0.10, "max": 0.30},
    "z_squash":               {"type": "float_range", "min": 0.45, "max": 0.70},
    "subdivisions":           {"type": "int_choice", "values": [3, 4, 4, 5]},
    "color_variant":          {"type": "categorical",
                                "values": ["basalt_dark", "granite_grey", "sandstone_warm"],
                                "weights": [0.5, 0.3, 0.2]}
  },
  "target_tris": 1500,
  "lod_ladder": [1.00, 0.50, 0.20, 0.08],
  "lod_distances_m": [25, 60, 120, 200],
  "billboard": false
}

CLI:
  python variation_sweep.py sweeps/rock_small_x8.json
  python variation_sweep.py sweeps/barrel_x4.json --max 2  # cap count
  python variation_sweep.py sweeps/*.json --skip-existing
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = Path(r"D:\assets")
LIBRARY = ASSETS / "world" / "props" / "library"
SWEEPS_DIR = ROOT / "sweeps"

PROC_GENERATE = ROOT / "proc_generate.py"
LOD_CHAIN = ROOT / "lod_chain.py"
COLLISION_DECOMPOSE = ROOT / "collision_decompose.py"


def sample_param(spec: dict, rng: random.Random):
    t = spec.get("type")
    if t == "float_range":
        lo, hi = float(spec["min"]), float(spec["max"])
        return round(rng.uniform(lo, hi), 4)
    if t == "int_range":
        lo, hi = int(spec["min"]), int(spec["max"])
        return rng.randint(lo, hi)
    if t == "int_choice":
        return rng.choice(spec["values"])
    if t == "categorical":
        values = spec["values"]
        weights = spec.get("weights")
        if weights:
            return rng.choices(values, weights=weights, k=1)[0]
        return rng.choice(values)
    if t == "constant":
        return spec["value"]
    raise ValueError(f"unknown param type {t!r}")


def sample_params(params_spec: dict, seed: int) -> dict:
    rng = random.Random(seed * 9173 + 1)
    out: dict = {}
    for k, sp in params_spec.items():
        out[k] = sample_param(sp, rng)
    return out


def _python() -> str:
    return sys.executable or "python"


def run_proc_generate(family: str, prop_id: str, seed: int, params: dict,
                      target_tris: int, kit: str) -> tuple[bool, str]:
    cmd = [
        _python(), str(PROC_GENERATE), family,
        "--id", prop_id,
        "--seed", str(seed),
        "--target-tris", str(target_tris),
        "--params", json.dumps(params),
        "--kit", kit,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return False, r.stdout[-1000:] + "\n" + r.stderr[-1000:]
    return True, r.stdout[-200:]


def run_lod_chain(prop_id: str, ladder: list[float] | None,
                  distances: list[float] | None) -> tuple[bool, str]:
    cmd = [_python(), str(LOD_CHAIN), prop_id]
    if ladder:
        cmd.extend(["--ladder", *[str(x) for x in ladder]])
    if distances:
        cmd.extend(["--distances", *[str(x) for x in distances]])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return False, r.stdout[-1000:] + "\n" + r.stderr[-1000:]
    return True, r.stdout[-200:]


def run_collision_decompose(prop_id: str) -> tuple[bool, str]:
    cmd = [_python(), str(COLLISION_DECOMPOSE), prop_id]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return False, r.stdout[-1000:] + "\n" + r.stderr[-1000:]
    return True, r.stdout[-200:]


def finalize_prop_json(prop_dir: Path, spec: dict, params: dict, seed: int) -> None:
    pj = prop_dir / "prop.json"
    if not pj.exists():
        return
    data = json.loads(pj.read_text(encoding="utf-8"))
    data["sweep_spec"] = spec.get("name") or spec.get("id_prefix")
    data["sweep_seed"] = seed
    data["sweep_params"] = params
    if spec.get("kit"):
        data["kit"] = spec["kit"]
    pj.write_text(json.dumps(data, indent=2))


def run_sweep(spec_path: Path, *, max_count: int | None = None,
              skip_existing: bool = False, no_collision: bool = False) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema") != "prop_sweep.v1":
        raise ValueError(f"{spec_path}: not a prop_sweep.v1 spec")

    family = spec["family"]
    count = spec.get("count", 1)
    if max_count is not None:
        count = min(count, max_count)
    id_prefix = spec.get("id_prefix", f"{family}_a")
    id_start = spec.get("id_start_index", 1)
    base_seed = spec.get("base_seed", 0)
    target_tris = spec.get("target_tris", 1500)
    ladder = spec.get("lod_ladder")
    distances = spec.get("lod_distances_m")
    kit = spec.get("kit", "first_party_proc")
    params_spec = spec.get("params", {})
    coll_policy = spec.get("collision", "none")

    rows: list[dict] = []
    for i in range(count):
        seed = base_seed + i
        prop_id = f"{id_prefix}{id_start + i:02d}"
        prop_dir = LIBRARY / prop_id

        if skip_existing and (prop_dir / "model_lod0.glb").exists():
            print(f"[variation_sweep] {prop_id} exists, skipping")
            rows.append({"id": prop_id, "ok": True, "skipped": True})
            continue

        params = sample_params(params_spec, seed)
        print(f"[variation_sweep] {prop_id} seed={seed} params={params}")
        ok, log = run_proc_generate(family, prop_id, seed, params, target_tris, kit)
        if not ok:
            print(f"  proc_generate FAILED: {log[-300:]}", file=sys.stderr)
            rows.append({"id": prop_id, "ok": False, "stage": "proc_generate", "err": log[-200:]})
            continue

        ok, log = run_lod_chain(prop_id, ladder, distances)
        if not ok:
            print(f"  lod_chain FAILED: {log[-300:]}", file=sys.stderr)
            rows.append({"id": prop_id, "ok": False, "stage": "lod_chain", "err": log[-200:]})
            continue

        if coll_policy not in (None, "none", False) and not no_collision:
            ok, log = run_collision_decompose(prop_id)
            if not ok:
                print(f"  collision_decompose WARNING: {log[-200:]}", file=sys.stderr)

        finalize_prop_json(prop_dir, spec, params, seed)
        rows.append({"id": prop_id, "ok": True, "seed": seed, "params": params})

    return {
        "spec": spec_path.name,
        "family": family,
        "count_requested": count,
        "count_ok": sum(1 for r in rows if r.get("ok")),
        "rows": rows,
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+", type=Path,
                    help="paths to one or more prop_sweep.v1 .json specs")
    ap.add_argument("--max", type=int, default=None,
                    help="cap count per spec (default: from spec)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip prop ids that already have model_lod0.glb")
    ap.add_argument("--no-collision", action="store_true",
                    help="skip collision_decompose stage even if spec asks for it")
    ap.add_argument("--report", type=Path, default=None,
                    help="write a JSON sweep report (default: print summary)")
    args = ap.parse_args()

    summaries = []
    for spec_path in args.specs:
        if not spec_path.exists():
            print(f"[variation_sweep] missing spec {spec_path}", file=sys.stderr)
            continue
        s = run_sweep(spec_path,
                      max_count=args.max,
                      skip_existing=args.skip_existing,
                      no_collision=args.no_collision)
        summaries.append(s)
        print(f"[variation_sweep] {spec_path.name} -> {s['count_ok']}/{s['count_requested']} ok")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summaries, indent=2))
        print(f"[variation_sweep] report -> {args.report}")
    total_ok = sum(s["count_ok"] for s in summaries)
    total_req = sum(s["count_requested"] for s in summaries)
    return 0 if total_ok == total_req else 1


if __name__ == "__main__":
    raise SystemExit(main())
