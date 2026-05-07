"""
glb_repack.py — Task 5: swap the embedded baseColorTexture in a GLB binary.

Public API:
    repack_albedo(src_glb, new_albedo, out_glb, mesh_idx=0, prim_idx=0) -> Path

CLI:
    python glb_repack.py --src <input.glb> --albedo <variant_albedo.png>
                         --out <output_variant.glb> [--mesh-idx 0] [--prim-idx 0]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pygltflib


def repack_albedo(
    src_glb: "Path | str",
    new_albedo: "Path | str",
    out_glb: "Path | str",
    mesh_idx: int = 0,
    prim_idx: int = 0,
) -> Path:
    """
    Replace the baseColorTexture of the specified mesh primitive in src_glb
    with new_albedo, writing the result to out_glb. Returns out_glb path.

    Raises:
        FileNotFoundError  — src_glb or new_albedo doesn't exist
        IndexError         — mesh_idx or prim_idx out of range
        ValueError         — missing material, baseColorTexture, or non-embedded image
    """
    src_glb = Path(src_glb)
    new_albedo = Path(new_albedo)
    out_glb = Path(out_glb)

    # --- validate inputs -------------------------------------------------------
    if not src_glb.exists():
        raise FileNotFoundError(f"src_glb not found: {src_glb}")
    if not new_albedo.exists():
        raise FileNotFoundError(f"new_albedo not found: {new_albedo}")

    # --- load GLB --------------------------------------------------------------
    glb = pygltflib.GLTF2().load(str(src_glb))

    # --- locate target mesh primitive ------------------------------------------
    if mesh_idx >= len(glb.meshes):
        raise IndexError(
            f"mesh_idx {mesh_idx} out of range (GLB has {len(glb.meshes)} mesh(es))"
        )
    mesh = glb.meshes[mesh_idx]

    if prim_idx >= len(mesh.primitives):
        raise IndexError(
            f"prim_idx {prim_idx} out of range (mesh[{mesh_idx}] has "
            f"{len(mesh.primitives)} primitive(s))"
        )
    prim = mesh.primitives[prim_idx]

    # --- walk material → texture → image ---------------------------------------
    if prim.material is None:
        raise ValueError(
            f"mesh[{mesh_idx}].primitives[{prim_idx}] has no material assigned"
        )

    mat = glb.materials[prim.material]
    pbr = mat.pbrMetallicRoughness
    if pbr is None or pbr.baseColorTexture is None:
        raise ValueError(
            f"material[{prim.material}] has no pbrMetallicRoughness.baseColorTexture"
        )

    tex_idx = pbr.baseColorTexture.index
    tex = glb.textures[tex_idx]
    if tex.source is None:
        raise ValueError(f"texture[{tex_idx}] has no source image index")

    img_idx = tex.source
    img = glb.images[img_idx]

    if img.bufferView is None:
        raise ValueError(
            f"image[{img_idx}] uses a URI ('{img.uri}') rather than embedded data; "
            "only embedded (bufferView) images are supported by repack_albedo"
        )

    bv_idx = img.bufferView

    # --- read new texture bytes ------------------------------------------------
    new_bytes = new_albedo.read_bytes()

    # --- rebuild binary blob ---------------------------------------------------
    # Iterate all bufferViews in index order, replacing bv_idx with new_bytes.
    # Align each bufferView start to a 4-byte boundary (GLB spec requirement).
    orig_blob = glb._glb_data  # raw bytes of the original binary chunk
    new_blob_parts: list[bytes] = []
    cursor = 0

    for i, bv in enumerate(glb.bufferViews):
        # 4-byte alignment padding before each bufferView
        pad = (4 - cursor % 4) % 4
        if pad:
            new_blob_parts.append(b"\x00" * pad)
            cursor += pad

        if i == bv_idx:
            data = new_bytes
        else:
            orig_offset = bv.byteOffset or 0
            data = orig_blob[orig_offset : orig_offset + bv.byteLength]

        # Update bufferView metadata in-place
        bv.byteOffset = cursor
        bv.byteLength = len(data)

        new_blob_parts.append(data)
        cursor += len(data)

    new_blob = b"".join(new_blob_parts)

    # Update buffer 0 total length
    glb.buffers[0].byteLength = len(new_blob)

    # Push new binary chunk into the GLB
    glb.set_binary_blob(new_blob)

    # Update image mimeType to match the new file
    img.mimeType = (
        "image/png" if new_albedo.suffix.lower() == ".png" else "image/jpeg"
    )

    # --- write output ----------------------------------------------------------
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    glb.save(str(out_glb))

    return out_glb


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Swap the embedded baseColorTexture in a GLB binary."
    )
    p.add_argument("--src", required=True, help="Input GLB path")
    p.add_argument("--albedo", required=True, help="New albedo PNG/JPEG to embed")
    p.add_argument("--out", required=True, help="Output GLB path")
    p.add_argument(
        "--mesh-idx", type=int, default=0, help="Target mesh index (default: 0)"
    )
    p.add_argument(
        "--prim-idx", type=int, default=0, help="Target primitive index (default: 0)"
    )
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        out_path = repack_albedo(
            src_glb=args.src,
            new_albedo=args.albedo,
            out_glb=args.out,
            mesh_idx=args.mesh_idx,
            prim_idx=args.prim_idx,
        )
        print(f"Wrote: {out_path}")
    except (FileNotFoundError, ValueError, IndexError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
