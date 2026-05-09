"""Build the master data catalog by scanning every known data location.

This is the single source of truth for "what data do we have." It scans:
- dems/ (raw DEM TIF cache; bbox parsed from filenames)
- world/textures/library/ (procedural texture library)
- world3/textures/wgv3/ (runtime-staged textures)
- world3/opentopo/processed/heightmaps/ (per-region OT heightmap bundles)
- world3/opentopo/processed/master_stacks/ (worker-built fused stacks)
- world3/opentopo/processed/textures/ (OT real-source materials)
- pipelines/terrain/output/ (single + stitched heightmap bundles)

And cross-references existing catalogs:
- world3/materials/catalog.json (M1 canonical material catalog)
- world/textures/catalog/materials.jsonl (one-line-per-material library log)
- world3/jobs/regions.json (region-to-kit assignments)
- art_lab/biomes/data_wishlist.json (DEM pull intent)
- ~/.opentopo_calls.jsonl (every OT API call)

Output: world3/data_catalog.json (machine-readable)
        docs/MASTER_DATA_CATALOG.md (human-readable summary, written separately)

Run this whenever data lands or moves. It's idempotent and read-only.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

REPO = Path(r"D:\assets")

# Roots
DEMS = REPO / "dems"
LIBRARY = REPO / "world" / "textures" / "library"
WGV3 = REPO / "world3" / "textures" / "wgv3"
OPENTOPO_HEIGHTMAPS = REPO / "world3" / "opentopo" / "processed" / "heightmaps"
OPENTOPO_MASTER = REPO / "world3" / "opentopo" / "processed" / "master_stacks"
OPENTOPO_TEXTURES = REPO / "world3" / "opentopo" / "processed" / "textures"
OPENTOPO_RAW = REPO / "world3" / "opentopo" / "raw"
TERRAIN_OUTPUT = REPO / "pipelines" / "terrain" / "output"

# Existing catalogs / manifests
M1_CATALOG = REPO / "world3" / "materials" / "catalog.json"
LIBRARY_JSONL = REPO / "world" / "textures" / "catalog" / "materials.jsonl"
REGIONS_JSON = REPO / "world3" / "jobs" / "regions.json"
WISHLIST = REPO / "art_lab" / "biomes" / "data_wishlist.json"
OT_CALL_LOG = Path.home() / ".opentopo_calls.jsonl"
BIOME_KITS = REPO / "world3" / "jobs" / "biome_kits.json"
TRANSITION_RULES = REPO / "world3" / "jobs" / "biome_transition_rules.json"

OUT_JSON = REPO / "world3" / "data_catalog.json"


# ---------- Scanners ---------------------------------------------------------

DEM_PAT = re.compile(r"(\w+)_([+-][\d.]+)_([+-][\d.]+)_([+-][\d.]+)_([+-][\d.]+)\.tif$")


def scan_dems() -> list[dict]:
    """Parse raw DEM TIF files in dems/ — extract dataset + bbox + size."""
    out = []
    if not DEMS.exists():
        return out
    for f in sorted(DEMS.glob("*.tif")):
        m = DEM_PAT.match(f.name)
        if not m:
            continue
        ds, w, s, e, n = m.groups()
        try:
            stat = f.stat()
            out.append({
                "dataset": ds,
                "bbox": [float(w), float(s), float(e), float(n)],
                "filename": f.name,
                "path": str(f.relative_to(REPO)).replace("\\", "/"),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
            })
        except OSError:
            pass
    return out


def scan_texture_library() -> list[dict]:
    """Walk world/textures/library/ — every material id directory."""
    out = []
    if not LIBRARY.exists():
        return out
    for d in sorted(LIBRARY.iterdir()):
        if not d.is_dir():
            continue
        # Look for the "main" PBR album (id-prefixed). Catalog the maps present.
        maps = {}
        for kind in ("albedo", "normal", "roughness", "height", "ao", "metallic"):
            cand = d / f"{d.name}_{kind}.png"
            if cand.exists():
                maps[kind] = str(cand.relative_to(REPO)).replace("\\", "/")
        # Pipeline log if present
        log_path = d / "aaa_pipeline.json"
        log_meta = {}
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text(encoding="utf-8"))
                log_meta = {
                    "category": log.get("category"),
                    "quality": log.get("quality"),
                    "grade": log.get("grade"),
                    "method": log.get("method"),
                    "prompt": log.get("prompt", "")[:120],
                }
            except Exception:
                pass
        out.append({
            "id": d.name,
            "library_dir": str(d.relative_to(REPO)).replace("\\", "/"),
            "maps_present": list(maps.keys()),
            "maps": maps,
            "pipeline_log": log_meta,
        })
    return out


def scan_wgv3_staged() -> list[dict]:
    """Walk world3/textures/wgv3/ — runtime-staged texture dirs + .tres files."""
    out_dirs = []
    out_tres = []
    if not WGV3.exists():
        return out_dirs
    for entry in sorted(WGV3.iterdir()):
        if entry.is_dir():
            maps = {}
            for kind in ("albedo", "normal", "roughness", "height", "ao", "metallic"):
                cand = entry / f"{kind}.png"
                if cand.exists():
                    maps[kind] = str(cand.relative_to(REPO)).replace("\\", "/")
            out_dirs.append({
                "slot_dir": entry.name,
                "path": str(entry.relative_to(REPO)).replace("\\", "/"),
                "maps_present": list(maps.keys()),
            })
        elif entry.is_file() and entry.suffix == ".tres":
            out_tres.append({
                "tres": entry.name,
                "path": str(entry.relative_to(REPO)).replace("\\", "/"),
            })
    return {"slot_dirs": out_dirs, "tres_files": out_tres}


def scan_opentopo_heightmap_bundles() -> list[dict]:
    """Per-region OT heightmap bundles."""
    out = []
    if not OPENTOPO_HEIGHTMAPS.exists():
        return out
    for d in sorted(OPENTOPO_HEIGHTMAPS.iterdir()):
        if not d.is_dir():
            continue
        # Some regions have one bundle, others have per-dataset subbundles
        region_id = d.name
        bundles = []
        # Look for direct bundle (heightmap.png + meta.json at this level)
        if (d / "heightmap.png").exists() and (d / "meta.json").exists():
            try:
                meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                bundles.append({
                    "dataset": meta.get("source_dataset", "unknown"),
                    "path": str(d.relative_to(REPO)).replace("\\", "/"),
                    "world_size_m": meta.get("world_size_m"),
                    "elev_min_m": meta.get("elevation_min_m"),
                    "elev_max_m": meta.get("elevation_max_m"),
                })
            except Exception:
                pass
        # Also look for sub-bundles
        for sub in d.iterdir():
            if sub.is_dir() and (sub / "heightmap.png").exists() and (sub / "meta.json").exists():
                try:
                    meta = json.loads((sub / "meta.json").read_text(encoding="utf-8"))
                    bundles.append({
                        "dataset": sub.name,
                        "path": str(sub.relative_to(REPO)).replace("\\", "/"),
                        "world_size_m": meta.get("world_size_m"),
                        "elev_min_m": meta.get("elevation_min_m"),
                        "elev_max_m": meta.get("elevation_max_m"),
                    })
                except Exception:
                    pass
        out.append({
            "region_id": region_id,
            "bundle_count": len(bundles),
            "bundles": bundles,
        })
    return out


def scan_master_stacks() -> list[dict]:
    """Worker-built fused master stacks."""
    out = []
    if not OPENTOPO_MASTER.exists():
        return out
    for d in sorted(OPENTOPO_MASTER.iterdir()):
        if not d.is_dir():
            continue
        # Stack manifest if present
        manifest = d / "stack_manifest.json"
        meta = {}
        if manifest.exists():
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Tally layer files
        layers = []
        for f in d.iterdir():
            if f.is_file() and f.suffix in (".png", ".tif"):
                layers.append(f.name)
        out.append({
            "id": d.name,
            "path": str(d.relative_to(REPO)).replace("\\", "/"),
            "layer_count": len(layers),
            "manifest": "stack_manifest.json" if manifest.exists() else None,
            "layers_sample": sorted(layers)[:10],
        })
    return out


def scan_terrain_output() -> list[dict]:
    """pipelines/terrain/output/ — heightmap bundles produced by build_world.py
    or tile_stitch.py. These are the runtime-ready heightmaps for game scenes."""
    out = []
    if not TERRAIN_OUTPUT.exists():
        return out
    for d in sorted(TERRAIN_OUTPUT.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "metadata.json"
        height_path = d / "height_16.png"
        tile_grid = d / "tile_grid.json"
        meta = {}
        is_stitched = tile_grid.exists()
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        elif tile_grid.exists():
            try:
                meta = json.loads(tile_grid.read_text(encoding="utf-8"))
            except Exception:
                pass
        out.append({
            "id": d.name,
            "path": str(d.relative_to(REPO)).replace("\\", "/"),
            "has_height": height_path.exists(),
            "is_stitched": is_stitched,
            "kind": "stitched" if is_stitched else "single",
            "meta_summary": {
                k: meta.get(k) for k in (
                    "id", "dataset", "rows", "cols",
                    "tiles_ok", "tiles_fail",
                    "elev_min_m", "elev_max_m", "world_size_m",
                ) if k in meta
            },
        })
    return out


def scan_opentopo_real_textures() -> list[dict]:
    """world3/opentopo/processed/textures — worker-built real-source materials."""
    out = []
    if not OPENTOPO_TEXTURES.exists():
        return out
    for source in sorted(OPENTOPO_TEXTURES.iterdir()):
        if not source.is_dir():
            continue
        classes = []
        for cls in source.iterdir():
            if cls.is_dir():
                classes.append(cls.name)
        out.append({
            "source": source.name,
            "path": str(source.relative_to(REPO)).replace("\\", "/"),
            "class_count": len(classes),
            "classes_sample": sorted(classes)[:10],
        })
    return out


def scan_opentopo_raw_dataspace() -> list[dict]:
    """world3/opentopo/raw/dataspace — direct-download Dataspace project files."""
    out = []
    ds_root = OPENTOPO_RAW / "dataspace"
    if not ds_root.exists():
        return out
    for d in sorted(ds_root.iterdir()):
        if not d.is_dir():
            continue
        files = []
        size_total = 0
        for f in d.rglob("*"):
            if f.is_file():
                files.append(f.name)
                try:
                    size_total += f.stat().st_size
                except OSError:
                    pass
        out.append({
            "project": d.name,
            "path": str(d.relative_to(REPO)).replace("\\", "/"),
            "file_count": len(files),
            "total_size_mb": round(size_total / (1024 * 1024), 1),
            "files_sample": sorted(files)[:8],
        })
    return out


# ---------- Cross-reference lookups -----------------------------------------

def load_optional_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def call_log_summary() -> dict:
    """Summary of OT API calls."""
    if not OT_CALL_LOG.exists():
        return {"total_calls": 0, "available": False}
    rows = []
    with OT_CALL_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                rows.append(rec)
            except Exception:
                continue
    if not rows:
        return {"total_calls": 0, "available": True}
    last_24h = sum(1 for r in rows if r.get("ts", 0) > time.time() - 24 * 3600)
    by_dataset = {}
    by_success = {"true": 0, "false": 0}
    for r in rows:
        ds = r.get("dataset", "unknown")
        by_dataset[ds] = by_dataset.get(ds, 0) + 1
        by_success["true" if r.get("success") else "false"] += 1
    return {
        "total_calls": len(rows),
        "calls_last_24h": last_24h,
        "by_dataset": by_dataset,
        "by_success": by_success,
        "ledger_path": str(OT_CALL_LOG),
    }


def wishlist_summary() -> dict:
    d = load_optional_json(WISHLIST) or {}
    if not d:
        return {"available": False}
    tiers = d.get("tiers", {})
    breakdown = {}
    total = 0
    for tn, td in tiers.items():
        n = len(td.get("regions", []))
        breakdown[tn] = n
        total += n
    return {
        "available": True,
        "path": str(WISHLIST.relative_to(REPO)).replace("\\", "/"),
        "tier_breakdown": breakdown,
        "total_regions": total,
    }


def m1_catalog_summary() -> dict:
    d = load_optional_json(M1_CATALOG) or {}
    if not d:
        return {"available": False}
    materials = d.get("materials", [])
    by_source = {}
    by_status = {}
    by_shader = {}
    for m in materials:
        src = m.get("source", "?")
        by_source[src] = by_source.get(src, 0) + 1
        st = m.get("asset_status", "?")
        by_status[st] = by_status.get(st, 0) + 1
        sh = m.get("shader_binding", "?")
        by_shader[sh] = by_shader.get(sh, 0) + 1
    return {
        "available": True,
        "path": str(M1_CATALOG.relative_to(REPO)).replace("\\", "/"),
        "total_materials": len(materials),
        "by_source": by_source,
        "by_asset_status": by_status,
        "by_shader_binding": by_shader,
    }


def regions_summary() -> dict:
    d = load_optional_json(REGIONS_JSON) or []
    if not d:
        return {"available": False}
    by_kit = {}
    for r in d:
        k = r.get("biome_kit", "?")
        by_kit[k] = by_kit.get(k, 0) + 1
    return {
        "available": True,
        "path": str(REGIONS_JSON.relative_to(REPO)).replace("\\", "/"),
        "total_regions": len(d),
        "by_kit": by_kit,
        "region_ids": [r.get("id") for r in d],
    }


def kit_summary() -> dict:
    d = load_optional_json(BIOME_KITS) or {}
    kits = d.get("kits", {})
    return {
        "available": bool(kits),
        "path": str(BIOME_KITS.relative_to(REPO)).replace("\\", "/"),
        "kit_count": len(kits),
        "kit_ids": list(kits.keys()),
    }


def transition_rule_summary() -> dict:
    d = load_optional_json(TRANSITION_RULES) or {}
    rules = d.get("rules", []) if isinstance(d, dict) else []
    return {
        "available": bool(rules),
        "path": str(TRANSITION_RULES.relative_to(REPO)).replace("\\", "/"),
        "rule_count": len(rules),
    }


# ---------- Aggregate breakdowns --------------------------------------------

def dems_breakdown(dems: list[dict]) -> dict:
    """Group dems by dataset + sum size."""
    by_ds = {}
    total_mb = 0
    for d in dems:
        ds = d["dataset"]
        if ds not in by_ds:
            by_ds[ds] = {"count": 0, "size_mb": 0.0}
        by_ds[ds]["count"] += 1
        by_ds[ds]["size_mb"] += d["size_mb"]
        total_mb += d["size_mb"]
    for ds in by_ds:
        by_ds[ds]["size_mb"] = round(by_ds[ds]["size_mb"], 1)
    return {
        "by_dataset": by_ds,
        "total_count": len(dems),
        "total_size_mb": round(total_mb, 1),
        "total_size_gb": round(total_mb / 1024, 2),
    }


# ---------- Main -------------------------------------------------------------

def main() -> int:
    print("Scanning data sources…")

    raw_dems = scan_dems()
    print(f"  dems/                                  {len(raw_dems)} TIFs")

    library = scan_texture_library()
    print(f"  world/textures/library/                 {len(library)} materials")

    wgv3 = scan_wgv3_staged()
    print(f"  world3/textures/wgv3/ slot dirs         {len(wgv3['slot_dirs'])}")
    print(f"  world3/textures/wgv3/ .tres files       {len(wgv3['tres_files'])}")

    ot_heights = scan_opentopo_heightmap_bundles()
    print(f"  world3/opentopo/processed/heightmaps    {len(ot_heights)} regions")

    master_stacks = scan_master_stacks()
    print(f"  world3/opentopo/processed/master_stacks {len(master_stacks)} stacks")

    terrain_out = scan_terrain_output()
    print(f"  pipelines/terrain/output/               {len(terrain_out)} bundles")

    real_textures = scan_opentopo_real_textures()
    print(f"  world3/opentopo/processed/textures      {len(real_textures)} sources")

    raw_dataspace = scan_opentopo_raw_dataspace()
    print(f"  world3/opentopo/raw/dataspace/          {len(raw_dataspace)} projects")

    catalog = {
        "version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generator": "pipelines/terrain/build_master_catalog.py",
        "summary_role": "Single source of truth for what data lives where.",
        "raw_dems": {
            "summary": dems_breakdown(raw_dems),
            "items": raw_dems,
        },
        "texture_library": {
            "count": len(library),
            "items": library,
        },
        "runtime_staged_textures": wgv3,
        "opentopo_heightmap_bundles": {
            "count": len(ot_heights),
            "items": ot_heights,
        },
        "opentopo_master_stacks": {
            "count": len(master_stacks),
            "items": master_stacks,
        },
        "terrain_output_bundles": {
            "count": len(terrain_out),
            "items": terrain_out,
        },
        "opentopo_real_source_textures": {
            "count": len(real_textures),
            "items": real_textures,
        },
        "opentopo_raw_dataspace_projects": {
            "count": len(raw_dataspace),
            "items": raw_dataspace,
        },
        "cross_referenced_catalogs": {
            "m1_material_catalog": m1_catalog_summary(),
            "regions_json": regions_summary(),
            "biome_kits": kit_summary(),
            "transition_rules": transition_rule_summary(),
            "wishlist_dem_targets": wishlist_summary(),
            "ot_api_call_ledger": call_log_summary(),
        },
    }

    OUT_JSON.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"\nWrote {OUT_JSON.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
