# world3 Workflow

The full top-to-bottom sequence we've used to get from "raw OpenTopography
DEM tile" to "Tetons mountain rendered with hex-tile + macro-variation
shader in iso/topdown/walk modes." This is the *as-built* workflow
captured 2026-05-07 — not aspirational, this is what we actually run.

If anything in here goes wrong, this is the place to come check the
expected outputs at each step. Roadmap, planning, and decision context
live in their own docs (`ROADMAP.md`, `PLAN.md`, `DECISIONS.md`).

---

## Top-level shape

```
OpenTopography DEM (.tif)
        │
        ▼   pipeline/build_world.py
heightmap/heightmap.png + meta.json
        │
        ▼   Godot 4.5
runtime mesh + collision + 3 view scenes
        │
        ▼   shader stack
hex-tile + macro variation
        │
        ▼   headless capture
PNG screenshots
```

Texture pipeline is parallel; it produces PBR sets that the shader
consumes:

```
ComfyUI (FLUX 2 klein) ─┐
                         │
                         ▼   pipelines/textures/aaa_texture.py
                    PBR set (5-6 maps, 512×512, grade-A tileable)
```

---

## Stage 1 — Pull a DEM tile

Cached DEMs already live at `D:/assets/dems/` (ignored by git, ~9 GB).
Filename convention `<DATASET>_<W>_<S>_<E>_<N>.tif`. The Tetons tile
we've been using:

```
D:/assets/dems/COP30_-110.8500_+43.6500_-110.6500_+43.8500.tif
```

That's 0.2° square (~16 km × 16 km), elevation 1959–4059 m, COP30
30-meter posting.

If you need a fresh tile, the OpenTopography fetch lives in
`pipelines/terrain/import_dem.py` (v1 code — still works, populates this
cache).

OpenTopography-specific acquisition, point-cloud processing, color/orthophoto
exports, canopy mosaics, and the sample viewer workflow are documented in:

- `world3/docs/OPENTOPO_GUIDE.md`
- `world3/docs/OPENTOPO_DATA_TYPES.md`
- `world3/docs/OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md`
- `world3/docs/OPENTOPO_MASTER_STACKS_AUDIT.md`
- `world3/opentopo/STATUS.md`

Those docs are the source of truth for the newer OpenTopo campaign under
`world3/opentopo/`. Do not add a new OpenTopo pipeline step without updating
those files.

## Stage 2 — Build a heightmap

```powershell
$env:PYTHONIOENCODING = "utf-8"
python D:/assets/world3/pipeline/build_world.py `
  "D:/assets/dems/COP30_-110.8500_+43.6500_-110.6500_+43.8500.tif" `
  "D:/assets/world3/heightmap" `
  --size 1024 `
  --material rock_dark `
  --center -110.803 43.741 --extent-km 4
```

What it does (`pipeline/build_world.py`):
1. Opens the GeoTIFF with rasterio
2. Optionally crops with `--bbox left bottom right top` or
   `--center lon lat --extent-km N` (the latter recommended for game-scale)
3. Builds a source-valid mask, fills no-data for render-safe geometry, and
   writes repair masks
4. Resamples to a square `--size` × `--size` PNG using LANCZOS in
   float32, then quantizes to 16-bit grayscale
5. Computes world XZ size in meters from DEM bounds (handles geographic
   and projected CRS; for projected, uses raw bounds)
6. Writes:
   - `heightmap.png` — 16-bit grayscale, square
   - `meta.json` — elevation min/max/range, world_size_m, source bounds,
     CRS, target material name

Expected output:
```
OK heightmap.png (1024x1024 u16) elev 2498..4059m world 4000m material=rock_dark
```

For runtime/export-oriented walk scenes, also build the generated-image caches:

```powershell
python D:/assets/world3/pipeline/build_runtime_image_cache.py
```

This writes:

```text
world3/runtime_cache/heightmap_rf32.{json,bin}
world3/runtime_cache/alpine_splat_rgba8.{json,bin}
```

`RuntimeImageCache.gd` reads these through `FileAccess` and creates `Image` /
`ImageTexture` objects at runtime. The primary `walk.tscn` path uses these
caches for height and splat inputs; legacy review utilities may still load PNGs
directly until touched.

## Stage 3 — Generate texture sets (parallel pipeline)

Prereq: ComfyUI running on `127.0.0.1:8188`.

```powershell
& "D:\assets\animators\ComfyUI\venv\Scripts\python.exe" `
  "D:\assets\animators\ComfyUI\main.py" --listen 127.0.0.1 --port 8188
```

For each texture:
```powershell
$env:PYTHONIOENCODING = "utf-8"
cd D:/assets
python pipelines/textures/aaa_texture.py `
  --prompt "rich brown dirt with small pebbles and fine debris, top-down photo, even lighting, photoreal" `
  --id wgv3_dirt `
  --category Ground `
  --quality default
```

This runs the full 7-stage texture pipeline (variant generation → delight
→ PBR estimation via StableMaterials → seam repair → QA → Blender
preview → quality gate). See `pipelines/textures/PIPELINE.md` for the
detailed mechanics, presets, failure modes, and how to debug.

The world3 shipping textures (post Phase A polish, 2026-05-07):

| ID                       | Current prompt (latest cookbook)                                                                            | Notes                  |
|--------------------------|-------------------------------------------------------------------------------------------------------------|------------------------|
| wgv3_dirt                | "rich brown dirt with small pebbles and fine debris..."                                                     | grade A                |
| wgv3_grass               | "lush green grass with small clovers and dirt patches..."                                                   | grade B                |
| wgv3_forest_floor        | "ground-level photograph of autumn leaf litter, damp dark soil visible underneath, no plants growing..."   | A.3 rewrite, grade A   |
| wgv3_rock_light          | "weathered tan limestone rock surface with cracks and lichen..."                                            | grade B (seed=100, vars=6) |
| wgv3_rock_dark           | "dark grey volcanic rock surface, weathered, sharp edges and small cracks..."                               | grade A                |
| wgv3_snow                | "fresh white snow with small dimples..."                                                                    | A.3 rewrite, grade A. Old "compacted ridges" cue removed (was producing lace pattern). |
| wgv3_tundra_ice          | "uneven compacted snow with sparse small ice crystals..."                                                   | A.6 rewrite, grade A. Old "wind ridges" removed. |
| wgv3_desert_canyon_rock  | "weathered tan canyon sandstone..."                                                                         | A.6 rewrite, grade A. Old "horizontal striations" removed. |

The Phase A polish iteration (2026-05-07) also added pipeline options
beyond the default `aaa_texture.py` invocation — richness advisory
gate, CHORD/hybrid PBR backends, variant_blend rescue tool, reference-
anchor mode. Canonical commands per use case live in
[`pipelines/textures/RECIPES.md`](../../pipelines/textures/RECIPES.md).

Output of each texture lives at `world/textures/library/<id>/`. Stage
4 pulls from there.

For M8/M1-M7 remediation work, inventory the generated texture lane before
promoting or rerendering:

```powershell
python world3/pipeline/build_comfy_material_candidate_catalog.py
```

This writes `world3/materials/comfy_texture_workflow_inventory.json` and
`world3/docs/COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md`. Use
`world3/jobs/comfy_texture_regen_candidates.json` as the first ComfyUI
regeneration queue for noisy organic blockers. These generated materials are
peer inputs to the source-stack workflow, but they still need seam QA, 2x2
review, and Godot terrain-context close/mid/far review before promotion.

When a regenerated material passes `aaa_texture.py` QA, stage it into the
quarantined sidecar catalog instead of editing the canonical material catalog:

```powershell
python world3/pipeline/stage_comfy_candidate_material.py `
  --library-id m8_grassland_grass_calm_v3 `
  --source-material-id grassland_grass `
  --color-family pale-dry-grassland-straw
```

This writes PBR maps under `world3/textures/wgv3_comfy_candidates/<id>/` and
updates `world3/materials/catalog_comfy_candidates.json`. Review tools opt into
that sidecar with `--extra-catalog`; canonical promotion stays blocked until
terrain-context and M4/M7 rerender trials pass.

M8 organic-material rule: strict `aaa_texture.py` QA is necessary but not
sufficient. Before sidecar staging, visually veto rectangular panels, bright
patch islands, repeated dark/colored landmarks, individual plant objects, and
pale washout. `M8_GRASS_REGEN_ATTEMPTS_REVIEW_2026_05_08.md` is the first
recorded failure case for this rule.

Use the advisory visual-veto helper before sidecar staging organic candidates:

```powershell
python world3/pipeline/audit_comfy_visual_veto.py `
  --library-id m8_grass_calm_v1 `
  --out-json world3/docs/M8_GRASS_VISUAL_VETO_AUDIT.json `
  --out-md world3/docs/M8_GRASS_VISUAL_VETO_AUDIT.md
```

`needs_visual_review` is not a pass. It means the helper did not catch an
obvious hard veto and the tile still needs human/vision review.

Source-stack runtime review has its own validity contract. The builder should
keep source macro color anchored to source-valid pixels, then let the shader
fall back to procedural/tileable terrain outside that mask:

```powershell
python world3/pipeline/build_source_stack_runtime_review.py `
  --detail-material grassland_grass `
  --id gloss_grassland_current_source_stack
```

`build_source_stack_runtime_review.py` discovers `texture_coverage_mask.png`,
`source_valid_mask.png`, or inverted `render_fill_mask.png`, writes
`source_macro_valid_mask.png`, edge-bleeds source macro color, and emits a
material using `source_macro_valid_mask`. The policy and rerender evidence live
in `SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`.

## Stage 4 — Stage textures into world3

Each texture set gets its own subfolder under `world3/textures/wgv3/`
with a uniform layout:

```
world3/textures/wgv3/<name>/
  albedo.png  normal.png  roughness.png  metallic.png  height.png  ao.png
  material.tres                  # StandardMaterial3D (baseline triplanar)
  material_hex.tres              # ShaderMaterial (hex-tile + macro)
  _tile_2x2.png                  # tiled-2×2 albedo for visual review
  _blender_plane.png             # Blender CYCLES PBR render on a tilted plane
  _blender_sphere.png            # ditto on a sphere
```

To stage from `world/textures/library/<id>/`:
```powershell
# Per-texture (currently a manual copy; see world3/textures/wgv3/README.md
# for a one-shot PowerShell loop that does all 6).
$id = "wgv3_dirt"
$src = "D:/assets/world/textures/library/$id"
$dst = "D:/assets/world3/textures/wgv3/dirt"
foreach ($map in @("albedo","normal","roughness","metallic","height","ao")) {
  Copy-Item "$src/${id}_${map}.png" "$dst/${map}.png"
}
Copy-Item "$src/qa/tile_2x2.png" "$dst/_tile_2x2.png"
Copy-Item "$src/qa/blender_plane.png" "$dst/_blender_plane.png"
Copy-Item "$src/qa/blender_sphere.png" "$dst/_blender_sphere.png"
```

Materials are written by hand or via the small templates in
`world3/textures/wgv3/<name>/material.tres` and `material_hex.tres`.
Both follow the same shape; only the hex one references the custom
shader.

## Stage 5 — The shader stack

Lives at `world3/shaders/terrain_hex.gdshader`. Two AAA tricks layered
on top of standard triplanar PBR. Both are world-space (use vertex
position, not UVs) so they work seamlessly across triangles.

### Layer 1 — Triplanar
Standard. Sample the texture three times (XZ, XY, YZ projections),
blend by `pow(abs(world_normal), blend_sharpness)`. Eliminates UV
stretching on cliffs.

### Layer 2 — Hex-tile sampling (kills tile period)
At each pixel, find the three nearest hex-grid centers. At each
center, sample the texture with a small random rotation + offset
derived from the cell ID. Blend by barycentric weights. Variance-
preserving for albedo (Heitz-Neyret 2018 trick).

Net effect: no two adjacent samples have the same rotation/offset, so
the visible tile period vanishes. Costs 3× texture samples per channel
— well within terrain budget.

Tunable: `hex_strength` 0..1. 0 = plain triplanar, 1 = full hex-tile.

### Layer 3 — Macro variation noise (kills uniform color)
A 2-octave value-noise sample at world position, scaled by
`1/macro_scale` (m per period). The result modulates albedo brightness
and (separately) channel-shifts r/g/b for a tiny hue wobble.

Tunable:
- `macro_scale` — meters per noise period. **80** is calibrated; smaller
  gives visible blotches, bigger gives gentle gradients.
- `macro_value_strength` — brightness modulation. **0.15** is calibrated;
  0.35 was too aggressive (visible quilt patches).
- `macro_hue_strength` — channel hue drift. **0.03**.

### Material binding
Each texture set has a `material_hex.tres` (ShaderMaterial) that loads
the shader and binds the 4 PBR maps + tunable params. The same shader
serves all 6 textures; only the textures and tuning differ. When we
add iter 4 (macro+detail) and iter 5 (slope+height blend), they go in
this same shader file — incremental.

Current streamed walk scenes use the newer unified prototype shader:

- `world3/shaders/terrain_splat_unified.gdshader`
- `world3/textures/wgv3/terrain_splat_alpine.tres`
- `world3/textures/m4_splat/alpine_height_slope_weights_rgba.png`

That shader supports five semantic terrain slots, RGBA splat weights with a
fifth-slot remainder, OpenTopo macro/detail compatibility, an opt-in M6
transition-strip sampler, and the M7 generated transition-mask path.

Runtime boundary placement lives in `ChunkLoader.gd`:

- `enable_transition_boundaries = true`
- `transition_rules_path = res://jobs/biome_transition_rules.json`
- `transition_rule_id = <rule id>`
- generated mask sampled through `UV2` by `use_transition_mask`

The manual `use_transition_strip` uniforms remain for shader review. Production
runtime placement should use the rule/mask path.

## Stage 6 — The Godot project

Layout:
```
world3/
  project.godot                  # Godot 4.5 project root
  pipeline/build_world.py        # Stage 2
  pipeline/build_runtime_image_cache.py
  heightmap/                     # Stage 2 output
    heightmap.png
    meta.json
  runtime_cache/                 # M6 export-safe generated image caches
  textures/wgv3/                 # Stage 4 staged textures + materials
    dirt/  grass/  ...
  shaders/
    terrain_hex.gdshader         # Stage 5 shader
    terrain_splat_unified.gdshader
  scripts/
    Terrain.gd                   # builds mesh + collision at runtime
    ChunkLoader.gd               # streams visible/collision terrain chunks
    RuntimeImageCache.gd         # reads generated image caches
    IsoCam.gd                    # auto-frames the AABB in ortho
    TopDownCam.gd                # auto-frames from straight above
    Walker.gd                    # CharacterBody3D, F=fly toggle
    FlyCam.gd                    # debug fly cam
    HeadlessCapture.gd           # one-shot screenshot wrapper
    HeadlessTextureGrid.gd       # texture viewer multi-shot
    TextureViewer.gd             # 2×3 grid of ground planes
  scenes/
    iso.tscn  topdown.tscn  walk.tscn          # the 3 game-mode scenes
    capture_iso.tscn  capture_topdown.tscn
    capture_walk.tscn                           # headless wrappers
    texture_viewer.tscn                         # baseline triplanar grid
    texture_viewer_hex.tscn                     # hex+macro grid
    capture_texture_grid.tscn
    capture_texture_grid_hex.tscn               # capture wrappers
```

`Terrain.gd` is the original single-mesh path:
1. Reads `meta.json` for world size + elevation range
2. Loads the heightmap through `RuntimeImageCache.gd` when a cache path is set
3. Builds a subdivided plane `ArrayMesh` at runtime (default 256×256,
   ~131k tris) with vertex Y from heightmap, normals from finite
   differences, world-space UVs
4. If a `collision_target` `StaticBody3D` is set, attaches a
   `HeightMapShape3D` matching the mesh. The body is uniformly scaled
   so each cell spans `world_size / subdivisions` meters.

The 3 view scenes share `Terrain.gd` + a hex-shader material; differ
only in camera setup, sun angle, fog, ambient.

`walk.tscn` is now the streamed prototype path:

1. `ChunkLoader.gd` tiles the source heightmap into 256 m chunks at 8 m mesh
   spacing.
2. Visible terrain uses `terrain_splat_alpine.tres` and runtime splat weights.
3. Height and splat inputs come from `world3/runtime_cache/`.
4. Collision is built per loaded chunk when `build_collision_chunks = true`.
5. `M5WalkStreamRunner.gd` measures chunk, collision, update, and frame timing
   budgets for repeatable smoke tests.

## Stage 7 — Run, view, capture

Godot binary on this machine: `C:/Godot/Godot_v4.5-stable_win64.exe`.

### Reimport (after any new asset / shader edit)
```powershell
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" --headless --import
```

If you need PowerShell to *wait* for Godot to finish (the GUI binary
sometimes returns control before the child process exits):
```powershell
$args = @("--path", "D:/assets/world3", "--headless", "--import")
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -WindowStyle Hidden -Wait -PassThru
"EXIT=$($p.ExitCode)"
```

### Open in editor
```powershell
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3"
```
Main scene is `iso.tscn`. Scenes available from FileSystem dock.

### Capture scenes
Each capture writes a PNG to `D:/tmp/world3_screens/`. Outputs are named
`iso.png`, `topdown.png`, `walk.png`.

Capture scenes wrap the real scene + `scripts/HeadlessCapture.gd`:
- `res://scenes/capture_iso.tscn`
- `res://scenes/capture_topdown.tscn`
- `res://scenes/capture_walk.tscn`
- `res://scenes/capture_opentopo_samples.tscn` (sample-switching viewer
  for converted OpenTopo heightmaps; smoke-test after script or
  sample-layout changes)

Run capture scenes through normal Godot with the explicit `--scene` option.
This is the current validated Windows path for real viewport screenshots.

```powershell
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" --scene "res://scenes/capture_iso.tscn"
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" --scene "res://scenes/capture_topdown.tscn"
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" --scene "res://scenes/capture_walk.tscn"
```

Waited version (when you need PowerShell to block on the capture):
```powershell
$args = @("--path", "D:/assets/world3", "--single-window", "--disable-crash-handler", "--scene", "res://scenes/capture_iso.tscn")
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -Wait -PassThru
"EXIT=$($p.ExitCode)"
```

If a capture appears to do nothing, check for an existing Godot editor
or hung Godot process before rerunning.

Do not add `-WindowStyle Hidden` for viewport review captures on this machine;
hidden launches have triggered Godot access violations before scene code ran.

For OpenTopo review screenshots, use the same explicit `--scene` pattern with
`res://toporeview/capture_phase*.tscn`. Do not use the older waited
`--headless --scene ... --quit-after ...` path as scene validation; that path
can fail locally with a Windows access violation even when the real capture
scene works.

For M10 seam review captures, use the dedicated wrapper scenes:

```text
res://scenes/review/capture_source_stack_seam_integration_topdown.tscn
res://scenes/review/capture_source_stack_seam_integration_iso.tscn
res://scenes/review/capture_source_stack_seam_integration_3d.tscn
res://scenes/review/capture_source_stack_seam_nonoverlap_topdown.tscn
res://scenes/review/capture_source_stack_seam_nonoverlap_iso.tscn
res://scenes/review/capture_source_stack_seam_nonoverlap_3d.tscn
res://scenes/review/capture_source_stack_real_procedural_topdown.tscn
res://scenes/review/capture_source_stack_real_procedural_iso.tscn
res://scenes/review/capture_source_stack_real_procedural_close.tscn
res://scenes/review/capture_source_stack_real_procedural_medium.tscn
```

Open the live non-overlap review scene with:

```powershell
$args = @("--path", "D:/assets/world3", "--single-window", "--disable-crash-handler", "--scene", "res://scenes/review/source_stack_seam_nonoverlap_tour.tscn")
Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args
```

Open the live real-to-procedural review scene with:

```powershell
$args = @("--path", "D:/assets/world3", "--single-window", "--disable-crash-handler", "--scene", "res://scenes/review/source_stack_real_procedural_tour.tscn")
Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args
```

`toporeview/TopoReviewCapture.gd` is the deterministic comparison helper for
OpenTopo close-up screenshots. It sets the same camera pose across multiple
review scenes before saving the viewport.

For OpenTopo albedo repair, use `pipeline/build_opentopo_render_albedo.py`.
It is source-first: it preserves real orthophoto color and only extends nearby
real pixels into explicit color gaps. It does not procedurally repaint terrain.

For turning OpenTopo top-down imagery into reusable ground materials, use the
separate tileable texture workflow:

```text
D:/assets/world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md
```

That workflow deliberately separates source crops, tileable-real derivatives,
and stylized/fantasy derivatives. Real-place maps should be chunked; reusable
ground textures can be tiled, repaired, downscaled, or stylized with provenance.

First Guadalupe Cypress pilot command:

```powershell
python D:/assets/world3/pipeline/build_opentopo_tileable_texture.py `
  --stack-dir D:/assets/world3/toporeview/phase2_fusion_max `
  --output-dir D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress `
  --crop-sizes-m 32,64 `
  --output-size 1024 `
  --macro-output-size 4096
```

Review scene:

```text
res://toporeview/tileable_texture_review.tscn
res://toporeview/tileable_hex_column_16x16.tscn
```

The review scene deliberately shows both plain repeat and `hex anti-tile`. Plain
repeat exposes whether a crop is truly seamless; hex anti-tiling is the current
practical path for hiding square repetition from real orthophoto crops.
The focused `tileable_hex_column_16x16.tscn` scene isolates the third column at
`16x` repeat for interactive review. It looks substantially better than plain
repeat, but faint tile-to-tile lines remain because it still reuses one crop.
The follow-up production step is now implemented as a soft composite prototype:
several unlike real crops per material class are independently repaired, color
normalized, and blended with periodic soft masks into one seamless PBR product.

Current soft-composite review assets:

```text
res://toporeview/tileable_variant_atlas_review.tscn
res://toporeview/tileable_soft_composite_gallery.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_soft_composite_gallery.png
D:/assets/world3/docs/captures/opentopo/opentopo_soft_composite_2x2_material_sheet.png
```

The six current Guadalupe Cypress classes are `bare_soil`, `bright_rock`,
`dry_wash`, `rocky_slope`, `scrub_dense`, and `scrub_sparse`. Use these as
source-real meso material candidates; keep the full map as macro color/reference
and add separate close detail where real-world motifs repeat too visibly.

Current finish pass:

```powershell
python D:/assets/world3/pipeline/finish_opentopo_soft_materials.py
```

It writes `finished_material/` siblings with balanced albedo, neutral
source-derived detail maps, `material_hex_detail_finished.tres`, and
`finish_manifest.json`. Review the endpoint in:

```text
res://toporeview/tileable_finished_material_review.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_finished_material_review.png
D:/assets/world3/docs/captures/opentopo/godot_tileable_finished_material_close.png
```

### Texture grid captures (testing the shader at scale)
The viewer scenes lay 6 ground planes (200×200 m) in a 2×3 grid, then
take far_overhead, mid_oblique (per plane), and close_walk shots:

```powershell
# Baseline triplanar
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_texture_grid.tscn"
# Hex+macro stack
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_texture_grid_hex.tscn"
```

Outputs go to `D:/tmp/world3_screens/textures/` and `textures_hex/`.

### Walker controls
| Input  | Action                       |
|--------|------------------------------|
| WASD   | move                         |
| Space  | jump (walk) / up (fly)       |
| Ctrl   | down (fly)                   |
| Shift  | run / fast-fly multiplier    |
| F      | toggle fly mode              |
| Esc    | release captured mouse       |
| Mouse  | look                         |

## Where outputs end up

| What                                                | Where                                        |
|-----------------------------------------------------|----------------------------------------------|
| Heightmap PNG + meta                                | `world3/heightmap/`                          |
| Texture sets (full provenance)                      | `world/textures/library/<id>/`               |
| Texture sets (staged for world3)                    | `world3/textures/wgv3/<name>/`               |
| Shaders                                             | `world3/shaders/`                            |
| Godot scenes / scripts                              | `world3/scenes/`, `world3/scripts/`          |
| Headless capture PNGs                               | `D:/tmp/world3_screens/`                     |
| Texture grid captures (baseline + hex)              | `D:/tmp/world3_screens/textures{,_hex}/`     |
| Per-iteration archive (workflow milestones)         | `world3/docs/captures/iter*/`                |
| Catalog (one JSON line per generated texture)       | `world/textures/catalog/materials.jsonl`     |

## Where to look when something goes wrong

| Symptom                                             | First place to look                                      |
|-----------------------------------------------------|----------------------------------------------------------|
| Texture pipeline gate fails                         | `world/textures/library/<id>/aaa_pipeline.json` `gate.failures` |
| Texture has visible center seam                     | `world/textures/library/<id>/qa/tile_2x2.png`            |
| Mesh looks flat / no relief                         | `world3/heightmap/meta.json` — is `elevation_range_m` sensible?  |
| Camera frames the wrong area                        | Iso/TopDown auto-frame from terrain AABB — check `print` lines in capture log  |
| Walk scene player falls forever                     | `Terrain.gd` collision_target wired? `Walker.gd` fly_mode default?  |
| Shader doesn't compile                              | `--headless --import` log from Godot                     |
| Heightmap drops to 8-bit precision                  | `Terrain.gd` falls back to `load_from_file` automatically — printed warning is harmless |

## Shader iterations (currently)

The shader stack is built incrementally in three separate files so any
iteration can be A/B'd against the previous one. Same uniform names
where they overlap.

| File                          | What it adds                                                                           |
|-------------------------------|----------------------------------------------------------------------------------------|
| `terrain_hex.gdshader`        | Triplanar + hex-tile sampling + macro variation noise. Single PBR set.                 |
| `terrain_hex_detail.gdshader` | Above + macro+detail layering (samples the same set at 8x scale, blends by soft-light + RNM, distance-faded). |
| `terrain_blend.gdshader`      | Multi-texture (5 PBR sets) selected by world Y (height-banded) and surface slope. Shared hex+macro. |

Iter 5 (`terrain_blend`) is what's bound to the iso/topdown/walk Tetons
scenes. As of Phase E (2026-05-07) each scene binds a per-mode-tuned
variant:

- `walk.tscn` → `terrain_blend_alpine_walk.tres` (UV scale 0.4, sharp
  normals, low macro tint — close-up surface detail)
- `iso.tscn` → `terrain_blend_alpine_iso.tres` (UV scale 0.1, default
  normal, moderate macro — mid-detail blend; same as historical default)
- `topdown.tscn` → `terrain_blend_alpine_topdown.tres` (UV scale 0.02,
  muted normal, high macro tint — color-blocking dominates)

The `terrain_blend_<kit>_<mode>.tres` variants are emitted from each
kit's base `terrain_blend_<kit>.tres` by
`pipelines/textures/emit_per_mode_materials.py`. Re-run after any kit
shader-param change.

Layer weights (same in every variant):

| Layer        | Selected when                                  |
|--------------|------------------------------------------------|
| grass        | low height (<20%), low slope                   |
| dirt         | mid-low height (20–55%), low slope             |
| rock_dark    | mid-high height (55–85%), low slope            |
| snow         | high height (>85%)                             |
| rock_light   | high slope (>0.45) — wins at any height        |

`elev_min_m` and `elev_range_m` are populated by `Terrain.gd` from the
heightmap's `meta.json` so the same `.tres` works for any DEM.

## Region library + biome kits (Phase 2 + 2.5 — DONE)

The OpenTopo workflow populates `world3/opentopo/processed/heightmaps/<site>/<dataset>/` with `heightmap.png + meta.json` bundles. world3 indexes these into a region catalog and renders any one through the slope+height blend shader, using a kit-appropriate biome material.

```powershell
# Index regions + assign biome kits (re-run when biome_kits.json changes)
python world3/pipeline/index_regions.py

# Generate per-kit terrain_blend.tres from biome_kits.json
python world3/pipeline/build_kit_materials.py

# Render gallery (iso + topdown per region, with the right kit per region)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/region_gallery.tscn"
```

`world3/jobs/biome_kits.json` defines 5 kits (alpine/desert/tundra/
temperate_forest/grassland). Each kit binds 5 texture slots, sets
per-kit height-band thresholds + slope threshold, and lists which
regions belong to it. `regions.json` carries the kit assignment.
`RegionGalleryCapture.gd` swaps `material_override` to the kit's
terrain_blend.tres before loading each heightmap.

To produce a new kit's textures (run from `D:/assets`):
```powershell
# Pick an anchor texture (defines the palette)
python pipelines/textures/aaa_texture.py `
  --prompt "fine pale sand with subtle wind ripples..." `
  --id desert_sand --category Sand

# Lock 4 supporting textures to the anchor's palette
python pipelines/textures/palette_lock.py `
  --kit desert --anchor desert_sand `
  --add "sparse dry desert brush...:desert_dry_brush:Foliage" `
  --add "weathered tan canyon sandstone...:desert_canyon_rock:Rock" `
  --add "dark basalt rock with red-brown patina...:desert_dark_rock:Rock" `
  --add "white salt pan crust with hexagonal cracks...:desert_salt_pan:Ground" `
  --strength 0.55

# Stage into world3 (manual copy loop — see world3/textures/wgv3/README.md)
# Re-index regions + regenerate kit materials
python world3/pipeline/index_regions.py
python world3/pipeline/build_kit_materials.py
```

## Post-M12 review and promotion audits

Use these after generating or reviewing source-stack workflow artifacts:

```powershell
# Inventory source-stack review scenes and gameplay-band captures.
python world3/pipeline/audit_m12_view_mode_parity.py

# Check whether workflow/asset candidates have enough evidence for promotion.
python world3/pipeline/audit_production_promotion_candidates.py

# Rebuild the M14 close-play material quality board.
python world3/pipeline/build_m14_close_play_quality_board.py
```

The promotion audit reads
`world3/jobs/production_promotion_candidates.json` and writes
`world3/docs/PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`. A workflow can be
accepted while still blocked for production by close-play quality, placeholder
scatter, missing evidence, or pending live review.

The M14 board reads the M8 organic regeneration queue plus
`world3/jobs/m14_texture_bakeoff_plan.json` and writes
`world3/docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`. It is the operating
board for close-play material quality before candidates are promoted through
M13.

M14 organic materials use a layered review method:

```powershell
# Run a FLUX/Aura/SD bakeoff for a candidate prompt.
python pipelines/textures/diversity_compare.py --prompt "<material prompt>" --id <m14_id> --seed <seed> --models active --heal-strength 0.35

# When one lane is clearly the viable one, run a broad same-model sweep.
python pipelines/textures/diversity_compare.py --prompt "<family prompt>" --id <m14_id_family_seed> --seed <seed> --models flux2_klein --heal-strength 0.30
```

For organic terrain, do not ask one flat tile to carry the whole readable
biome. M14 should produce calm substrate/detail candidates; M15 scatter/features
carry blades, clumps, leaves, sticks, roots, and other readable objects. Record
the visual veto before staging a sidecar for close/medium/iso/topdown review.
If a candidate family is cheap enough to run, produce 10-50 same-model samples
across prompt families and shortlist from 2x2 sheets. This is the production
method for organic blockers: curation first, PBR/runtime staging only after the
tile survives object-repeat review.

When a bakeoff survivor is albedo-only, convert and stage it as a quarantined
sidecar before source-stack runtime review:

```powershell
python pipelines/textures/derive_pbr_v2.py --albedo "<final_albedo.png>" --id <candidate_id> --category Ground --out "D:/assets/world/textures/library/<candidate_id>" --normal-strength 1.2
python world3/pipeline/stage_comfy_candidate_material.py --library-id <candidate_id> --source-material-id <source_material_id> --color-family <short-family> --scale-m-per-repeat 10.0
python world3/pipeline/build_source_stack_runtime_review.py --detail-material <candidate_id> --id <review_id> --extra-catalog world3/materials/catalog_comfy_candidates.json --normal-strength 0.0 --detail-normal-strength 0.0 --detail-albedo-strength 0.035 --detail-rough-strength 0.015
```

Iso/tactical sidecar research starts with a cached 2D card proof:

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m16_iso_impostor_card.tscn'
```

That scene displays the M12 runtime iso bake without live terrain meshes or a
`ChunkLoader`. It is a first M16 renderer experiment, not a replacement for
3D/iso/topdown validation.

## What's NOT yet documented here (because it doesn't exist yet)

- **Tundra kit textures** — kit schema defined in `biome_kits.json`
  but the 5 tundra_* textures haven't been generated yet.
- **Multi-DEM stitching, infinite world, kernel-driven generation** —
  see `ROADMAP.md` for the long-term plan.
