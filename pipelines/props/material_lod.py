"""Material-LOD kit atlas — far-tier albedo unification.

Per J2 §5: at LOD2/LOD3 distances (>60m), specular highlights from normal
maps don't read; flat shading with baked-in AO is correct. The win is
**draw-call reduction**: every distant kit prop UV-references a single
atlas, so Godot binds one texture and a single MultiMesh draws all of them.

This MVP version sticks to the **procedural-prop reality**: our LOD0 GLBs
already ship Principled-BSDF flat-color materials (no textures). Re-baking
into an atlas would be ~5-10s/prop in Cycles for zero pixel difference.
Instead we:

  1. Read each prop in the kit.
  2. Extract per-material slot albedo colors from a quick Blender introspect
     (or, when running standalone, sample the GLB via `pygltflib`).
  3. Pack all colors as 1×1 tiles into a small kit atlas PNG (8x8 = 64 slots
     at 256² total, scaled up so each tile is 32×32 with smooth edges).
  4. Write `kit_atlas_lod_far.png` + `kit_atlas_manifest.json` mapping
     `prop_id -> [tile_x, tile_y]` per material slot.
  5. Update each prop's prop.json with `material_lod.kit_atlas` reference.

The `.tscn` material rebinder is a follow-up; for now the manifest is the
machine-readable source of truth, and Godot can be wired later to use a
single SpatialMaterial with this atlas for distant LOD2/LOD3 nodes.

For full PBR-bake parity (ship LOD2 GLBs with rebound UVs) we need the
xatlas + Cycles bake path — see `proc_atlas_bake.py` (deferred).

CLI:
  python material_lod.py --kit first_party_proc
  python material_lod.py --kit first_party_proc --tile-px 32 --grid 8
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIBRARY = Path(r"D:\assets\world\props\library")
KIT_OUT_DIR = Path(r"D:\assets\world\props\kits")


def _try_imports():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("[material_lod] missing PIL; pip install pillow", file=sys.stderr)
        sys.exit(2)


def extract_glb_material_colors(glb_path: Path) -> list[tuple[float, float, float]]:
    """Pull Principled BSDF base-color values from a GLB.

    GLB stores PBR materials in JSON header; we read with pygltflib if
    available, fall back to trimesh, or return an empty list.
    """
    try:
        import pygltflib
        gltf = pygltflib.GLTF2().load(str(glb_path))
        out = []
        for mat in gltf.materials or []:
            if mat.pbrMetallicRoughness and mat.pbrMetallicRoughness.baseColorFactor:
                rgba = mat.pbrMetallicRoughness.baseColorFactor
                out.append((rgba[0], rgba[1], rgba[2]))
            else:
                out.append((0.5, 0.5, 0.5))
        return out
    except ImportError:
        pass
    try:
        import trimesh
        scene = trimesh.load(glb_path)
        out = []
        if hasattr(scene, "geometry"):
            for k, g in scene.geometry.items():
                col = (0.5, 0.5, 0.5)
                if hasattr(g, "visual") and hasattr(g.visual, "material"):
                    m = g.visual.material
                    if hasattr(m, "baseColorFactor") and m.baseColorFactor is not None:
                        bcf = m.baseColorFactor
                        col = (bcf[0] / 255.0 if bcf[0] > 1 else bcf[0],
                               bcf[1] / 255.0 if bcf[1] > 1 else bcf[1],
                               bcf[2] / 255.0 if bcf[2] > 1 else bcf[2])
                out.append(col)
        return out
    except Exception:
        return []


def build_kit_atlas(kit: str, *, tile_px: int = 32, grid: int = 8,
                    library: Path = LIBRARY,
                    out_dir: Path = KIT_OUT_DIR) -> dict:
    from PIL import Image, ImageDraw

    out_kit = out_dir / kit
    out_kit.mkdir(parents=True, exist_ok=True)

    # Walk the library for props in this kit.
    props_in_kit = []
    for d in sorted(library.iterdir()):
        if not d.is_dir():
            continue
        pj = d / "prop.json"
        if not pj.exists():
            continue
        data = json.loads(pj.read_text(encoding="utf-8"))
        if data.get("kit") != kit:
            continue
        glb = d / "model_lod0.glb"
        if not glb.exists():
            continue
        props_in_kit.append((d.name, data, glb))

    if not props_in_kit:
        return {"kit": kit, "ok": False, "err": f"no props with kit={kit!r}"}

    atlas_px = tile_px * grid
    atlas = Image.new("RGBA", (atlas_px, atlas_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)

    manifest = {
        "schema": "kit_atlas.v1",
        "kit": kit,
        "tile_px": tile_px,
        "grid": grid,
        "atlas_px": atlas_px,
        "props": {},
    }

    slot_idx = 0
    skipped = []
    for pid, data, glb in props_in_kit:
        colors = extract_glb_material_colors(glb)
        if not colors:
            skipped.append(pid)
            colors = [(0.5, 0.5, 0.5)]
        slot_entries = []
        for mat_idx, rgb in enumerate(colors):
            if slot_idx >= grid * grid:
                skipped.append(f"{pid}#{mat_idx} (atlas full)")
                break
            tx = (slot_idx % grid)
            ty = (slot_idx // grid)
            x0 = tx * tile_px
            y0 = ty * tile_px
            r = max(0, min(255, int(rgb[0] * 255)))
            g = max(0, min(255, int(rgb[1] * 255)))
            b = max(0, min(255, int(rgb[2] * 255)))
            draw.rectangle([x0, y0, x0 + tile_px - 1, y0 + tile_px - 1],
                           fill=(r, g, b, 255))
            slot_entries.append({
                "material_index": mat_idx,
                "tile_xy": [tx, ty],
                "uv_center": [(tx + 0.5) / grid, (ty + 0.5) / grid],
                "rgb": [round(rgb[0], 4), round(rgb[1], 4), round(rgb[2], 4)],
            })
            slot_idx += 1
        manifest["props"][pid] = {"slots": slot_entries}

        # Update prop.json
        pj = library / pid / "prop.json"
        pdata = json.loads(pj.read_text(encoding="utf-8"))
        pdata["material_lod"] = {
            "kit_atlas": f"world/props/kits/{kit}/kit_atlas_lod_far.png",
            "kit_atlas_manifest": f"world/props/kits/{kit}/kit_atlas_manifest.json",
            "slots": slot_entries,
        }
        pj.write_text(json.dumps(pdata, indent=2))

    atlas.save(out_kit / "kit_atlas_lod_far.png")
    (out_kit / "kit_atlas_manifest.json").write_text(json.dumps(manifest, indent=2))

    return {
        "kit": kit,
        "ok": True,
        "props": len(props_in_kit),
        "slots_used": slot_idx,
        "atlas_path": str(out_kit / "kit_atlas_lod_far.png"),
        "skipped": skipped,
    }


def main() -> int:
    _try_imports()
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True)
    ap.add_argument("--tile-px", type=int, default=32)
    ap.add_argument("--grid", type=int, default=8)
    ap.add_argument("--library", type=Path, default=LIBRARY)
    ap.add_argument("--out", type=Path, default=KIT_OUT_DIR)
    args = ap.parse_args()

    result = build_kit_atlas(args.kit,
                              tile_px=args.tile_px,
                              grid=args.grid,
                              library=args.library,
                              out_dir=args.out)
    if not result["ok"]:
        print(f"[material_lod] FAIL: {result.get('err')}", file=sys.stderr)
        return 1
    print(f"[material_lod] kit={result['kit']}  props={result['props']}  "
          f"slots={result['slots_used']}  atlas={result['atlas_path']}")
    if result.get("skipped"):
        print(f"  skipped: {result['skipped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
