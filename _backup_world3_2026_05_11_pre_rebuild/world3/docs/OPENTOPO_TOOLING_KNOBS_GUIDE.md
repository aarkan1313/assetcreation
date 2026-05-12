# OpenTopo Tooling And Knobs Guide

This is the short control-panel guide for the OpenTopography branch. Use it
when choosing what to pull, how large to make it, what quality knobs matter,
and what artifact should come out of the pipeline.

## Current Rule

Build the richest source stack first, validate it, then package smaller runtime
exports from that master. Do not throw away precision early.

Recommended tiers:

| Tier | Purpose | Formats |
|------|---------|---------|
| Source | Raw evidence from OpenTopo | GeoTIFF, LAZ/LAS, COG/VRT downloads |
| Master stack | Lossless aligned working data | float32 GeoTIFF, compressed/tiled GeoTIFF, optional Zarr later |
| Review stack | Godot-visible QA | 16-bit height PNG, 8/16-bit layer PNGs, `meta.json`, `stack_manifest.json` |
| Runtime pack | Game delivery | chunked height PNGs, compressed color textures, masks, normal/roughness/biome maps |

A megastack can absolutely be compressed after creation. The quality-safe path
is to keep lossless master layers, then export compressed runtime packs after
we know which layers matter.

## Data Combos

| Combo | What It Gives | Best Use | Main Limit |
|-------|---------------|----------|------------|
| DEM/DTM only | Bare terrain height | base mesh, collision, slope, drainage | no real color or vegetation |
| DSM only | surface height | canopy/building silhouette QA | bad as player ground unless intentional |
| DTM + DSM | terrain plus surface height | vegetation masks, obstruction, canopy density, surface-vs-ground QA | needs matched grids/datums |
| DTM + orthophoto | real ground texture over real terrain | beautiful real-place scenes, baked texture source | cliffs stretch in top-down imagery |
| DTM + RGB + NIR + CHM | color plus vegetation signal | strongest fused scene/material authoring stack | rare, heavy, alignment-sensitive |
| LAZ + DTM | raw point evidence plus ground | custom DSM/CHM, density, class masks, point color | expensive processing, tile-size sensitive |
| GEDI + DEM | coarse canopy/height metric | regional forest structure | coarse raster, not local tree placement |
| bathymetry + land DEM | land/ocean elevation | islands, coast, world maps | too coarse for local walking terrain |

Decision rules:

- Use DTM/DEM for the playable ground.
- Use DSM as a surface/vegetation/building layer, not as default ground.
- Use `DSM - DTM` for canopy/surface masks.
- Use orthophoto only when we want real color.
- Use no-color stacks when we want procedural/fantasy material control.
- Use LAZ when we need the deepest evidence, but start with small AOIs.

## Acquisition Knobs

| Knob | Where | Effect |
|------|-------|--------|
| Dataset | `opentopo_fetch.py` | Chooses DEM/DSM/bathy/GEDI product. Biggest quality decision. |
| AOI / bbox | `--bbox`, `--center`, `--extent-km` | Controls size, API eligibility, and file weight. |
| Tile grid | `fetch_opentopo_tile_grid.py` | Lets one area exceed a single-call cap. |
| Overlap | `fetch_opentopo_tile_grid.py` | More overlap improves seam QA and blending, costs data. |
| API key env | `opentopo/config/opentopo.env` | Required for API products. Never paste key into docs. |
| Public COG fallback | `opentopo_fetch.py` COG products | Good for broad global data without API jobs. |

Important caps:

- `USGS1m` is the high-detail U.S. workhorse but has a `250 km2` per-request
  cap in our current docs.
- Four `USGS1m` calls can make a large high-detail mosaic, but the practical
  limit is disk, RAM, Godot mesh density, and review texture size.

## Processing Knobs

| Knob | Script | Effect |
|------|--------|--------|
| Output size | `build_world.py`, stack builders | Heightmap/layer pixel size. Higher improves texture/layer clarity, not source resolution. |
| Target CRS/cell size | mosaic builders | Determines real-world alignment and resampling cost. |
| Reducer | `build_opentopo_mosaic*.py` | `mean` smooths DEM seams; `max` can preserve DSM surface peaks. |
| No-data repair | `build_world.py` | Fills render holes without pretending they are source-valid. |
| Fill buffer | `build_world.py` | Creates mask for blending repaired areas. |
| Cliff threshold | `build_world.py` | Marks top-down texture stretch risk on steep slopes. |
| Hillshade azimuth/altitude | layer exporters | Changes perceived landform in procedural review textures. |
| Surface-height max | DTM/DSM stack builder | Controls canopy/vegetation mask contrast. |
| Material ramp | review layer exporters | Sets no-color terrain look without changing source data. |
| Valid-footprint crop | `build_opentopo_textured_master_stack.py` | Removes empty source bounds before Godot export. |
| Texture fill distance | `build_opentopo_textured_master_stack.py` | Extends nearby real orthophoto pixels into render-facing edge gaps. |
| Coverage/seam QA rasters | `export_heightmap_review_layers.py` | Adds tile coverage and seam delta overlays to no-color scenes. |

Quality warning: increasing output PNG size after a coarse source helps Godot
display smooth layers, but it does not invent real terrain detail. It is still
worth doing for masks, review texture clarity, and non-blocky camera views.

## Texture And Material Knobs

| Knob | Script/Scene | Effect |
|------|--------------|--------|
| Crop size meters | `build_opentopo_tileable_texture.py` | Real-world scale of reusable ground material source. |
| Variant count | `build_opentopo_texture_variant_atlas.py` | More unlike tiles reduce obvious repetition. |
| Soft composite size | `finish_opentopo_soft_materials.py` | Bigger final sheets hide seams better and cost VRAM. |
| Hex/detail shader | `tileable_finished_material_review.tscn` | Breaks square repetition in Godot. |
| Hard transition review | `biome_tile_transition_review.tscn` | Shows unlike OpenTopo and regular biome tiles touching with no blend. |
| Downscale/pixelate/filter | texture scripts | Can stylize real ground when photoreal scale breaks. |
| Material masks | DTM/DSM/orthophoto stack | Slope, canopy, wetness, rock, and fill masks drive shader blends. |

Use the full map as a macro texture when it looks good from above. Use tileable
materials when the camera will travel across repeated ground at close range.

## Godot Knobs

| Knob | Where | Effect |
|------|-------|--------|
| Mesh subdivisions | review `.tscn` `Terrain.subdivisions` | More geometry detail; expensive above 1024. |
| Height scale | `Z` / `X` in `TopoReview.gd` | Review-only vertical exaggeration. |
| Layer cycling | `L`, `Tab`, `[`, `]` | Compare source, derived, and QA layers. |
| Camera presets | `1`, `2`, `3`, `R` | Fast iso/top/low review positions. |
| Capture wrapper | `capture_*.tscn` | Real Godot screenshot path; avoid old headless scene validation. |

Normal launch pattern:

```powershell
$args = @("--path", "D:/assets/world3", "res://toporeview/<scene>.tscn")
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -Wait -PassThru
"EXIT=$($p.ExitCode)"
```

## Recommended Workflows

### 1. Same-Type Large Mosaic

Use when one product is too large for one call.

Output: stitched DEM/DTM, coverage mask, seam delta, heightmap, Godot scene.

Core docs:

```text
world3/docs/OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md
world3/docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md
```

### 2. Cross-Type Megastack

Use when multiple aligned layers describe one place.

Preferred layer order:

```text
DTM/DEM base
DSM or LAZ surface
DSM-DTM / CHM
orthophoto RGB
NIR / false color
slope / roughness / hillshade
source-valid / fill / seam QA
material masks
```

Output: lossless master stack, `stack_manifest.json`, Godot review package,
then optional compressed runtime pack.

### 3. No-Color Terrain Intelligence Stack

Use when color is unavailable but DTM/DSM or GEDI exists.

Output: DTM heightmap plus procedural terrain texture, surface-height layer,
forest/canopy mask, rock/slope mask, wetness/valley mask, QA layers.

This is the next implementation target using:

```text
D:/assets/world3/opentopo/raw/cog/tcf_bc_coast_canada/
```

### 4. Reusable Real Ground Material

Use when top-down real ground looks excellent as a texture source.

Output: source crop, tileable variant atlas, soft composite, Godot material
review.

Core doc:

```text
world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md
```

### 5. Current Master Stack Pair

Use this when we need one real-textured example and one big procedural/no-color
example.

Textured:

```text
Gloss Mountain Textured Master Stack
DEM + orthomosaic
0.62 x 1.08 km review scene
real orthophoto, raw reference layer, fill mask, cliff mask
```

No-texture:

```text
Zion USGS10m No-Texture Master Stack
4 API tiles, 36.80 x 36.88 km
procedural sandstone review material
coverage_count and seam_delta QA layers
```

Canonical audit and commands:

```text
D:/assets/world3/docs/OPENTOPO_MASTER_STACKS_AUDIT.md
```

Rejection rule from this pass: do not select a master candidate only because the
nominal bounding box is large. First inspect valid-source coverage. Rainier
`USGS1m` was rejected despite high resolution because only about `7.4 percent`
of the target grid was valid.

### 6. Biome-To-Biome Transition Review

Use when judging whether unlike materials can sit beside each other.

Output: hard-adjacency Godot review, OpenTopo close strip, regular biome-kit
close strip, and notes on which pairs need transition bands.

Core doc:

```text
D:/assets/world3/docs/OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md
```

Rule: this is a failure-finding scene. Do not judge a material pair by whether a
hard border looks shippable. Judge which normalization, transition material, or
blend mask is required.

## Compression Plan For Megastacks

Authoring should be generous:

- Keep raw source files untouched.
- Write aligned master rasters as float32 tiled GeoTIFF with `DEFLATE` or `ZSTD`
  when available.
- Keep masks as uint8/uint16 where possible.
- Keep a manifest that records source CRS, bounds, nodata, resampling, min/max,
  and every generated layer.

Delivery should be selective:

- Height: 16-bit PNG or chunked 16-bit PNG tiles.
- Color: compressed PNG/JPEG/WebP depending on whether loss is acceptable.
- Masks: packed RGBA PNG where channels are independent masks.
- Terrain normal/roughness: generated from the delivery height or packed masks.
- Large worlds: chunked tiles plus a lower-res overview texture.

Do not compress away source truth until a Godot review scene and QA layers look
right.
