"""Job recipe schema + validator. No external deps (no pydantic)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

VALID_QUALITY = {"draft", "good", "max"}
VALID_DEM_SOURCES = {"opentopography"}
VALID_DATASETS = {"COP30", "SRTMGL1", "AW3D30", "USGS1m", "GEBCO"}
VALID_CAMERAS = {"character", "iso", "topdown", "worldview"}
VALID_EDIT_STYLES = {"realistic", "exaggerated", "terraced", "mythic"}


@dataclass(frozen=True)
class DemSpec:
    source: str
    dataset: str
    bbox: tuple[float, float, float, float]  # west, south, east, north


@dataclass(frozen=True)
class EditSpec:
    style: str
    strength: float


@dataclass(frozen=True)
class Job:
    id: str
    dem: DemSpec
    edit: EditSpec
    biomes: tuple[str, str, str, str]
    quality: str
    cameras: tuple[str, ...]


def load_dict(data: dict[str, Any]) -> Job:
    if "id" not in data or not isinstance(data["id"], str):
        raise ValueError("job: 'id' must be a string")
    dem_raw = data.get("dem")
    if not isinstance(dem_raw, dict):
        raise ValueError("job: 'dem' must be an object")
    src = dem_raw.get("source")
    if src not in VALID_DEM_SOURCES:
        raise ValueError(f"job: dem.source must be one of {VALID_DEM_SOURCES}, got {src!r}")
    ds = dem_raw.get("dataset")
    if ds not in VALID_DATASETS:
        raise ValueError(f"job: dem.dataset must be one of {VALID_DATASETS}, got {ds!r}")
    bbox = dem_raw.get("bbox")
    if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
        raise ValueError("job: dem.bbox must be a 4-element [W,S,E,N] list of numbers")
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError(f"job: dem.bbox values out of range or unordered: {bbox}")

    edit_raw = data.get("edit") or {"style": "realistic", "strength": 1.0}
    if edit_raw.get("style") not in VALID_EDIT_STYLES:
        raise ValueError(f"job: edit.style must be one of {VALID_EDIT_STYLES}")
    if not isinstance(edit_raw.get("strength"), (int, float)):
        raise ValueError("job: edit.strength must be a number")

    biomes = data.get("biomes")
    if not (isinstance(biomes, list) and len(biomes) == 4 and all(isinstance(b, str) for b in biomes)):
        raise ValueError("job: 'biomes' must be exactly 4 strings")

    quality = data.get("quality", "good")
    if quality not in VALID_QUALITY:
        raise ValueError(f"job: 'quality' must be one of {VALID_QUALITY}, got {quality!r}")

    cameras = data.get("cameras") or ["character"]
    if not (isinstance(cameras, list) and cameras and all(c in VALID_CAMERAS for c in cameras)):
        raise ValueError(f"job: 'cameras' must be a non-empty list from {VALID_CAMERAS}")

    return Job(
        id=data["id"],
        dem=DemSpec(source=src, dataset=ds, bbox=(float(w), float(s), float(e), float(n))),
        edit=EditSpec(style=edit_raw["style"], strength=float(edit_raw["strength"])),
        biomes=tuple(biomes),  # type: ignore[arg-type]
        quality=quality,
        cameras=tuple(cameras),
    )
