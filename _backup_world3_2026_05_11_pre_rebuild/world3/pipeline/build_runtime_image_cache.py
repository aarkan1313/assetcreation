#!/usr/bin/env python3
"""Build export-safe runtime image caches for Godot CPU/GPU terrain inputs.

Godot's Image.load_from_file() is convenient in editor/dev runs but warns that
it will not work in export. This tool writes a tiny JSON manifest plus raw data
blob that can be loaded through FileAccess from res:// in both editor and
exported builds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def rel_res_path(path: Path) -> str:
    return "res://" + path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_height_cache(source: Path, out_manifest: Path, out_data: Path) -> None:
    im = Image.open(source)
    arr = np.asarray(im)
    if arr.ndim == 3:
        arr = arr[..., 0]
    if np.issubdtype(arr.dtype, np.integer):
        max_value = float(np.iinfo(arr.dtype).max)
        arr_f = arr.astype(np.float32) / max(max_value, 1.0)
    else:
        arr_f = arr.astype(np.float32)
        arr_min = float(arr_f.min())
        arr_max = float(arr_f.max())
        if arr_min < 0.0 or arr_max > 1.0:
            arr_f = (arr_f - arr_min) / max(arr_max - arr_min, 1e-6)
    arr_f = np.ascontiguousarray(np.clip(arr_f, 0.0, 1.0), dtype="<f4")

    out_data.parent.mkdir(parents=True, exist_ok=True)
    out_data.write_bytes(arr_f.tobytes(order="C"))
    write_manifest(out_manifest, {
        "version": 1,
        "kind": "runtime_image_cache",
        "source_path": rel_res_path(source),
        "source_sha256": sha256_file(source),
        "width": int(arr_f.shape[1]),
        "height": int(arr_f.shape[0]),
        "format": "rf32",
        "data_path": rel_res_path(out_data),
    })


def build_rgba_cache(source: Path, out_manifest: Path, out_data: Path) -> None:
    im = Image.open(source).convert("RGBA")
    arr = np.asarray(im, dtype=np.uint8)
    arr = np.ascontiguousarray(arr)

    out_data.parent.mkdir(parents=True, exist_ok=True)
    out_data.write_bytes(arr.tobytes(order="C"))
    write_manifest(out_manifest, {
        "version": 1,
        "kind": "runtime_image_cache",
        "source_path": rel_res_path(source),
        "source_sha256": sha256_file(source),
        "width": int(arr.shape[1]),
        "height": int(arr.shape[0]),
        "format": "rgba8",
        "data_path": rel_res_path(out_data),
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--height-source", default=str(ROOT / "heightmap/heightmap.png"))
    ap.add_argument("--splat-source", default=str(ROOT / "textures/m4_splat/alpine_height_slope_weights_rgba.png"))
    ap.add_argument("--out-dir", default=str(ROOT / "runtime_cache"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    height_source = Path(args.height_source)
    splat_source = Path(args.splat_source)

    build_height_cache(
        height_source,
        out_dir / "heightmap_rf32.json",
        out_dir / "heightmap_rf32.bin",
    )
    build_rgba_cache(
        splat_source,
        out_dir / "alpine_splat_rgba8.json",
        out_dir / "alpine_splat_rgba8.bin",
    )
    print(f"wrote runtime caches under {out_dir}")


if __name__ == "__main__":
    main()
