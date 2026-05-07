"""Volumetric fog density-volume baker.

Per `research/C2_vfx_3d_volumetric.md` §2: bake biome-tagged 3D density
volumes once, sample at runtime via a `shader_type fog;` shader on a
`FogVolume` node.

Implementation:
  - Generate a (W, H, D) density volume via Worley/Perlin/value noise
    (numpy only - no GPU dependency).
  - Pack the slices side-by-side into a wide PNG (W*D x H), one slice per
    horizontal stripe. Godot 4.5 imports this as a regular Texture2D; the
    fog shader reconstructs 3D sampling by computing slice index from UVW.z.
  - Emit `fog_material.tres` (FogMaterial referencing fog.gdshader) and
    `fog.gdshader` (shader_type fog reading the slice atlas).

Backend params:
  volume_resolution:  [W, H, D]   default [64, 64, 32]
  noise_type:         "worley" | "perlin" | "value"   default "worley"
  noise_scale:        float (cells per volume edge)   default 4.0
  noise_octaves:      int                             default 3
  density_curve:      "exp_falloff" | "linear" | "uniform"  default "exp_falloff"
  density_max:        float (clamped per-voxel)        default 0.5
  color_top:          hex                              palette[0]
  color_bottom:       hex                              palette[-1]
  emission_strength:  float                            default 0.0
  extents_m:          [x, y, z] FogVolume size (used by exporter)
  fog_shape:          "box" | "ellipsoid" | "cylinder"

This is the "no frames, no fps" backend: BakeManifest.flipbook = "" and
frames_dir = "". The exporter (export_godot_3d.py fog_volume target)
assembles the .tscn from `fog_material.tres` + `density.png`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import BakeManifest, Effect  # noqa: E402


def _hex_rgb(c: str) -> tuple[float, float, float]:
    s = c.lstrip("#")[:6]
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)


def _worley_3d(W: int, H: int, D: int, n_seeds: int,
              rng: np.random.Generator) -> np.ndarray:
    """Cellular noise: distance to closest of n_seeds random points,
    normalized to [0, 1]. Lower = closer to a seed = higher fog density."""
    seeds = rng.uniform(0.0, 1.0, (n_seeds, 3)).astype(np.float32)
    seeds *= np.array([W, H, D], dtype=np.float32)
    out = np.empty((W, H, D), dtype=np.float32)
    # voxel grid
    xs = np.arange(W, dtype=np.float32)
    ys = np.arange(H, dtype=np.float32)
    zs = np.arange(D, dtype=np.float32)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1)  # (W,H,D,3)
    grid = grid.reshape(-1, 3)  # (W*H*D, 3)
    # Distance to closest seed: process in chunks to bound memory.
    n_vox = grid.shape[0]
    closest = np.full(n_vox, np.inf, dtype=np.float32)
    chunk = 16384
    for s in seeds:
        for i in range(0, n_vox, chunk):
            sub = grid[i:i + chunk]
            d = np.linalg.norm(sub - s, axis=1)
            closest[i:i + chunk] = np.minimum(closest[i:i + chunk], d)
    return closest.reshape(W, H, D)


def _value_3d(W: int, H: int, D: int, scale: float, octaves: int,
             rng: np.random.Generator) -> np.ndarray:
    """Simple multi-octave value noise. Good enough for fog masks."""
    out = np.zeros((W, H, D), dtype=np.float32)
    amp = 1.0
    total_amp = 0.0
    for o in range(octaves):
        f = scale * (2 ** o)
        gW = max(int(W / max(f, 1)), 2)
        gH = max(int(H / max(f, 1)), 2)
        gD = max(int(D / max(f, 1)), 2)
        coarse = rng.uniform(0.0, 1.0, (gW, gH, gD)).astype(np.float32)
        # nearest-resample to (W, H, D); good enough at low octaves
        xi = (np.arange(W) * (gW - 1) / max(W - 1, 1)).astype(np.int32)
        yi = (np.arange(H) * (gH - 1) / max(H - 1, 1)).astype(np.int32)
        zi = (np.arange(D) * (gD - 1) / max(D - 1, 1)).astype(np.int32)
        sample = coarse[xi[:, None, None], yi[None, :, None], zi[None, None, :]]
        out += sample * amp
        total_amp += amp
        amp *= 0.5
    return out / max(total_amp, 1e-6)


def _bake_density(p: dict, rng: np.random.Generator) -> np.ndarray:
    res = p.get("volume_resolution", [64, 64, 32])
    W, H, D = int(res[0]), int(res[1]), int(res[2])
    noise_type = p.get("noise_type", "worley")
    octaves = int(p.get("noise_octaves", 3))
    scale = float(p.get("noise_scale", 4.0))
    if noise_type == "worley":
        n_seeds = max(int(scale * 4), 6)
        d = _worley_3d(W, H, D, n_seeds, rng)
        # Worley distance is large -> small fog. Invert + normalize.
        d_max = d.max()
        if d_max > 0:
            d = 1.0 - (d / d_max)
    else:  # value / perlin-fallback
        d = _value_3d(W, H, D, scale, octaves, rng)
        d_min, d_max = d.min(), d.max()
        if d_max - d_min > 1e-6:
            d = (d - d_min) / (d_max - d_min)

    # Vertical density curve: ground-heavy fog
    curve = p.get("density_curve", "exp_falloff")
    yy = np.linspace(0, 1, H, dtype=np.float32)
    if curve == "exp_falloff":
        # high at y=0, decays going up
        falloff = np.exp(-yy * 3.0)
    elif curve == "linear":
        falloff = 1.0 - yy
    else:
        falloff = np.ones_like(yy)
    d *= falloff[None, :, None]

    d_max_clamp = float(p.get("density_max", 0.5))
    return np.clip(d, 0.0, d_max_clamp).astype(np.float32)


def _pack_slices_horizontal(volume: np.ndarray, color_top: tuple[float, float, float],
                            color_bottom: tuple[float, float, float]) -> Image.Image:
    """Tile the D depth slices side-by-side into a (W*D x H) RGBA PNG.
    R = density. GBA store optional color (we lerp top->bottom by Y inside the
    shader instead, so we encode density only and leave color in the .tres
    uniforms - cleaner)."""
    W, H, D = volume.shape
    arr = np.zeros((H, W * D, 4), dtype=np.uint8)
    for z in range(D):
        slab = volume[:, :, z].T  # H, W (PNG y-down convention)
        # density encoded in R (8-bit). G/B = 0. A = density too so editors show
        # something sensible on inspection.
        a = (slab * 255).astype(np.uint8)
        arr[:, z * W:(z + 1) * W, 0] = a
        arr[:, z * W:(z + 1) * W, 3] = a
    return Image.fromarray(arr, "RGBA")


# --- shader / material text ------------------------------------------------

FOG_SHADER = """\
// Volumetric fog material - reads sliced 3D density from a 2D atlas.
// `density_atlas` layout: D slices, each WxH, concatenated horizontally
// -> total atlas size (W*D, H). The shader reconstructs 3D by interpolating
// between two adjacent z-slices at the voxel's UVW.z.
shader_type fog;

uniform sampler2D density_atlas : filter_linear, repeat_disable;
uniform vec3 atlas_meta = vec3(64.0, 64.0, 32.0);  // W, H, D
uniform float density_scale = 1.0;
uniform vec3 color_top : source_color = vec3(1.0);
uniform vec3 color_bottom : source_color = vec3(0.4);
uniform float emission_strength = 0.0;
uniform float anim_speed = 0.05;
uniform float anim_amp = 0.05;

float sample_density(vec3 uvw) {
    float W = atlas_meta.x;
    float H = atlas_meta.y;
    float D = atlas_meta.z;
    float zf = clamp(uvw.z, 0.0, 1.0) * (D - 1.0);
    float z0 = floor(zf);
    float z1 = min(z0 + 1.0, D - 1.0);
    float zt = zf - z0;
    vec2 cell = vec2(W / (W * D), 1.0);  // = vec2(1/D, 1)
    float u_in = clamp(uvw.x, 0.0, 1.0) * cell.x;
    float v_in = clamp(uvw.y, 0.0, 1.0);
    vec2 uv0 = vec2(z0 / D + u_in, v_in);
    vec2 uv1 = vec2(z1 / D + u_in, v_in);
    float d0 = texture(density_atlas, uv0).r;
    float d1 = texture(density_atlas, uv1).r;
    return mix(d0, d1, zt);
}

void fog() {
    // OBJECT_POSITION -> UVW [0,1] within the FogVolume.
    // The fog renderer feeds us UVW directly; just read.
    vec3 uvw = UVW;
    // Cheap time warp on UV so density slowly evolves.
    uvw.xz += vec2(sin(TIME * anim_speed), cos(TIME * anim_speed * 1.3)) * anim_amp;

    float d = sample_density(uvw);
    DENSITY = d * density_scale;
    vec3 col = mix(color_bottom, color_top, clamp(uvw.y, 0.0, 1.0));
    ALBEDO = col;
    EMISSION = col * emission_strength;
}
"""


def _make_material_tres(godot_rel: str, atlas_w: int, atlas_h: int,
                        W: int, H: int, D: int,
                        color_top: tuple[float, float, float],
                        color_bottom: tuple[float, float, float],
                        density_scale: float, emission: float) -> str:
    return (
        '[gd_resource type="FogMaterial" load_steps=3 format=3]\n\n'
        f'[ext_resource type="Shader" path="res://{godot_rel}/fog.gdshader" id="1_sh"]\n'
        f'[ext_resource type="Texture2D" path="res://{godot_rel}/density.png" id="2_atlas"]\n\n'
        '[resource]\n'
        '# FogMaterial.shader is set so volumetric_fog samples our shader.\n'
        'shader = ExtResource("1_sh")\n'
        'shader_parameter/density_atlas = ExtResource("2_atlas")\n'
        f'shader_parameter/atlas_meta = Vector3({W}, {H}, {D})\n'
        f'shader_parameter/density_scale = {density_scale}\n'
        f'shader_parameter/color_top = Color({color_top[0]}, {color_top[1]}, {color_top[2]}, 1)\n'
        f'shader_parameter/color_bottom = Color({color_bottom[0]}, {color_bottom[1]}, {color_bottom[2]}, 1)\n'
        f'shader_parameter/emission_strength = {emission}\n'
        'shader_parameter/anim_speed = 0.05\n'
        'shader_parameter/anim_amp = 0.05\n'
    )


# --- baker entry point -----------------------------------------------------

def bake(effect: Effect, out_root: Path) -> BakeManifest:
    p = effect.backend_params
    rng = np.random.default_rng(p.get("seed", 0))
    res = p.get("volume_resolution", [64, 64, 32])
    W, H, D = int(res[0]), int(res[1]), int(res[2])

    palette = effect.visual.palette
    color_top = _hex_rgb(p.get("color_top", palette[0] if palette else "#ffffff"))
    color_bottom = _hex_rgb(p.get("color_bottom", palette[-1] if palette else "#666666"))
    emission = float(p.get("emission_strength", 0.5 if effect.visual.bloom else 0.0))
    density_scale = float(p.get("density_scale", 1.0))

    volume = _bake_density(p, rng)
    img = _pack_slices_horizontal(volume, color_top, color_bottom)
    density_path = out_root / "density.png"
    out_root.mkdir(parents=True, exist_ok=True)
    img.save(density_path)

    # Shader + Material .tres land next to effect.json. The fog_material.tres
    # references fog.gdshader and density.png at `res://vfx/<kind>/<id>/...`,
    # which is where they end up when the user copies vfx/catalog/ contents
    # into res://vfx/. No path rewriting needed at export time.
    (out_root / "fog.gdshader").write_text(FOG_SHADER, encoding="utf-8")
    kind = effect.kind
    godot_rel = f"vfx/{kind}/{effect.id}"
    mat_text = _make_material_tres(godot_rel, img.size[0], img.size[1],
                                   W, H, D, color_top, color_bottom,
                                   density_scale, emission)
    (out_root / "fog_material.tres").write_text(mat_text, encoding="utf-8")

    return BakeManifest(
        effect_id=effect.id,
        backend="volumetric_fog",
        n_frames=0,
        fps=0,
        bounds_px=(img.size[0], img.size[1]),
        flipbook="",
        frames_dir="",
        extras={
            "density_volume": str(density_path),
            "fog_shader": str(out_root / "fog.gdshader"),
            "fog_material": str(out_root / "fog_material.tres"),
            "volume_resolution": [W, H, D],
            "color_top": list(color_top),
            "color_bottom": list(color_bottom),
        },
        metrics={
            "voxels": int(W * H * D),
            "density_max": float(volume.max()),
            "density_mean": float(volume.mean()),
        },
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# --- biome preset emitter --------------------------------------------------

# Colour + tuning per biome. Sourced from
# `art_lab/biomes/biome_scatter_rules.json` palettes (averaged) plus C2's
# narrative recommendation of "ground-heavy haze that takes the biome's hue".
BIOME_PRESETS: dict[str, dict] = {
    "lava_field": {
        "color_top": "#ff5e1e", "color_bottom": "#3a0a05",
        "density_max": 0.55, "density_scale": 1.2,
        "emission_strength": 0.8, "noise_type": "worley", "noise_scale": 6.0,
        "extents_m": [24.0, 6.0, 24.0], "fog_shape": "box",
    },
    "ice_cavern": {
        "color_top": "#cfe6f5", "color_bottom": "#5a7a92",
        "density_max": 0.45, "density_scale": 0.9,
        "emission_strength": 0.0, "noise_type": "value", "noise_scale": 5.0,
        "extents_m": [24.0, 8.0, 24.0], "fog_shape": "box",
    },
    "mana_crystal": {
        "color_top": "#d8a8ff", "color_bottom": "#3a1a55",
        "density_max": 0.40, "density_scale": 0.8,
        "emission_strength": 1.0, "noise_type": "worley", "noise_scale": 4.0,
        "extents_m": [22.0, 7.0, 22.0], "fog_shape": "ellipsoid",
    },
    "grassland": {
        "color_top": "#e6f0c8", "color_bottom": "#5a6a3a",
        "density_max": 0.25, "density_scale": 0.5,
        "emission_strength": 0.0, "noise_type": "value", "noise_scale": 3.5,
        "extents_m": [32.0, 4.0, 32.0], "fog_shape": "box",
    },
    "ruins": {
        "color_top": "#a89c80", "color_bottom": "#332b1f",
        "density_max": 0.40, "density_scale": 1.0,
        "emission_strength": 0.0, "noise_type": "value", "noise_scale": 4.5,
        "extents_m": [20.0, 6.0, 20.0], "fog_shape": "box",
    },
    "swamp": {
        "color_top": "#9bb380", "color_bottom": "#1f2a18",
        "density_max": 0.50, "density_scale": 1.0,
        "emission_strength": 0.0, "noise_type": "worley", "noise_scale": 5.5,
        "extents_m": [28.0, 5.0, 28.0], "fog_shape": "box",
    },
    "ash_waste": {
        "color_top": "#7a6a5a", "color_bottom": "#1a1612",
        "density_max": 0.45, "density_scale": 0.9,
        "emission_strength": 0.05, "noise_type": "value", "noise_scale": 4.0,
        "extents_m": [28.0, 5.0, 28.0], "fog_shape": "box",
    },
}


def emit_biome_preset_effects(catalog_root: Path) -> list[Path]:
    """Write one effect.json per biome under
    vfx/catalog/ambient/<biome>_haze/. Returns paths written."""
    out_root = catalog_root / "ambient"
    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for biome, preset in BIOME_PRESETS.items():
        eid = f"{biome}_haze"
        eff_dir = out_root / eid
        eff_dir.mkdir(exist_ok=True)
        ej_path = eff_dir / "effect.json"
        if ej_path.exists():
            continue
        effect = {
            "id": eid,
            "kind": "ambient",
            "phenomenon": "smoke",
            "backend": "volumetric_fog",
            "duration_s": 1.0,  # placeholder; non-frame backend
            "fps": 8,
            "bounds_px": [256, 256],
            "visual": {
                "palette": [preset["color_top"], preset["color_bottom"]],
                "blend": "alpha",
                "background": "#00000000",
                "bloom": preset["emission_strength"] > 0.1,
            },
            "visual3d": {
                "billboard_mode": "off",
                "world_size_m": float(preset["extents_m"][0]),
            },
            "backend_params": {
                "volume_resolution": [64, 64, 32],
                "noise_type": preset["noise_type"],
                "noise_scale": preset["noise_scale"],
                "noise_octaves": 3,
                "density_curve": "exp_falloff",
                "density_max": preset["density_max"],
                "density_scale": preset["density_scale"],
                "color_top": preset["color_top"],
                "color_bottom": preset["color_bottom"],
                "emission_strength": preset["emission_strength"],
                "extents_m": preset["extents_m"],
                "fog_shape": preset["fog_shape"],
                "biome_id": biome,
                "seed": hash(biome) & 0xFFFF,
            },
            "gameplay": {"shape": "self", "damage_tags": [], "collision": "none"},
            "element": "neutral",
            "archetype": "ambient",
            "tags": ["biome", biome, "fog"],
            "export_target": "fog_volume",
            "notes": f"Per-biome volumetric haze for {biome}. Place a FogVolume "
                     f"node in scenes that contain this biome zone.",
        }
        ej_path.write_text(json.dumps(effect, indent=2))
        written.append(ej_path)
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect_json", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--emit-biome-presets", action="store_true",
                    help="Write effect.json stubs for all biome presets and exit.")
    ap.add_argument("--catalog", type=Path,
                    default=Path(r"D:\assets\vfx\catalog"))
    args = ap.parse_args()

    if args.emit_biome_presets:
        written = emit_biome_preset_effects(args.catalog)
        for p in written:
            print(f"[volumetric_fog] wrote {p}")
        if not written:
            print(f"[volumetric_fog] no new biome presets (already exist)")
        return

    if not args.effect_json:
        ap.error("provide effect_json or --emit-biome-presets")

    effect = Effect.model_validate_json(args.effect_json.read_text(encoding="utf-8"))
    out = args.out or args.effect_json.parent
    out.mkdir(parents=True, exist_ok=True)
    manifest = bake(effect, out)
    (out / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    print(f"[volumetric_fog] {effect.id}: {manifest.metrics['voxels']} voxels, "
          f"density_max={manifest.metrics['density_max']:.3f} -> {out}")


if __name__ == "__main__":
    main()
