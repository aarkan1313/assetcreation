"""world3 orchestrator: region_request.json -> world-data bundle.

One command. One config. One bundle. End-to-end.

This is the Phase E.3 deliverable. Consumes a region request, resolves
which stages from stages.json apply, executes them in dependency
order, captures per-stage output, writes a run.json provenance
record.

Usage:
    # Validate-only:
    python world3/pipeline/world3_make.py \\
        world3/jobs/examples/desert_canyon_procedural.json --dry-run

    # Full execution:
    python world3/pipeline/world3_make.py \\
        world3/jobs/examples/desert_canyon_procedural.json

    # Only the first stages (e.g. build, skip captures + gate):
    python world3/pipeline/world3_make.py \\
        path/to/req.json --only-stages build_procedural_neighbor,build_runtime_image_cache

    # Resume mid-flow from a specific stage:
    python world3/pipeline/world3_make.py \\
        path/to/req.json --from-stage render_captures_walk

Exit codes:
    0  success (all required stages completed)
    1  one or more stages failed
    2  validation / config error (before any stage ran)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]  # D:/assets
WORLD3_ROOT = Path(__file__).resolve().parents[1]  # D:/assets/world3
STAGES_PATH = WORLD3_ROOT / "jobs" / "stages.json"
RUN_RECORDS_DIR = WORLD3_ROOT / "jobs" / "run_records"


def load_request(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"ERROR: request not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: request is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)


def load_stages() -> dict[str, Any]:
    if not STAGES_PATH.exists():
        print(f"ERROR: stages manifest not found: {STAGES_PATH}", file=sys.stderr)
        sys.exit(2)
    return json.loads(STAGES_PATH.read_text(encoding="utf-8"))


def validate_request(request_path: Path) -> bool:
    """Run validate_region_request.py against the request."""
    validator = WORLD3_ROOT / "pipeline" / "validate_region_request.py"
    result = subprocess.run(
        [sys.executable, str(validator), str(request_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        print(f"\nERROR: request failed schema validation (exit {result.returncode})", file=sys.stderr)
        return False
    return True


def determine_active_stages(request: dict, stages_manifest: dict) -> list[dict]:
    """Walk the declared stages and return those whose required_if
    evaluates true given the request.

    For now uses simple text-pattern matching against the request shape
    (no full expression evaluator). The required_if strings are designed
    to be human-readable; this function understands a small subset:

    - "always" -> always true
    - "source.type == 'X'" -> true if request.source.type == X
    - "source.type == 'X' and source.<field> is not None" -> compound
    - "source.type == 'X' or source.type == 'Y'" -> compound
    - "options.<field>" -> true if request.options.<field> is truthy
    - "world_type.<field> ..." -> field-shape checks
    """
    source_type = request.get("source", {}).get("type")
    has_orthophoto = request.get("source", {}).get("orthophoto") is not None
    view_modes = request.get("world_type", {}).get("view_modes", [])
    promote_to_gate = request.get("options", {}).get("promote_to_gate", False)
    render_captures = request.get("options", {}).get("render_captures", True)
    has_multiple_modes = len(view_modes) > 1

    active = []
    for stage in stages_manifest.get("stages", []):
        cond = stage.get("required_if", "")

        if cond == "always":
            active.append(stage)
        elif cond == "source.type == 'real' and source.orthophoto is not None":
            if source_type == "real" and has_orthophoto:
                active.append(stage)
        elif cond == "source.type == 'real' and source.orthophoto is None":
            if source_type == "real" and not has_orthophoto:
                active.append(stage)
        elif cond == "source.type == 'procedural' or source.type == 'hybrid'":
            if source_type in ("procedural", "hybrid"):
                active.append(stage)
        elif cond == "source.type == 'hybrid'":
            if source_type == "hybrid":
                active.append(stage)
        elif cond == "world_type.view_modes contains 'walk'":
            if "walk" in view_modes:
                active.append(stage)
        elif cond.startswith("world_type.biome_kit exists"):
            # Run only when the kit's terrain_blend .tres files are stale
            # or missing. Skip when the kit is already deployed so we
            # don't hit deploy_kit_to_world3.py's smaller --kit allowlist
            # (Phase E.7 finding 2026-05-11 — the deploy script only
            # knows grassland/temperate_forest, but other kits like
            # tundra and desert already have their .tres files on disk
            # from earlier work and don't need re-deployment).
            kit = request.get("world_type", {}).get("biome_kit")
            if kit:
                tres = ROOT / "world3" / "textures" / "wgv3" / f"terrain_blend_{kit}.tres"
                if not tres.exists():
                    active.append(stage)
        elif cond == "world_type.view_modes has more than one entry":
            if has_multiple_modes:
                active.append(stage)
        elif cond.startswith("options.render_captures and "):
            mode = cond.split("'")[1]
            if render_captures and mode in view_modes:
                active.append(stage)
        elif cond == "options.promote_to_gate":
            if promote_to_gate:
                active.append(stage)
        else:
            print(f"  [warn] unknown required_if '{cond}' on stage '{stage.get('id')}'; skipping", file=sys.stderr)
    return active


def topological_order(active_stages: list[dict], stages_manifest: dict) -> list[dict]:
    """Order active stages so each comes after its dependencies."""
    active_ids = {s["id"] for s in active_stages}
    deps = stages_manifest.get("stage_dependencies", [])
    # Build "after -> before" graph among active stages only
    edges: dict[str, list[str]] = {sid: [] for sid in active_ids}
    in_degree: dict[str, int] = {sid: 0 for sid in active_ids}
    for d in deps:
        a, b = d.get("after"), d.get("before")
        if a in active_ids and b in active_ids:
            edges[a].append(b)
            in_degree[b] += 1

    # Kahn's algorithm
    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    ordered = []
    by_id = {s["id"]: s for s in active_stages}
    while queue:
        sid = queue.pop(0)
        ordered.append(by_id[sid])
        for nxt in edges[sid]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(ordered) < len(active_stages):
        # cycle or missing dep
        missing = [s["id"] for s in active_stages if s["id"] not in {o["id"] for o in ordered}]
        print(f"  [warn] could not topologically order all stages; missing: {missing}", file=sys.stderr)
        # append in declaration order as fallback
        for s in active_stages:
            if s["id"] not in {o["id"] for o in ordered}:
                ordered.append(s)
    return ordered


def _hybrid_resolve_real_height_meta(real_bundle: Path) -> tuple[Path, Path]:
    """Hybrid seam-integration's `real.bundle_path` points at the
    source-stack layer dir (textures/source_stack/<id>/) which has
    macro + mask but not heightmap + meta. The matching topo bundle
    lives elsewhere; the source-stack manifest's `source_stack` field
    is a res:// URL pointing at it."""
    manifest_path = real_bundle / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        src_stack = manifest.get("source_stack", "")
        if src_stack.startswith("res://"):
            topo_dir = ROOT / "world3" / src_stack[len("res://"):]
            height = topo_dir / "heightmap.png"
            meta = topo_dir / "meta.json"
            if height.exists() and meta.exists():
                return (height, meta)
    # Fallback: convention — toporeview/<bundle_id>/
    bundle_id = real_bundle.name.replace("_source_stack", "_textured_master")
    fallback_topo = ROOT / "world3" / "toporeview" / bundle_id
    return (fallback_topo / "heightmap.png", fallback_topo / "meta.json")


def resolve_args(stage: dict, request: dict) -> list[str]:
    """Resolve the script's args from the stage declaration + request.

    The stages.json inputs are a hint for the orchestrator; this
    function maps them to concrete CLI args. Each stage has its own
    pattern because the underlying scripts have different arg shapes.

    Returns a list of CLI args (sans the script path itself).
    """
    stage_id = stage["id"]
    out_dir = (ROOT / request["output"]["bundle_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if stage_id == "validate_request":
        # Validator takes the request file path as a positional arg. The
        # orchestrator already validates the request as its first step,
        # so this stage is a redundant safety net (intentional — keeps
        # the stage manifest authoritative for "what runs").
        return [str(Path(request.get("__request_path__", "")).resolve())] if request.get("__request_path__") else []

    if stage_id == "build_real_master_stack":
        src = request["source"]
        crop = src.get("crop", {})
        biome_kit = request["world_type"]["biome_kit"]
        # Map biome_kit -> material id used by the stack builder. For
        # now, hardcode the convention from existing manifests.
        material = f"real_{biome_kit}_orthophoto"
        args = [
            "--dem", str((ROOT / src["dem"]).resolve()),
            "--orthophoto", str((ROOT / src["orthophoto"]).resolve()),
            "--output-dir", str(out_dir),
            "--name", request.get("description") or request["id"],
            "--material", material,
            "--review-max-dim", str(src.get("review_max_dim", 8192)),
            "--fill-distance-px", str(src.get("fill_distance_px", 64.0)),
        ]
        if crop.get("to_valid_dem"):
            args.append("--crop-to-valid-dem")
        if "margin_px" in crop:
            args += ["--crop-margin-px", str(crop["margin_px"])]
        return args

    if stage_id == "build_real_heightmap_only":
        src = request["source"]
        biome_kit = request["world_type"]["biome_kit"]
        args = [
            str((ROOT / src["dem"]).resolve()),
            str(out_dir),
            "--material", biome_kit,  # uses kit name as material id
        ]
        if "bbox" in src.get("crop", {}):
            args += ["--bbox", *(str(x) for x in src["crop"]["bbox"])]
        return args

    if stage_id == "build_procedural_neighbor":
        # For source.type=procedural, args come from request.source.*
        # For source.type=hybrid, args come from request.source.procedural.*
        src = request["source"]
        if src["type"] == "hybrid":
            ps = src["procedural"]
        else:
            ps = src
        size = ps.get("size_px", [512, 1024])
        world = ps.get("world_size_m", [120.0, 240.0])
        # For hybrid, write procedural output to a sub-dir; for procedural,
        # output goes to the bundle dir directly.
        if src["type"] == "hybrid":
            proc_out = out_dir / "_procedural_side"
        else:
            proc_out = out_dir
        args = [
            "--material-id", ps["material_id"],
            "--out", str(proc_out),
            "--size", f"{size[0]},{size[1]}",
            "--world-size-m", f"{world[0]},{world[1]}",
            "--elev-min-m", str(ps.get("elev_min_m", 412.0)),
            "--elev-range-m", str(ps.get("elev_range_m", 18.0)),
            "--seed", str(ps.get("seed", 1021)),
            "--name", request.get("description") or request["id"],
        ]
        # F.3.1: thread neighbor edge constraints if the iterator put them
        # into the request. west_edge from the tile to our west; north_edge
        # from the tile to our north.
        nbw = ps.get("neighbor_west_edge")
        if nbw:
            args += ["--neighbor-west-edge", str((ROOT / nbw).resolve())]
        nbn = ps.get("neighbor_north_edge")
        if nbn:
            args += ["--neighbor-north-edge", str((ROOT / nbn).resolve())]
        feather = ps.get("neighbor_edge_feather_px")
        if feather is not None:
            args += ["--neighbor-edge-feather-px", str(int(feather))]
        # F.3.2: biome ids for splat-weight crossfade decisions
        this_biome = ps.get("this_biome")
        if this_biome:
            args += ["--this-biome", str(this_biome)]
        east_biome = ps.get("neighbor_east_biome")
        if east_biome:
            args += ["--neighbor-east-biome", str(east_biome)]
        south_biome = ps.get("neighbor_south_biome")
        if south_biome:
            args += ["--neighbor-south-biome", str(south_biome)]
        splat_feather = ps.get("neighbor_splat_feather_px")
        if splat_feather is not None:
            args += ["--neighbor-splat-feather-px", str(int(splat_feather))]
        # F.3.3: thread biome_kit so the procedural builder can emit
        # a per-bundle ShaderMaterial .tres binding the kit's 5 materials.
        biome_kit = (
            ps.get("biome_kit")
            or request.get("world_type", {}).get("biome_kit", "")
        )
        if biome_kit:
            args += ["--biome-kit", str(biome_kit)]
        return args

    if stage_id == "build_seam_integration":
        # Hybrid only. Joins a real source crop to a procedural neighbor
        # bundle (produced by the build_procedural_neighbor stage that
        # runs earlier in the chain).
        # Reference arg contract: world3/jobs/m18_representative_slice_manifest.json.
        # Left source is the real bundle's source-stack macro/heightmap;
        # right source is the procedural neighbor we just built into
        # <out_dir>/_procedural_side/.
        src = request["source"]
        if src["type"] != "hybrid":
            return ["__STAGE_PLACEHOLDER__"]
        real = src.get("real", {})
        real_bundle = (ROOT / real["bundle_path"]).resolve()
        # The "real bundle" referenced is the source-stack layer dir,
        # but the seam solver wants the actual heightmap + meta which
        # live in a sibling toporeview dir. The request schema doesn't
        # encode that mapping yet; recover it from the source_stack/
        # manifest.json which points at the heightmap source.
        proc_out = out_dir / "_procedural_side"
        real_macro = real_bundle / "source_macro_albedo.png"
        real_mask = real_bundle / "source_macro_valid_mask.png"
        # Walk source-stack manifest to find the matching heightmap +
        # meta. Fall back to a sibling-toporeview convention if the
        # manifest doesn't say.
        real_height, real_meta = _hybrid_resolve_real_height_meta(real_bundle)
        proc_macro = proc_out / "layers" / "render_albedo.png"
        proc_mask = proc_out / "layers" / "source_valid_mask.png"
        proc_height = proc_out / "heightmap.png"
        proc_meta = proc_out / "meta.json"
        crop = real.get("crop_macro_px", [0, 0, 512, 1024])
        seam = src.get("seam", {})
        size = src.get("procedural", {}).get("size_px", [512, 1024])
        # Output target dimensions must equal the procedural side (which
        # is the right crop). When left + right crops differ, the solver
        # also needs --output-size; we always pass it for explicitness.
        right_crop = [0, 0, size[0], size[1]]
        args = [
            "--left-macro",   str(real_macro),
            "--left-valid-mask", str(real_mask),
            "--left-heightmap",  str(real_height),
            "--left-meta",       str(real_meta),
            "--right-macro",     str(proc_macro),
            "--right-valid-mask", str(proc_mask),
            "--right-heightmap",  str(proc_height),
            "--right-meta",       str(proc_meta),
            "--left-crop",   f"{crop[0]},{crop[1]},{crop[2]},{crop[3]}",
            "--right-crop",  f"{right_crop[0]},{right_crop[1]},{right_crop[2]},{right_crop[3]}",
            "--output-size", f"{size[0]},{size[1]}",
            "--overlap-px",         str(seam.get("overlap_px", 128)),
            "--height-feather-px",  str(seam.get("height_feather_px", 224)),
            "--color-feather-px",   str(seam.get("color_feather_px", 384)),
            "--macro-band-mode",    seam.get("macro_band_mode", "blend"),
            "--macro-bridge-blur-px", str(seam.get("macro_bridge_blur_px", 26.0)),
            "--macro-bridge-detail-strength", str(seam.get("macro_bridge_detail_strength", 0.12)),
            "--texture-out", str(out_dir),
            "--topo-out",    str(out_dir),
            "--metrics-out", str(out_dir / "seam_metrics.json"),
            "--artifact-name", request.get("description") or request["id"],
            "--integration-kind", "world3_make_hybrid_seam_integration",
        ]
        return args

    if stage_id == "build_runtime_image_cache":
        # Inputs: heightmap PNG (in the bundle dir) and an optional
        # splat-source PNG. Output: per-bundle runtime cache subdir.
        height_source = out_dir / "heightmap.png"
        # Splat source is conditional on Phase E per-mode work; default
        # to the legacy alpine splat the build script falls back to, so
        # bundles that don't yet emit a splat layer don't fail here.
        splat_source = ROOT / "world3" / "textures" / "m4_splat" / "alpine_height_slope_weights_rgba.png"
        # Look for a per-bundle splat in the bundle dir first.
        bundle_splat = out_dir / "layers" / "height_slope_weights_rgba.png"
        if bundle_splat.exists():
            splat_source = bundle_splat
        runtime_out = out_dir / "runtime_cache"
        return [
            "--height-source", str(height_source),
            "--splat-source",  str(splat_source),
            "--out-dir",       str(runtime_out),
        ]

    if stage_id == "deploy_kit_materials":
        biome_kit = request["world_type"]["biome_kit"]
        return ["--kit", biome_kit]

    if stage_id == "emit_per_mode_materials":
        biome_kit = request["world_type"]["biome_kit"]
        # emit_per_mode_materials.py argparse TBD; check via --help
        return ["--kit", biome_kit]

    if stage_id.startswith("render_captures_"):
        # Phase E.4 capture driver. The stage script is run_orchestrator_capture.py
        # (set in stages.json); we build the per-mode invocation here.
        mode = stage_id.replace("render_captures_", "")
        biome_kit = request["world_type"]["biome_kit"]
        bundle_id = request["id"]
        # res:// paths into the bundle dir
        bundle_res = "res://" + str(out_dir.relative_to(ROOT / "world3")).replace("\\", "/")
        material_res = f"res://textures/wgv3/terrain_blend_{biome_kit}.tres"
        output_res = f"res://docs/captures/review/{bundle_id}_{mode}.png"
        # Optional macro overrides — only if the bundle layers exist on disk
        args = [
            "--bundle-dir", bundle_res,
            "--material",   material_res,
            "--mode",       mode,
            "--output",     output_res,
            "--style-pack", request.get("world_type", {}).get("style_pack", "photoreal"),
        ]
        layers_dir = out_dir / "layers"
        if (layers_dir / "render_albedo.png").exists():
            args += ["--macro-albedo",
                     f"{bundle_res}/layers/render_albedo.png"]
        if (layers_dir / "source_valid_mask.png").exists():
            args += ["--macro-mask",
                     f"{bundle_res}/layers/source_valid_mask.png"]
        return args

    if stage_id == "register_promotion_candidate":
        # Phase E.3 promotion-gate extension — deferred until M13 gate
        # integration lands as a real stage.
        return ["__STAGE_PLACEHOLDER__"]

    return ["__STAGE_PLACEHOLDER__"]


def execute_stage(stage: dict, request: dict, dry_run: bool) -> dict:
    """Run one stage. Returns a dict with timing + status + output paths."""
    stage_id = stage["id"]
    script = stage.get("script", "")
    args = resolve_args(stage, request)

    record = {
        "id": stage_id,
        "script": script,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "args": args,
    }

    # Skip placeholder stages (Phase E.4+ items not yet implemented).
    if args == ["__STAGE_PLACEHOLDER__"]:
        record["status"] = "skipped_placeholder"
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
        record["wall_time_sec"] = 0.0
        return record

    if not script.endswith(".py"):
        record["status"] = "skipped_non_python"
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
        record["wall_time_sec"] = 0.0
        return record

    if dry_run:
        record["status"] = "dry_run"
        record["preview_cmd"] = [sys.executable, str(ROOT / script), *args]
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
        record["wall_time_sec"] = 0.0
        return record

    script_path = ROOT / script
    if not script_path.exists():
        record["status"] = "error_script_missing"
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
        record["wall_time_sec"] = 0.0
        record["error"] = f"script not found: {script_path}"
        return record

    cmd = [sys.executable, str(script_path), *args]
    print(f"  [run] {' '.join(cmd)}")
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        wall = time.time() - t0
        record["exit_code"] = result.returncode
        record["wall_time_sec"] = round(wall, 2)
        record["stdout_tail"] = result.stdout.splitlines()[-5:] if result.stdout else []
        record["stderr_tail"] = result.stderr.splitlines()[-5:] if result.stderr else []
        record["status"] = "ok" if result.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        record["status"] = "timeout"
        record["wall_time_sec"] = round(time.time() - t0, 2)
    except Exception as e:
        record["status"] = "error"
        record["error"] = f"{type(e).__name__}: {e}"
        record["wall_time_sec"] = round(time.time() - t0, 2)

    record["completed_at"] = datetime.now(timezone.utc).isoformat()
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("request", type=Path, help="Path to region_request.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the stage chain + resolved args without executing")
    ap.add_argument("--from-stage", default=None,
                    help="Skip stages until reaching this id (resume mid-flow)")
    ap.add_argument("--only-stages", default=None,
                    help="Run only the comma-separated stage ids listed")
    ap.add_argument("--skip-validation", action="store_true",
                    help="Skip the schema-validation step (dangerous)")
    args = ap.parse_args()

    print(f"=== world3 orchestrator ===")
    print(f"Request: {args.request}")
    print()

    request = load_request(args.request)
    request["__request_path__"] = str(args.request)
    request_id = request.get("id", "<no id>")

    # Step 1: validate schema
    if not args.skip_validation:
        print("--- Validating request schema ---")
        if not validate_request(args.request):
            return 2
        print()

    # Step 2: resolve stages
    print("--- Resolving stages ---")
    stages_manifest = load_stages()
    active = determine_active_stages(request, stages_manifest)
    ordered = topological_order(active, stages_manifest)

    # Filter via --only-stages / --from-stage
    if args.only_stages:
        wanted = {s.strip() for s in args.only_stages.split(",")}
        ordered = [s for s in ordered if s["id"] in wanted]
    if args.from_stage:
        idx = next((i for i, s in enumerate(ordered) if s["id"] == args.from_stage), None)
        if idx is None:
            print(f"ERROR: --from-stage '{args.from_stage}' not in active stages", file=sys.stderr)
            return 2
        ordered = ordered[idx:]

    print(f"  active stages ({len(ordered)}):")
    for s in ordered:
        print(f"    {s['id']}  -- {s.get('description', '?')[:70]}")
    print()

    # Step 3: execute
    print(f"--- Executing ({'dry-run' if args.dry_run else 'real'}) ---")
    records = []
    any_failure = False
    for stage in ordered:
        rec = execute_stage(stage, request, args.dry_run)
        records.append(rec)
        status_sym = "OK   " if rec["status"] in ("ok", "skipped_placeholder", "skipped_non_python", "dry_run") else "FAIL "
        wall = rec.get("wall_time_sec", 0)
        print(f"  [{status_sym}] {rec['id']}  ({rec['status']}, {wall}s)")
        if rec["status"] in ("failed", "error", "timeout", "error_script_missing"):
            any_failure = True
            if rec.get("stderr_tail"):
                for line in rec["stderr_tail"]:
                    print(f"    stderr: {line}")
            if rec.get("error"):
                print(f"    error: {rec['error']}")

    # Step 4: provenance
    RUN_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{request_id}_{ts}"
    run_path = RUN_RECORDS_DIR / f"{run_id}.json"
    run_record = {
        "schema_version": 1,
        "run_id": run_id,
        "request_id": request_id,
        "request_path": str(args.request.resolve()),
        "request": request,
        "started_at": records[0]["started_at"] if records else None,
        "completed_at": records[-1]["completed_at"] if records else None,
        "ok": not any_failure,
        "stages": records,
        "dry_run": args.dry_run,
    }
    run_path.write_text(json.dumps(run_record, indent=2), encoding="utf-8")
    print(f"\n--- Provenance ---")
    print(f"  Run record: {run_path.relative_to(ROOT)}")

    print(f"\n=== world3 orchestrator {'DONE' if not any_failure else 'FAILED'} ===")
    return 0 if not any_failure else 1


if __name__ == "__main__":
    sys.exit(main())
