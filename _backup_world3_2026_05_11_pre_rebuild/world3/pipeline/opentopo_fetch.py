"""OpenTopography acquisition helper for world3.

Reads opentopo/sample_plan.json, computes per-site bounding boxes, optionally
queries otCatalog, and downloads raster samples from globaldem/usgsdem.

Examples:
    python pipeline/opentopo_fetch.py --priority 1 --dry-run
    python pipeline/opentopo_fetch.py --priority 1 --catalog
    python pipeline/opentopo_fetch.py --site-id des_mojave_usa --global COP30,NASADEM --usgs USGS10m

Set OPENTOPOGRAPHY_API_KEY before downloading rasters. OPENTOPO_API_KEY is
accepted as a local alias.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://portal.opentopography.org/API"
S3_BASE = "https://opentopography.s3.sdsc.edu"
COG_DATASETS = {
    "COP30": f"/vsicurl/{S3_BASE}/raster/COP30/COP30_hh.vrt",
    "COP90": f"/vsicurl/{S3_BASE}/raster/COP90/COP90_hh.vrt",
    "NASADEM": f"/vsicurl/{S3_BASE}/raster/NASADEM/NASADEM_be.vrt",
    "SRTMGL1": f"/vsicurl/{S3_BASE}/raster/SRTM_GL1/SRTM_GL1_srtm.vrt",
    "AW3D30": f"/vsicurl/{S3_BASE}/raster/AW3D30/AW3D30_global.vrt",
    "AW3D30_E": f"/vsicurl/{S3_BASE}/raster/AW3D30_E/AW3D30_E_global.vrt",
    "SRTM15Plus": f"/vsicurl/{S3_BASE}/raster/SRTM15Plus/SRTM15Plus_srtm.vrt",
    "GEBCOIceTopo": f"/vsicurl/{S3_BASE}/raster/GEBCOIceTopo/GEBCOIceTopo.vrt",
    "GEBCOSubIceTopo": f"/vsicurl/{S3_BASE}/raster/GEBCOSubIceTopo/GEBCOSubIceTopo.vrt",
    "CA_MRDEM_DTM": f"/vsicurl/{S3_BASE}/raster/CA_MRDEM/CA_MRDEM_be.vrt",
    "CA_MRDEM_DSM": f"/vsicurl/{S3_BASE}/raster/CA_MRDEM/CA_MRDEM_hh.vrt",
    "GEDI_L3_ELEV": f"/vsicurl/{S3_BASE}/raster/GEDI_L3/GEDI_L3_be.vrt",
    "GEDI_L3_RH100": f"/vsicurl/{S3_BASE}/raster/GEDI_L3/GEDI_L3_vh.vrt",
    "EU_DTM": f"/vsicurl/{S3_BASE}/raster/EU_DTM/EU_DTM_be.vrt",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_plan(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_local_env(root: Path) -> None:
    env_path = root / "opentopo" / "config" / "opentopo.env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    primary = os.environ.get("OPENTOPOGRAPHY_API_KEY")
    alias = os.environ.get("OPENTOPO_API_KEY")
    if primary and not alias:
        os.environ["OPENTOPO_API_KEY"] = primary
    elif alias and not primary:
        os.environ["OPENTOPOGRAPHY_API_KEY"] = alias


def flatten_sites(plan: dict) -> list[dict]:
    rows: list[dict] = []
    for biome in plan["biomes"]:
        for site in biome["sites"]:
            row = dict(site)
            row["biome_code"] = biome["code"]
            row["biome_name"] = biome["name"]
            rows.append(row)
    return rows


def bbox_for_site(site: dict, sample_km: float) -> dict[str, float]:
    half_km = sample_km * 0.5
    lat = float(site["lat"])
    lon = float(site["lon"])
    lat_delta = half_km / 110.574
    cos_lat = max(math.cos(math.radians(lat)), 0.05)
    lon_delta = half_km / (111.320 * cos_lat)
    return {
        "south": max(lat - lat_delta, -90.0),
        "north": min(lat + lat_delta, 90.0),
        "west": max(lon - lon_delta, -180.0),
        "east": min(lon + lon_delta, 180.0),
    }


def slug_bbox(bbox: dict[str, float]) -> str:
    return (
        f"{bbox['west']:+.4f}_{bbox['south']:+.4f}_"
        f"{bbox['east']:+.4f}_{bbox['north']:+.4f}"
    ).replace("+", "p").replace("-", "m")


def http_get(url: str, params: dict[str, object], timeout: int = 120) -> tuple[int, bytes]:
    full_url = url + "?" + urlencode(params)
    req = Request(full_url, headers={"User-Agent": "world3-opentopo-fetch/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def looks_like_geotiff(data: bytes) -> bool:
    return data.startswith(b"II*\x00") or data.startswith(b"MM\x00*")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def summarize_catalog(raw: dict) -> dict:
    datasets = raw.get("Datasets") or []
    counts: dict[str, int] = {}
    examples: list[dict] = []
    for item in datasets:
        dataset = item.get("Dataset", {})
        ident = dataset.get("identifier", {})
        provider = ident.get("propertyID", "unknown")
        counts[provider] = counts.get(provider, 0) + 1
        if len(examples) < 10:
            examples.append({
                "name": dataset.get("name"),
                "id_type": provider,
                "id": ident.get("value"),
                "format": dataset.get("fileFormat"),
                "temporal": dataset.get("temporalCoverage"),
                "url": dataset.get("url"),
            })
    return {"count": len(datasets), "by_identifier_type": counts, "examples": examples}


def select_sites(sites: list[dict], priority: int | None, site_id: str | None) -> list[dict]:
    if site_id:
        return [s for s in sites if s["id"] == site_id]
    if priority is not None:
        return [s for s in sites if int(s.get("priority", 99)) == priority]
    return sites


def download_catalog(root: Path, site: dict, bbox: dict[str, float]) -> dict:
    params = {
        "minx": bbox["west"],
        "miny": bbox["south"],
        "maxx": bbox["east"],
        "maxy": bbox["north"],
        "productFormat": "PointCloud",
        "outputFormat": "json",
        "include_federated": "true",
        "detail": "false",
    }
    status, raw_bytes = http_get(f"{API_BASE}/otCatalog", params)
    if status == 204 or not raw_bytes:
        raw_bytes = b'{"Datasets":[]}'
    raw = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    raw_path = root / "opentopo" / "catalog" / "otcatalog_raw" / f"{site['id']}.json"
    summary_path = root / "opentopo" / "catalog" / "site_catalog_summary.json"
    write_json(raw_path, raw)

    summary = summarize_catalog(raw)
    all_summary = {}
    if summary_path.exists():
        all_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    all_summary[site["id"]] = {
        "biome_code": site["biome_code"],
        "locale": site["locale"],
        "bbox": bbox,
        **summary,
    }
    write_json(summary_path, all_summary)
    return summary


def download_globaldem(root: Path, site: dict, bbox: dict[str, float], demtype: str, api_key: str) -> Path:
    params = {
        "demtype": demtype,
        **bbox,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }
    out = root / "opentopo" / "raw" / "globaldem" / site["id"] / f"{demtype}_{slug_bbox(bbox)}.tif"
    out.parent.mkdir(parents=True, exist_ok=True)
    status, data = http_get(f"{API_BASE}/globaldem", params, timeout=300)
    if status == 204 or not data:
        raise RuntimeError(f"No raster returned for globaldem {demtype}")
    if not looks_like_geotiff(data):
        preview = data[:120].decode("utf-8", errors="replace").replace("\n", " ")
        raise RuntimeError(f"Non-GeoTIFF response for globaldem {demtype}: {preview}")
    out.write_bytes(data)
    return out


def download_usgsdem(root: Path, site: dict, bbox: dict[str, float], dataset: str, api_key: str) -> Path:
    params = {
        "datasetName": dataset,
        **bbox,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }
    out = root / "opentopo" / "raw" / "usgsdem" / site["id"] / f"{dataset}_{slug_bbox(bbox)}.tif"
    out.parent.mkdir(parents=True, exist_ok=True)
    status, data = http_get(f"{API_BASE}/usgsdem", params, timeout=300)
    if status == 204 or not data:
        raise RuntimeError(f"No raster returned for usgsdem {dataset}")
    if not looks_like_geotiff(data):
        preview = data[:120].decode("utf-8", errors="replace").replace("\n", " ")
        raise RuntimeError(f"Non-GeoTIFF response for usgsdem {dataset}: {preview}")
    out.write_bytes(data)
    return out


def download_cog(root: Path, site: dict, bbox: dict[str, float], dataset: str) -> Path:
    try:
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds
    except ImportError as exc:
        raise RuntimeError("rasterio is required for --cog downloads") from exc

    if dataset not in COG_DATASETS:
        raise RuntimeError(f"Unknown COG dataset {dataset}; known: {', '.join(sorted(COG_DATASETS))}")

    out = root / "opentopo" / "raw" / "cog" / site["id"] / f"{dataset}_{slug_bbox(bbox)}.tif"
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(COG_DATASETS[dataset]) as src:
        if src.crs and str(src.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
            left, bottom, right, top = transform_bounds(
                "EPSG:4326",
                src.crs,
                bbox["west"],
                bbox["south"],
                bbox["east"],
                bbox["north"],
                densify_pts=21,
            )
        else:
            left, bottom, right, top = bbox["west"], bbox["south"], bbox["east"], bbox["north"]
        window = from_bounds(left, bottom, right, top, src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window, boundless=True, masked=True)
        if data.size == 0:
            raise RuntimeError(f"No pixels returned for COG {dataset}")
        profile = src.profile.copy()
        profile.update({
            "driver": "GTiff",
            "height": data.shape[0],
            "width": data.shape[1],
            "count": 1,
            "transform": src.window_transform(window),
            "compress": "deflate",
            "tiled": True,
        })
        if getattr(data, "mask", None) is not None and data.mask is not False:
            nodata = profile.get("nodata")
            if nodata is None:
                nodata = -9999.0
                profile["nodata"] = nodata
            data_to_write = data.filled(nodata)
        else:
            data_to_write = data
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(data_to_write, 1)
    return out


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> int:
    root = project_root()
    load_local_env(root)
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, default=root / "opentopo" / "sample_plan.json")
    ap.add_argument("--priority", type=int, default=None, help="select priority group, e.g. 1")
    ap.add_argument("--site-id", default=None, help="select one site id")
    ap.add_argument("--km", type=float, default=None, help="sample width/height in km")
    ap.add_argument("--catalog", action="store_true", help="query otCatalog for selected sites")
    ap.add_argument("--global", dest="global_demtypes", default="", help="comma list, e.g. COP30,NASADEM")
    ap.add_argument("--usgs", dest="usgs_datasets", default="", help="comma list, e.g. USGS10m,USGS1m")
    ap.add_argument("--cog", dest="cog_datasets", default="", help="comma list of public COG/VRT sources, e.g. COP30,SRTMGL1")
    ap.add_argument("--dry-run", action="store_true", help="print planned requests without network")
    args = ap.parse_args()

    plan = load_plan(args.plan)
    sample_km = float(args.km or plan.get("default_initial_sample_km", 20))
    sites = select_sites(flatten_sites(plan), args.priority, args.site_id)
    if not sites:
        print("No sites matched selection", file=sys.stderr)
        return 2

    global_demtypes = split_csv(args.global_demtypes)
    usgs_datasets = split_csv(args.usgs_datasets)
    cog_datasets = split_csv(args.cog_datasets)
    needs_key = bool(global_demtypes or usgs_datasets)
    api_key = os.environ.get("OPENTOPOGRAPHY_API_KEY") or os.environ.get("OPENTOPO_API_KEY", "")
    if needs_key and not api_key and not args.dry_run:
        print("Set OPENTOPOGRAPHY_API_KEY before raster downloads.", file=sys.stderr)
        return 2

    for site in sites:
        bbox = bbox_for_site(site, sample_km)
        print(f"{site['id']} | {site['biome_code']} | {site['locale']} | {sample_km:g} km")
        print(f"  bbox south={bbox['south']:.6f} north={bbox['north']:.6f} west={bbox['west']:.6f} east={bbox['east']:.6f}")
        if args.dry_run:
            if args.catalog:
                print("  would query otCatalog")
            for demtype in global_demtypes:
                print(f"  would download globaldem {demtype}")
            for dataset in usgs_datasets:
                print(f"  would download usgsdem {dataset}")
            for dataset in cog_datasets:
                print(f"  would download COG {dataset}")
            continue
        if args.catalog:
            try:
                summary = download_catalog(root, site, bbox)
                print(f"  catalog count={summary['count']} by={summary['by_identifier_type']}")
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                print(f"  ERROR catalog: {exc}", file=sys.stderr)
        for demtype in global_demtypes:
            try:
                out = download_globaldem(root, site, bbox, demtype, api_key)
                print(f"  wrote {out}")
            except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
                print(f"  ERROR globaldem {demtype}: {exc}", file=sys.stderr)
        for dataset in usgs_datasets:
            try:
                out = download_usgsdem(root, site, bbox, dataset, api_key)
                print(f"  wrote {out}")
            except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
                print(f"  ERROR usgsdem {dataset}: {exc}", file=sys.stderr)
        for dataset in cog_datasets:
            try:
                out = download_cog(root, site, bbox, dataset)
                print(f"  wrote {out}")
            except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
                print(f"  ERROR COG {dataset}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
