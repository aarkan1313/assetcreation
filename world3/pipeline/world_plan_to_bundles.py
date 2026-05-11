"""Phase F.3 — plan-to-bundles iterator.

Reads a validated world plan and emits:
  - One region_request.json per tile under world3/worlds/<plan_id>/requests/
  - One world_map.json under world3/worlds/<plan_id>/ for the F.7 streaming director

Optionally invokes world3_make.py on each emitted request (--run).

Per-tile seed derivation: sha256(plan_seed || col || row) mod 2^31. This is
deterministic across runs and across machines, so re-running the iterator
produces byte-identical request files and bundles.

Usage:
    python world3/pipeline/world_plan_to_bundles.py world3/jobs/examples/world_plan_starter_2x2_procedural.json
    python world3/pipeline/world_plan_to_bundles.py <plan> --run
    python world3/pipeline/world_plan_to_bundles.py <plan> --dry-run

Exit codes:
    0  emit + (if --run) orchestrator runs all OK
    1  validation failed, emit aborted, or any orchestrator run failed
    2  internal error (schema malformed, plan unreadable)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
WORLDS_DIR = WORLD3 / "worlds"

# Re-use the world plan validator rather than reimplement; it carries
# the full semantic ruleset (bounds divisibility, tile coverage,
# adjacency check, etc.).
from validate_world_plan import (  # noqa: E402
    load_schema as _load_plan_schema,
    validate_plan as _validate_plan,
)


def derive_tile_seed(plan_seed: int, col: int, row: int) -> int:
    """sha256(plan_seed:col:row) mod 2^31. Stable across runs/machines."""
    payload = f"{plan_seed}:{col}:{row}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _resolve_tile_source(plan: dict, layout_entry: dict) -> tuple[dict, str]:
    """Returns (source_dict, biome_id). Per-tile source_override wins."""
    biome_id = layout_entry["biome"]
    biome = next(b for b in plan["biomes"] if b["id"] == biome_id)
    source = dict(layout_entry.get("source_override") or biome["source"])
    return source, biome_id


def _layout_entry_for(plan: dict, col: int, row: int) -> dict | None:
    for e in plan.get("biome_layout", []):
        xy = e.get("tile_xy", [-1, -1])
        if xy[0] == col and xy[1] == row:
            return e
    return None


def emit_request_for_tile(
    plan: dict,
    layout_entry: dict,
    plan_id: str,
    out_root: Path,
) -> dict:
    """Write one region_request.json for the given tile, return a world_map tile entry."""
    col, row = layout_entry["tile_xy"]
    tile_seed = derive_tile_seed(plan["seed"], col, row)

    base_source, biome_id = _resolve_tile_source(plan, layout_entry)
    source = dict(base_source)
    # Per-tile determinism: replace seed if procedural/hybrid source has one
    if source.get("type") == "procedural":
        source["seed"] = tile_seed
    elif source.get("type") == "hybrid":
        proc = dict(source.get("procedural", {}))
        proc["seed"] = tile_seed
        source["procedural"] = proc

    bundle_id = f"{plan_id}__tile_{col}_{row}"
    bundle_dir_rel = f"world3/worlds/{plan_id}/bundles/{bundle_id}"

    # F.3.1: thread neighbor edge constraints. If a tile exists to our
    # west (col-1, row) or north (col, row-1) and that neighbor is
    # procedural, point this tile's source at the neighbor's expected
    # edge JSON. The orchestrator runs tiles in row-major order, so the
    # W and N neighbors will have built their edge JSONs before this
    # tile runs.
    if source.get("type") == "procedural":
        west_neighbor = _layout_entry_for(plan, col - 1, row)
        if west_neighbor is not None:
            west_bid = f"{plan_id}__tile_{col-1}_{row}"
            source["neighbor_west_edge"] = (
                f"world3/worlds/{plan_id}/bundles/{west_bid}/edges/east_edge.json"
            )
        north_neighbor = _layout_entry_for(plan, col, row - 1)
        if north_neighbor is not None:
            north_bid = f"{plan_id}__tile_{col}_{row-1}"
            source["neighbor_north_edge"] = (
                f"world3/worlds/{plan_id}/bundles/{north_bid}/edges/south_edge.json"
            )

        # F.3.2: thread biome ids for splat-weight crossfade decisions.
        # The procedural builder uses east_biome / south_biome to decide
        # whether to crossfade splat channels at the relevant edges.
        source["this_biome"] = biome_id
        east_neighbor = _layout_entry_for(plan, col + 1, row)
        if east_neighbor is not None and east_neighbor["biome"] != biome_id:
            source["neighbor_east_biome"] = east_neighbor["biome"]
        south_neighbor = _layout_entry_for(plan, col, row + 1)
        if south_neighbor is not None and south_neighbor["biome"] != biome_id:
            source["neighbor_south_biome"] = south_neighbor["biome"]
    request = {
        "schema_version": 1,
        "id": bundle_id,
        "description": f"Phase F.3 emitted from plan '{plan_id}' tile ({col}, {row}) biome '{biome_id}'",
        "source": source,
        "world_type": {
            "biome_kit": next(b["biome_kit"] for b in plan["biomes"] if b["id"] == biome_id),
            "style_pack": plan.get("style_pack", "photoreal"),
            "view_modes": plan.get("perspectives", ["iso"]),
        },
        "options": {
            "render_captures": False,
            "promote_to_gate": False
        },
        "output": {
            "bundle_dir": bundle_dir_rel,
            "overwrite": True
        }
    }

    requests_dir = out_root / "requests"
    requests_dir.mkdir(parents=True, exist_ok=True)
    request_path = requests_dir / f"{bundle_id}.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")

    world_x = col * plan["tile_size_m"]
    world_z = row * plan["tile_size_m"]
    return {
        "tile_xy": [col, row],
        "world_xy_m": [world_x, world_z],
        "biome": biome_id,
        "source_type": source["type"],
        "bundle_id": bundle_id,
        "request_path": str(request_path.relative_to(ROOT)).replace("\\", "/"),
        "bundle_dir": bundle_dir_rel,
        "tile_seed": tile_seed,
    }


def write_world_map(plan: dict, plan_id: str, tile_entries: list[dict], out_root: Path) -> Path:
    bounds = plan["bounds_m"]
    tile = plan["tile_size_m"]
    world_map = {
        "schema_version": 1,
        "plan_id": plan_id,
        "bounds_m": bounds,
        "tile_size_m": tile,
        "seed": plan["seed"],
        "grid": [int(bounds[0] / tile), int(bounds[1] / tile)],
        "tiles": tile_entries,
        "perspectives": plan.get("perspectives", []),
        "style_pack": plan.get("style_pack", "photoreal"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    world_map_path = out_root / "world_map.json"
    world_map_path.write_text(json.dumps(world_map, indent=2), encoding="utf-8")
    return world_map_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("plan", type=Path, help="world plan JSON")
    ap.add_argument("--run", action="store_true",
                    help="After emitting, invoke world3_make.py on each request in order.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate + emit without writing files (preview).")
    ap.add_argument("--only-stages", default=None,
                    help="Pass-through to world3_make.py --only-stages when --run.")
    args = ap.parse_args()

    if not args.plan.exists():
        print(f"ERROR: plan not found at {args.plan}", file=sys.stderr)
        return 2

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    plan_id = plan.get("id")
    print(f"=== world_plan_to_bundles ===")
    print(f"Plan: {args.plan} (id={plan_id})")
    print()

    # Validate before doing anything destructive
    print("--- Validating plan ---")
    schema = _load_plan_schema()
    ok, errs, warns = _validate_plan(args.plan, schema)
    for w in warns:
        print(f"  warn: {w}")
    if not ok:
        for e in errs:
            print(e)
        return 1
    print(f"  [OK  ] {args.plan.relative_to(ROOT) if args.plan.is_absolute() else args.plan}")
    print()

    # F.4 transition audit gate: if a transition audit exists for this
    # plan, surface its summary. Hard gate (--block-on-transition-fail)
    # disabled by default until the starter catalog clears its existing
    # fails — the audit is soft-warn for now.
    audit_path = WORLD3 / "jobs" / "transition_audits" / f"{plan_id}.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        warn = audit.get("warn_count", 0)
        fail = audit.get("fail_count", 0)
        err = audit.get("error_count", 0)
        print(f"--- Transition audit ({audit_path.relative_to(ROOT)}) ---")
        print(f"  pass={audit.get('pass_count', 0)} warn={warn} fail={fail} error={err}")
        if fail or err:
            print(f"  WARN: {fail+err} pair(s) failed audit but emit proceeding (soft gate).")
            print(f"        Run audit_transition_pairs.py to see actionable remediation.")
        print()

    out_root = WORLDS_DIR / plan_id
    if args.dry_run:
        print(f"--- Dry run (no files written) ---")
        tile_entries = []
        for entry in plan["biome_layout"]:
            col, row = entry["tile_xy"]
            bundle_id = f"{plan_id}__tile_{col}_{row}"
            tile_entries.append({
                "tile_xy": [col, row],
                "biome": entry["biome"],
                "bundle_id": bundle_id,
            })
        for t in tile_entries:
            print(f"  [tile {t['tile_xy']}] biome={t['biome']} bundle_id={t['bundle_id']}")
        print(f"  would write {len(tile_entries)} request files + world_map.json to {out_root.relative_to(ROOT)}")
        return 0

    print(f"--- Emitting tile requests ---")
    tile_entries = []
    # F.3.1: emit in row-major order (low row first, then low col) so
    # each tile's W and N neighbors are processed before it. This is the
    # iteration order the orchestrator will use under --run.
    ordered_layout = sorted(
        plan["biome_layout"],
        key=lambda e: (e["tile_xy"][1], e["tile_xy"][0]),
    )
    for entry in ordered_layout:
        tile = emit_request_for_tile(plan, entry, plan_id, out_root)
        tile_entries.append(tile)
        print(f"  [tile {tile['tile_xy']}] biome={tile['biome']} -> {tile['request_path']}")
    print(f"  wrote {len(tile_entries)} request files")
    print()

    world_map_path = write_world_map(plan, plan_id, tile_entries, out_root)
    print(f"--- World map ---")
    print(f"  {world_map_path.relative_to(ROOT)}")
    print()

    if args.run:
        print(f"--- Running orchestrator on {len(tile_entries)} tiles ---")
        make_script = WORLD3 / "pipeline" / "world3_make.py"
        for t in tile_entries:
            request_abs = ROOT / t["request_path"]
            cmd = [sys.executable, str(make_script), str(request_abs)]
            if args.only_stages:
                cmd += ["--only-stages", args.only_stages]
            print(f"  [run] tile {t['tile_xy']} -> {t['bundle_id']}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  [FAIL] tile {t['tile_xy']} (exit={result.returncode})")
                print(result.stdout[-2000:])
                print(result.stderr[-1000:], file=sys.stderr)
                return 1
            # Tail the orchestrator's "=== DONE ===" line
            for line in result.stdout.splitlines()[-3:]:
                if line.strip():
                    print(f"        {line}")
        print(f"  all {len(tile_entries)} tiles OK")

    print()
    print(f"=== world_plan_to_bundles DONE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
