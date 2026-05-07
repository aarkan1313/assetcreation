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
3. Replaces nodata pixels with the local minimum
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

## Stage 6 — The Godot project

Layout:
```
world3/
  project.godot                  # Godot 4.5 project root
  pipeline/build_world.py        # Stage 2
  heightmap/                     # Stage 2 output
    heightmap.png
    meta.json
  textures/wgv3/                 # Stage 4 staged textures + materials
    dirt/  grass/  ...
  shaders/
    terrain_hex.gdshader         # Stage 5 shader
  scripts/
    Terrain.gd                   # builds mesh + collision at runtime
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

`Terrain.gd` is the heart of it:
1. Reads `meta.json` for world size + elevation range
2. Loads `heightmap.png` (prefers Godot's resource system; falls back
   to `Image.load_from_file` so 16-bit precision survives Godot's
   8-bit import normalize)
3. Builds a subdivided plane `ArrayMesh` at runtime (default 256×256,
   ~131k tris) with vertex Y from heightmap, normals from finite
   differences, world-space UVs
4. If a `collision_target` `StaticBody3D` is set, attaches a
   `HeightMapShape3D` matching the mesh. The body is uniformly scaled
   so each cell spans `world_size / subdivisions` meters.

The 3 view scenes share `Terrain.gd` + a hex-shader material; differ
only in camera setup, sun angle, fog, ambient.

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

Run capture scenes through normal Godot with the capture scene as the trailing
argument. This is the validated Windows path for real viewport screenshots.

```powershell
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_iso.tscn"
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_topdown.tscn"
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_walk.tscn"
```

Wait/hidden version (when you need PowerShell to block on the capture):
```powershell
$args = @("--path", "D:/assets/world3", "res://scenes/capture_iso.tscn")
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -WindowStyle Hidden -Wait -PassThru
"EXIT=$($p.ExitCode)"
```

If a capture appears to do nothing, check for an existing Godot editor
or hung Godot process before rerunning.

For OpenTopo review screenshots, use the same trailing-argument pattern with
`res://toporeview/capture_phase*.tscn`. Do not use the older waited
`--headless --scene ... --quit-after ...` path as scene validation; that path
can fail locally with a Windows access violation even when the real capture
scene works.

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
scenes via `world3/textures/wgv3/terrain_blend_tetons.tres`. Layer
weights:

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

## What's NOT yet documented here (because it doesn't exist yet)

- **Tundra kit textures** — kit schema defined in `biome_kits.json`
  but the 5 tundra_* textures haven't been generated yet.
- **Multi-DEM stitching, infinite world, kernel-driven generation** —
  see `ROADMAP.md` for the long-term plan.
