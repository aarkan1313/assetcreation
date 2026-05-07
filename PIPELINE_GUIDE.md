# Pipeline Guide

Walkthroughs for the production-ready pipelines. Tool directory at [TOOLS_INDEX.md](TOOLS_INDEX.md). Live status at [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md). Research backing at [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md).

Sections:
- [Region Pipeline (one command)](#one-command-region-pipeline) — preset → fantasy edit → biomes → AAA → 3 Godot scenes
- [Bulk DEM ingestion](#bulk-dem-ingestion) — wishlist + cache + rate-limit-aware pulls
- [Tile-stitched DEMs](#tile-stitched-dems) — multi-tile composer for huge/high-res regions
- [AAA Texture Workflow](#aaa-texture-workflow) — prompt → tileable PBR set, grade A
- [Character Pipeline](#character-pipeline-2d-image--animated-2d-sprite) — 2D image → animated sprite
- [Terrain Bundle Workflow](#terrain-bundle-workflow) — heightmap → Godot Terrain3D ready
- [World Map Workflow](#world-map-workflow) — strategic political/biome/road map
- [Biome Decoration Workflow](#biome-decoration-workflow) — kit + terrain → scatter plan
- [Shader Workflow](#shader-workflow) — Godot shader templates + batch review

---

## One-shot pre-flight (every new shell)

```powershell
# Make the OpenTopography API key available to subprocesses
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")
```

Without this, `import_dem.py` and the orchestrators bail with "Set OPENTOPOGRAPHY_API_KEY env var." Subprocess inheritance from PowerShell doesn't pick up User-scope env vars by default; this line copies it into the current process.

---

## Tile-stitched DEMs

For regions too large for a single API call (USGS1m caps at 250 km² per request, USGS10m at 25,000 km², etc), `tile_stitch.py` splits a target bbox into N×M overlapping tiles, fetches each, and seam-blends them into one heightmap.

```powershell
# Whole Yosemite Valley + Tuolumne ridges at 1m, 9-tile composite (~30km × 30km @ 1m)
python pipelines\terrain\tile_stitch.py `
  --id yosemite_full_1m --bbox -119.75 37.65 -119.40 37.90 `
  --dataset USGS1m --rows 3 --cols 3 --overlap 0.002 --size 4096

# Full Bryce amphitheater at 1m, 4-tile
python pipelines\terrain\tile_stitch.py `
  --id bryce_extended_1m --bbox -112.30 37.50 -112.00 37.80 `
  --dataset USGS1m --rows 2 --cols 2 --size 4096

# Mt St Helens crater + lahar fields
python pipelines\terrain\tile_stitch.py `
  --id mt_st_helens_flank_1m --bbox -122.30 46.10 -122.10 46.30 `
  --dataset USGS1m --rows 2 --cols 2 --size 4096
```

Outputs land at `pipelines/terrain/output/<id>/height_16.png` plus `tile_grid.json` provenance. Then run `region_pipeline.py --skip-dem --id <id> ...` to reuse.

Pre-defined recipes for the `stitched` tier are in `art_lab/biomes/data_wishlist.json` (Yosemite, Bryce, Grand Canyon, Mt St Helens, Rainier, Crater Lake, Death Valley, Olympic Peninsula, Aconcagua, Norwegian fjordland).

---

## AAA Texture Workflow

**One command** generates a self-generated tileable PBR material from a text prompt. Current on-disk QA best is seam grade A (0.00037); `cobblestone_aaa` is grade B (0.00329).

### Prerequisites
1. ComfyUI running at http://127.0.0.1:8188 with FLUX.2-klein-4B + Qwen3-4B + flux2-vae loaded:
   ```powershell
   cd D:\assets\animators\ComfyUI
   .\start.ps1
   ```
2. `animators/mesa-env/venv` with StableMaterials cached (needed for `--quality default` and `strict`).
3. Blender 5.x at `C:\Program Files\Blender Foundation\Blender 5.x\blender.exe` (preview render).

### Workflow

```powershell
# Default quality: 4 variants, StableMaterials PBR, seam B+ required (<= 0.010)
python pipelines\textures\aaa_texture.py `
  --prompt "weathered cobblestone street, mossy gaps" `
  --id cobblestone_aaa `
  --category Bricks `
  --quality default

# Strict: 6 variants, seam A required (<= 0.005)
python pipelines\textures\aaa_texture.py `
  --prompt "obsidian temple floor, gold inlay" `
  --id temple_floor `
  --category Marble `
  --quality strict
# (Note: fast uses derive_pbr_v2. default/strict use StableMaterials.
#  MA's image-to-PBR was removed from the AAA pipeline because it
#  requires multi-view 3D mesh consolidation; on a single 2D texture
#  it produces flat grey output. For mesh-driven experiments use
#  material_anything_adapter.py.)

# Optional: 2K or 4K upscale
python pipelines\textures\flux_upscale.py `
  --material world\textures\library\cobblestone_aaa --target 2048
```

### Stages (chained automatically by `aaa_texture.py`)
1. **Variant generation** — N seeds × `flux_seamless.py` (text2img → offset → img2img heal → reverse offset)
2. **Best-pick** — pick lowest seam-score winner
3. **De-lighting** — LAB-space large-blur subtraction (`delight.py`)
4. **PBR estimation** — StableMaterials single-image PBR (`default`/`strict`) or `derive_pbr_v2` (heuristic, `fast`)
5. **Seam repair** — PatchMatch synced across all maps
6. **Texture QA** — seam grade + sphere/plane sanity
7. **Blender Cycles render** — lit sphere + tiled plane at grazing angle (real PBR validation)
8. **Quality gate** — must beat seam threshold for the chosen preset
9. **Catalog manifest** — provenance, all variant scores, every stage timing

### Output

```
world/textures/library/<id>/
├── <id>_albedo.png        de-lit, palette-locked, tile-perfect
├── <id>_normal.png
├── <id>_roughness.png
├── <id>_metallic.png
├── <id>_height.png
├── <id>_bump.png
├── <id>_rm.png            packed roughness+metallic
├── qa/
│   ├── blender_sphere.png  Cycles render under PBR lighting
│   ├── blender_plane.png   tiled grazing-angle render
│   ├── seam_score.json
│   ├── tile_2x2.png
│   └── summary.json
├── aaa_pipeline.json      every stage's timing + scores
├── variant_select.json    which seeds were tried
└── *.pre_delight.png, *.pre_upscale.png    backups
```

### Building a coherent biome kit

**Easiest path: one command (kit generator)**

```powershell
# Pick a builtin: highland_ruins, frozen_volcanic, desert_temple, forest_floor
python pipelines\textures\kit_generator.py --kit forest_floor --quality default

# With detail pyramids (each material gets a high-frequency overlay layer)
python pipelines\textures\kit_generator.py --kit highland_ruins --quality default --pyramid

# Custom recipe
python pipelines\textures\kit_generator.py --recipe my_biome.json --quality strict
```

The kit generator chains: anchor AAA → 5 sibling AAA passes through `palette_lock.py` (LAB hist-match to anchor) → HDRI Cycles render of each → optional detail-pyramid pass. Verified `forest_floor` builds 6 palette-coherent materials in ~3.5 min on `--quality fast`.

Output: `art_lab/biomes/kits/<kit_id>_textures.json` lists every member, plus each material lives at `world/textures/library/<id>/`.

**Manual path (one anchor + manual siblings):**

```powershell
python pipelines\textures\aaa_texture.py --prompt "mossy basalt rock" --id basalt_anchor --category Rock

python pipelines\textures\palette_lock.py --kit highland --anchor basalt_anchor `
  --add "wet mossy soil:soil:Ground" `
  --add "fern undergrowth:fern:Ground" `
  --add "weathered stone steps:steps:Bricks"
```

### Macro + Detail texture pairing (close-up AAA)

For terrain or hero walls that need to look crisp at 0-2m AND believable at 5-30m:

```powershell
# Add a detail layer to an existing AAA material
python pipelines\textures\detail_pyramid.py --macro world\textures\library\basalt_anchor

# Use the macro_detail_v1 shader template in Godot
# (art_lab/shaders/templates/macro_detail_v1.gdshader)
```

The pair works like: macro UV @ 4m repeat + detail UV @ 0.4m repeat, blended via Reoriented Normal Mapping (RNM) and soft-light albedo, with distance fade so detail vanishes past 30m.

---

## Terrain Bundle Workflow

Generate a Godot-ready terrain folder from any of 6 input modes.

```powershell
# Synthetic FBM (fast, free)
python pipelines\terrain\terrain_bundle.py --id alpine_a --biome mountains --size 1024 --erosion 60 --erosion-mode hydraulic

# Real-world DEM (no auth needed for Mapzen)
python pipelines\terrain\import_dem.py --source mapzen --mapzen-tile 8 50 90 --id colorado_a --size 1024

# Real-world DEM (OpenTopography — needs OPENTOPOGRAPHY_API_KEY in env;
#   set permanently with: [Environment]::SetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "<key>", "User"))
# 13 presets include utah_canyon, colorado_alpine, appalachian, alps_dolomites,
# iceland_volcanic, sahara_dunes, norwegian_fjord, nz_glacier, bryce_hoodoo,
# scottish_highlands, patagonian_spires, moroccan_atlas, japanese_alps.
python pipelines\terrain\import_dem.py --source opentopo --preset utah_canyon --id utah_a --size 1024
# or by bbox: --bbox W S E N
# or override dataset: --dataset SRTMGL3|AW3D30|COP30|COP90|EU_DTM

# AI-generated from text
$env:HF_HOME = "C:\Users\josep\.cache\huggingface"  # if not set
D:\assets\animators\mesa-env\venv\Scripts\python.exe `
  pipelines\terrain\mesa_terrain.py --prompt "Sentinel-2 image of arid badlands and mesas" --id mesa_badlands --steps 30

# WorldEngine continent-scale → bundle
worldengine world -s 1234 -n smoke -x 256 -y 256 --gs -r
python pipelines\terrain\worldengine_to_bundle.py --we-dir output\worldengine_smoke --id worldengine_a

# FastNoiseLite SIMD noise
python pipelines\terrain\fastnoise_height.py --id ridged_a --noise OpenSimplex2 --fractal Ridged

# Apply additional erosion in-place
python pipelines\terrain\particle_erosion.py --bundle output\smoketest_a --particles 50000
```

Every bundle has the same shape: `height_16.png`, `normal.png`, `splat_rgba.png`, `biome.png`, `vegetation_density.png`, `water_mask.png`, `flow.png`, hypsometric + hillshade previews, `terrain.json`, and `godot/heightmapshape3d.tres`.

---

## Multi-Biome Coherent World (Phase A)

One command generates a world with 4+ biomes that share a coherent identity across world / regional / local zoom levels, with terrain-feature-aware transitions (rivers / ridges / altitude bands) instead of straight Voronoi cuts.

```powershell
# Synthetic continental base
python art_lab\biomes\tools\world_biome_engine.py `
  --id mythos_world `
  --biomes lava_field,ice_cavern,mana_crystal,grassland `
  --size 1024 --seed 42 --erosion 30

# Real-DEM base — paint biomes on top of real geography
# (first generate the DEM via import_dem.py, then point at its height_16.png)
python pipelines\terrain\import_dem.py --source opentopo --preset norwegian_fjord --id fjord_real --size 1024
python art_lab\biomes\tools\world_biome_engine.py `
  --id fjord_4biome `
  --biomes lava_field,ice_cavern,mana_crystal,grassland `
  --base-heightmap pipelines\terrain\output\fjord_real\height_16.png `
  --size 1024 --seed 7 --erosion 15
```

Output: `world/worlds/<id>/`:
- `world_view.png` (128 px) — overview, one color per biome + ocean
- `regional_view.png` (512 px) — palette fill with hillshading
- `local_view.png` (1024 px) — full detail playable view
- `biome_labels_colored.png` — categorical colors for inspection
- `height_16.png`, `normal.png`, `splat_rgba.png`, `flow.png`, `vegetation_density.png`, etc.
- `godot/heightmapshape3d.tres` — drop into Godot 4.5

How it works:
1. Continental base heightmap (continental + ridge + fine FBM stack — looks like a real continent, not noise)
2. Poisson-disc biome seed placement weighted by per-biome priority
3. Influence field per biome = Voronoi distance × altitude affinity × slope affinity
4. **Sea-level cutoff** — anything below 0.32 is ocean (separate from biomes)
5. **Boundary snap** — pulls biome edges onto natural terrain features (rivers / ridges / altitude crossings) per the `transitions.blend_neighbours[<other>].feature_priority` spec in each biome kit
6. **Spatially-coherent boundary jitter** (FBM-driven, not per-pixel noise) for organic blobby boundaries
7. Per-biome heightmap shaping — bias toward each biome's altitude range + carve features:
   - `lava_field`: 8-15 m hex cracks, 0.5-1.5 m deep (sparse, 1 per ~30×30 px)
   - `ice_cavern`: tall narrow spires 5-15 m tall, 5 m wide (sparse, 1 per ~80×80 px)
   - `mana_crystal`: clusters of 4-8 sharp spikes 10-22 m tall (1 cluster per ~90×90 px)
8. Thermal erosion pass on the final heightmap
9. Re-derive flow / slope / normals from final state
10. Render all three zoom levels

Biome kits live at `art_lab/biomes/world_kits/*.json`. Schema: [`art_lab/biomes/BIOME_KIT_SCHEMA.md`](art_lab/biomes/BIOME_KIT_SCHEMA.md).

Reference kits shipped: `lava_field`, `ice_cavern`, `mana_crystal`, `grassland`. New biomes are JSON files matching the schema.

---

## Region Zoom (Phase B — world chunk → playable terrain)

After generating a coherent world, zoom into a chunk at playable resolution. The region inherits the world's biome layout but gets fresh fine-frequency detail and full-scale feature carving.

```powershell
# By bbox in world-pixel coords:
python art_lab\biomes\tools\region_zoom.py `
  --world mythos_world `
  --bbox 250 600 750 1000 `
  --id mythos_region_a `
  --size 1024 --seed 200 --erosion 25
```

Output: `world/regions/<id>/` — a standard terrain bundle (drop into Godot exporter, biome dressing, etc.). Includes `region.json` provenance linking back to source world + bbox.

How it works:
1. Read the source world's `height_16.png` and `biome_labels.png`
2. Crop to the bbox
3. Bicubic-upsample the heightmap to target resolution (preserves the macro shape)
4. Add 3-octave mid-frequency + 5-octave fine FBM on top for detail
5. Nearest-neighbour upsample biome labels (categorical, no blur)
6. Re-carve per-biome features (lava cracks / ice spires / crystal spikes) at full playable scale
7. Erosion pass + re-derive flow / slope / normals

Use this to bridge: **world overview → "player walks here"**. The biome composition is locked to the source world (so visiting the same coords twice gives the same biomes), but the small-scale terrain shape is freshly generated.

---

## Biome ↔ AAA Texture Binding (world → Godot terrain shader)

Once you have a multi-biome world, this workflow binds every biome to a real PBR texture set, builds the splat the shader reads, and stages everything into a Godot 4.5 project.

```powershell
# 1. Build the biome splat (registry-driven RGBA channel assignment)
python pipelines\terrain\biome_splat.py --world world\worlds\qa_fjord_4biome

# 2. Ensure each biome has an AAA texture set (auto-generates any missing).
#    Reads art_lab\biomes\biome_texture_registry.json for prompt seeds.
python pipelines\textures\biome_texture_bind.py `
  --world world\worlds\qa_fjord_4biome `
  --quality default

# 3. Stage into a Godot project (copies height + splat + 4 PBR sets,
#    writes ShaderMaterial .tres + ready-to-play .tscn)
python pipelines\godot_export\stage_biome_terrain.py `
  --world world\worlds\qa_fjord_4biome `
  --project C:\Users\josep\test\new-game-project
```

Then in Godot 4.5: open the project, load `biome_terrain_test/biome_terrain_<world_id>.tscn`, and press F6.

### Add scatter, walkable mode, and A/B camera scenes

```powershell
# Per-biome scatter (placeholder primitives until real GLB props arrive).
# Auto-picked up by the main scene as a Scatter child node.
python pipelines\godot_export\stage_biome_scatter.py `
  --world world\worlds\qa_fjord_4biome `
  --project C:\Users\josep\test\new-game-project `
  --max-instances 800

# Walkable testbed: HeightMapShape3D collision + CharacterBody3D
# WASD / Shift sprint / Space jump / mouse-look / Esc release mouse
python pipelines\godot_export\stage_biome_terrain.py `
  --world world\worlds\qa_fjord_4biome `
  --project C:\Users\josep\test\new-game-project `
  --walkable

# A/B comparison scenes for 2D top-down vs 2.5D iso look
python pipelines\godot_export\stage_biome_terrain.py `
  --world world\worlds\qa_fjord_4biome `
  --project C:\Users\josep\test\new-game-project `
  --cameras

# All together (idempotent — re-run any time)
python pipelines\godot_export\stage_biome_terrain.py `
  --world world\worlds\qa_fjord_4biome `
  --project C:\Users\josep\test\new-game-project `
  --walkable --cameras
```

The comparison scenes:
- `biome_<id>_topdown.tscn` — orthographic camera looking straight down (TLTE-style 2D feel).
- `biome_<id>_iso.tscn` — 45° yaw / ~30° pitch ortho camera (Diablo / PoE 2.5D feel).
Both reuse the same terrain + scatter assets, so they're cheap to keep around.

How it works:
1. **Registry** (`art_lab/biomes/biome_texture_registry.json`) is the source of truth: each biome_id maps to a `set_id` (lives at `world/textures/library/<set_id>/`), a fixed `splat_channel` (R/G/B/A), a `prompt_seed` (auto-regenerates the set via `aaa_texture.py` if missing), and a `tiling_meters`.
2. **biome_splat.py** reads `biome_labels.png` + `world.json`, writes `biome_splat_rgba.png` where each biome occupies its registry-assigned channel. Soft Gaussian smoothing means the shader doesn't see hard 1-px steps.
3. **biome_texture_bind.py** ensures each biome's texture set exists (calls `aaa_texture.py` with the registry prompt if not), then writes `biome_pbr_pack.json` next to the world — the single file the shader/stager reads to wire all 4 layers.
4. **stage_biome_terrain.py** copies `height_16.png` + `biome_splat_rgba.png` + all 4 PBR sets (albedo / normal / roughness) into `<project>/biome_terrain_test/assets/<world_id>/`, then writes `biome_terrain_<world_id>.tres` (preconfigured ShaderMaterial referencing all 14 textures + per-biome tiling) and `biome_terrain_<world_id>.tscn` (a 256-subdivided PlaneMesh, DirectionalLight, Camera).
5. **biome_terrain.gdshader** displaces the plane in the vertex stage using the heightmap (analytic gradient normal from 4 neighbours), then in the fragment stage blends 4 PBR layers by splat weights with **triplanar projection** so cliffs/canyon walls don't stretch. Tweak via `triplanar_strength` (0 = top-down only, 1 = full triplanar) and `triplanar_sharpness` (1–16) on the `.tres`.

To add a new biome: define a `world_kits/<id>.json` for terrain identity, add an entry in `biome_texture_registry.json` for texture binding, then run the workflow.

---

## One-command Region Pipeline

The fastest path from "I want a Bryce-canyon-style spired land" to a playable Godot scene:

```powershell
python pipelines\terrain\region_pipeline.py `
  --preset bryce_hoodoo `
  --style spired `
  --strength 1.5 `
  --biomes mana_crystal,grassland,grassland,grassland `
  --id spire_garden `
  --project C:\Users\josep\test\new-game-project `
  --size 1024
```

This chains the entire stack: pulls the real Bryce Canyon DEM (or skips with `--skip-dem` if cached), applies a "spired" fantasy edit (peaks injected with cubic spires), paints 4 biomes on the result, builds the splat, ensures all 4 AAA texture sets exist (auto-generates if missing), generates ~5000 scatter instances, then writes 3 Godot scenes (walkable, top-down, iso). Open the project in Godot 4.5 and load any of the `.tscn` files.

### Reusing cached DEMs (skip-dem)

If the DEM is already pulled (which is true for any region in the cache after a `bulk_pull`), reuse it:

```powershell
python pipelines\terrain\region_pipeline.py `
  --preset utah_canyon --style mythic --strength 1.4 `
  --biomes ice_cavern,grassland,grassland,mana_crystal `
  --id yosemite_valley `
  --project C:\Users\josep\test\new-game-project `
  --size 1024 --skip-dem
```

`--skip-dem` makes the orchestrator look up `pipelines/terrain/output/<id>/height_16.png` instead of refetching. The `--id` must match an already-pulled region. Use `bulk_pull.py --dry-run --tier <name>` to see available IDs.

### Using high-res LiDAR sources

For US locations, swap `--preset` for an explicit bbox + `--dataset USGS1m` (with OT+ subscription) or `USGS10m` (free tier):

```powershell
python pipelines\terrain\region_pipeline.py `
  --bbox -119.65 37.70 -119.50 37.80 --dataset USGS1m `
  --style mythic --strength 1.4 `
  --biomes ice_cavern,grassland,grassland,mana_crystal `
  --id yose_v2 --project C:\Users\josep\test\new-game-project --size 2048
```

For regions too big for a single API call, see [Tile-stitched DEMs](#tile-stitched-dems) above — pull as a multi-tile composite, then `region_pipeline --skip-dem` reuses it.

### Fantasy style presets

```powershell
python pipelines\terrain\dem_fantasy_edit.py --in <heightmap>.png --out fantasy.png --style mythic --strength 1.2
```

| Style | Effect |
|---|---|
| `realistic`   | passthrough (sanity) |
| `exaggerated` | vertical 2-3× scaling — Avatar Pandora |
| `terraced`    | quantized bands — temple-mountain look |
| `sharpened`   | unsharp mask on heightmap, ridges pop |
| `spired`      | cubic spike injection at peaks (>0.6 height) |
| `floating`    | mask-and-invert, Avatar floating mountains |
| `mythic`      | exaggerated + sharpened + mild spire injection |

### Declarative region configs (`region.config.v1`) — preferred for production

Per the character-pipeline pattern, every reproducible region lives in a JSON
config under `art_lab/biomes/regions/`. Run via:

```powershell
# Generate fresh template
python pipelines\terrain\region_pipeline_from_config.py --template my_region > art_lab\biomes\regions\my_region.region.json

# Edit the JSON, then run
python pipelines\terrain\region_pipeline_from_config.py --config art_lab\biomes\regions\my_region.region.json

# Batch many regions
python pipelines\terrain\region_pipeline_from_config.py --batch art_lab\biomes\regions\*.region.json

# Dry-run (validate + print resolved CLI without running)
python pipelines\terrain\region_pipeline_from_config.py --config <FILE> --dry-run
```

Config schema captures every choice declaratively (DEM source, fantasy style,
biomes, splat mode, shader preset, terrain extents, scatter cap, camera
framing, project, quality). See [art_lab/biomes/regions/README.md](art_lab/biomes/regions/README.md)
for the full field reference. First example:
[art_lab/biomes/regions/death_valley_basin.region.json](art_lab/biomes/regions/death_valley_basin.region.json).

### Phase 1 swap-points (CLI)

The `region_pipeline.py` and `stage_biome_terrain.py` CLIs expose 4 new
orthogonal swap-points (also settable via region.config.v1):

| Flag | Values | What it does |
|---|---|---|
| `--shader-preset` | topdown / triplanar / hextile / heightblend | Picks a `.gdshader` from `godot_pack/shaders/shader_registry.json`. topdown (default) is cleanest for ARPG iso/topdown; triplanar is for first-person; hextile/heightblend are reserved (fall back to topdown). |
| `--splat-mode` | gaussian / soft / hard / height_blend | Splat boundary blend strategy. gaussian = 1.6 px Gaussian (default). hard = 1-px crisp. height_blend reserved for the future heightblend shader. |
| `--use-real-extents` | flag | Read terrain dims from world.json's dem_meta (real bbox span + elev range) instead of legacy 512m × 64m. Pair with `--terrain-size-m N` / `--terrain-height-m N` for explicit overrides. |
| `--triplanar` | 0.0 .. 1.0 | Override the shader preset's `triplanar_strength` uniform. 0 = pure top-down UV; 1 = full slope-aware blend. |

### Curated starter regions

`art_lab/biomes/world_catalogue.json` lists 10 known-good combinations:

| ID | Recipe | Tagline |
|---|---|---|
| `frostfang_fjord` | norwegian_fjord + sharpened + ice/ice/mana/grass | Towering ice spires above arctic fjord |
| `embercaldera` | iceland_volcanic + exaggerated + lava/lava/mana/grass | Volcanic caldera with ember plains |
| `spire_garden` | bryce_hoodoo + spired + mana/mana/grass/grass | Bryce hoodoos as glowing crystal spires |
| `obsidian_mesas` | utah_canyon + terraced + lava/mana/grass/grass | Canyons → terraced obsidian temples |
| `skyforest` | patagonian_spires + floating + mana/mana/grass/ice | Avatar-style floating mountains |
| ... | ... | ... |

## Bulk DEM ingestion

The full `data_wishlist.json` has 172 named regions across `showcase` (USGS 1m, OT+ tier), `premium` (30m large bbox), `standard` (30m medium bbox), `bathymetric` (GEBCO seafloor), `stitched` (multi-tile composites), and `highres_open` (LINZ/Arctic/REMA — endpoint TBD) tiers. `bulk_pull.py` walks any tier and caches every TIFF locally.

```powershell
# Pre-flight: dry-run to see what will be pulled
python pipelines\terrain\bulk_pull.py --tier premium --dry-run

# Real pull (resumable, rate-limit-aware, cache-aware)
python pipelines\terrain\bulk_pull.py --tier premium

# Showcase tier (USGS 1m via OT+, 20 regions, ~10 GB)
python pipelines\terrain\bulk_pull.py --tier showcase

# Mystery tier (300 procedurally-sampled unknown regions worldwide)
python pipelines\terrain\bulk_pull.py --wishlist art_lab\biomes\data_wishlist_mystery.json

# Custom quota for academic/Pro tier (default 400/24h matches OT+; bump higher for Enterprise)
python pipelines\terrain\bulk_pull.py --tier premium --quota 800
```

`bulk_pull.py` tracks daily call count in `~/.opentopo_calls.jsonl` and stops when it hits the quota. Resume by running again the next day; cache hits make completed regions free.

Cached TIFFs live at `pipelines/terrain/source_dems/` — pruning is safe but re-pulling costs API credits.

---

## Strategic World Map (factions / settlements / labels)

Different from the multi-biome world above — this is the political *map screen* with named settlements, A* roads, weighted-Voronoi factions, river GeoJSON, etc.

```powershell
python art_lab\maps\generators\generate_world_map.py `
  --id mythos_a --size 1024 --seed 7 --biome custom `
  --n-settlements 14 --n-landmarks 8 --n-factions 4
```

Output: `world/maps/mythos_a/` with `layers/{height,biome,water,rivers,roads,regions,settlements,landmarks,labels,fog_mask}.{png|geojson|json}` + 5 previews + Godot scene.

---

## Biome Decoration Workflow

Kit + terrain bundle + map → scatter placement plan.

```powershell
# Use the example kit, smoketest terrain, mythos map
python art_lab\biomes\tools\dress_biome.py `
  --kit mossy_highland_ruins `
  --terrain smoketest_a `
  --map mythos_a `
  --id mossy_x_mythos `
  --m-per-pixel 0.5
```

Output: `art_lab/biomes/output/<id>/` with `placements/scatter.csv`, `placements/decals.csv`, per-asset masks, top-down preview, Godot recipe.

---

## Shader Workflow

Godot shader templates + LLM-driven request JSON + batch-explore-and-review.

```powershell
# Single shader from a request
python art_lab\tools\shader_compile_preview.py `
  --request art_lab\shaders\generated\examples\arcane_shield_ring.request.json

# Or from defaults
python art_lab\tools\shader_compile_preview.py --template ring_field_2d --id ring_test --no-render

# Batch exploration with non-OCR scoring (best for LLM-driven iteration)
python art_lab\tools\shader_batch_review.py `
  --batch-id storm_portal_001 --count 80 --frames 8 --size 256 `
  --intent "AAA-quality storm/shield/portal/projectile/aura/dissolve"

# Promote only the best/diverse candidates to human review
python art_lab\tools\shader_promote.py `
  --latest 3 --queue-id review_storm_portal_001 --min-score 82 --max-count 24

# Optional: score against curated references in art_lab\shaders\reference_sets\<name>
python art_lab\tools\shader_reference_score.py `
  --batch-dir art_lab\shaders\batches\storm_portal_001 `
  --reference-set storm_projectile `
  --update-summary

# Target-driven evolution against a reference folder
python art_lab\tools\shader_evolve.py `
  --reference art_lab\shaders\reference_sets\storm_projectile `
  --batch-id storm_projectile_evolve_001 `
  --template beam_lightning_2d --template portal_swirl_2d `
  --population 36 --generations 5 --elites 6 `
  --frames 8 --size 256

# Optional: final engine render when Godot 4.5 is available
python art_lab\tools\shader_godot_render.py `
  --batch-dir art_lab\shaders\batches\storm_portal_001 `
  --godot-exe "C:\path\to\Godot_v4.5-stable_mono_win64.exe" `
  --frames 8 --no-headless
```

5 templates ship: `ring_field_2d`, `beam_lightning_2d`, `dissolve_fire_2d`, `shield_ripple_2d`, `portal_swirl_2d`. Add new templates by writing a `.gdshader` with `uniform`s and dropping it into `art_lab/shaders/templates/`. Use `shader_evolve.py` only when you have curated references; otherwise broad batch plus local mutation is better.

Recovered legacy reference: `art_lab/legacy/shader-cauldron-v6.html` and `art_lab/legacy/FOUND_OLD_SHADER_WORKFLOW.md`.

---

## Audio SFX Workflow

Offline procedural SFX v1: synthesize, process, QA, manifest, and export Godot randomizers.

```powershell
# Build the current 3-sound, 9-variant demo set:
python pipelines\audio\build_demo.py

# Or step-by-step for one sound family:
python pipelines\audio\synth_sfx.py fireball_cast --out audio\sfx\fb_v0.wav --variants 3 --seed 7
python pipelines\audio\process_audio.py audio\sfx\fb_v0.wav --out audio\sfx\fb_v0_p.wav --target-rms-db -16
python pipelines\audio\audio_qa.py audio\sfx\fb_v0_p.wav
python pipelines\audio\export_godot.py
```

Output: `audio/sfx/*.wav`, per-file QA folders, `audio/sfx_manifest.json`, and `audio/godot/` with `.import` files, cue JSON, bus layout, and `AudioStreamRandomizer` resources.

Optional cloud SFX path when `ELEVENLABS_API_KEY` is set:

```powershell
python pipelines\audio\eleven_sfx.py --prompt "short fireball cast, dry ignition, airy whoosh, no explosion tail" --duration 0.8 --out audio\sfx\fireball_eleven.wav
```

---

## Game Data Workflow

Schema-first content compiler v1: generate JSONL, validate/link, export typed Godot resources, then round-trip check.

```powershell
python pipelines\game_data\generate_records.py item --count 5 --seed 42
python pipelines\game_data\generate_records.py ability --count 3 --seed 42
python pipelines\game_data\generate_records.py faction --count 2 --seed 42
python pipelines\game_data\validate_records.py
python pipelines\game_data\generate_records.py npc --count 2 --seed 42
python pipelines\game_data\generate_records.py lore_term --count 2 --seed 42

python pipelines\game_data\validate_records.py
python pipelines\game_data\export_godot.py
python pipelines\game_data\roundtrip_test.py
```

Output: `game_data/generated/*.jsonl`, `game_data/validated/*.jsonl`, `game_data/reports/validation_*.md`, and `game_data/godot/` with GDScript Resource classes plus one `.tres` per record. The current demo exports 14 resources and round-trips 14/14.

Optional OpenAI structured-output generation:

```powershell
python pipelines\game_data\generate_records.py item --count 25 --backend openai --model gpt-4o-mini --seed 7
```

---

# Character Pipeline (2D Image → Animated 2D Sprite)

Full walkthrough for the character asset pipeline.

## Batch preprocess (one-time, fills `preprocessed/`)

If you have a fresh batch of Meshy outputs at `meshy/output/<name>/model.glb`, run this once:

```powershell
# Preprocesses every Meshy asset that doesn't already have a preprocessed companion.
# Skips already-done assets unless you pass --force.
python D:\assets\meshy\batch_preprocess.py
```

Originals are never modified. Output goes to `preprocessed/<name>_p.glb`. Average ~13s/asset on the RTX 5090. Summary at `preprocessed/_batch_summary.json` lists successes/failures.

To re-preprocess a single asset with different settings:
```powershell
python D:\assets\meshy\batch_preprocess.py --asset goblin --force --clean-internals
```

---

## TL;DR — Two paths

**Path A (fast, no rigging):** image → mesh → preprocess → AnimateAnyMesh → bake sprites → atlas. Best for one-off attack/idle/walk loops on creatures. ~5 min total.

**Path B (rigged, motion library):** image → mesh → preprocess → RigAnything → hy-motion → bake sprites → atlas. Best when you want consistent walk cycles, attack animations, and the ability to pose freely later. ~10 min total + ~10 GB hy-motion weights download (one-time).

---

## Path Mesh2Motion — self-hosted Mixamo alternative

If you don't want to use Adobe's Mixamo (or you need quadruped/bird rigging that Mixamo can't do), Mesh2Motion runs locally in your browser.

```powershell
D:\assets\animators\mesh2motion-app\start.ps1
# Opens http://localhost:5173 in your browser
# Upload your <name>.fbx (run glb_to_fbx.py first)
# Pick skeleton type (humanoid / fox / bird / dragon)
# Adjust bones, browse animations, export
```

Stop with Ctrl+C in the spawned PowerShell window.

**Tradeoffs vs Mixamo:** smaller animation library, but supports quadrupeds, bird, dragon — and you don't need an Adobe account.

---

## Path A — Quick sprite from an image

### Step 1: Generate or grab a 3D model
```powershell
# Option A1: Use Meshy (uses ~30 credits remaining)
python D:\assets\meshy\generate.py D:\assets\images\new_creature.png --name new_creature

# Option A2: Use a model we already have
$model = "D:\assets\meshy\output\goblin\model.glb"
```

### Step 2: Preprocess the mesh
Meshy outputs are usually 300k+ tris. Decimate before further processing:
```powershell
python D:\assets\meshy\preprocess.py D:\assets\meshy\output\goblin\model.glb --target-tris 30000
```
Output: `D:\assets\meshy\preprocessed\goblin_p.glb` (or `<name>_p.glb`).

### Step 3: Animate via AnimateAnyMesh (WSL)
The script copies your input mesh into `/tmp/aam_<name>` so AAM's data loader can find it.

```powershell
wsl -d Ubuntu-24.04 -- bash -c '
  source /opt/miniconda3/bin/activate animateanymesh
  cd /mnt/d/assets/animators/AnimateAnyMesh
  rm -rf /tmp/aam_goblin
  mkdir -p /tmp/aam_goblin
  cp /mnt/d/assets/meshy/preprocessed/goblin_p.glb /tmp/aam_goblin/goblin.glb

  python test_drive.py \
    --data_dir /tmp/aam_goblin \
    --vae_dir ./checkpoints \
    --rf_model_dir ./checkpoints \
    --json_dir ./checkpoints/dvae_factors \
    --rf_exp rf_model \
    --rf_epoch f \
    --seed 42 \
    --test_name goblin \
    --prompt "the creature walks forward" \
    --export_format fbx
'
```

Output: `D:\assets\animators\AnimateAnyMesh\output_videos\rf_model\goblin.fbx` (16-frame animated FBX with shape keys).

### Step 4: Bake to PNG sprites
```powershell
python D:\assets\meshy\bake.py `
    "D:\assets\animators\AnimateAnyMesh\output_videos\rf_model\goblin.fbx" `
    --angles 8 --frames 16 --res 512 --ortho --elevation 15
```

Output: `D:\assets\meshy\sprites\goblin\angle_000\frame_0000.png` ... 8 angles × 16 frames = 128 PNGs + a `manifest.json`.

Flag tips:
- `--angles 4` for cardinal directions only (faster, smaller atlas)
- `--ortho` for clean sprite-friendly projection (no perspective distortion)
- `--elevation 15` to tilt the camera slightly above horizon (3/4 view feel)
- `--res 256` for smaller output if your final sprite doesn't need much resolution

### Step 5: Pack into a sprite sheet
```powershell
python D:\assets\meshy\pack_sheet.py D:\assets\meshy\sprites\goblin --crop
```
Output: `D:\assets\meshy\sprites\goblin\sheet.png` + `sheet.json` (layout metadata).

The `--crop` flag tight-crops each frame to its non-transparent silhouette, then pads each cell to the largest cell size — yields a tighter atlas with consistent cell size.

### Step 6 (optional): Pixel-art conversion
**Apply pixel art to individual frames BEFORE packing**, not to the assembled atlas. The atlas is large (~6800 px); pixelating it makes each tile microscopic.

Correct order: bake → pixelate frames → pack pixelated frames.

```powershell
# Pixelate every frame (creates a parallel sprites/<name>_pix tree)
python D:\assets\meshy\pixel_art.py D:\assets\meshy\sprites\goblin D:\assets\meshy\sprites\goblin_pix `
    --pixel-size 64 --palette 16 --outline

# Then pack the pixelated tree
python D:\assets\meshy\pack_sheet.py D:\assets\meshy\sprites\goblin_pix --crop
```
Output: `D:\assets\meshy\sprites\goblin_pix\sheet.png`.

---

## Path B — Rigged character with Mixamo motion library (recommended)

**The most practical path for humanoid game characters.** Mixamo gives you 2500+ professionally hand-crafted animations and free auto-rigging via web UI.

### Step 1-2: Same as Path A
Generate + preprocess the mesh.

### Step 3: Convert to Mixamo-ready FBX
```powershell
python D:\assets\meshy\glb_to_fbx.py D:\assets\meshy\preprocessed\goblin_p.glb
```
Output: `D:\assets\meshy\mixamo_ready\<name>.fbx` — 1.7m tall, feet at world origin, ready for upload.

### Step 4: Auto-rig on Mixamo (browser, ~2 min per model)
1. Go to https://www.mixamo.com (free, requires Adobe account)
2. Click "Upload Character" → drop the FBX
3. Place 6 markers as Mixamo prompts: chin, wrists, elbows, knees, groin
4. Click "Next" — Mixamo auto-rigs the character on their server (~30 sec)
5. Mesh is now rigged with Mixamo's standard humanoid skeleton

### Step 5: Apply motion from library
1. Browse animations on the left side panel (search "walk", "attack", "idle", etc.)
2. Click any animation to preview on your character
3. Tweak speed/intensity/space sliders to taste
4. Click "Download" → choose "FBX Binary" + "With Skin" + "60 fps" → save to your project

### Step 6: Bake to sprites (same as Path A step 4-5)
```powershell
python D:\assets\meshy\bake.py "D:\path\to\downloaded_animation.fbx" --angles 8 --frames 24 --ortho --elevation 15
python D:\assets\meshy\pack_sheet.py D:\assets\meshy\sprites\<name> --crop
```

### Mixamo notes & limitations
- **Humanoid only.** Mixamo's auto-rigger expects a roughly bipedal humanoid silhouette. Quadrupeds (hellhound, wendigo) will fail or produce broken rigs.
- **Single mesh, single texture.** Multi-part assets get flattened.
- **No batch.** Manual per-character upload + animation selection. Takes ~3 min per character per animation set.
- **Free tier has no rate limits as of writing**, but downloads must be triggered manually each time.

---

## Path B-alt — hy-motion-fbx-exporter (text-to-motion AI)

Use this when you need a custom motion **not in Mixamo's library** (specific creature actions, unusual movements). Requires you've already done a Mixamo upload+rig of the character — hy-motion adds custom motion to an existing Mixamo-rigged FBX.

### Setup (one-time)
- ✅ HY-Motion Lite model: 1.76 GB downloaded to `D:\assets\animators\hy-motion-fbx-exporter\models-data\` (junction'd to `~/.hy-motion-exporter` on C:)
- On first inference: Qwen3-8B + CLIP encoders auto-download (a few more GB)

### Generate a custom motion
```powershell
& D:\assets\animators\hy-motion-fbx-exporter\.venv\Scripts\hy-motion-export.exe `
    "the goblin attacks with claws while crouching" `
    -c D:\assets\meshy\mixamo_ready\goblin_rigged.fbx `
    -o D:\assets\meshy\custom_motion\goblin_crouch_attack.fbx `
    -m lite -d 3.0
```

Output: an FBX with the rigged Mixamo character + AI-generated motion clip applied.

### Caveats
- Input character **must already be Mixamo-rigged** (run it through Mixamo first)
- Generated motions are sometimes janky compared to Mixamo's hand-crafted clips
- Best for unique/creature motions. Use Mixamo for standard locomotion.

---

## Path C (rare) — Custom rigging via SkinTokens / RigAnything / MagicArticulate

Use this when:
- You want a non-humanoid creature rigged (Mixamo can't do quadrupeds)
- You don't need Mixamo's specific skeleton naming
- You'll handle animation in Blender or write your own animation system

The output is a rigged GLB; pose it manually in Blender or feed motions from a custom system. **You will not get a free 2500-clip motion library** — that's the tradeoff.

### Path C steps (all in our existing tools)
1. Preprocess as Path A
2. Run a rigger:
   - **RigAnything** (WSL): `sh scripts/inference.sh <input.glb> 1 8192` → simplest, fastest
   - **SkinTokens** (Windows venv): `python demo.py --input <input.glb> --output <out.glb>` → best skinning quality
   - **MagicArticulate** (WSL `magicarti-flash`): skeleton-only output
3. Pose / animate manually in Blender (open the rigged GLB, switch to Pose Mode)
4. Export animated FBX, then bake sprites as Path A step 4-5

---

## Picking parameters

### `--angles`
- `4` — N/E/S/W only. Smallest atlas. Good for retro top-down games.
- `8` — Adds NE/SE/SW/NW. Good for isometric or 3/4 perspective.
- `16` — Smooth turning animation. Atlas gets large; consider lower `--res`.
- `1` — Single facing only (front view). Good for static portraits.

### `--frames`
- `8-16` for walk cycles, idle, simple attacks.
- `24-32` for smoother motion (matches AnimateAnyMesh's 16-frame output if you want repeats).
- `1` for static character sheets (no animation, just turnaround).

### `--res`
- `128` — pixel-art games at modest scale.
- `256` — modern retro games, clear sprite detail.
- `512` — high-res 2D games or modern UI portraits.
- `1024` — only if you'll display the sprite at near-full resolution.

### `--ortho`
**Almost always use this for sprites**. Perspective lenses cause near/far distortion that looks weird across angles. Ortho gives consistent silhouette regardless of camera distance.

### `--elevation`
- `0` — pure side view (Castlevania-style).
- `15-25` — 3/4 view (common in 2D RPGs, isometric).
- `45-60` — top-down (Hyper Light Drifter, Stardew Valley).
- `90` — straight-down view (Hotline Miami).

---

## Verifying outputs

After each step, sanity-check before going further:

| After... | Sanity check |
|---|---|
| Meshy generation | Open `previews/<name>/_tmp/view_0.png` — does the mesh look like the input image? |
| Preprocess | Run `render_preview.py` on the preprocessed GLB — should look identical to original |
| Rigging | Run `render_rig.py` — bones should follow the body, head separate from torso, limbs articulated |
| Animation | Open the FBX in Blender and scrub timeline — does the motion match the prompt? |
| Bake | View `manifest.json` — should list all expected angles × frames |
| Pack | Open `sheet.png` — visually inspect for missing/black cells |

---

## When something fails

**Meshy returns weird mesh:** It happens with non-humanoid creatures. Use Trellis2 instead:
```powershell
& D:\assets\animators\Trellis2\venv\Scripts\python.exe D:\assets\animators\Trellis2\example.py
```

**Preprocess produces bad geometry:** Try `--quad-remesh` for organic shapes (loses UVs, will need re-textured), or skip preprocess entirely if the mesh is already game-ready.

**RigAnything produces bad skeleton:** Try SkinTokens (Windows). If both fail, fall back to SKAVA in Blender for manual marker placement.

**AnimateAnyMesh ignores the prompt:** Try simpler prompts ("the object walks", "the creature attacks"). The model has limited vocabulary; stick to physical action verbs.

**Sprite bake produces black/empty frames:** Camera framing issue. Run with `--padding 1.5` for more space, or check that the mesh isn't far from origin (preprocess centers it; un-preprocessed meshes often aren't).

**Atlas frames don't align:** Use `--crop` flag in `pack_sheet.py` — pads each cell to the largest tight-cropped cell size.
