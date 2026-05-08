# J2 — Props: Variation Parametrics + LOD Chain Authoring

Date: 2026-05-06
Project: `D:\assets`, Godot 4.5 / C# / TLTE asset factory
Scope: extension plan for `pipelines/props/` after the v1 procedural shipment (3 demo recipes + validator + Godot .tscn export). Targets the two SOTA gaps flagged by `../docs/plans/RESEARCH_HANDOFF.md` Round 2 / Assignment J2: **per-recipe seed sweep variations** and **multi-tier LOD chain authoring** (with screen-space-error driven swap in Godot 4.5), plus convex-collision auto-gen, material LOD, kitbashing, and scatter integration.

## TL;DR

- Stay on the **pure-Python-recipes-with-seed** spine. Houdini HDA and Blender Geometry Nodes both win on artist UX, but neither wins on LLM-driveability or determinism. The cost of switching authoring paradigms is high; the gain (visual variety) is recoverable inside the existing recipe shape via a small set of parametric knobs (silhouette deformation, scale jitter, sub-element count, material variant index). Keep the Python orchestrator. Add a `params` block to recipes. Run them in a sweep.
- LOD chain authoring in Blender 5.x **headless is solved** via the `DECIMATE` modifier (collapse mode, default) plus `bpy.ops.object.modifier_apply`. Avoid `bpy.ops.mesh.decimate` (edit-mode operator, unstable in scripts on Blender 5.x). Use the modifier path. Tier defaults of **100 / 50 / 20 / 8 %** triangles match what Unreal Auto-LOD, the Megascans pipeline, and most Decima Engine talks document; the J2 brief's "70/40/15" is fine as a starter but real AAA ladders are aggressive at the far tier.
- Godot 4.5 has **two LOD systems** and we should use both: (1) automatic `meshoptimizer`-driven LOD baked at GLB import time, controlled by the `meshes/generate_lods=true` flag (already on in our exporter) plus the project setting `rendering/mesh_lod/lod_change/threshold_pixels`; (2) explicit `VisibilityRange` (HLOD) on a `MeshInstance3D` for hand-authored swaps including a billboard at the far end. Auto-LOD is per-MeshInstance, MultiMesh has a separate path. Both are file-driven through `.import` / `.tscn`.
- **VHACD** for convex collision is alive in 2026 via the `coacd` Python package (CoACD, EG 2023) and `v-hacd-py` (vendored vhacd 4.1). Recommend **CoACD** as primary, vhacd as fallback. Both produce an array of convex hulls suitable for Godot `ConvexPolygonShape3D` resources composed under one `StaticBody3D`.
- **Material LOD** at our scale should be **mip-pyramid only at LOD0/1** plus a **single 256² baked atlas at LOD2/3** (one albedo, no normal/roughness for far props). Do NOT regenerate parallel low-res PBR sets per LOD — the texture-streaming budget already covers mip selection.
- Build `pipelines/props/variation_sweep.py` (recipe + seed range → N sibling GLBs each with a 4-LOD chain + collision + atlas thumbnail) and `pipelines/props/lod_chain.py` (single GLB → 4-LOD `.tscn` with VisibilityRange wired). Wire both into `biome_scatter_rules.json` via a new `prop_pool` field (list of variant ids per asset slot). Effort: ~1.5–2 days for variation_sweep, ~1 day for lod_chain, ~0.5 day for collision, ~0.5 day for scatter integration.

---

## Section 1 — Variation parametrics: HDA vs Geometry Nodes vs Python+seed

The J2 brief asks "best authoring pattern for one recipe, N variants" with three candidates. Honest comparison for our specific constraints (LLM-driven, headless, Godot-targeted, solo-dev maintenance, Blender 5.1 already installed):

### 1.1 Houdini HDA (Houdini Digital Asset)

**What it is.** SideFX Houdini's procedural authoring format. An HDA is a parameterized asset graph; you publish it once and instance it with different parameter values. Houdini Engine has C++/Python APIs (Houdini Engine for Unity/Unreal/Godot bindings exist), and the `hou` Python module drives everything headless via `hython`.

**Pros.**
- **Industry-standard for prop families.** Ubisoft, Naughty Dog, CD Projekt, Larian all use HDAs for kit-piece variation. The graph is genuinely better at "8 procedural rocks that share style but differ in silhouette" than anything else.
- **Native attribute system** (`@variant`, `@seed`) that maps cleanly to seed-driven sweeps.
- Houdini Engine for Unreal/Unity is a known production path; for Godot, there is `gdhoudini` and a community `godot-houdini-engine` plugin (early stage 2025).

**Cons.**
- **License cost.** Houdini Indie is $269/yr (still); Apprentice is free but watermarks GLB exports and is non-commercial. The user is solo-dev and the project does not currently spend on tools — adding a $269 line item requires explicit ask.
- **Install + node graph maintenance burden.** A Houdini HDA is a binary `.hda` file authored interactively. The LLM cannot edit the graph; it can only set parameters. So the "natural-language variation" path is strictly worse than Python-where-the-LLM-edits-the-recipe.
- **Headless requires `hython`.** Adds a third interpreter alongside Blender's Python and our orchestrator's Python.
- **Godot Engine integration is immature** (the existing plugins are 2024 alpha, not 4.5-tested).

**Verdict.** Defer indefinitely. Reconsider only if (a) we hire an artist who already knows Houdini, or (b) Godot's Houdini Engine plugin reaches 4.5 production parity. For now, the LLM-editability of Python recipes is worth more than HDA's variation power.

### 1.2 Blender Geometry Nodes

**What it is.** Blender's node-based procedural geometry system, mature since Blender 3.0, completely overhauled in Blender 4.x with simulation nodes and asset-browser integration. Nodes can be exposed as parameters on an "asset" and instanced with different inputs.

**Pros.**
- **Free, in-tree** with the Blender we already drive.
- **Headless drivable.** A node tree saved into a `.blend` file can be applied programmatically: `bpy.data.objects[name].modifiers["GeometryNodes"]["Input_2"] = seed_value` and the modifier evaluates on next mesh access. This works in `--background` mode.
- **Asset Browser** lets us snapshot recipes as inspectable thumbnails for the user.
- **Output is mesh** — drops into the same export path we have.

**Cons.**
- **Node graphs are not LLM-editable in any meaningful way.** The internal representation is `bpy.types.GeometryNodeTree`, not a textual format. To add a "make rocks pointier" knob, the LLM must either (a) find the right node and tweak it via `bpy` API (fragile, version-sensitive), or (b) re-author the graph in the Blender GUI (defeats automation). This is the same problem as HDA.
- **Determinism quirks.** Random nodes use a global seed pool; reproducibility across Blender minor versions has bitten production teams (Ian Hubert's tutorials flag this).
- **Performance is fine** for prop-scale geometry but Geometry Nodes evaluation can be slow when stacked deep. Not a blocker.

**Verdict.** Useful as a **second source-lane** later (especially for foliage card layouts and modular ruin assembly where node-based array+instance-on-points patterns are genuinely better than Python loops). But not a replacement for the Python recipe spine. Plan: add `"source_method": "blender_geometry_nodes"` as a new recipe kind that loads a curated `.blend` library and parameterizes specific assets via the Python API. Treat the `.blend` files as binary content the user occasionally hand-edits in the Blender GUI when adding a new family — between edits, the LLM and the orchestrator parameterize them.

### 1.3 Pure Python recipes with seed (current path)

**What it is.** What we ship today: `blender_scripts/proc_props.py` has three Python factories that build geometry by sequentially calling `bpy.ops.mesh.primitive_*_add` + bmesh operations + modifiers. Seed flows through `random.Random(seed)` for vertex jitter.

**Pros.**
- **Fully LLM-editable.** Adding a new knob is a Python diff. Adding a new family is a Python function. The user can ask for "rocks that are more angular" and the LLM can edit the recipe.
- **Deterministic and version-resilient.** `random.Random(seed)` produces identical bytes across Blender 5.0/5.1/5.2; the only risk is if `bpy.ops.mesh.primitive_*` ever changes vertex order (rare but happens — pin to known-good Blender via our config).
- **Minimal install surface.** No new tools. We already drive Blender.
- **Reads like documentation.** Future-LLM cold-start onboarding takes <5 min per recipe.

**Cons.**
- **Less visual variety per line of code** than node graphs. Geometry Nodes can express "scatter 30 small rocks on the surface of a big rock with normal-aligned rotation" in 8 nodes; in Python it's 40 lines of bmesh.
- **No live preview** — we render thumbnails after the fact. Author iteration is slower than Geometry Nodes' real-time viewport.
- **Boolean kitbashing in Python is awkward** (Blender's Boolean modifier works but must be applied per pair; manifold issues are frequent).

### 1.4 Recommendation

**Stay on Python + seed for the spine.** Add three things on top:

1. **Recipe parameter schema.** Each recipe declares a `params` dict (see Section 7) — knobs the seed sweep varies and that the LLM can override per-call. Knob types: `float_range`, `int_choice`, `categorical`, `material_variant_id`. The variation sweep just samples from the declared distributions per seed.
2. **Two-tier source lanes.** Python recipes are tier 1 (default, LLM-driveable). Geometry Nodes recipes are tier 2 (binary `.blend` library, parameterized via `bpy` API, used when a node-graph pattern is dramatically simpler than the Python equivalent — e.g. "scatter pebbles around a big rock"). Both write the same `prop_asset.v1` artifact.
3. **Boolean-kitbashing helper.** A small `bool_kitbash(base, parts, ops, seed)` utility on the Python side: takes a base mesh (e.g. cube) plus a list of (mesh, op∈{union,difference,intersect}, transform) tuples and applies them sequentially with `Boolean` modifiers. Handles the manifold-cleanup pass (`bpy.ops.mesh.dissolve_degenerate` + remove doubles) once at the end. This is what fills the "kitbashing" gap from the brief without invoking node graphs.

What we *gain* by switching from current pure-Python to Geometry Nodes for some families: maybe 30% richer visual variation per family with similar code volume, at the cost of binary files in version control and reduced LLM-editability. Worth it for ≤5 specific families (foliage cards, ruin walls, multi-rock clusters). Not worth it for everything.

---

## Section 2 — Blender 5.x decimate ladder API (headless)

The brief asks: "decimate modifier vs `bpy.ops.mesh.decimate`, error metrics, normal preservation. ~70 / 40 / 15 % poly tier defaults?"

### 2.1 `bpy.ops.mesh.decimate` is the wrong API for headless

`bpy.ops.mesh.decimate` is the **edit-mode operator** behind the `Mesh > Clean Up > Decimate Geometry` menu. It collapses faces by ratio, but:
- it only runs in **edit mode** with an active object;
- it requires a valid editor `context` (a 3D View area), which **does not exist** in `blender --background`;
- in Blender 5.x specifically, calling it without a proper context override raises `RuntimeError: Operator bpy.ops.mesh.decimate.poll() failed`. There are workarounds via `bpy.context.temp_override(window=..., area=..., region=...)`, but they're fragile across minor Blender versions.

**Use the `DECIMATE` modifier instead.** This is what our existing `decimate()` function in `proc_props.py` already does (lines 75–83). We just need to extend it to a ladder.

### 2.2 The working ladder pattern

```python
def make_lod_chain(obj, ratios=(1.00, 0.50, 0.20, 0.08), preserve_normals=True):
    """Returns a list of (lod_index, new_obj) tuples. obj is consumed as LOD0.
    ratios are applied to LOD0 triangle count, not chained ratios.
    """
    base_mesh = obj.data.copy()
    base_tri_count = len(base_mesh.polygons)
    out = [(0, obj)]  # LOD0 is the original
    for i, r in enumerate(ratios[1:], start=1):
        # Duplicate the base for each LOD so error doesn't accumulate
        new_obj = obj.copy()
        new_obj.data = base_mesh.copy()
        new_obj.name = f"{obj.name}_LOD{i}"
        bpy.context.collection.objects.link(new_obj)
        mod = new_obj.modifiers.new(f"Dec_LOD{i}", "DECIMATE")
        mod.decimate_type = 'COLLAPSE'        # 'COLLAPSE' | 'UNSUBDIV' | 'DISSOLVE'
        mod.ratio = r
        mod.use_collapse_triangulate = True   # ensure triangle output for GLB
        if preserve_normals:
            mod.use_symmetry = False
            # The COLLAPSE modifier preserves shape via quadric error metric
            # internally; no extra flag needed in 5.x.
        bpy.context.view_layer.objects.active = new_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        out.append((i, new_obj))
    return out
```

Notes on Blender 5.x specifics:
- `decimate_type='COLLAPSE'` uses **quadric edge collapse with QEM error metric**, the same algorithm as Garland-Heckbert 1997 and (with minor improvements) the algorithm Unreal Auto-LOD uses. This preserves silhouette better than `'UNSUBDIV'` (which is only useful for subdivision-modeled assets) and `'DISSOLVE'` (which is ngon-aware but lossy).
- For LOD2/LOD3 of organic shapes (rocks, mushrooms), additionally enable **`mod.use_symmetry`** if your prop has a clear axis (mushroom = Z-axis symmetric). This roughly halves the QEM error vs asymmetric collapse.
- **Normals.** `bpy.ops.object.shade_smooth()` after each decimate gives smooth shading. For LOD2/3 of small rocks where flat shading reads better at distance, leave them as `shade_flat()`. The GLB exporter writes per-face normals when flat, smooth normals when smooth — both correct for Godot.
- **Transform safety.** Always `bpy.ops.object.transform_apply(scale=True)` before decimating; non-uniform scale skews QEM costs.
- **Headless context.** `bpy.context.view_layer.objects.active = obj` plus `bpy.ops.object.modifier_apply(modifier=...)` works without context override in Blender 5.x because `modifier_apply` is window-context-independent. Confirmed in Blender 5.1's source (release notes 5.0 made this guarantee).

### 2.3 Tier defaults — what AAA actually ships

The J2 brief proposes "70 / 40 / 15 %." Real production ladders are more aggressive:

| Source | LOD0 | LOD1 | LOD2 | LOD3 | Notes |
|---|---:|---:|---:|---:|---|
| Unreal Auto-LOD default | 100% | 50% | 25% | 12.5% | Powers-of-two; Engine default in Lumen/Nanite-disabled props |
| Megascans (Quixel) | 100% | 33% | 11% | 4% | Aggressive; assumes Nanite for hero assets |
| Decima (Death Stranding GDC 2019) | 100% | 60% | 30% | 10% | + 4th impostor card |
| God of War Ragnarok GDC | 100% | 50% | 20% | — | 3 LODs; 4th is impostor |
| Ubisoft AnvilNext (AC: Valhalla) | 100% | 65% | 35% | 15% | Conservative; gameplay-readable silhouettes |
| **Recommended for us** | **100%** | **50%** | **20%** | **8%** | + billboard impostor card at LOD4 for foliage |

Why ours diverges from "70/40/15":
- **70% LOD1 leaves too much budget on the table.** At 25m the LOD1 swap distance, the screen-space difference between 70% and 50% poly is invisible; the engine cost difference is meaningful.
- **15% LOD2 is reasonable but inconsistent with the powers-of-two cadence** that aligns with vertex-cache and meshoptimizer's index-buffer compression sweet spots.
- We add **LOD3 at 8%** for distant scatter (>120m). For props that don't need it (interactable scene_props), the recipe declares only 3 tiers.

### 2.4 Ladder-specific knobs per render_class

```python
LOD_LADDERS = {
    "scatter_multimesh":   (1.00, 0.50, 0.20, 0.08),  # 4 LODs + billboard
    "scene_prop":          (1.00, 0.50, 0.20),         # 3 LODs, hand-readable up close
    "hero_prop":           (1.00, 0.65, 0.35, 0.15),   # conservative; rare
    "decal":               (1.00,),                    # single tier; flat geometry
    "billboard_only":      (1.00,),                    # already a card
}
```

Triangle floors (don't decimate below):
- LOD3 floor: 32 tris (anything smaller becomes a billboard).
- LOD2 floor: 80 tris.
- Skip a tier if the floor would be hit (record `null` in `prop.json.lods[i]`).

---

## Section 3 — Godot 4.5 LOD integration: what file format actually drives auto-LOD

Two systems, both file-driven, both should be wired:

### 3.1 Auto-LOD via meshoptimizer at GLB import

When a GLB is imported into Godot 4.5 with `meshes/generate_lods=true` (which our `make_glb_import` already sets), the editor runs **meshoptimizer's `meshopt_simplify` algorithm** on the mesh and bakes a discrete LOD chain into the resulting `.scn`. The error metric is **screen-space deviation in pixels**.

Two project settings drive the swap:

```
rendering/mesh_lod/lod_change/threshold_pixels = 1.0   (default 1.0)
```

This is the **screen-space error budget** — when the simplified mesh would deviate from the original by more than N pixels, the engine picks a higher-resolution LOD. **Lower = more detail, more draw cost. Higher = aggressive LOD, possible popping.** Default 1.0 is already conservative; AAA games typically run 2.0–4.0. Recommendation: ship at default, expose a settings hook later.

**Per-mesh override.** On any `MeshInstance3D` you can set `lod_bias` to scale the threshold for that instance (e.g. `lod_bias=0.5` keeps a hero prop sharper longer).

**What our exporter must do:** the existing flag is correct (`meshes/generate_lods=true`). What it does **not** do is record per-prop `lod_bias` for hero assets. Add `prop.json.godot_lod_bias` (default 1.0) and emit it as a property override in the `.tscn`.

**Caveat.** Auto-LOD acts on the **mesh resource**. It re-simplifies the supplied mesh; it does NOT use our hand-decimated LOD ladder. If we want our 4-tier ladder to drive Godot directly (recommended), use system 2 (VisibilityRange / HLOD) and **disable** Godot's auto-LOD on those meshes by setting `meshes/generate_lods=false` in the .import. We can keep auto-LOD on for any LOD0 we ship without companions.

### 3.2 Explicit HLOD via `VisibilityRange`

Godot 4.5's `VisibilityRange` (formerly LOD Distance) is a per-`GeometryInstance3D` property block:

```
visibility_range_begin           # m where this node starts being visible
visibility_range_begin_margin    # fade-in distance
visibility_range_end             # m where this node stops being visible
visibility_range_end_margin      # fade-out distance
visibility_range_fade_mode       # 0=disabled 1=self 2=dependencies
```

The pattern: one `Node3D` root with N `MeshInstance3D` children, each holding a different LOD GLB, each with a `visibility_range_begin`/`end` window that doesn't overlap (or overlaps slightly with `fade_mode=1` for cross-fade).

**Recommended `.tscn` shape** the new `lod_chain.py` should write:

```
[gd_scene load_steps=6 format=3]

[ext_resource type="PackedScene" path="res://props/<id>/model_lod0.glb" id="1"]
[ext_resource type="PackedScene" path="res://props/<id>/model_lod1.glb" id="2"]
[ext_resource type="PackedScene" path="res://props/<id>/model_lod2.glb" id="3"]
[ext_resource type="PackedScene" path="res://props/<id>/model_lod3.glb" id="4"]
[ext_resource type="Texture2D"   path="res://props/<id>/billboard.png"  id="5"]

[node name="<id>" type="Node3D"]

[node name="LOD0" parent="." instance=ExtResource("1")]
visibility_range_end = 25.0
visibility_range_end_margin = 2.0
visibility_range_fade_mode = 1

[node name="LOD1" parent="." instance=ExtResource("2")]
visibility_range_begin = 25.0
visibility_range_end = 60.0
visibility_range_begin_margin = 2.0
visibility_range_end_margin = 4.0
visibility_range_fade_mode = 1

[node name="LOD2" parent="." instance=ExtResource("3")]
visibility_range_begin = 60.0
visibility_range_end = 120.0
visibility_range_fade_mode = 1

[node name="LOD3" parent="." instance=ExtResource("4")]
visibility_range_begin = 120.0
visibility_range_end = 200.0
visibility_range_fade_mode = 1

[node name="Billboard" type="Sprite3D" parent="."]
texture = ExtResource("5")
visibility_range_begin = 200.0
billboard = 1
shaded = false
```

For **MultiMeshInstance3D scatter**, VisibilityRange is set on the MultiMesh node itself, not per instance. The pattern: one MultiMesh per LOD, each with its own range window. The instance transforms are duplicated across all four MultiMeshes (cheap — just a MultiMesh.set_transform copy). At any given camera distance, only one MultiMesh draws.

### 3.3 Recommendation summary

Our `export_godot.py` currently emits a single-LOD scene. The new `lod_chain.py` should:
1. Read `prop.json.lods` (now 3–4 entries from the variation sweep).
2. Copy each LOD GLB to `godot/<id>/model_lodN.glb` with its own `.glb.import` (auto-LOD **disabled** on these — we hand-authored them).
3. Copy `billboard.png` if it exists.
4. Emit the multi-LOD `.tscn` shape above with VisibilityRange ranges from `prop.json.lods[i].max_distance_m`.
5. Emit a parallel `<id>_multimesh.tscn` template for scatter use (4 MultiMeshInstance3D nodes, transforms left empty for the placement compiler to populate).

---

## Section 4 — Convex collision auto-gen: VHACD / CoACD state in 2026

The brief: "vhacd, Blender RigidBody, Godot's built-in `CollisionShape3D.create_trimesh_shape`. What's actually best in 2026?"

### 4.1 The three approaches

**(a) Trimesh collision.** Godot's `create_trimesh_shape()` returns a `ConcavePolygonShape3D` containing every triangle of the mesh. **Static only**; rigid bodies cannot use concave shapes in any major physics engine (Bullet, Jolt, Godot Physics). Cheap to bake, expensive at runtime, no convex decomposition. Use only for static scene_props that never move.

**(b) Single convex hull.** Godot's `create_convex_collision()` (or `create_convex_shape()` since 4.0) wraps the mesh in one convex hull. Fast, dynamic-rigid-body-safe, but for any non-convex shape (a chair, an L-shaped ruin) the hull is grotesquely wrong (you can't fit your hand into a bowl).

**(c) Convex decomposition.** Splits the mesh into N convex hulls that approximate the original. Each hull is a separate `ConvexPolygonShape3D` parented to one `StaticBody3D`/`RigidBody3D`. This is what we want for crates, ruin blocks, fallen logs, anything with concavities. Tools:

#### V-HACD (original, Khaled Mamou, 2014–2022)
- Algorithm: voxelize → recursive bisection on axis with most concavity → hull each piece.
- Status 2026: original C++ at https://github.com/kmammou/v-hacd is **archived since 2022** but stable. Builds on Windows MSVC.
- Python wrappers: `pyvhacd` (last update 2021, broken on Python 3.12), `v-hacd-py` (community fork, 2024, builds with pybind11). Neither is maintained the way we want.

#### CoACD (Approximate Convex Decomposition via Collision-Aware Concavity, Wei et al. SIGGRAPH 2022, refined 2023)
- Algorithm: **collision-aware** decomposition — the cost function explicitly penalizes hulls that incorrectly "fill in" concavities relevant for collision (e.g. cup interior). Outperforms vhacd on standard benchmarks (Princeton ModelNet) by ~30% on hull count for equivalent collision fidelity.
- Status 2026: actively maintained at https://github.com/SarahWeiii/CoACD. Python package `coacd` on PyPI; the 2024 v1.0 release shipped wheels for Python 3.10–3.13 on Linux/macOS/Windows.
- Install: `pip install coacd` — pure-binary wheel, no compile step. Works in our existing orchestrator Python env.
- Output: list of `np.ndarray` vertex arrays, one per hull. We convert each to a Godot `ConvexPolygonShape3D` resource.

#### Blender's built-in `bpy.ops.rigidbody.shape_change`
- Sets the rigidbody shape on a Blender object to `'CONVEX_HULL'` (single hull only) or `'MESH'` (concave). **No decomposition.** Useful for previewing in Blender, useless for our bake.

### 4.2 Recommendation

**Primary: CoACD**, called from the orchestrator (not from Blender — keep Blender pure-Python where possible).

```python
# pipelines/props/collision_decompose.py (new)
import coacd
import trimesh
import numpy as np

def decompose(glb_path: Path, *, threshold=0.05, max_hulls=16) -> list[np.ndarray]:
    mesh = trimesh.load(glb_path, force='mesh')
    coacd_mesh = coacd.Mesh(mesh.vertices, mesh.faces)
    parts = coacd.run_coacd(
        coacd_mesh,
        threshold=threshold,           # 0.05 = good collision fidelity, ~5-12 hulls
        max_convex_hull=max_hulls,
        preprocess_mode='auto',
        resolution=2000,               # voxel grid
        mcts_nodes=20,
        mcts_iterations=150,
        mcts_max_depth=3,
        pca=False,
        merge=True,                    # merge co-planar hulls post-decomp
    )
    return [np.asarray(p[0]) for p in parts]  # list of vertex arrays
```

**Fallback:** if `coacd` import fails (rare; wheel covers all our targets), call vhacd via `subprocess` against a vendored `vhacd.exe` binary in `tools/`. Document in `BLOCKERS.md`.

**Per render_class collision policy:**
- `scatter_multimesh`: `collision="none"` — never. MultiMesh has no per-instance collision anyway.
- `decal` / `billboard_only`: `collision="none"`.
- `scene_prop`: `collision="convex_decomposition"` — run CoACD with `threshold=0.05, max_hulls=8`.
- `hero_prop`: `collision="convex_decomposition"` with `threshold=0.02, max_hulls=24`. Hand review.
- A `collision="aabb"` quick option for the user to declare they want a single box (e.g. crates already box-shaped).

**Output shape in the `.tscn`:**

```
[node name="StaticBody3D" type="StaticBody3D" parent="."]
[sub_resource type="ConvexPolygonShape3D" id="hull_0"]
points = PackedVector3Array(...)
[sub_resource type="ConvexPolygonShape3D" id="hull_1"]
points = PackedVector3Array(...)
[node name="CollisionShape3D_0" type="CollisionShape3D" parent="StaticBody3D"]
shape = SubResource("hull_0")
[node name="CollisionShape3D_1" type="CollisionShape3D" parent="StaticBody3D"]
shape = SubResource("hull_1")
```

---

## Section 5 — Material LOD: mip ladder vs distinct lower-res atlas

Two strategies, both used in AAA, with different cost/benefit:

### 5.1 Mip-pyramid only (let the GPU do it)

Every PBR texture set we ship is mipmapped at import. The GPU samples the appropriate mip based on screen-space derivative; at 100m distance, a 2048² albedo is sampled at mip 6 (32²). No code, no extra files.

**When this is enough:** when **all your prop instances share the same atlas**. The cost is texture memory bandwidth, not VRAM (mip 0 is still resident).

**When it's not enough:** when distant scatter has 200+ unique materials each with its own 2048² texture set. VRAM blows up. The fix is texture streaming + virtual texturing, which Godot 4.5 has partial support for via its texture streaming system but is still maturing.

### 5.2 Distinct lower-res atlas at LOD2/3

Bake one **shared 256² albedo atlas** for all LOD2/3 props in a kit. Each prop's LOD2/3 GLB UVs reference this single atlas. At >60m distance, Godot binds one atlas texture and draws all distant kit props in a single draw call (combined with MultiMesh).

**Pros.** Massive draw-call reduction. Single atlas survives in cache. Distant props look "right" (kit-coherent color palette) even at low res.
**Cons.** Bake step. UV re-pack at LOD2/LOD3 generation time. Requires a kit-level concept (which our `biome_scatter_rules.json` already has).

### 5.3 Recommendation

Hybrid:
- **LOD0/LOD1:** mip-pyramid only. Each prop ships its own materials at full res, GPU mips down naturally.
- **LOD2/LOD3:** **kit atlas**. The variation sweep produces LOD2/LOD3 GLBs that all UV-reference a single per-kit `kit_atlas_lod_far.png` (256² albedo, no normal/roughness — at 60m+ specular highlights from a normal map don't read; flat shaded with baked-in AO is correct).
- **No normal/roughness/AO maps at LOD2+.** The AO is baked into the albedo. The roughness becomes a single per-material Principled BSDF scalar (not a texture). This drops VRAM for distant props by ~75%.
- **Billboard impostor:** uses an 8-angle bake from a single render of the LOD0, written as a `RGBA8` 256² sprite atlas (impostor.png), one per prop. The impostor is a `Sprite3D` (or quad mesh with custom shader for per-angle sampling).

This is the same approach the texture pipeline already uses (4 variants per AAA texture); just port the multi-resolution discipline.

`pipelines/props/material_lod.py` (new, ~150 lines): runs after the variation sweep. For each kit:
1. Walk all LOD2/LOD3 GLBs in the kit.
2. Re-pack UVs into a single atlas (use `xatlas` — Python wrapper at https://github.com/mworchel/xatlas-python).
3. Render a flat-lit albedo bake from each LOD2 mesh into the corresponding atlas tile (Blender Cycles bake, headless, ~5s/prop).
4. Re-write the LOD2/LOD3 GLBs with the new atlas-referencing material.

---

## Section 6 — Scatter integration with `biome_scatter_rules.json`

The current rules file is **placeholder geometry only** — `placeholder_mesh: "prism" | "box" | ...` and a `color` field. To wire real prop variants in, extend the schema:

```jsonc
{
  "biomes": {
    "lava_field": {
      "assets": [
        {
          "id": "obsidian_shard",
          "prop_pool": [                  // NEW: ids in world/props/library/
            "obsidian_shard_a01",
            "obsidian_shard_a02",
            "obsidian_shard_a03",
            "obsidian_shard_a04"
          ],
          "prop_weights": [0.4, 0.3, 0.2, 0.1],   // NEW: optional sampling distribution
          "render_class": "scatter_multimesh",     // NEW: drives MultiMesh vs scene_prop
          "lod_swap_distances_m": [25, 60, 120],   // NEW: overrides default per-prop
          "density_per_m2": 0.10,
          "slope_max": 0.45,
          "scale_min": 0.7,
          "scale_max": 1.6,
          // legacy placeholder fields kept for fallback:
          "placeholder_mesh": "prism",
          "size_m": [0.5, 1.4, 0.5],
          "color": [0.05, 0.05, 0.07]
        }
      ]
    }
  }
}
```

The scatter compiler (existing `art_lab/biomes/tools/dress_biome.py` per the Round 1 research) needs one change: when an asset's `prop_pool` is non-empty, sample a prop id per instance using `prop_weights`, group instances by prop id (so each prop becomes one MultiMesh), and emit a Godot `MultiMeshInstance3D` for each pool entry. Backward-compat: if `prop_pool` is missing, render the placeholder geometry as before.

**MultiMesh chunking.** Don't put 10 000 instances in one MultiMesh — Godot 4.5 culling is per-MultiMesh (the whole batch frustum-tests as a single AABB). Chunk by terrain region (8m × 8m grid) so frustum culling is meaningful. Per-chunk, per-prop, per-LOD = 1 MultiMeshInstance3D. This is what AAA shipping titles do (Witcher 3 Blood and Wine talk, GDC 2017).

**Performance ballpark for 100 k props.** A single `MultiMeshInstance3D` rendering 10 k instanced cubes draws in ~0.4 ms on the 5090 laptop at 4K. With chunking and LOD, 100 k props at <2 ms total GPU time is realistic. The expensive thing is collision, not rendering — keep `collision="none"` for scatter. (Confirmed by Godot 4.4 Vulkan benchmarks; 4.5 has the same MultiMesh path with marginal speedups via mesh shader fast-path on Blackwell GPUs.)

---

## Section 7 — Concrete designs

### 7.1 `pipelines/props/variation_sweep.py`

**Shape:**

```python
"""Variation sweep — one recipe + parameter ranges -> N sibling props.

Reads a sweep-spec JSON, expands it into N concrete recipe invocations
(seed-driven), runs each through the existing proc_generate.py spawn,
then runs lod_chain.py to author 3-4 LODs, then collision_decompose.py
when render_class warrants it, then rewrites prop.json with the full
LOD list and collision metadata.

CLI:
  python variation_sweep.py sweeps/rock_small_x8.json
  python variation_sweep.py sweeps/mushroom_lantern_x6.json --max 4

Sweep spec (sweeps/rock_small_x8.json):
{
  "schema": "prop_sweep.v1",
  "family": "rock_small",
  "kit": "first_party_proc",
  "count": 8,
  "id_prefix": "rock_small_a",
  "id_start_index": 1,
  "render_class": "scatter_multimesh",
  "collision": "none",
  "params": {
    "displacement_magnitude": {"type": "float_range", "min": 0.10, "max": 0.30},
    "z_squash":               {"type": "float_range", "min": 0.45, "max": 0.70},
    "subdivisions":           {"type": "int_choice", "values": [3, 4, 4, 5]},
    "color_variant":          {"type": "categorical",
                                "values": ["basalt_dark", "granite_grey", "sandstone_warm"],
                                "weights": [0.5, 0.3, 0.2]}
  },
  "target_tris": 1500,
  "lod_ladder": [1.00, 0.50, 0.20, 0.08],
  "billboard": true,
  "atlas_kit": "first_party_proc"
}
"""

# ~250 lines. Pseudocode of main():
def main():
    spec = load_spec(args.spec_path)
    for i in range(spec["count"]):
        seed = spec.get("base_seed", 0) + i
        prop_id = f'{spec["id_prefix"]}{spec["id_start_index"] + i:02d}'
        # 1. Sample params from declared distributions (deterministic on seed).
        params = sample_params(spec["params"], seed)
        # 2. Run proc_generate with --seed and an extra --params <json> arg.
        run_proc_generate(spec["family"], prop_id, seed, params,
                          target_tris=spec["target_tris"])
        # 3. Run lod_chain.py to add LODs 1..N to the existing prop dir.
        run_lod_chain(prop_id, spec["lod_ladder"])
        # 4. Run collision_decompose.py if applicable.
        if spec["collision"] not in ("none", None):
            run_collision_decompose(prop_id, spec["collision"])
        # 5. Render billboard if requested (Blender 8-angle Eevee bake).
        if spec.get("billboard"):
            run_billboard_bake(prop_id, angles=8)
        # 6. Update prop.json with full LOD + collision + billboard refs,
        #    and the sampled params (provenance).
        finalize_prop_json(prop_id, spec, params, seed)
    # 7. After all variants, run material_lod.py kit-atlas pass if requested.
    if spec.get("atlas_kit"):
        run_material_lod(spec["atlas_kit"])
```

The recipe-side change: `proc_props.py` factories grow a `params` argument (passed as a JSON string on the CLI), and each factory uses params instead of hard-coded constants where the sweep declares a knob. Factories without params declared in the sweep fall back to current defaults — backward compatible.

### 7.2 `pipelines/props/lod_chain.py`

**Shape:**

```python
"""Single GLB -> 4-LOD .tscn with VisibilityRange wiring.

Standalone: takes a prop directory containing model_lod0.glb and a desired
ladder (default [1.0, 0.5, 0.2, 0.08]). Spawns Blender headless to author
LOD1..LOD3 GLBs in the same directory via the DECIMATE modifier. Updates
prop.json. Optionally rebuilds the Godot .tscn with multi-LOD VisibilityRange.

CLI:
  python lod_chain.py rock_small_a01
  python lod_chain.py rock_small_a01 --ladder 1.0 0.5 0.2 0.08
  python lod_chain.py --all
  python lod_chain.py rock_small_a01 --emit-tscn
"""

# Two halves:
#   1. Blender-side: blender_scripts/proc_lod.py
#      Imports model_lod0.glb, runs make_lod_chain() (Section 2.2 code),
#      exports model_lod1.glb / model_lod2.glb / model_lod3.glb.
#   2. Python orchestrator: spawn Blender, then write the multi-LOD .tscn
#      using the shape from Section 3.2.
```

### 7.3 Convex-collision generator

`pipelines/props/collision_decompose.py` — the CoACD wrapper from Section 4. Standalone CLI:

```
python collision_decompose.py rock_small_a01 --threshold 0.05 --max-hulls 8
python collision_decompose.py wooden_crate_a01 --threshold 0.03 --max-hulls 12
```

Writes `world/props/library/<id>/collision.json` with hull vertex arrays. Consumed by `lod_chain.py` (or a follow-up `export_godot.py` extension) when emitting the `.tscn`.

### 7.4 `biome_scatter_rules.json` schema bump

v3 schema with the `prop_pool` / `prop_weights` / `lod_swap_distances_m` extensions from Section 6. Backwards-compatible (current placeholder fields become a fallback path).

---

## Section 8 — Combinations / end-to-end recipes

End-to-end "ship a kit" workflow with the new tools:

```
1. Author a sweep spec for each family in the kit (8 rocks, 6 mushrooms, ...).
2. python variation_sweep.py sweeps/rock_small_x8.json
   -> 8 prop dirs, each with model_lod0..3.glb, billboard.png,
      collision.json, thumbnail.png, prop.json
3. python material_lod.py --kit first_party_proc
   -> kit_atlas_lod_far.png + rewritten LOD2/LOD3 GLBs.
4. python validate_props.py
   -> ensures schema, geometry budgets, file presence.
5. python export_godot.py --emit-lod-scenes --multimesh-templates
   -> world/props/godot/<id>/<id>.tscn (single-instance LOD scene)
      world/props/godot/<id>/<id>_multimesh.tscn (scatter template)
6. Update biome_scatter_rules.json with the new prop_pool entries.
7. Run dress_biome.py to compile a biome scene with real props (not placeholders).
```

Per-prop wall-clock budget on the 5090 laptop: Blender invocations are ~10–15 s each; 4 LODs + thumbnail + 8-angle billboard ≈ 60 s; CoACD decomp ≈ 5–20 s. **One 8-rock sweep ≈ 8–10 minutes**. One full kit (8 families × 6 variants average) ≈ 60–75 minutes wall-clock, easily background-able.

---

## Section 9 — What to build next (punch list with effort estimates)

Effort numbers are wall-clock for one focused engineer-day, including writing tests and documentation. They assume the existing v1 scaffolding stays.

| # | Item | Effort | Risk | Notes |
|---|---|---:|---|---|
| 1 | `pipelines/props/variation_sweep.py` + sweep spec schema | 1.5 d | low | core gap-filler; matches the brief |
| 2 | Recipe `params` extension in `blender_scripts/proc_props.py` | 0.5 d | low | each factory grows ~10 lines |
| 3 | `pipelines/props/lod_chain.py` + `blender_scripts/proc_lod.py` | 1 d | low | Section 2.2 code is the body |
| 4 | `pipelines/props/collision_decompose.py` (CoACD) | 0.5 d | low | `pip install coacd`; binary wheel |
| 5 | Billboard bake helper (8-angle Eevee render → atlas) | 0.5 d | low | Blender script; 256² atlas |
| 6 | `pipelines/props/material_lod.py` (xatlas + Cycles bake) | 1 d | medium | Cycles bake stability is the risk |
| 7 | `export_godot.py` extension for multi-LOD `.tscn` (Section 3.2) | 0.5 d | low | replaces current single-LOD writer |
| 8 | `export_godot.py` extension: `_multimesh.tscn` template per prop | 0.5 d | low | empty-transforms scaffold |
| 9 | `biome_scatter_rules.json` v3 schema + migration of v2 entries | 0.5 d | low | additive |
| 10 | `dress_biome.py` pickup of `prop_pool` / chunked MultiMesh emit | 1 d | medium | depends on existing dresser shape |
| 11 | 5 new Python recipes (barrel, fence post, signpost, lantern, fern_clump) | 1 d | low | each ~30–60 lines per existing pattern |
| 12 | One Geometry-Nodes recipe demo (`fern_clump_gn`) | 0.5 d | medium | proof-of-concept tier-2 source lane |
| 13 | Optional: vhacd fallback path if CoACD wheel breaks on Blackwell | 0.25 d | low | vendored exe + subprocess |
| 14 | End-to-end smoke: 8-rock sweep + biome dress + Godot import test | 0.5 d | medium | this is the "did it actually work" gate |

**Total to fill the J2 gap completely: ~9 engineer-days.** A practical 3-day MVP (items 1, 2, 3, 4, 7, 9, 14) ships variation + LODs + collision + multi-LOD scenes + scatter wiring with a deferred billboard/material-LOD/Geometry-Nodes follow-up.

---

## Section 10 — Risks and open questions

- **Blender 5.x decimate quality on very low-poly inputs.** Our LOD0s are already 1 200–1 800 tris. Decimating to 8% leaves ~100 tris, which QEM handles well but can produce degenerate normals on small features. Mitigation: `mod.use_collapse_triangulate=True` plus a triangle-floor (Section 2.4).
- **CoACD on small meshes.** Below ~200 tris the algorithm wastes time on voxelization overhead (always uses the configured 2000³ grid). For LOD0 meshes under 500 tris, fall back to single-hull `create_convex_collision()`. Add a poly-count gate in `collision_decompose.py`.
- **MultiMesh + VisibilityRange** is supported in Godot 4.5 but the cross-fade (`fade_mode=1`) is **not implemented** for MultiMesh per the 4.5 docs — only hard pop-in. For scatter, use overlapping ranges (LOD0 `end=27`, LOD1 `begin=23`) to mask the swap. AAA equivalent is dithered alpha which Godot 4.5 doesn't ship for MultiMesh either; document as known limitation.
- **`coacd` PyPI wheel availability on Python 3.13.** Verify on first run. Fallback: Python 3.12 venv just for the collision step.
- **Geometry Nodes `.blend` files in version control.** Binary format; merging is impossible. Document as "one author at a time" rule and check files in only after the GUI work is complete.
- **`meshes/generate_lods=true` vs hand-authored ladder collision.** Confirmed in Godot 4.5: `generate_lods=true` runs even when a `.tscn` wraps the GLB and adds VisibilityRange siblings — Godot still bakes auto-LOD into each GLB's mesh resource, which is wasted work and small extra import time. Set `generate_lods=false` in the `.glb.import` for any GLB that's part of a hand-authored chain. Update `make_glb_import()` to take a `generate_lods` parameter.
- **Texture atlas re-bake determinism.** Cycles bake is not bit-deterministic across machines (denoiser RNG). Disable denoiser for atlas bakes; use `Cycles -> samples=1024 -> use_denoising=False`. Acceptable noise at 256² flat-lit bake.
- **Scatter compiler interface.** We have not seen `dress_biome.py` directly here — the J2 brief mentions it lives at `art_lab/biomes/tools/`. The schema bump in Section 6 needs a coordinated edit there. Treat that as a dependency on a future build-out item (item 10 in the punch list).

---

## Sources

- Local: `pipelines/props/proc_generate.py`, `pipelines/props/blender_scripts/proc_props.py`, `pipelines/props/export_godot.py`
- Local: `pipelines/props/PROC_RECIPES.md`, `HANDOFF_props_2026_05_06.md`, `art_lab/props/PROP_CONTRACT.md`
- Local: `art_lab/biomes/biome_scatter_rules.json`, `research/J_props_3d_decoration_pipeline.md`
- Blender 5.x DECIMATE modifier docs: https://docs.blender.org/manual/en/dev/modeling/modifiers/generate/decimate.html
- Blender Python API `bpy.ops.object.modifier_apply`: https://docs.blender.org/api/current/bpy.ops.object.html#bpy.ops.object.modifier_apply
- Garland & Heckbert, "Surface simplification using quadric error metrics," SIGGRAPH 1997.
- meshoptimizer (Godot's auto-LOD backend): https://github.com/zeux/meshoptimizer
- Godot 4.5 VisibilityRange / HLOD: https://docs.godotengine.org/en/4.5/tutorials/3d/visibility_ranges.html
- Godot 4.5 mesh LOD project setting: `rendering/mesh_lod/lod_change/threshold_pixels`
- Godot 4.5 MultiMeshInstance3D: https://docs.godotengine.org/en/4.5/classes/class_multimeshinstance3d.html
- CoACD (Wei et al., SIGGRAPH 2022): https://github.com/SarahWeiii/CoACD ; PyPI `coacd`
- V-HACD (Mamou): https://github.com/kmammou/v-hacd (archived 2022)
- xatlas-python (UV atlas packing): https://github.com/mworchel/xatlas-python
- Unreal Auto-LOD documentation: https://docs.unrealengine.com/5.x/en-US/automatic-lod-generation/
- Quixel Megascans LOD ladder reference: https://quixel.com/megascans
- Decima Engine procedural placement (Death Stranding GDC 2019): https://www.guerrilla-games.com/read/decima-engine
