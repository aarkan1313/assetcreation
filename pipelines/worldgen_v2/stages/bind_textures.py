"""Stage 5: generate 4 albedo PNGs (one per biome) + pbr_pack.json.

Two modes:
- **procedural** (default): flat colour + multi-octave noise. Fast, offline,
  always works. Looks like Minecraft mud.
- **flux**: AAA seamless tiles via FLUX.2-klein-4B through ComfyUI. Photoreal.
  Requires `WORLDGEN_V2_USE_FLUX=1` and a running ComfyUI server. ~35s/biome.

The mode is chosen per-run by the `WORLDGEN_V2_USE_FLUX` environment variable.
This keeps the test suite fast and lets a one-shot CLI run be photoreal.
"""
from __future__ import annotations
import json
import os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from pipelines.worldgen_v2 import paths, presets
from pipelines.worldgen_v2.job_schema import Job

TEX_SIZE = 512
FLUX_TEX_SIZE = 1024  # FLUX outputs 1k tiles by default
GRAIN_AMPLITUDE = 14
COARSE_AMPLITUDE = 28


def _procedural_albedo(rgb: tuple[int, int, int], seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grain = rng.integers(-GRAIN_AMPLITUDE, GRAIN_AMPLITUDE + 1,
                         size=(TEX_SIZE, TEX_SIZE), dtype=np.int16)
    coarse_seed = rng.integers(-256, 256, size=(TEX_SIZE, TEX_SIZE)).astype(np.float32)
    coarse = gaussian_filter(coarse_seed, sigma=14.0)
    coarse_norm = coarse / (np.abs(coarse).max() or 1.0)
    coarse_int = (coarse_norm * COARSE_AMPLITUDE).round().astype(np.int16)
    base = np.array(rgb, dtype=np.int16)
    combined = grain + coarse_int
    img = base.reshape(1, 1, 3) + combined[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def _use_flux() -> bool:
    return os.environ.get("WORLDGEN_V2_USE_FLUX", "").strip() not in ("", "0", "false", "False")


def _flux_albedo_for_biome(job_id: str, biome: str, palette, dest_path) -> int:
    """Generate (or reuse cached) FLUX albedo. Returns the texture size in px."""
    from pipelines.worldgen_v2.stages import flux_albedo

    if not palette.flux_prompt:
        raise RuntimeError(
            f"bind_textures: WORLDGEN_V2_USE_FLUX is set but biome {biome!r} "
            "has no 'flux_prompt' field in presets/biomes.json"
        )
    asset_id = f"wgv2_{job_id}_{biome}"
    cached = flux_albedo.V1_LIBRARY / asset_id / f"{asset_id}_albedo.png"
    if cached.exists():
        print(f"[bind_textures] reusing cached FLUX texture: {cached.name}")
        import shutil
        shutil.copyfile(cached, dest_path)
    else:
        flux_albedo.generate_to(
            prompt=palette.flux_prompt,
            asset_id=asset_id,
            dest=dest_path,
            size=FLUX_TEX_SIZE,
            seed=hash(biome) & 0xFFFF,
        )
    return FLUX_TEX_SIZE


def run(job: Job) -> None:
    out = paths.job_output_dir(job.id)
    channels = []
    use_flux = _use_flux()
    if use_flux:
        print(f"[bind_textures] FLUX mode (WORLDGEN_V2_USE_FLUX=1)")
    tex_size = TEX_SIZE
    for i, biome in enumerate(job.biomes):
        palette = presets.load_biome_palette(biome)
        fname = f"albedo_{i}_{biome}.png"
        dest = out / fname
        if use_flux:
            tex_size = _flux_albedo_for_biome(job.id, biome, palette, dest)
        else:
            img = _procedural_albedo(palette.albedo_rgb, seed=hash(biome) & 0xFFFF)
            Image.fromarray(img, mode="RGB").save(dest)
        channels.append({
            "biome": biome,
            "channel_index": i,
            "albedo": fname,
            "roughness": palette.roughness,
        })
    pack = {
        "channels": channels,
        "tex_size": tex_size,
        "source": "flux" if use_flux else "procedural",
    }
    (out / "pbr_pack.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(f"[bind_textures] wrote 4 albedos + pbr_pack.json (source={pack['source']})")
