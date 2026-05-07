"""Build a Godot 4.5 scatter scene from a biome world.

Reads:
  <world>/biome_labels.png           (categorical, world.json gives the order)
  <world>/height_16.png              (16-bit grayscale 0..1)
  <world>/vegetation_density.png     (0..1, biased toward green/wet)
  <world>/water_mask.png             (avoid placing in water)
  art_lab/biomes/biome_scatter_rules.json  (per-biome asset list + density)

Emits a self-contained scene file under the project at:
  <project>/biome_terrain_test/biome_scatter_<world_id>.tscn

Each scatter asset becomes a MultiMeshInstance3D with a placeholder primitive
(BoxMesh or CylinderMesh) until real GLB props arrive. The main biome_terrain
scene `[ext_resource]`'s this scatter scene as a child node, so re-running
scatter never touches the main scene.

Coordinate convention matches stage_biome_terrain.py:
  PlaneMesh size 512×512 (centered at origin, ±256 m in X/Z)
  Heightmap range [0..1] × terrain_height_m (64) for world Y

Usage:
  python stage_biome_scatter.py `
    --world D:/assets/world/worlds/qa_fjord_4biome `
    --project C:/Users/josep/test/new-game-project `
    --max-instances 1500
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

RULES_PATH = Path(r"D:\assets\art_lab\biomes\biome_scatter_rules.json")
PROP_LIBRARY_DIR = Path(r"D:\assets\world\props\library")
PROP_LIBRARY_RES_PATH = "res://world/props/library"


def resolve_prop_pool(prop_pool: list, prop_weights: list | None) -> tuple[list[str], list[float]]:
    """Filter a prop_pool to ids that exist on disk and normalize weights.

    Returns (ids, weights). If the pool yields no usable ids, returns ([], [])
    and the caller falls back to legacy placeholder behavior. Missing props are
    surfaced as a [warn] line — failures should be loud, not silent.
    """
    if not prop_pool:
        return [], []
    ids: list[str] = []
    raw_weights: list[float] = []
    for i, pid in enumerate(prop_pool):
        glb = PROP_LIBRARY_DIR / pid / "model_lod0.glb"
        if not glb.exists():
            print(f"  [warn] prop_pool ref '{pid}' missing model_lod0.glb at {glb} — dropping")
            continue
        ids.append(pid)
        if prop_weights and i < len(prop_weights):
            raw_weights.append(float(prop_weights[i]))
        else:
            raw_weights.append(1.0)
    if not ids:
        return [], []
    total = sum(raw_weights)
    if total <= 0:
        weights = [1.0 / len(ids)] * len(ids)
    else:
        weights = [w / total for w in raw_weights]
    return ids, weights


def slope_from_height(h: np.ndarray) -> np.ndarray:
    pad = np.pad(h, 1, mode="edge")
    dx = (pad[1:-1, 2:] - pad[1:-1, :-2]) * 0.5
    dy = (pad[2:, 1:-1] - pad[:-2, 1:-1]) * 0.5
    return np.clip(np.sqrt(dx * dx + dy * dy) * 64.0, 0.0, 1.0)


def blue_noise_pick(mask: np.ndarray, target_count: int, rng: np.random.Generator,
                    min_dist_px: float) -> list[tuple[int, int]]:
    """Cheap candidate-rejection blue noise: oversample then filter by min distance."""
    if target_count <= 0:
        return []
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return []
    # oversample 8x to leave headroom for rejection
    over = min(len(ys), max(target_count * 8, 64))
    pick = rng.choice(len(ys), size=over, replace=False)
    cand = list(zip(ys[pick].tolist(), xs[pick].tolist()))

    placed: list[tuple[int, int]] = []
    md2 = float(min_dist_px) ** 2
    for y, x in cand:
        if len(placed) >= target_count:
            break
        ok = True
        for py, px in placed:
            if (py - y) ** 2 + (px - x) ** 2 < md2:
                ok = False
                break
        if ok:
            placed.append((y, x))
    return placed


def build_transform_buffer(positions: np.ndarray, scales: np.ndarray, rotations: np.ndarray) -> np.ndarray:
    """Pack into a contiguous float32 buffer of shape (n, 12).

    Each Transform3D occupies 12 floats laid out as:
      basis row 0 (3 floats), basis row 1, basis row 2, origin (3 floats)
    Yaw rotation about world Y only (rotations[i] in radians).
    """
    n = len(positions)
    out = np.zeros((n, 12), dtype=np.float32)
    c = np.cos(rotations).astype(np.float32)
    s = np.sin(rotations).astype(np.float32)
    sx = scales[:, 0]; sy = scales[:, 1]; sz = scales[:, 2]
    # Basis rows (Yaw about Y):
    # row0 (xx,yx,zx) = (c*sx, 0,    s*sx) along world-X output? Need to be careful.
    # Godot's Transform3D basis stored in PackedFloat32Array is column-major when
    # MultiMesh.set_buffer interprets it: per-instance entry is 12 floats =
    #   basis.x.x, basis.y.x, basis.z.x,
    #   basis.x.y, basis.y.y, basis.z.y,
    #   basis.x.z, basis.y.z, basis.z.z,
    #   origin.x, origin.y, origin.z
    # i.e. transposed from inline Transform3D() string.
    # Yaw(theta) basis with per-axis scale (sx,sy,sz):
    #   X axis = ( c*sx, 0, -s*sx )
    #   Y axis = ( 0,    sy, 0    )
    #   Z axis = ( s*sz, 0,  c*sz )
    # Stored as (Xx, Yx, Zx, Xy, Yy, Zy, Xz, Yz, Zz):
    out[:, 0] = c * sx        # Xx
    out[:, 1] = 0.0            # Yx
    out[:, 2] = s * sz         # Zx
    out[:, 3] = 0.0            # Xy
    out[:, 4] = sy             # Yy
    out[:, 5] = 0.0            # Zy
    out[:, 6] = -s * sx        # Xz
    out[:, 7] = 0.0            # Yz
    out[:, 8] = c * sz         # Zz
    out[:, 9]  = positions[:, 0]
    out[:, 10] = positions[:, 1]
    out[:, 11] = positions[:, 2]
    return out


RUNTIME_FILL_SCRIPT = '''extends Node3D

# Loads per-MultiMeshInstance3D transforms from a binary sidecar at startup.
# Sidecar format: for each child MultiMeshInstance3D (in scene-tree order),
# 4 bytes uint32 instance_count + (instance_count * 12) float32 values.
#
# v3 prop_pool support: nodes whose name starts with "prop_" carry a metadata
# entry "prop_glb_path" that points at a real model_lod0.glb. At _ready we
# instance that PackedScene once, harvest the first MeshInstance3D's Mesh,
# assign it to the MultiMesh, then free the temporary instance. This keeps
# the .tscn shape identical to legacy placeholder scatter while pointing at
# real prop geometry.

const SIDECAR := "res://biome_terrain_test/biome_scatter_BWORLDB.bin"


func _harvest_mesh_from_packed(packed: PackedScene) -> Mesh:
\tif packed == null:
\t\treturn null
\tvar inst: Node = packed.instantiate()
\tvar found_mesh: Mesh = null
\tvar stack: Array = [inst]
\twhile not stack.is_empty():
\t\tvar n: Node = stack.pop_back()
\t\tif n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
\t\t\tfound_mesh = (n as MeshInstance3D).mesh
\t\t\tbreak
\t\tfor child in n.get_children():
\t\t\tstack.push_back(child)
\tinst.queue_free()
\treturn found_mesh


func _ready() -> void:
\tvar f: FileAccess = FileAccess.open(SIDECAR, FileAccess.READ)
\tif f == null:
\t\tpush_error("[scatter] could not open sidecar %s" % SIDECAR)
\t\treturn
\tvar children: Array = []
\tfor c in get_children():
\t\tif c is MultiMeshInstance3D:
\t\t\tchildren.append(c)
\tfor mmi in children:
\t\tvar count: int = int(f.get_32())
\t\tvar data: PackedFloat32Array = f.get_buffer(count * 12 * 4).to_float32_array()
\t\tvar mm: MultiMesh = (mmi as MultiMeshInstance3D).multimesh
\t\tif mm == null:
\t\t\tpush_error("[scatter] %s has no multimesh resource" % (mmi as Node).name)
\t\t\tcontinue
\t\t# v3: if the node points at a real prop GLB, swap the placeholder mesh.
\t\tvar prop_path: String = ""
\t\tif mmi.has_meta("prop_glb_path"):
\t\t\tprop_path = String(mmi.get_meta("prop_glb_path"))
\t\tif prop_path != "":
\t\t\tvar packed: PackedScene = load(prop_path) as PackedScene
\t\t\tvar real_mesh: Mesh = _harvest_mesh_from_packed(packed)
\t\t\tif real_mesh != null:
\t\t\t\tmm.mesh = real_mesh
\t\t\telse:
\t\t\t\tpush_warning("[scatter] could not harvest mesh from %s (keeping placeholder)" % prop_path)
\t\t# Reset to allow transform_format change, then re-init.
\t\tmm.instance_count = 0
\t\tmm.transform_format = MultiMesh.TRANSFORM_3D
\t\tmm.instance_count = count
\t\tfor i in count:
\t\t\tvar base: int = i * 12
\t\t\tvar t: Transform3D = Transform3D(
\t\t\t\tBasis(
\t\t\t\t\tVector3(data[base + 0], data[base + 3], data[base + 6]),
\t\t\t\t\tVector3(data[base + 1], data[base + 4], data[base + 7]),
\t\t\t\t\tVector3(data[base + 2], data[base + 5], data[base + 8])
\t\t\t\t),
\t\t\t\tVector3(data[base + 9], data[base + 10], data[base + 11])
\t\t\t)
\t\t\tmm.set_instance_transform(i, t)
\tprint("[scatter] populated %d MultiMeshInstance3D nodes" % children.size())
'''


def _emit_one_mmi(
    biome_id: str,
    asset: dict,
    prop_id: str | None,
    bucket_n: int,
    sub_id_for: dict,
    subresources: list[str],
    nodes: list[str],
    counts: dict[str, int],
    sub_id_state: list[int],
) -> None:
    """Append one (mesh, material, multimesh, node) to the scene buffers.

    Mesh/material is keyed by (placeholder_mesh, color) so identical placeholders
    share sub-resources. When prop_id is set, the resulting MultiMeshInstance3D
    carries `metadata/prop_glb_path = res://world/props/library/<id>/model_lod0.glb`
    that the runtime fill script swaps in for the placeholder mesh.
    """
    mesh_kind = asset["placeholder_mesh"]
    color = asset["color"]
    sig = (mesh_kind, tuple(color))
    if sig not in sub_id_for:
        sub_id_state[0] += 1
        sub_id = sub_id_state[0]
        mesh_sid = f"mesh_{sub_id}"
        mat_sid = f"mat_{sub_id}"
        metallic = float(asset.get("metallic", 0.0))
        roughness = float(asset.get("roughness", 0.85))
        emission_strength = float(asset.get("emission", 0.0))
        emission_color = asset.get("emission_color", color)
        extra = ""
        if emission_strength > 0:
            extra += (
                f'emission_enabled = true\n'
                f'emission = Color({emission_color[0]}, {emission_color[1]}, {emission_color[2]}, 1)\n'
                f'emission_energy_multiplier = {emission_strength}\n'
            )
        subresources.append(
            f'\n[sub_resource type="StandardMaterial3D" id="{mat_sid}"]\n'
            f'albedo_color = Color({color[0]}, {color[1]}, {color[2]}, 1)\n'
            f'metallic = {metallic}\n'
            f'roughness = {roughness}\n'
            + extra
        )
        if mesh_kind == "cone":
            subresources.append(
                f'\n[sub_resource type="CylinderMesh" id="{mesh_sid}"]\n'
                f'top_radius = 0.05\nbottom_radius = 0.5\nheight = 1.0\n'
                f'radial_segments = 6\nrings = 1\n'
                f'material = SubResource("{mat_sid}")\n'
            )
        elif mesh_kind == "cyl":
            subresources.append(
                f'\n[sub_resource type="CylinderMesh" id="{mesh_sid}"]\n'
                f'top_radius = 0.35\nbottom_radius = 0.5\nheight = 1.0\n'
                f'radial_segments = 8\nrings = 1\n'
                f'material = SubResource("{mat_sid}")\n'
            )
        elif mesh_kind == "sphere":
            subresources.append(
                f'\n[sub_resource type="SphereMesh" id="{mesh_sid}"]\n'
                f'radius = 0.5\nheight = 1.0\nradial_segments = 8\nrings = 4\n'
                f'material = SubResource("{mat_sid}")\n'
            )
        elif mesh_kind == "prism":
            subresources.append(
                f'\n[sub_resource type="PrismMesh" id="{mesh_sid}"]\n'
                f'size = Vector3(1, 1, 1)\nleft_to_right = 0.5\n'
                f'material = SubResource("{mat_sid}")\n'
            )
        else:  # box
            subresources.append(
                f'\n[sub_resource type="BoxMesh" id="{mesh_sid}"]\n'
                f'size = Vector3(1, 1, 1)\n'
                f'material = SubResource("{mat_sid}")\n'
            )
        sub_id_for[sig] = (mesh_sid, mat_sid)
    mesh_sid, _ = sub_id_for[sig]

    node_name = (
        f"{biome_id}_{asset['id']}_{prop_id}" if prop_id
        else f"{biome_id}_{asset['id']}"
    )
    mm_sid = f"mm_{node_name}"
    subresources.append(
        f'\n[sub_resource type="MultiMesh" id="{mm_sid}"]\n'
        f'mesh = SubResource("{mesh_sid}")\n'
    )

    # MultiMesh in .tres has nasty property-order races between
    # transform_format / instance_count / buffer. The runtime fill script
    # reconfigures the MultiMesh on _ready from a binary sidecar — and, when
    # `metadata/prop_glb_path` is set, swaps the placeholder mesh for the
    # real GLB's mesh in the same pass.
    node = (
        f'\n[node name="{node_name}" type="MultiMeshInstance3D" parent="."]\n'
        f'multimesh = SubResource("{mm_sid}")\n'
    )
    if prop_id:
        glb_res_path = f"{PROP_LIBRARY_RES_PATH}/{prop_id}/model_lod0.glb"
        node += f'metadata/prop_glb_path = "{glb_res_path}"\n'
    nodes.append(node)
    counts[node_name] = bucket_n
    suffix = f" -> prop:{prop_id}" if prop_id else ""
    print(f"  [{biome_id}] {asset['id']}: {bucket_n} instances{suffix}")


def stage(world_dir: Path, project_dir: Path, max_instances_per_asset: int,
          use_prop_pool: bool = True) -> Path:
    world = json.loads((world_dir / "world.json").read_text(encoding="utf-8"))
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    world_id = world["id"]
    size_px = world["size"]
    terrain_size_m = 512.0
    terrain_height_m = 64.0
    px_per_m = float(size_px) / terrain_size_m  # pixels per meter

    labels = np.asarray(Image.open(world_dir / "biome_labels.png"))
    h_arr = np.asarray(Image.open(world_dir / "height_16.png")).astype(np.float32)
    if h_arr.max() > 1.0:
        h_arr = h_arr / (65535.0 if h_arr.max() > 256.0 else 255.0)
    h_arr = np.clip(h_arr, 0.0, 1.0)
    veg = np.asarray(Image.open(world_dir / "vegetation_density.png")).astype(np.float32) / 255.0
    water = np.asarray(Image.open(world_dir / "water_mask.png")).astype(np.float32) / 255.0
    slope = slope_from_height(h_arr)

    rng = np.random.default_rng(42)

    label_to_biome = {i: bid for i, bid in enumerate(world["biomes"])}

    test_dir = project_dir / "biome_terrain_test"
    test_dir.mkdir(parents=True, exist_ok=True)

    nodes: list[str] = []
    subresources: list[str] = []
    counts: dict[str, int] = {}
    sub_id_state: list[int] = [0]
    sub_id_for: dict = {}  # mesh signature -> sub id
    transform_buffers: list[np.ndarray] = []  # one per MultiMeshInstance3D, in node-emit order

    for label_idx, biome_id in label_to_biome.items():
        rules_b = rules["biomes"].get(biome_id)
        if not rules_b:
            print(f"[warn] no scatter rules for biome '{biome_id}' — skipping")
            continue

        biome_mask = (labels == label_idx) & (water < 0.5)
        biome_area_m2 = float(biome_mask.sum()) / (px_per_m * px_per_m)

        # Cache per-biome picks-by-asset-id so 'share_positions_with' rules can
        # reuse the parent's blue-noise picks (paired tree trunk + canopy spheres).
        biome_picks_cache: dict[str, list[tuple[int, int]]] = {}

        for asset in rules_b["assets"]:
            share_with = asset.get("share_positions_with")
            if share_with and share_with in biome_picks_cache:
                # Reuse parent asset's picks; ignore density/slope/veg gates.
                picks = biome_picks_cache[share_with]
            else:
                slope_max = asset.get("slope_max", 1.0)
                veg_min = asset.get("vegetation_min", 0.0)
                target_density = asset.get("density_per_m2", 0.0)

                if target_density <= 0:
                    continue

                elig = biome_mask & (slope <= slope_max) & (veg >= veg_min)
                if not elig.any():
                    continue

                target = min(int(biome_area_m2 * target_density), max_instances_per_asset)
                if target <= 0:
                    continue

                min_dist_px = max(0.5, 0.5 / np.sqrt(max(target_density, 0.001)) * px_per_m)
                picks = blue_noise_pick(elig, target, rng, min_dist_px)
                if not picks:
                    continue
                biome_picks_cache[asset["id"]] = picks

            # v3 prop_pool resolution: if the asset declares a prop_pool that
            # resolves to ≥1 on-disk prop, partition this asset's picks by
            # sampled prop_id and emit one MultiMeshInstance3D per (asset, prop)
            # carrying a `prop_glb_path` meta key the runtime swaps in.
            # If the pool is empty/unresolvable, fall through to placeholder.
            pool_ids, pool_weights = resolve_prop_pool(
                asset.get("prop_pool", []) if use_prop_pool else [],
                asset.get("prop_weights"),
            )
            render_class_hint = asset.get("render_class_hint", "scatter_multimesh")
            # scene_prop pools are NOT scattered as MultiMesh today — they'd need
            # per-pick PackedScene Node3D children, which is a separate seam.
            # Surface a [seam] line so the gap is visible, then fall through to
            # placeholder so the rest of the scene still works.
            if pool_ids and render_class_hint == "scene_prop":
                print(
                    f"  [seam] {biome_id}/{asset['id']}: prop_pool present but "
                    f"render_class_hint=scene_prop — falling back to placeholder "
                    f"(per-pick PackedScene scatter not yet wired)"
                )
                pool_ids = []

            # Sample one prop per pick (or use a single 'placeholder' bucket).
            n_picks = len(picks)
            if pool_ids:
                pick_prop_idx = rng.choice(len(pool_ids), size=n_picks, p=pool_weights)
                # Partition picks by prop. Order: keep stable, prop_pool order.
                buckets: list[tuple[str | None, list[int]]] = []
                for prop_i, pid in enumerate(pool_ids):
                    idx = np.where(pick_prop_idx == prop_i)[0]
                    if len(idx) > 0:
                        buckets.append((pid, idx.tolist()))
            else:
                buckets = [(None, list(range(n_picks)))]

            ys_all = np.array([p[0] for p in picks], dtype=np.float32)
            xs_all = np.array([p[1] for p in picks], dtype=np.float32)

            sx_m, sy_m, sz_m = asset["size_m"]
            scale_min = asset.get("scale_min", 0.8)
            scale_max = asset.get("scale_max", 1.2)
            y_offset = float(asset.get("y_offset_m", 0.0))

            for prop_id, idx_list in buckets:
                ys = ys_all[idx_list]
                xs = xs_all[idx_list]
                world_x = (xs / size_px - 0.5) * terrain_size_m
                world_z = (ys / size_px - 0.5) * terrain_size_m
                world_y = h_arr[ys.astype(int), xs.astype(int)] * terrain_height_m

                bucket_n = len(idx_list)
                scale_factors = rng.uniform(scale_min, scale_max, size=bucket_n).astype(np.float32)
                scales = np.stack([scale_factors * sx_m, scale_factors * sy_m, scale_factors * sz_m], axis=1)
                # Spawn pivots are typically at center; lift each instance by half its Y size so the bottom sits on terrain.
                # y_offset_m allows e.g. a tree canopy to sit ON TOP of a trunk that's sitting on the ground.
                world_y = world_y + scales[:, 1] * 0.5 + y_offset

                rotations = rng.uniform(0.0, 2.0 * np.pi, size=bucket_n).astype(np.float32)

                positions = np.stack([world_x, world_y.astype(np.float32), world_z], axis=1)
                buf = build_transform_buffer(positions, scales, rotations)
                transform_buffers.append(buf)
                _emit_one_mmi(
                    biome_id=biome_id,
                    asset=asset,
                    prop_id=prop_id,
                    bucket_n=bucket_n,
                    sub_id_for=sub_id_for,
                    subresources=subresources,
                    nodes=nodes,
                    counts=counts,
                    sub_id_state=sub_id_state,
                )
            # legacy single-MMI path is now folded into _emit_one_mmi above

    # Write binary sidecar: for each MultiMeshInstance3D, uint32 count + count*12 float32
    bin_path = test_dir / f"biome_scatter_{world_id}.bin"
    with bin_path.open("wb") as f:
        for buf in transform_buffers:
            n = buf.shape[0]
            f.write(np.uint32(n).tobytes())
            f.write(buf.astype(np.float32, copy=False).tobytes(order="C"))

    # Write the runtime-fill script (specialised with this world's id)
    script_path = test_dir / f"biome_scatter_{world_id}.gd"
    script_path.write_text(
        RUNTIME_FILL_SCRIPT.replace("BWORLDB", world_id),
        encoding="utf-8",
    )

    # load_steps must include every ext_resource + sub_resource block.
    # We have 1 ext_resource (the fill script) + len(subresources) blocks
    # (each block is one [sub_resource ...] section). +1 for the file header itself.
    load_steps = 1 + len(subresources) + 1
    out_path = test_dir / f"biome_scatter_{world_id}.tscn"
    out_path.write_text(
        f'[gd_scene load_steps={load_steps} format=3]\n'
        f'\n[ext_resource type="Script" path="res://biome_terrain_test/biome_scatter_{world_id}.gd" id="fill"]\n'
        + "".join(subresources)
        + '\n[node name="BiomeScatter" type="Node3D"]\n'
        + 'script = ExtResource("fill")\n'
        + "".join(nodes),
        encoding="utf-8",
    )
    total = sum(counts.values())
    print(f"\nwrote {out_path}")
    print(f"  sidecar: {bin_path} ({bin_path.stat().st_size} bytes)")
    print(f"  script:  {script_path}")
    print(f"total instances: {total} across {len(counts)} asset types")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", type=Path, required=True)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--max-instances", type=int, default=1500,
                    help="cap per asset type to keep .tscn file size reasonable")
    ap.add_argument("--no-prop-pool", action="store_true",
                    help="Disable v3 prop_pool resolution; emit placeholder primitives only "
                         "(matches v1/v2 behavior). Use to A/B against the prop-pool path.")
    args = ap.parse_args()
    stage(args.world, args.project, args.max_instances,
          use_prop_pool=not args.no_prop_pool)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
