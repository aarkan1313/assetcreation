"""Postprocess orchestrator for AI-route prop outputs.

Takes a fresh GLB from `trellis2_route.py` / `hunyuan3d_route.py` / `meshy_route.py`
and walks it through every existing postprocess stage to produce a Godot-ready
prop entry under `world/props/library/<id>/`. Each stage is one of the existing
scripts; this file is glue, not new logic.

Pipeline (per render_class defaults):

  AI-route GLB
    -> 1. stage into library: world/props/ai_routes/<route>/<id>/  ->  world/props/library/<id>/
    -> 2. preprocess: meshy/preprocess.py (clean / merge verts / normalize-scale / target-tris)
    -> 3. lod_chain.py: 4-tier (or 1-tier for billboard_only) DECIMATE chain
    -> 4. collision_decompose.py: CoACD convex hulls (skipped for scatter)
    -> 5. billboard_bake.py: 8-angle horizontal strip (skipped for hero/decal)
    -> 6. pbr_material_bind.py: bind to texture-library set
    -> 7. validate_props.py: prop.json contract check
    -> 8. export_godot.py: multi-LOD .tscn + multimesh template

The orchestrator writes a per-stage timing report to <out_dir>/postprocess_log.json
and returns non-zero if any stage failed.

CLI (single prop):
  python postprocess_ai_route.py \
    --source-glb D:/assets/world/props/ai_routes/trellis2/ruined_obelisk_a_gate/model_lod0.glb \
    --id obelisk_egyptian_a01 \
    --family obelisk \
    --render-class hero_prop \
    --texture-set biome_grassland

CLI (skip-from):
  --skip-from preprocess     # already preprocessed; jump straight to LOD chain
  --skip-from lod            # mesh + LOD chain done; jump to collision
  --skip-from collision      # ...etc

CLI flags fan out to per-stage scripts. See `--help`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ASSETS = Path(r"D:\assets")
LIBRARY = ASSETS / "world" / "props" / "library"
TEXTURE_LIBRARY = ASSETS / "world" / "textures" / "library"
GODOT_OUT = ASSETS / "godot_pack" / "props"

PREPROCESS_PY = ASSETS / "meshy" / "preprocess.py"
LOD_PY        = ASSETS / "pipelines" / "props" / "lod_chain.py"
COLLISION_PY  = ASSETS / "pipelines" / "props" / "collision_decompose.py"
BILLBOARD_PY  = ASSETS / "pipelines" / "props" / "billboard_bake.py"
PBR_BIND_PY   = ASSETS / "pipelines" / "props" / "pbr_material_bind.py"
VALIDATE_PY   = ASSETS / "pipelines" / "props" / "validate_props.py"
EXPORT_PY     = ASSETS / "pipelines" / "props" / "export_godot.py"


# Per-render_class defaults. Match what J2 SOTA spec + ai_route_dispatch say.
RENDER_CLASS_DEFAULTS = {
    "hero_prop": {
        "preprocess_target_tris": 100_000,   # keep most of Trellis2's 194k
        "lod_ratios": [1.0, 0.65, 0.35, 0.15],
        "lod_distances_m": [25, 60, 120, 200],
        "collision": "convex",
        "do_billboard": False,                # hero never falls back to a sprite
    },
    "scene_prop": {
        "preprocess_target_tris": 30_000,
        "lod_ratios": [1.0, 0.5, 0.2, 0.08],
        "lod_distances_m": [15, 40, 90, 160],
        "collision": "convex",
        "do_billboard": True,
    },
    "scatter_multimesh": {
        "preprocess_target_tris": 8_000,
        "lod_ratios": [1.0, 0.5, 0.2, 0.08],
        "lod_distances_m": [25, 60, 120, 200],
        "collision": "none",                  # never per-instance collision in scatter
        "do_billboard": True,
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd: list, *, label: str) -> tuple[bool, float, str]:
    """Run a subprocess, time it, return (ok, elapsed_s, stderr_tail)."""
    print(f"\n[postprocess] $ {label}")
    print(f"[postprocess]   {' '.join(str(c) for c in cmd)}")
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0
    ok = r.returncode == 0
    if r.stdout:
        # echo last few stdout lines for visibility
        tail = "\n".join(r.stdout.strip().splitlines()[-8:])
        print(f"[postprocess]   stdout (tail):\n{tail}")
    if not ok:
        err_tail = (r.stderr or r.stdout or "").strip().splitlines()[-12:]
        err = "\n".join(err_tail)
        print(f"[postprocess]   FAILED in {elapsed:.1f}s\n[postprocess]   stderr (tail):\n{err}",
              file=sys.stderr)
        return False, elapsed, err
    print(f"[postprocess]   OK in {elapsed:.1f}s")
    return True, elapsed, ""


def stage_into_library(*, source_glb: Path, library_dir: Path, prop_id: str,
                       family: str, render_class: str, source_method: str,
                       license_str: str, source_image: Path | None) -> Path:
    """Copy the AI-route GLB into the library and bootstrap a v1 prop.json.

    Stages downstream of this assume:
      - library/<id>/model_lod0.glb exists
      - library/<id>/prop.json exists with at minimum:
          schema, id, family, kit, render_class, collision (placeholder),
          lods (single-tier, will be expanded by lod_chain),
          material_slots, source_method, license
    """
    out_dir = library_dir / prop_id
    out_dir.mkdir(parents=True, exist_ok=True)
    dst_glb = out_dir / "model_lod0.glb"
    shutil.copy2(source_glb, dst_glb)

    # Inspect the source mesh to bootstrap a sane `triangles` hint. lod_chain.py
    # multiplies this by each LOD ratio to populate prop.json's per-LOD count;
    # if we leave it as 0, every LOD reports tris=8 (the floor).
    base_tris = 0
    try:
        import trimesh as _tm
        _m = _tm.load(source_glb, force="mesh")
        base_tris = int(len(_m.faces))
    except Exception as _e:
        print(f"[postprocess] WARNING: couldn't read mesh face count from {source_glb} ({_e})")

    # Bootstrap prop.json. lod_chain.py + collision + pbr_bind + validator
    # will rewrite/expand fields they own.
    prop = {
        "schema": "prop_asset.v1",
        "id": prop_id,
        "family": family,
        "kit": "ai_hero_props",
        "source_method": source_method,
        "license": license_str,
        "render_class": render_class,
        "collision": "none",  # collision_decompose will overwrite if applicable
        "origin": "model_origin",
        "scale_m": [1.0, 1.0, 1.0],
        "footprint_radius_m": 0.5,
        "lods": [
            {"file": "model_lod0.glb", "max_distance_m": 25, "triangles": base_tris,
             "ratio_of_lod0": 1.0},
        ],
        "placement_tags": ["ai_prop", family],
        "material_slots": ["pbr_default"],
        "qa": "qa.json",
        "provenance": {
            "source_glb": str(source_glb),
            "staged_at_utc": now_iso(),
        },
    }
    if source_image and source_image.exists():
        prop["provenance"]["source_image"] = str(source_image)
        try:
            shutil.copy2(source_image, out_dir / "source_concept.png")
        except Exception:
            pass

    (out_dir / "prop.json").write_text(json.dumps(prop, indent=2), encoding="utf-8")
    print(f"[postprocess] staged {source_glb.name} -> {dst_glb}")
    return out_dir


def update_prop_field(prop_dir: Path, **fields: Any) -> None:
    p = prop_dir / "prop.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data.update(fields)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def stage_preprocess(prop_dir: Path, *, target_tris: int, normalize_scale: bool) -> tuple[bool, float, str]:
    """Run meshy/preprocess.py on the LOD0 GLB, in-place."""
    src = prop_dir / "model_lod0.glb"
    tmp = prop_dir / "model_lod0_pre.glb"
    cmd = [
        sys.executable, str(PREPROCESS_PY), str(src), str(tmp),
        "--target-tris", str(target_tris),
        "--merge-distance", "0.0001",
    ]
    if normalize_scale:
        cmd.append("--normalize-scale")
    ok, t, err = run(cmd, label=f"preprocess {prop_dir.name}")
    if ok and tmp.exists():
        # Replace the LOD0 with the preprocessed version
        shutil.copy2(tmp, src)
        tmp.unlink()
    return ok, t, err


def stage_lod_chain(prop_dir: Path, *, ratios: list[float], distances: list[float]) -> tuple[bool, float, str]:
    cmd = [
        sys.executable, str(LOD_PY), prop_dir.name,
        "--ladder", *[str(r) for r in ratios],
        "--distances", *[str(d) for d in distances],
        "--library", str(prop_dir.parent),
    ]
    return run(cmd, label=f"lod_chain {prop_dir.name}")


def stage_collision(prop_dir: Path, render_class: str) -> tuple[bool, float, str]:
    cmd = [sys.executable, str(COLLISION_PY), prop_dir.name,
           "--library", str(prop_dir.parent)]
    if render_class == "hero_prop":
        cmd += ["--threshold", "0.02", "--max-hulls", "24"]
    elif render_class == "scene_prop":
        cmd += ["--threshold", "0.05", "--max-hulls", "8"]
    return run(cmd, label=f"collision_decompose {prop_dir.name}")


def stage_billboard(prop_dir: Path) -> tuple[bool, float, str]:
    cmd = [
        sys.executable, str(BILLBOARD_PY), prop_dir.name,
        "--library", str(prop_dir.parent),
        "--single",  # cheap front-only impostor; adequate for far-distance scatter
    ]
    return run(cmd, label=f"billboard_bake {prop_dir.name}")


def stage_pbr_bind(prop_dir: Path, *, texture_set: str | None) -> tuple[bool, float, str]:
    cmd = [sys.executable, str(PBR_BIND_PY), prop_dir.name,
           "--library", str(prop_dir.parent)]
    if texture_set:
        cmd += ["--slot", f"pbr_default={texture_set}"]
    return run(cmd, label=f"pbr_material_bind {prop_dir.name}")


def stage_validate(prop_dir: Path) -> tuple[bool, float, str]:
    # validate_props.py validates ALL props under --library; no per-id flag.
    # That's fine for our purposes — a fresh prop will be included; if any
    # OTHER prop in the library is broken, that's an existing factory bug,
    # not something this orchestrator caused. We treat exit code 0 as pass.
    cmd = [sys.executable, str(VALIDATE_PY),
           "--library", str(prop_dir.parent)]
    return run(cmd, label=f"validate_props (full library; this prop = {prop_dir.name})")


def stage_export_godot(prop_dir: Path, godot_out: Path) -> tuple[bool, float, str]:
    cmd = [sys.executable, str(EXPORT_PY),
           "--library", str(prop_dir.parent),
           "--out", str(godot_out),
           "--id", prop_dir.name]
    return run(cmd, label=f"export_godot {prop_dir.name}")


STAGES = [
    "preprocess", "lod", "collision", "billboard", "pbr_bind", "validate", "export",
]


def orchestrate(*, source_glb: Path, prop_id: str, family: str, render_class: str,
                source_method: str, license_str: str, source_image: Path | None,
                texture_set: str | None, library_dir: Path, godot_out: Path,
                preprocess_target_tris: int | None = None,
                lod_ratios: list[float] | None = None,
                lod_distances: list[float] | None = None,
                normalize_scale: bool = True,
                skip_from: str | None = None,
                stop_after: str | None = None) -> dict:
    """Run all 7 postprocess stages on a fresh AI-route GLB.

    Returns a stage-by-stage report dict (also written to postprocess_log.json
    inside the prop dir).
    """
    defaults = RENDER_CLASS_DEFAULTS[render_class]
    if preprocess_target_tris is None:
        preprocess_target_tris = defaults["preprocess_target_tris"]
    if lod_ratios is None:
        lod_ratios = defaults["lod_ratios"]
    if lod_distances is None:
        lod_distances = defaults["lod_distances_m"]
    do_collision = defaults["collision"] != "none"
    do_billboard = defaults["do_billboard"]

    report: dict = {
        "prop_id": prop_id,
        "render_class": render_class,
        "source_glb": str(source_glb),
        "started_at_utc": now_iso(),
        "stages": [],
        "ok": True,
    }

    # Stage 0: stage into library + bootstrap prop.json (always).
    prop_dir = stage_into_library(
        source_glb=source_glb, library_dir=library_dir, prop_id=prop_id,
        family=family, render_class=render_class,
        source_method=source_method, license_str=license_str,
        source_image=source_image,
    )
    report["prop_dir"] = str(prop_dir)
    report["stages"].append({"stage": "stage_into_library", "ok": True, "elapsed_s": 0.0})

    skip_idx = STAGES.index(skip_from) if skip_from else -1
    stop_idx = STAGES.index(stop_after) if stop_after else len(STAGES)

    def should_run(stage_name: str) -> bool:
        i = STAGES.index(stage_name)
        return i > skip_idx and i <= stop_idx

    # Stage 1: preprocess
    if should_run("preprocess"):
        ok, t, err = stage_preprocess(prop_dir, target_tris=preprocess_target_tris,
                                      normalize_scale=normalize_scale)
        report["stages"].append({"stage": "preprocess", "ok": ok, "elapsed_s": t,
                                 "target_tris": preprocess_target_tris, "err": err})
        if not ok:
            report["ok"] = False
            (prop_dir / "postprocess_log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

    # Stage 2: LOD chain
    if should_run("lod"):
        ok, t, err = stage_lod_chain(prop_dir, ratios=lod_ratios, distances=lod_distances)
        report["stages"].append({"stage": "lod", "ok": ok, "elapsed_s": t,
                                 "ratios": lod_ratios, "distances_m": lod_distances, "err": err})
        if not ok:
            report["ok"] = False
            (prop_dir / "postprocess_log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

    # Stage 3: collision (skip if scatter / decal)
    if should_run("collision"):
        if do_collision:
            update_prop_field(prop_dir, collision="convex")
            ok, t, err = stage_collision(prop_dir, render_class)
            report["stages"].append({"stage": "collision", "ok": ok, "elapsed_s": t, "err": err})
            if not ok:
                report["ok"] = False
                (prop_dir / "postprocess_log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                return report
        else:
            report["stages"].append({"stage": "collision", "ok": True, "elapsed_s": 0.0,
                                     "skipped": "render_class doesn't use collision"})

    # Stage 4: billboard
    if should_run("billboard"):
        if do_billboard:
            ok, t, err = stage_billboard(prop_dir)
            report["stages"].append({"stage": "billboard", "ok": ok, "elapsed_s": t, "err": err})
            # Billboard failure is non-fatal — hero/scene props don't need it.
            if not ok and render_class == "scatter_multimesh":
                report["ok"] = False
        else:
            report["stages"].append({"stage": "billboard", "ok": True, "elapsed_s": 0.0,
                                     "skipped": "hero_prop doesn't use billboards"})

    # Stage 5: PBR bind
    if should_run("pbr_bind"):
        ok, t, err = stage_pbr_bind(prop_dir, texture_set=texture_set)
        report["stages"].append({"stage": "pbr_bind", "ok": ok, "elapsed_s": t,
                                 "texture_set": texture_set, "err": err})
        if not ok:
            report["ok"] = False
            (prop_dir / "postprocess_log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

    # Stage 6: validate
    if should_run("validate"):
        ok, t, err = stage_validate(prop_dir)
        report["stages"].append({"stage": "validate", "ok": ok, "elapsed_s": t, "err": err})
        if not ok:
            report["ok"] = False
            (prop_dir / "postprocess_log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

    # Stage 7: Godot export
    if should_run("export"):
        ok, t, err = stage_export_godot(prop_dir, godot_out)
        report["stages"].append({"stage": "export", "ok": ok, "elapsed_s": t, "err": err})
        if not ok:
            report["ok"] = False

    report["finished_at_utc"] = now_iso()
    (prop_dir / "postprocess_log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[postprocess] FINISHED prop_id={prop_id} ok={report['ok']}")
    print(f"[postprocess] log -> {prop_dir / 'postprocess_log.json'}")
    print(f"[postprocess] godot -> {godot_out / prop_id}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-glb", type=Path, required=True,
                    help="Path to the fresh AI-route GLB to postprocess.")
    ap.add_argument("--id", required=True, help="Target prop_id (becomes the library folder name).")
    ap.add_argument("--family", default="hero",
                    help="Prop family (e.g. obelisk, fountain, statue).")
    ap.add_argument("--render-class", default="hero_prop",
                    choices=list(RENDER_CLASS_DEFAULTS.keys()))
    ap.add_argument("--source-method", default="trellis2_image_to_3d",
                    help="Provenance: which AI route produced the source GLB.")
    ap.add_argument("--license", dest="license_str", default="MIT",
                    help="License string. MIT for Trellis2; tencent_hunyuan_community for HY3D.")
    ap.add_argument("--source-image", type=Path, default=None,
                    help="Original concept PNG; archived alongside the prop for provenance.")
    ap.add_argument("--texture-set", default=None,
                    help="Texture-library set to bind (e.g. biome_grassland, biome_lava_field). "
                         "If omitted, pbr_material_bind picks a default.")
    ap.add_argument("--library", type=Path, default=LIBRARY)
    ap.add_argument("--godot-out", type=Path, default=GODOT_OUT)
    ap.add_argument("--preprocess-target-tris", type=int, default=None)
    ap.add_argument("--lod-ratios", nargs="+", type=float, default=None)
    ap.add_argument("--lod-distances", nargs="+", type=float, default=None)
    ap.add_argument("--no-normalize-scale", action="store_true",
                    help="Don't run --normalize-scale in preprocess. Default normalizes longest axis to 1.0.")
    ap.add_argument("--skip-from", choices=STAGES, default=None,
                    help="Skip past this stage (use when re-running after a stage's output exists).")
    ap.add_argument("--stop-after", choices=STAGES, default=None,
                    help="Stop after this stage (debug).")
    args = ap.parse_args()

    if not args.source_glb.exists():
        print(f"[postprocess] missing source GLB: {args.source_glb}", file=sys.stderr)
        return 2

    report = orchestrate(
        source_glb=args.source_glb,
        prop_id=args.id,
        family=args.family,
        render_class=args.render_class,
        source_method=args.source_method,
        license_str=args.license_str,
        source_image=args.source_image,
        texture_set=args.texture_set,
        library_dir=args.library,
        godot_out=args.godot_out,
        preprocess_target_tris=args.preprocess_target_tris,
        lod_ratios=args.lod_ratios,
        lod_distances=args.lod_distances,
        normalize_scale=not args.no_normalize_scale,
        skip_from=args.skip_from,
        stop_after=args.stop_after,
    )

    # Print summary table
    print("\n=== postprocess summary ===")
    print(f"{'stage':<22} {'ok':<5} {'elapsed_s':>9}")
    for s in report["stages"]:
        print(f"{s['stage']:<22} {str(s['ok']):<5} {s['elapsed_s']:>9.1f}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
