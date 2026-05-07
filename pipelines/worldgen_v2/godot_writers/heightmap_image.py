"""Writer: copy DEM/splat/albedo PNGs into the Godot project.

Heightmaps and splats are data textures, not view textures. Godot's default
3D import path can VRAM-compress PNGs to S3TC/BPTC and generate mipmaps; that
is fine for albedo but corrupts height/splat samples enough to show terrain
cracks and black biome holes. We force those two files to import losslessly.
"""
from __future__ import annotations
import shutil
from pathlib import Path
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job


DATA_TEXTURES = {"height_16.png", "biome_splat_rgba.png"}


def _res_path(godot_project: Path, path: Path) -> str:
    return path.relative_to(godot_project).as_posix()


def _write_lossless_import(godot_project: Path, png_path: Path) -> None:
    """Force a PNG to stay lossless/no-mipmap when Godot imports it."""
    sidecar = png_path.with_suffix(png_path.suffix + ".import")
    sidecar.write_text(
        (
            "[remap]\n\n"
            'importer="texture"\n'
            'type="CompressedTexture2D"\n\n'
            "[deps]\n\n"
            f'source_file="res://{_res_path(godot_project, png_path)}"\n\n'
            "[params]\n\n"
            "compress/mode=0\n"
            "compress/high_quality=false\n"
            "compress/lossy_quality=0.7\n"
            "compress/hdr_compression=0\n"
            "compress/normal_map=0\n"
            "compress/channel_pack=0\n"
            "mipmaps/generate=false\n"
            "mipmaps/limit=-1\n"
            "roughness/mode=0\n"
            'roughness/src_normal=""\n'
            "process/channel_remap/red=0\n"
            "process/channel_remap/green=1\n"
            "process/channel_remap/blue=2\n"
            "process/channel_remap/alpha=3\n"
            "process/fix_alpha_border=false\n"
            "process/premult_alpha=false\n"
            "process/normal_map_invert_y=false\n"
            "process/hdr_as_srgb=false\n"
            "process/hdr_clamp_exposure=false\n"
            "process/size_limit=0\n"
            "detect_3d/compress_to=0\n"
        ),
        encoding="utf-8",
    )


def _clear_import_cache(godot_project: Path, png_path: Path) -> int:
    """Delete stale imported cache files so changed .import params take effect."""
    imported = godot_project / ".godot" / "imported"
    if not imported.exists():
        return 0
    deleted = 0
    for cache_file in imported.glob(f"{png_path.name}-*"):
        if cache_file.is_file():
            cache_file.unlink()
            deleted += 1
    return deleted


def write(job: Job, godot_project: Path) -> Path:
    out = paths.job_output_dir(job.id)
    dest_dir = godot_project / "terrain" / job.id
    dest_dir.mkdir(parents=True, exist_ok=True)
    files = ["height_16.png", "biome_splat_rgba.png"]
    for i, biome in enumerate(job.biomes):
        files.append(f"albedo_{i}_{biome}.png")
    for f in files:
        src = out / f
        if not src.exists():
            raise FileNotFoundError(f"heightmap_image: upstream missing {src}")
        dst = dest_dir / f
        shutil.copyfile(src, dst)
        if f in DATA_TEXTURES:
            _write_lossless_import(godot_project, dst)
            cleared = _clear_import_cache(godot_project, dst)
            if cleared:
                print(f"[heightmap_image] cleared {cleared} stale import cache file(s) for {f}")
    print(f"[heightmap_image] copied {len(files)} files to {dest_dir}")
    return dest_dir
