"""Preset loader. Reads JSON from presets/ dir and returns typed dataclasses."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pipelines.worldgen_v2 import paths


@dataclass(frozen=True)
class QualityPreset:
    dem_size: int
    mesh_subdiv: int
    collision_res: int
    shader: str
    triplanar_strength: float
    # Diorama render dimensions. v1 shipped 23 scenes at 512m wide / 64m relief
    # because those values keep texture tiles + scatter densities + camera FOVs
    # all in a known-good range. The DEM heightmap data is still real Death
    # Valley topology — it's just visually scaled to fit the diorama box.
    render_size_m: float
    render_height_m: float


@dataclass(frozen=True)
class CameraPreset:
    name: str
    fov: float | None
    ortho_size_m: float | None
    near: float
    far: float
    y_offset_m: float | None
    elevation_deg: float | None
    azimuth_deg: float | None


@dataclass(frozen=True)
class BiomePalette:
    albedo_rgb: tuple[int, int, int]
    roughness: float
    flux_prompt: str | None = None


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_quality(name: str) -> QualityPreset:
    data = _read_json(paths.PRESETS_DIR / "quality.json")
    if name not in data:
        raise KeyError(f"unknown quality preset: {name!r} (have {list(data)})")
    d = data[name]
    return QualityPreset(
        dem_size=int(d["dem_size"]),
        mesh_subdiv=int(d["mesh_subdiv"]),
        collision_res=int(d["collision_res"]),
        shader=str(d["shader"]),
        triplanar_strength=float(d["triplanar_strength"]),
        render_size_m=float(d.get("render_size_m", 512.0)),
        render_height_m=float(d.get("render_height_m", 64.0)),
    )


def load_camera(name: str) -> CameraPreset:
    data = _read_json(paths.PRESETS_DIR / "cameras.json")
    if name not in data:
        raise KeyError(f"unknown camera preset: {name!r} (have {list(data)})")
    d = data[name]
    return CameraPreset(
        name=name,
        fov=float(d["fov"]) if "fov" in d else None,
        ortho_size_m=float(d["ortho_size_m"]) if "ortho_size_m" in d else None,
        near=float(d["near"]),
        far=float(d["far"]),
        y_offset_m=float(d["y_offset_m"]) if "y_offset_m" in d else None,
        elevation_deg=float(d["elevation_deg"]) if "elevation_deg" in d else None,
        azimuth_deg=float(d["azimuth_deg"]) if "azimuth_deg" in d else None,
    )


def load_biome_palette(name: str) -> BiomePalette:
    data = _read_json(paths.PRESETS_DIR / "biomes.json")
    if name not in data:
        raise KeyError(f"unknown biome: {name!r} (have {list(data)})")
    d = data[name]
    rgb = tuple(int(x) for x in d["albedo_rgb"])
    return BiomePalette(
        albedo_rgb=rgb,
        roughness=float(d["roughness"]),
        flux_prompt=d.get("flux_prompt"),
    )
