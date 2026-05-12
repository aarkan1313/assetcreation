# W4 Tools & Workflows Index

> One-line-per-item index of every pipeline script, shader, runtime
> component, and scene. The doc says *what each thing is* + *when to
> reach for it*. For end-to-end run instructions, see
> `ORCHESTRATOR_GUIDE.md`.
>
> Keep this index current as files are added/renamed. Update protocol
> at the bottom.

## Top-level workflows

| I want to... | Run / see |
|---|---|
| Build the anchor world from a DEM | `ORCHESTRATOR_GUIDE.md` "TL;DR" |
| Build the scale_demo world | `pipeline/pick_dem_crop_scale.py` → `slice_to_tiles.py` → `write_material_tres_scale_v1.py` → Godot `--import` |
| Generate a single texture from a prompt | `D:/assets/pipelines/textures/aaa_texture.py` — see `pipelines/textures/PIPELINE.md` |
| Generate a biome kit (3 slots × 4 maps via klein-9B) | `pipeline/generate_biome_kits.py` (calls aaa_texture per slot, installs into W4 materials/) |
| Emit `.tres` materials for the 4 new biomes | `pipeline/write_material_tres_biomes.py` |
| Build the Axis 6 layer manifest (biomes → texture-array layers per tier) | `pipeline/build_biome_arrays.py` |
| Emit per-tile splat maps for Axis 6 (controls biome blending per tile) | `pipeline/build_tile_splats.py` |
| Emit the global terrain material that binds `terrain_world_v2.gdshader` | `pipeline/write_global_terrain_material.py` |
| Run all the Axis 6 pipeline tests | `cd "world 4" && python -m pytest tests/ -v` |
| Reimport Godot after changing files outside the editor | `"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import` |
| Headless capture a scene | `"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/<capture_scene>.tscn"` |
| Debug a visual artifact | `reference/PITFALLS.md` (match symptom → root cause → fix) |

## Pipeline scripts (`world 4/pipeline/`)

System Python 3.12. No per-lane venv — small dep set
(`numpy`, `Pillow`, `rasterio` for DEM scripts).

### Build pipeline

| Script | What it does | When to run |
|---|---|---|
| `pick_dem_crop.py` | Crops a 256m × 256m subregion from a USGS1m DEM tile, scores by relief, writes anchor heightmap.png + meta.json. | Anchor builds; rerun to change DEM crop. |
| `pick_dem_crop_scale.py` | Same as above but 1024m × 1024m for scale_demo. Has `ALLOW_RIDGED_OVERRIDE` for pinning the diagnostic banded crop (see PITFALLS #4). | scale_demo builds; rerun to change crop. |
| `slice_to_tiles.py` | Gaussian-smooths the world heightmap (sigma 1.0 px, PITFALLS #2) and slices into a 4×4 tile grid with per-tile meta.json + the world-level meta.json. | After `pick_dem_crop_scale.py`. |
| `build_anchor.py` | Orchestrator that runs the v1 anchor stages in order. Mostly legacy — anchor v2 doesn't need it. | Legacy. Prefer running stages directly. |
| `build_splat_and_macro.py` | v1 anchor splat + macro layer generator. **Legacy** (v2 shader does slope blending in-shader). | Don't run. Kept for reference. |

### Material emitters (write Godot `.tres` files)

| Script | Emits | Bound shader |
|---|---|---|
| `write_material_tres.py` | v1 anchor material.tres (splat+macro) | `terrain_anchor.gdshader` (legacy) |
| `write_material_tres_v2.py` | **v2 anchor material.tres** (3-slot slope-blend) | `terrain_anchor_v2.gdshader` |
| `write_material_tres_scale.py` | Old scale material.tres | (legacy) |
| `write_material_tres_scale_v1.py` | scale_demo material_scale_v1.tres (3-slot, unshaded with manual lighting; pre-Axis-6 single-biome path) | `terrain_scale_v1.gdshader` |
| `write_material_tres_views.py` | scale_demo per-view materials (iso, topdown) | `terrain_view_iso.gdshader`, `terrain_view_topdown.gdshader` |
| `write_material_tres_biomes.py` | 4 per-biome materials (alpine, desert, rocky, wetland) for the pre-Axis-6 biome path | `terrain_scale_v1.gdshader`, per-biome ambient tints |
| `write_global_terrain_material.py` | **scale_demo material_world_v2.tres** (single global material binding the Axis 6 shader + lighting defaults; texture arrays bound at runtime by ScaleWorld) | `terrain_world_v2.gdshader` |

The bold line is the currently-canonical emitter. The biome-per-tile
emitters (`write_material_tres_biomes.py`,
`write_material_tres_scale_v1.py`) are kept as fallback for the pre-
Axis-6 paths and remain wired through `ScaleWorld.biome_materials` /
`material_override_path`.

### Axis 6 — texture-array + splat pipeline

The Axis 6 (transitions) path replaces per-tile single-material
binding with one global terrain material + texture arrays + per-tile
splat maps. Pipeline order:

| Stage | Script | Output |
|---|---|---|
| 1. Catalog declares biomes / slots / tiers (hand-authored) | n/a | `worlds/scale_demo/biome_catalog.json` |
| 2. Pure-Python catalog loader/validator (used by all axis-6 pipeline scripts) | `pipeline/biome_catalog.py` | (module; no output file) |
| 3. Build the layer manifest (per-biome PBR maps → per-tier texture-array layers) | `pipeline/build_biome_arrays.py` | `worlds/scale_demo/arrays/layer_manifest.json` + `__upsampled` and `__rgb` sibling PNGs for any sub-tier-resolution or non-RGB source |
| 4. Build per-tile splat maps + per-slot (tier, layer) meta | `pipeline/build_tile_splats.py` | `worlds/scale_demo/tiles/tile_X_Z/splat.png` + `splat_meta.json` |
| 5. Emit the global terrain material (shader + lighting defaults) | `pipeline/write_global_terrain_material.py` | `worlds/scale_demo/material_world_v2.tres` |
| 6. Godot reimport + scale_demo run | (`--import` then run scale_demo.tscn) | ScaleWorld builds 8 Texture2DArrays from layer_manifest at scene init, sets per-tile uniforms |

Run the lot end-to-end:

```bash
# steps 3, 4, 5 (re-run any time the catalog or biome PNGs change)
python "world 4/pipeline/build_biome_arrays.py" --catalog ".../biome_catalog.json" --w4-root ".../the world 4" --out ".../arrays/layer_manifest.json"
python "world 4/pipeline/build_tile_splats.py"  --bundle ".../scale_demo" --manifest ".../arrays/layer_manifest.json" --mode hard --splat-size 64
python "world 4/pipeline/write_global_terrain_material.py" --w4-root ".../the world 4" --out "worlds/scale_demo/material_world_v2.tres"
# step 6
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "the world 4" --import
```

`build_tile_splats.py --mode hard` = every tile is its own biome with
no blending (used for the Stage 5a regression check). `--mode feather
--feather-width-m N` (Stage 5b) is where soft transitions enter the
splats.

### Tests (`world 4/tests/`)

| File | What it tests |
|---|---|
| `tests/test_biome_catalog.py` | Catalog schema validation: layer indexing, tier validation, missing-slot rejection, slot path lookup. |
| `tests/test_build_biome_arrays.py` | Manifest builder: per-tier layer ordering, oversize rejection, undersize auto-upsample, missing-map rejection, JSON roundtrip. |
| `tests/test_build_tile_splats.py` | Splat builder hard-mode: file shapes, channel-0 weight, per-slot tier/layer encoding, forest-spans-tiers, unknown-biome rejection. |
| `tests/conftest.py` | Inserts `pipeline/` into `sys.path` for test imports. |
| `pytest.ini` | Sets `testpaths = tests`. Run all tests via `python -m pytest tests/ -v` from the W4 dir. |

### Texture generation

| Script | What it does | When to run |
|---|---|---|
| `generate_biome_kits.py` | Batch driver: calls `aaa_texture.py` for each W4 biome slot with klein-9B fp8 + qwen_3_8b. Installs PBR maps into `materials/biome_<name>/<slot>/`. Supports `--only <slot_id>...` for partial reruns. | Generating / regenerating any biome ground/mid/rock texture. |
| `fix_texture_imports.py` | Patches `.import` settings on existing PNGs (compression, filter, mipmaps). | One-off when import settings drift. |

The full texture pipeline (`aaa_texture.py`, `flux_seamless.py`,
`variant_select.py`, `stablematerials_image2pbr.py`, `texture_qa.py`,
`palette_lock.py`, etc.) lives at `D:/assets/pipelines/textures/` and is
documented in `pipelines/textures/PIPELINE.md`. W4 only drives it via
`generate_biome_kits.py`.

## Shaders (`world 4/the world 4/shaders/`)

| Shader | render_mode | Used by | Status |
|---|---|---|---|
| `terrain_anchor.gdshader` | lit PBR | (none) | Legacy v1 — anchor switched to v2 |
| `terrain_anchor_rebuild.gdshader` | lit PBR | (none) | Debug-bisect leftover; can delete |
| `terrain_anchor_v2.gdshader` | lit PBR | anchor demo | **Canonical anchor shader.** Has all guardrails: `luma_floor`, `ao_floor`, NaN guards. Locked baseline. |
| `terrain_anchor_v2_minimal.gdshader` | lit PBR | (none) | 3-line bisect minimal — kept for future PBR-bug bisects |
| `terrain_scale_v1.gdshader` | **unshaded** + manual lighting | (pre-Axis-6 scale_demo walk + biome materials) | Pre-Axis-6 canonical. Same unshaded model as v2 but 3 fixed sampler2D slots per material → one material per tile. Kept as the fallback path through `ScaleWorld.biome_materials`. |
| `terrain_world_v2.gdshader` | **unshaded** + manual lighting | scale_demo walk view (Axis 6 path) | **Canonical scale-axis shader.** Same unshaded model as v1 but with `sampler2DArray` per tier × map (8 array uniforms) + per-tile splat texture + per-slot (tier, layer) `ivec4` indices. Lets a biome span tiers; lets one global material serve every tile. |
| `terrain_view_iso.gdshader` | unshaded | scale_demo iso view | Flatter lambertian + form-light term. Still single-material (no per-biome routing in iso/topdown yet). |
| `terrain_view_topdown.gdshader` | unshaded | scale_demo topdown view | Cartographic hillshade + sepia bias. Still single-material. |
| `water_anchor.gdshader` | lit | anchor water plane | Fresnel + depth fade |

## GDScripts (`world 4/the world 4/scripts/`)

| Script | What it does |
|---|---|
| `AnchorTerrain.gd` | Anchor: build one 257×257 ArrayMesh from heightmap.png, apply material, generate tangents. The anchor's whole runtime. |
| `AnchorWater.gd` | Sizes a water plane to the anchor's underwater region. Sets `cast_shadow = OFF`. |
| `AnchorCameraRig.gd` | 3-camera rig (walk / iso / topdown) + hotkey 1/2/3 switch + WASD pan on iso/topdown + scroll-wheel zoom on topdown. Calls `ScaleWorld.set_view_mode` on switch. |
| `ScaleWorld.gd` | scale_demo runtime: loads world meta + world_heightmap.png, spawns `TileTerrain` children per tile, handles radius paging (3×3 window), drives view-mode swaps, owns the cross-tile shared heightmap buffer. **Axis 6 additions:** when `world_v2_material_path` is set, reads `arrays/layer_manifest.json`, builds 8 `Texture2DArray`s at scene init (with forced `FORMAT_RGBA8` + `clear_mipmaps()` for uniform format across layers — see PITFALLS #5), and per-tile sets `splat` + `splat_ground/mid/rock_indices` + `tile_origin_m` + `tile_size_m` on a per-tile-duplicated global material. Legacy `material_override_path` / `biome_materials` paths remain as fallback. |
| `TileTerrain.gd` | Per-tile runtime: builds 257×257 mesh from this tile's heightmap.png, samples the shared world heightmap for cross-tile normals at borders (PITFALLS #4 mitigation), applies material. Async via `WorkerThreadPool.add_task`. **Axis 6 addition:** `shared_material: Material` export — when set by ScaleWorld it wins over `shared_material_path` (avoids re-loading the same .tres for every tile). |
| `AutoWalker.gd` | Optional debug helper: drives the camera on a fixed path for hitch profiling. Used by `autotest_scale_walk.tscn`. |
| `HeadlessCapture.gd` | Captures the current viewport to a PNG after N warmup frames. Used by all `capture_*.tscn` scenes. |
| `PerfHud.gd` | Top-right FPS / peak-ms / draw-calls overlay. |

## Scenes (`world 4/the world 4/scenes/`)

| Scene | Purpose |
|---|---|
| `anchor.tscn` | Anchor demo. Runnable (F6). Locked regression baseline. |
| `scale_demo.tscn` | scale_demo runnable scene (1024m world, 16 tiles, radius paging, 3 cameras). |
| `capture_anchor_walk.tscn` / `_iso.tscn` / `_topdown.tscn` | Anchor headless captures, one per view. |
| `capture_scale_walk.tscn` / `_iso.tscn` / `_topdown.tscn` | scale_demo headless captures, one per view. |
| `autotest_scale_walk.tscn` | AutoWalker-driven scale_demo run for hitch profiling. |
| `anchor.tscn.bak_20260511_165755` | Backup; safe to delete after a couple of clean sessions. |

## External tools / paths

| Tool | Path / how to invoke |
|---|---|
| Godot (non-mono) | `C:/Godot/Godot_v4.5-stable_win64.exe` |
| ComfyUI server | `D:/assets/animators/ComfyUI/venv/Scripts/python.exe D:/assets/animators/ComfyUI/main.py --listen 127.0.0.1 --port 8188` |
| FLUX2-klein 9B (canonical) | `flux-2-klein-9b-fp8.safetensors` + `qwen_3_8b_fp8mixed.safetensors` (under ComfyUI `models/diffusion_models/` and `models/text_encoders/`) |
| Texture pipeline (`aaa_texture.py` etc.) | `D:/assets/pipelines/textures/` |
| DEM cache | `D:/assets/dems/` |
| W3 (parts depot, not build target) | `D:/assets/world3/` |

## Update protocol

- One line per item. If a longer explanation is needed, the item gets
  its own doc and this index links to it.
- When adding a new pipeline script / shader / scene, append a row in
  the right table.
- When deleting / deprecating something, mark "legacy" rather than
  silently removing the row (cross-refs in build-notes may still
  point at it).
- If two scripts do the same thing, pick one as canonical and mark the
  other "legacy" with a one-line reason.
