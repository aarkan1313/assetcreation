"""Real-world DEM importer.

Pulls a heightmap from OpenTopography (or a Mapzen Terrarium PNG tile) and
emits the same bundle contract as terrain_bundle.py.

Usage:
  python import_dem.py --bbox W S E N --id colorado_a [--source opentopo|mapzen]
  python import_dem.py --preset utah_canyon --id utah_a

OpenTopography requires an API key (OPENTOPOGRAPHY_API_KEY env var). The
"globaldem" endpoint hands back GeoTIFF/PNG. We request a small public dataset
(SRTMGL3) by default to avoid permission walls.

Mapzen Terrarium tiles are public via AWS S3 (no key required); decode the
RGB PNG to elevation. We only fetch a single tile here for simplicity.

After download we resize to --size, normalize 0..1, then call into
terrain_bundle.process_height() to produce the bundle.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Bump PIL's decompression-bomb cap. USGS 1m can produce 200M+ pixel TIFFs at the
# 250 km² bbox limit (full LiDAR-grade granite cathedrals, etc); Pillow's default
# 178M cap rejects them. We're handling our own data, not random uploads.
Image.MAX_IMAGE_PIXELS = 1_000_000_000  # 1 billion pixels

# Ensure terrain_bundle is importable
sys.path.insert(0, str(Path(__file__).parent))


PRESETS = {
    "utah_canyon":       (-111.65, 36.75, -111.35, 37.05),
    "colorado_alpine":   (-106.40, 39.50, -106.10, 39.80),
    "appalachian":       ( -82.00, 35.50,  -81.70, 35.80),
    "alps_dolomites":    (  11.50, 46.30,   11.80, 46.60),
    "iceland_volcanic":  ( -19.00, 64.00,  -18.70, 64.30),
    "sahara_dunes":      (  10.00, 24.00,   10.30, 24.30),
    # Game-relevant fantasy-coded landscapes
    "norwegian_fjord":   (   6.50, 60.20,    6.85, 60.50),  # Hardanger fjord — vertical fjords, glacial valleys
    "nz_glacier":        ( 169.95, -43.65,  170.30, -43.45),  # Mt Cook / Tasman Glacier — peaks + glaciers
    "bryce_hoodoo":      (-112.20, 37.55, -112.00, 37.75),  # Bryce Canyon — hoodoos / pinnacles / amphitheatre
    "scottish_highlands":(  -5.20, 56.85,   -4.85, 57.10),  # Glen Coe — moors + lochs + dramatic ridges
    "patagonian_spires": ( -73.10, -50.95,  -72.85, -50.70),  # Torres del Paine — spires + glacial lakes
    "moroccan_atlas":    (  -7.95, 31.05,   -7.65, 31.30),  # High Atlas — arid mountains
    "japanese_alps":     ( 137.55, 36.45,  137.85, 36.75),  # Northern Alps — sharp ridges + valleys
}

# Default dataset is COP30 (Copernicus 30m, global coverage 90S-90N, cleanest
# 30m DEM widely available — fewer voids than SRTM/NASADEM, same resolution).
# Per-preset overrides only when COP30 doesn't have great coverage for that area
# (rarely needed; left empty for now).
PRESET_DATASETS = {
    # All presets default to COP30 unless listed here.
}

# Available datasets (for --dataset CLI). Each entry includes the bbox-area
# limit (km²) the API enforces — used by the pre-flight area check below.
# Source of truth: D:\assets\OPENTOPO_API.md (captured 2026-05-06).
DATASETS = {
    # /globaldem — Global topography (land elevation):
    "SRTMGL3":     {"endpoint": "globaldem", "res_m": 90,  "coverage": "60S-60N", "max_km2": 4_050_000,   "notes": "fast, low-res"},
    "SRTMGL1":     {"endpoint": "globaldem", "res_m": 30,  "coverage": "60S-60N", "max_km2":   450_000,   "notes": "30m SRTM, some voids"},
    "SRTMGL1_E":   {"endpoint": "globaldem", "res_m": 30,  "coverage": "60S-60N", "max_km2":   450_000,   "notes": "Ellipsoidal — DO NOT use for game terrain"},
    "AW3D30":      {"endpoint": "globaldem", "res_m": 30,  "coverage": "82S-82N", "max_km2":   450_000,   "notes": "ALOS, best high-latitude"},
    "AW3D30_E":    {"endpoint": "globaldem", "res_m": 30,  "coverage": "82S-82N", "max_km2":   450_000,   "notes": "ALOS Ellipsoidal — DO NOT use for game terrain"},
    "COP30":       {"endpoint": "globaldem", "res_m": 30,  "coverage": "90S-90N", "max_km2":   450_000,   "notes": "Copernicus, cleanest 30m global (DEFAULT)"},
    "COP90":       {"endpoint": "globaldem", "res_m": 90,  "coverage": "90S-90N", "max_km2": 4_050_000,   "notes": "Copernicus 90m"},
    "NASADEM":     {"endpoint": "globaldem", "res_m": 30,  "coverage": "60S-60N", "max_km2":   450_000,   "notes": "SRTM reprocessed, fewer voids"},
    "EU_DTM":      {"endpoint": "globaldem", "res_m": 25,  "coverage": "Europe",  "max_km2":   450_000,   "notes": "best European resolution"},
    "CA_MRDEM_DSM":{"endpoint": "globaldem", "res_m": 30,  "coverage": "Canada",  "max_km2":   450_000,   "notes": "Canadian DSM (with vegetation)"},
    "CA_MRDEM_DTM":{"endpoint": "globaldem", "res_m": 30,  "coverage": "Canada",  "max_km2":   450_000,   "notes": "Canadian DTM (bare earth)"},
    # /globaldem — Bathymetry / very-low-res global:
    "SRTM15Plus":      {"endpoint": "globaldem", "res_m": 463,  "coverage": "Global", "max_km2": 125_000_000, "notes": "Global Bathy+Topo SRTM15+ V2.1 500m, huge bbox limit"},
    "GEBCOIceTopo":    {"endpoint": "globaldem", "res_m": 463,  "coverage": "Global", "max_km2": 125_000_000, "notes": "GEBCO 2023 ice-surface (land + ice)"},
    "GEBCOSubIceTopo": {"endpoint": "globaldem", "res_m": 463,  "coverage": "Global", "max_km2": 125_000_000, "notes": "GEBCO 2023 bedrock under ice"},
    "GEDI_L3":         {"endpoint": "globaldem", "res_m": 1000, "coverage": "Global", "max_km2": 500_000_000, "notes": "Canopy-corrected 1km, ENORMOUS bbox limit (continent-scale)"},
    # /usgsdem — USGS 3DEP raster (US-only, much higher resolution):
    "USGS30m":     {"endpoint": "usgsdem",   "res_m": 30,  "coverage": "USA",     "max_km2": 225_000,   "notes": "USGS 30m, free-tier accessible"},
    "USGS10m":     {"endpoint": "usgsdem",   "res_m": 10,  "coverage": "USA",     "max_km2":  25_000,   "notes": "USGS 10m, free-tier accessible"},
    "USGS1m":      {"endpoint": "usgsdem",   "res_m":  1,  "coverage": "USA-LiDAR", "max_km2":     250, "notes": "USGS 1m LiDAR — academic/Enterprise key required"},
    # Regional high-res rasters — fetched directly from open S3 buckets via STAC,
    # bypassing OpenTopography. Discovered 2026-05-06: OT mirrors these but its
    # /globaldem endpoint refuses them; the data lives at the providers' open
    # AWS buckets as Cloud-Optimized GeoTIFFs and can be range-read for free.
    # See OPENTOPO_API.md and fetch_regional_stac.py.
    "ArcticDEM10m":    {"endpoint": "pgc_stac",  "res_m": 10, "coverage": "Arctic >50N", "max_km2":  25_000, "notes": "ArcticDEM 10m via PGC STAC; lat/lon bbox; no API key; reprojected to EPSG:4326"},
    "ArcticDEM32m":    {"endpoint": "pgc_stac",  "res_m": 32, "coverage": "Arctic >50N", "max_km2": 225_000, "notes": "ArcticDEM 32m via PGC STAC; large-bbox capable"},
    "REMA10m":         {"endpoint": "pgc_stac",  "res_m": 10, "coverage": "Antarctica",  "max_km2":  25_000, "notes": "REMA 10m via PGC STAC; lat/lon bbox; no API key"},
    "REMA32m":         {"endpoint": "pgc_stac",  "res_m": 32, "coverage": "Antarctica",  "max_km2": 225_000, "notes": "REMA 32m via PGC STAC"},
    # LINZ 1m via NZ Elevation S3 + LINZ static STAC catalog (217 regional collections).
    "LINZ1m_DTM":      {"endpoint": "linz_stac", "res_m": 1, "coverage": "New Zealand", "max_km2":     250, "notes": "NZ 1m LiDAR DTM via nz-elevation S3 (CC-BY-4.0); regional collections"},
    "LINZ1m_DSM":      {"endpoint": "linz_stac", "res_m": 1, "coverage": "New Zealand", "max_km2":     250, "notes": "NZ 1m LiDAR DSM via nz-elevation S3"},
}

DEFAULT_DATASET = "COP30"

# Persistent cache for raw OpenTopo TIFFs. Avoids re-downloading on re-runs and
# lets us re-process a region (different size, fantasy edits, etc) without
# spending API credits.
DEM_CACHE_DIR = Path(r"D:\assets\dems")


def _cache_key(bbox: tuple[float, float, float, float], dataset: str) -> Path:
    DEM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    w, s, e, n = bbox
    # 4-decimal-place bbox keeps cache hits stable; ~11m precision at equator
    return DEM_CACHE_DIR / f"{dataset}_{w:+.4f}_{s:+.4f}_{e:+.4f}_{n:+.4f}.tif"


def bbox_area_km2(bbox: tuple[float, float, float, float]) -> float:
    """Approximate area of a WGS84 bbox in km²."""
    import math
    w, s, e, n = bbox
    lat_mid = (s + n) / 2.0
    width_km = abs(e - w) * 111.32 * math.cos(math.radians(lat_mid))
    height_km = abs(n - s) * 110.57
    return width_km * height_km


def check_bbox_area(bbox: tuple[float, float, float, float], dataset: str) -> None:
    """Raise SystemExit with a helpful suggestion if bbox exceeds the dataset's API limit."""
    area = bbox_area_km2(bbox)
    info = DATASETS.get(dataset)
    if not info:
        return  # unknown dataset — let the API tell us
    limit = info.get("max_km2", 1e12)
    if area > limit:
        # Suggest a coarser dataset that would fit
        better = sorted(
            [(k, v["max_km2"]) for k, v in DATASETS.items()
             if v.get("max_km2", 0) >= area and v.get("endpoint") == info.get("endpoint")],
            key=lambda kv: kv[1])
        suggestion = ", ".join(k for k, _ in better[:3]) or "use a smaller bbox or tile"
        raise SystemExit(
            f"bbox area {area:,.0f} km² exceeds {dataset} limit of {limit:,.0f} km². "
            f"Try one of: {suggestion}"
        )


def fetch_opentopo(bbox: tuple[float, float, float, float], dataset: str = "SRTMGL3",
                   cache: bool = True) -> np.ndarray:
    """Returns a 2D float32 elevation array (meters). Caches raw TIFF on disk.

    Auto-routes to the right endpoint based on the DATASETS table:
      - 'globaldem' → /API/globaldem (passes demtype param)
      - 'usgsdem'   → /API/usgsdem  (passes datasetName param, US-only datasets)
    """
    try:
        import requests
    except ImportError:
        raise SystemExit("requests not installed; pip install requests")

    info = DATASETS.get(dataset, {})
    if not info:
        print(f"  [warn] dataset '{dataset}' not in DATASETS table; assuming /globaldem")

    # Pre-flight bbox area check (skipped for unknown datasets)
    if info:
        check_bbox_area(bbox, dataset)

    cached = _cache_key(bbox, dataset) if cache else None
    if cached and cached.exists():
        print(f"  [cache hit] {cached}")
        try:
            from osgeo import gdal
            ds = gdal.Open(str(cached))
            return ds.ReadAsArray().astype(np.float32)
        except ImportError:
            return np.array(Image.open(cached), dtype=np.float32)

    api_key = os.environ.get("OPENTOPOGRAPHY_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set OPENTOPOGRAPHY_API_KEY env var. Free key at https://opentopography.org/."
        )
    w, s, e, n = bbox

    endpoint = info.get("endpoint", "globaldem")
    if endpoint == "pgc_stac":
        # Delegate to the STAC fetcher (ArcticDEM / REMA via PGC + s3 COGs).
        from fetch_regional_stac import fetch_pgc
        out_path = _cache_key(bbox, dataset) if cache else Path("/tmp") / f"{dataset}.tif"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fetch_pgc(dataset, bbox, out_path, size=1024)
        try:
            from osgeo import gdal
            ds = gdal.Open(str(out_path))
            return ds.ReadAsArray().astype(np.float32)
        except ImportError:
            return np.array(Image.open(out_path), dtype=np.float32)
    if endpoint == "linz_stac":
        from fetch_regional_stac import fetch_linz
        out_path = _cache_key(bbox, dataset) if cache else Path("/tmp") / f"{dataset}.tif"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fetch_linz(dataset, bbox, out_path, size=1024)
        try:
            from osgeo import gdal
            ds = gdal.Open(str(out_path))
            return ds.ReadAsArray().astype(np.float32)
        except ImportError:
            return np.array(Image.open(out_path), dtype=np.float32)
    if endpoint == "regional_unknown":
        raise SystemExit(
            f"dataset '{dataset}' has no fetch endpoint wired up. "
            "See OPENTOPO_API.md and fetch_regional_stac.py."
        )
    if endpoint == "usgsdem":
        url = "https://portal.opentopography.org/API/usgsdem"
        params = {
            "datasetName": dataset,
            "south": s, "north": n, "west": w, "east": e,
            "outputFormat": "GTiff",
            "API_Key": api_key,
        }
    else:
        url = "https://portal.opentopography.org/API/globaldem"
        params = {
            "demtype": dataset,
            "south": s, "north": n, "west": w, "east": e,
            "outputFormat": "GTiff",
            "API_Key": api_key,
        }
    # USGS1m is slow: OT processes from raw LiDAR per request, ~10-12 min for a
    # 250km² tile (~160 MB GeoTIFF). Other datasets respond in <60s. Pick a
    # generous timeout per endpoint.
    timeout_s = 900 if dataset == "USGS1m" else 180
    print(f"  GET {url} bbox={bbox} dataset={dataset} (timeout={timeout_s}s)")
    r = requests.get(url, params=params, timeout=timeout_s)
    r.raise_for_status()
    # Detect non-TIFF responses (API errors come back as text/HTML)
    ct = r.headers.get("Content-Type", "")
    if not (r.content.startswith(b"II*\x00") or r.content.startswith(b"MM\x00*")
            or "tiff" in ct.lower() or "octet-stream" in ct.lower()):
        body = r.content[:500].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenTopography returned non-TIFF response ({ct}, {len(r.content)} bytes):\n"
            f"  body: {body!r}\n"
            f"  Try a different --dataset (SRTMGL3, AW3D30, COP90) or check coverage."
        )
    if cached:
        cached.write_bytes(r.content)
        print(f"  [cached] {cached} ({len(r.content) / (1024*1024):.1f} MB)")
        # Read back from the cache file so the rest of the function is unified
        try:
            from osgeo import gdal
            return gdal.Open(str(cached)).ReadAsArray().astype(np.float32)
        except ImportError:
            return np.array(Image.open(cached), dtype=np.float32)
    tmp = Path("__opentopo_tmp.tif")
    tmp.write_bytes(r.content)
    try:
        try:
            from osgeo import gdal
            ds = gdal.Open(str(tmp))
            arr = ds.ReadAsArray().astype(np.float32)
        except ImportError:
            # Pillow has limited GeoTIFF support but enough for elevation single-band
            im = Image.open(tmp)
            arr = np.array(im, dtype=np.float32)
    finally:
        tmp.unlink(missing_ok=True)
    return arr


def fetch_mapzen_terrarium(zoom: int, x: int, y: int) -> np.ndarray:
    """Fetch a single Mapzen Terrarium tile (256x256). Public S3, no auth.

    Decoding: elevation = (R * 256 + G + B / 256) - 32768
    """
    try:
        import requests
    except ImportError:
        raise SystemExit("requests not installed; pip install requests")
    url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{zoom}/{x}/{y}.png"
    print(f"  GET {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    tmp = Path("__mapzen_tmp.png")
    tmp.write_bytes(r.content)
    try:
        rgb = np.array(Image.open(tmp).convert("RGB"), dtype=np.float32)
    finally:
        tmp.unlink(missing_ok=True)
    elev = rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0
    return elev


def normalize(arr: np.ndarray, exaggerate: float = 1.0) -> np.ndarray:
    a = arr.astype(np.float32)
    a -= a.min()
    m = max(a.max(), 1e-9)
    a /= m
    if exaggerate != 1.0:
        a = np.clip(a ** (1.0 / exaggerate), 0, 1)
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--source", choices=["opentopo", "mapzen", "file"], default="opentopo")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    ap.add_argument("--preset", choices=list(PRESETS.keys()))
    ap.add_argument("--mapzen-tile", nargs=3, type=int, metavar=("Z", "X", "Y"))
    ap.add_argument("--input-tif", type=Path, help="(source=file) local elevation raster")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--exaggerate", type=float, default=1.0)
    ap.add_argument("--dataset", default=None,
                    choices=list(DATASETS.keys()),
                    help=f"OpenTopography dataset (default: {DEFAULT_DATASET}). "
                         f"USGS* require US bbox + 1m needs academic/Enterprise. "
                         f"See OPENTOPO_API.md for full reference.")
    ap.add_argument("--bathymetry", action="store_true",
                    help="Fetch GEBCO_2023 seafloor (negative elevations) and merge under "
                         "land DEM so submerged areas have real shape, not flat plane.")
    ap.add_argument("--res", type=int, default=None,
                    help="Override --size for source DEM resolution. Use this to pull at "
                         "high res (e.g. --res 4096) and let --size downsample later.")
    ap.add_argument("--erosion-mode", choices=["thermal", "hydraulic", "none"], default="none",
                    help="Real DEMs are already eroded; default to none")
    ap.add_argument("--erosion", type=int, default=0)
    args = ap.parse_args()

    if args.source == "opentopo":
        bbox = tuple(args.bbox) if args.bbox else PRESETS.get(args.preset)
        if not bbox:
            raise SystemExit("Need --bbox or --preset")
        dataset = args.dataset or PRESET_DATASETS.get(args.preset, DEFAULT_DATASET)
        elev = fetch_opentopo(bbox, dataset=dataset)
        if args.bathymetry:
            print(f"  fetching GEBCO bathymetry to merge with {dataset}...")
            sea = fetch_opentopo(bbox, dataset="GEBCOIceTopo")
            # Resize bathymetry to match land DEM shape
            if sea.shape != elev.shape:
                sea_im = Image.fromarray(sea, mode="F").resize(
                    (elev.shape[1], elev.shape[0]), Image.LANCZOS)
                sea = np.asarray(sea_im, dtype=np.float32)
            # Merge: land DEM is authoritative ABOVE sea level (>=0); GEBCO fills below.
            # Many land DEMs clip seafloor to 0; bathymetry gives us real negative values.
            elev = np.where(elev > 0.0, elev, np.minimum(elev, sea))
            print(f"  merged: min={elev.min():.1f}m max={elev.max():.1f}m")
    elif args.source == "mapzen":
        if not args.mapzen_tile:
            raise SystemExit("Need --mapzen-tile Z X Y")
        elev = fetch_mapzen_terrarium(*args.mapzen_tile)
    else:
        if not args.input_tif or not args.input_tif.exists():
            raise SystemExit("--input-tif required for source=file")
        try:
            from osgeo import gdal
            elev = gdal.Open(str(args.input_tif)).ReadAsArray().astype(np.float32)
        except ImportError:
            elev = np.array(Image.open(args.input_tif).convert("F"), dtype=np.float32)

    # Sanitize NoData sentinels (USGS uses -999999 / -3.4e38). Replace with the
    # min of the *valid* values so they don't dominate the normalize step below.
    nodata_mask = elev < -1e5
    if nodata_mask.any():
        valid_min = float(elev[~nodata_mask].min()) if (~nodata_mask).any() else 0.0
        n_bad = int(nodata_mask.sum())
        elev = np.where(nodata_mask, valid_min, elev)
        print(f"  [sanitize] replaced {n_bad} NoData pixels with {valid_min:.1f}m")
    print(f"  elevation: min={elev.min():.1f}m max={elev.max():.1f}m shape={elev.shape}")

    target_res = args.res or args.size
    h_full = normalize(elev, exaggerate=args.exaggerate)
    # Resize via float32 'F' mode — PIL 12+ doesn't accept LANCZOS on 'I;16'
    im_full = Image.fromarray(h_full.astype(np.float32), mode="F")
    im_full = im_full.resize((target_res, target_res), Image.LANCZOS)
    h_full = np.clip(np.asarray(im_full, dtype=np.float32), 0.0, 1.0)
    if target_res > args.size:
        # Downsample for renderable mesh resolution but keep h_full for normal-map bake.
        im = Image.fromarray(h_full, mode="F").resize((args.size, args.size), Image.LANCZOS)
        h = np.clip(np.asarray(im, dtype=np.float32), 0.0, 1.0)
    else:
        h = h_full

    # Stash to a temporary 16-bit png and call terrain_bundle in image mode.
    # Simpler: import terrain_bundle as a library and call it.
    from terrain_bundle import (
        slope_from_height, flow_accumulation_d8, derive_biome, splat_rgba,
        vegetation_density, water_mask, hillshade, hypsometric_preview,
        normal_from_height, to_png_16bit, GODOT_TERRAIN3D_HINT,
        heightmapshape3d_tres, hydraulic_erode_landlab, thermal_erode,
    )
    import json
    from datetime import datetime, timezone

    if args.erosion_mode == "hydraulic":
        h = hydraulic_erode_landlab(h, n_steps=args.erosion or 100)
    elif args.erosion_mode == "thermal":
        h = thermal_erode(h, iterations=args.erosion or 30)

    out_dir = Path(__file__).parent / "output" / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "godot").mkdir(parents=True, exist_ok=True)

    slope = slope_from_height(h)
    flow = flow_accumulation_d8(h, iterations=20)
    biome_rgb, labels = derive_biome(h, slope)
    splat = splat_rgba(labels)
    veg = vegetation_density(labels, slope, h)
    water = water_mask(h)

    to_png_16bit(h, out_dir / "height_16.png")
    if target_res > args.size:
        # Save the high-res heightmap as a sidecar for normal-map / detail use.
        to_png_16bit(h_full, out_dir / f"height_16_full_{target_res}.png")
        # Use the high-res version to bake a higher-quality normal map.
        normal_from_height(h_full).resize((args.size, args.size), Image.LANCZOS).save(out_dir / "normal.png")
    else:
        normal_from_height(h).save(out_dir / "normal.png")
    Image.fromarray(splat, mode="RGBA").save(out_dir / "splat_rgba.png")
    Image.fromarray(biome_rgb, mode="RGB").save(out_dir / "biome.png")
    Image.fromarray(veg, mode="L").save(out_dir / "vegetation_density.png")
    Image.fromarray(water, mode="L").save(out_dir / "water_mask.png")
    Image.fromarray((flow * 255).astype(np.uint8), mode="L").save(out_dir / "flow.png")
    hypsometric_preview(h).save(out_dir / "preview_hypsometric.png")
    Image.fromarray(hillshade(h), mode="L").save(out_dir / "preview_hillshade.png")
    (out_dir / "godot" / "terrain3d_import.json").write_text(GODOT_TERRAIN3D_HINT, encoding="utf-8")
    (out_dir / "godot" / "heightmapshape3d.tres").write_text(
        heightmapshape3d_tres("../height_16.png"), encoding="utf-8"
    )

    metadata = {
        "id": args.id,
        "created": datetime.now(timezone.utc).isoformat(),
        "source": args.source,
        "bbox": list(args.bbox) if args.bbox else None,
        "preset": args.preset,
        "mapzen_tile": list(args.mapzen_tile) if args.mapzen_tile else None,
        "size": args.size,
        "elevation_min_m": float(elev.min()),
        "elevation_max_m": float(elev.max()),
    }
    (out_dir / "terrain.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\ndone: {out_dir}")


if __name__ == "__main__":
    main()
