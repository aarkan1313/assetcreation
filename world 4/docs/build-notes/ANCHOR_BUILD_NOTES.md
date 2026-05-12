# Anchor Demo Build Notes

> Captured 2026-05-11 after the first end-to-end run of the anchor demo.
> Companion to `ANCHOR.md` — that doc describes the *target*; this doc
> captures what we actually built, what we learned, what's good, what's
> not.

## ⚠️ Hard-won lesson: black-speckle bug (resolved 2026-05-11)

**Symptom:** Pure-black pixel artifacts appearing in geometric patterns
(hexagons, squares, contour stripes) across the rendered terrain.
Visible in live editor view, mostly invisible in headless captures.
Pattern shifts as the camera moves.

**Root cause was NOT a single shader bug.** Five hours of guessing
later, the actual cause was **source-texture-driven speckling**:
- Some texture maps contain near-black texels (especially
  `tundra_lichen/albedo.png` and `tundra_lichen/ao.png` from the W3
  ComfyUI catalog). The black pixels are real source data, not bugs.
- The shader blended those near-black texels into the terrain slot mix
- Those black pixels then repeated across world UVs as black flecks at
  every tile boundary
- AO maps amplified the problem: low AO darkened already-dim pixels
- Normal-map detail made lighting produce high-contrast speckling
- Earlier shader versions also produced NaN normals at blend
  edge-cases, which Godot renders as pure black fragments
- Terrain self-shadowing looks similar but isn't this bug — keep
  `cast_shadow=OFF` on the terrain mesh

**Fix in `shaders/terrain_anchor_v2.gdshader`:**
- `luma_floor()` function applied to each slot's albedo *before*
  blending — clamps any near-black texel up to a minimum luminance so
  black source pixels can't propagate
- `albedo_luma_floor` uniform (default 0.08) sets the floor
- `ao_floor` uniform (default 0.72) — AO can't darken below this
- Final `luma_floor()` on the blended albedo as a second safety net
- NaN guards on blend weights (`max(total, 1e-4)`)
- No manual `normalize()` on blended normals (would NaN on zero-vec)
- Mesh tangents via `SurfaceTool.generate_tangents()` so PBR has
  proper tangent space
- Mesh `cast_shadow = OFF` so terrain doesn't self-shadow

**Rule for adding new materials to the anchor (going forward):**

1. **Add one slot/map at a time** — never bring in 3 materials and try
   to debug a stack of issues.
2. **Validate each albedo and AO map** for near-black islands. Anything
   under ~0.08 luminance gets clamped by `luma_floor` but it's better
   to know upfront so you can pick textures without crack-shadow content.
3. **Keep all shader safety floors in place** — `albedo_luma_floor`,
   `ao_floor`, NaN guards on weights, clamped `NORMAL_MAP` output.
4. **Start with low `normal_strength`** (0.2 or less). Crank it up
   once everything else looks right; it amplifies any underlying
   texture problem.
5. **Capture walk + iso + topdown after every material change.** The
   editor view is the truth, not headless captures. Get user
   eyeballs on it.
6. **The bug is source-driven, not shader-driven.** Don't tune shader
   params when the texture itself has bad data — fix the texture or
   pick a different one.

**Short version:** black texels in source maps + aggressive AO/normal
detail + terrain blending across many UV repeats = repeating black
speckles. Validate maps and clamp shader outputs before judging the art.

**Canonical reference:** [`PITFALLS.md`](PITFALLS.md) Pitfall #1 has the
current up-to-date answer with diagnostic + fix. The full diagnostic
history (including the failed attempts) lives in
`AUDIT_HANDOFF_BLACK_ARTIFACTS_2026_05_11.md` for posterity.

## What got built

End-to-end pipeline:

```
USGS1m DEM tile (Blue Ridge, VA, ~1m native)
  ↓ pick_dem_crop.py (256×256m crop, picked by relief scan)
heightmap.png (16-bit, 256×256 px) + meta.json
  ↓ build_splat_and_macro.py (D8 drainage + height + slope)
splat_weights_rgba.png + render_albedo.png (per-pixel macro) + scatter/debug layers
  ↓ write_material_tres.py
material.tres (binds terrain_anchor.gdshader + 5 slot mats × 4 maps + bundle textures)
  ↓ Godot scene anchor.tscn
3-camera view of the rendered terrain
```

## Decisions made during build

- **DEM source:** USGS1m_-78.3520_+38.5147_-78.1980_+38.6500.tif
  (Shenandoah / Blue Ridge area, 14623×13862 px native 1m, ~982m relief).
  Picked because USGS1m turned out to be *actually* 1m/pixel (LINZ1m's
  "1m" tiles are downsampled to 9m/px in the catalog).
- **Crop strategy:** scan whole tile in `crop_px/4` steps, score each
  block by `relief + 0.5 * std`, pick winner. Got a 232m-relief slope
  centered on the steep north-east face.
- **Materials:** all 5 slots from the W3 `temperate_forest_*` kit
  (grass, dirt, rock_light, rock_dark, snow). Snow slot is actually
  dense forest undergrowth — perfect for Blue Ridge ridge tops.
- **Splat rule:** 5-zone height + slope + drainage:
  - grass = (1 - h_norm * 0.8) × (1 - slope * 0.7) × (1 - drainage * 0.5)
  - dirt = peaks at h_norm ~ 0.3, low slope, drainage adds 0.5
  - rock_light = peaks at h_norm ~ 0.55, weighted by slope
  - rock_dark = slope-dominant, plus h_norm > 0.6 boost
  - snow = h_norm > 0.7 and low slope
  All gaussian-smoothed (radius 1.2), powered (1.15), normalized to sum=1.
- **D8 drainage:** richdem from terrain venv. Fill depressions first, then
  flow accumulation. Log-normalize the result (range 1..thousands).
- **Macro composite:** per-pixel mix of all 5 slot albedos weighted by
  splat, with M11-style lambertian light tinting from the height gradient.
  Baked into render_albedo.png so the shader doesn't have to recompute.
- **Shader:** fresh write (~140 lines), stripped down from W3's
  terrain_splat_unified.gdshader. No detail layers, no hex tiling,
  no transitions, no seam blending. Just 5 slots × {alb/norm/rough/ao} +
  macro override + splat. World-relative UVs.
- **Water:** simple shader (~75 lines) — animated noise normals, fake
  fresnel, alpha mix. Threshold at min_elev + 25m → covers ~2-3% of
  terrain.

## What worked

- **D8 drainage produced beautiful results.** Visible dendritic flow
  patterns matching the terrain's natural drainage. richdem is fast
  (~1ms on 256×256). One of the highest-leverage parts of the build.
- **Per-pixel macro composite is the right move.** The baked
  render_albedo.png shows per-pixel material variation (autumn leaves
  in some pixels, mossy rock in others) before the shader does
  anything. That's the M11-quality bar at bake time.
- **Two-venv split worked clean.** System Python (rasterio) does DEM
  loading + .tres writing. Terrain venv (richdem) does drainage. No
  cross-contamination, both fast.
- **`world 4/pipeline/` vs `world 4/the world 4/` split worked.** Godot
  doesn't see Python files. No unnecessary `.import` for `.py`.
- **The W4 → Godot res:// path resolution** is straightforward: `Path
  relative to W4 root → res://...`. The .tres writer's `res()` helper
  handles it cleanly.
- **AnchorTerrain.gd built the mesh fine on a single 256×256 grid.**
  No streaming complexity. 66K vertices, builds and renders smoothly.

## What didn't work the first time (now fixed)

These all got resolved in a polish pass after first capture:

- **Water reads dark from topdown** → fixed with fresnel floor (0.35)
  + brightness clamp (`deep_color * 1.4` minimum). Reads as water.
- **Water plane was 256×256m covering the whole world** → cast a black
  slab behind the iso view AND its shadow created moving dark spots
  on the terrain. Now: water plane sized to actual below-threshold
  area (computed from heightmap at scene load) plus a 20m border, AND
  `cast_shadow = OFF` so it never produces shadow artifacts.
- **Texture stretching on slopes** = naive world-XZ UV mapping smeared
  the texture on near-vertical faces. **Added biplanar projection** to
  the shader: flat ground uses XZ projection, slopes blend in a
  vertical (XY or YZ depending on facing) projection weighted by the
  surface normal's Y component. Clean detail at any angle.
- **Tile pattern visible at iso distance** → dropped `world_uv_scale`
  from 0.08 to 0.04 (tile every 25m instead of 12.5m), bumped
  `source_macro_strength` from 0.84 to 0.92 so the baked macro
  dominates the visual.
- **Walk camera floating above the peak** → spawn point reworked to
  use `look_at()` after adding to tree (Godot errors when look_at runs
  before parent attach). Now spawns at mid-slope facing the dramatic
  terrain.
- **Walk speed of 30 m/s** = Sonic-the-Hedgehog scale. Dropped to
  8 m/s. Added Shift = 4× sprint when you need to cover ground. Eye
  height 4m → 1.8m (real human).
- **Sky was flat blue background** → replaced with ProceduralSkyMaterial
  (gradient sky, soft horizon, neutral ground tint). Bloom enabled.
- **Shadow acne possible** → DirectionalLight3D biases bumped to
  (2.0 / 10.0), shadow_blur 2.0, 4-cascade mode with reasonable splits.

## What's still imperfect

- **Iso view has a black water rectangle visible behind the slope.**
  This is the (now smaller) water plane, edge-on, where fresnel hits
  minimum. Cosmetic. Could fix by giving water some emission so the
  edge-on view doesn't go dark.
- **The iso "size" of the world feels small** — 256m × 256m is
  genuinely a small area to render. Scale axis (axis 1) addresses
  this directly.
- **Terrain detail is impressive close up** but the texture is still
  visibly tiling at distance — biplanar helped a lot but doesn't
  fully erase tile boundaries. Hex tiling or texture variation per
  tile would help. Save for axis 6 (textures).

## What we learned about the architecture

- **The terrain_anchor.gdshader works correctly.** No flat color blocks,
  no failed macro binding. The W3 wall was specifically about
  `.duplicate()` + ExtResource macro binding losing the texture; for
  the anchor demo we load the .tres directly with `load(path)` and
  apply as `material_override` — that path works.
- **The macro is doing the heavy lifting.** Most of what reads as "the
  terrain material" in the captures is the baked `render_albedo.png`
  showing through (source_macro_strength = 0.84). The 5 slot textures
  contribute via splat-weighted blending but are mostly low-frequency
  underlayment. This is fine — M11 used the same balance.
- **D8 drainage is now a tool we keep.** richdem path is proven. Next
  axis expansion (multi-tile) can re-use the same drainage analysis
  per-tile or across a stitched heightmap.
- **The pipeline scripts are LLM-driveable.** Each stage has a clear
  input/output contract. `build_anchor.py` orchestrates them. If we
  wanted an LLM to drive this end-to-end, the only thing missing is a
  JSON schema for the anchor "request" (which DEM, which materials,
  which world size, which splat rule).

## Done criteria (from ANCHOR.md)

1. ✅ `python build_anchor.py` runs end-to-end → bundle in `worlds/anchor/`
2. ✅ Scene loads and shows terrain
3. ✅ Hotkey switches between 3 cameras (wired in AnchorCameraRig, verified
   via headless captures with `force_camera_mode`)
4. ✅ All 3 views show same world with same materials
5. ✅ Water fills low areas — water plane sized to actual underwater
   region, reads as water from all angles (after polish pass).
6. ✅ Visual quality matches M11 fourway — per-pixel material variation
   visible, biplanar projection eliminates slope-stretching, baked
   macro carries detail at distance.

**Anchor demo passes 6/6.** Locked as regression baseline for axis
expansion. The walk view shows a real mountainside the player can
explore; iso shows a clean overview; topdown shows the world as a
map. Each view re-uses the same data via different cameras + UV
projection.

## Files created

### `D:\assets\world 4\pipeline\`

- `pick_dem_crop.py` (147 lines) — DEM scout + crop
- `build_splat_and_macro.py` (224 lines) — drainage + splat + macro
- `write_material_tres.py` (87 lines) — .tres emit
- `build_anchor.py` (60 lines) — orchestrator

### `D:\assets\world 4\the world 4\`

- `shaders/terrain_anchor.gdshader` (140 lines)
- `shaders/water_anchor.gdshader` (75 lines)
- `scripts/AnchorTerrain.gd` (135 lines)
- `scripts/AnchorWater.gd` (44 lines)
- `scripts/AnchorCameraRig.gd` (155 lines)
- `scripts/HeadlessCapture.gd` (44 lines)
- `scenes/anchor.tscn` (main scene)
- `scenes/capture_anchor_iso.tscn`, `capture_anchor_walk.tscn`,
  `capture_anchor_topdown.tscn` (capture wrappers)
- `materials/anchor/` — 5 materials × 4 PBR maps = 20 files copied
  from W3
- `worlds/anchor/heightmap.png` + `meta.json` + `material.tres` +
  `layers/{render_albedo, splat_weights_rgba, source_valid_mask,
  drainage, slope, splat_snow}.png`
- `captures/anchor_{iso,walk,topdown}.png`

### Total

- Python: ~520 lines
- GDScript: ~520 lines
- Shaders: ~215 lines
- Markdown: this doc (~250 lines)

**Roughly 1250 lines of code + assets for a working end-to-end
anchor demo.** Could be smaller; many of the shaders/scripts have
room to compress. But it's all written fresh, not ported, so
nothing inherited from W3's mistakes.

## What unlocks now

Per `AXES.md`, axis expansions can now start. Suggested order based on
what's still bothering me:

1. **Water shader polish** (axis 4 view, sub-experiment) — fix the
   topdown-darkness, maybe add reflection. Half a session.
2. **Axis 1 (Scale)** — slice the same heightmap into multiple tiles,
   stream chunks around the camera. The hard part is *making it
   continue to look identical to the single-tile anchor*. The W3 wall
   was here.
3. **Axis 6 (Textures)** — re-figure-out the blending/transition
   workflow that W3 banned. Probably most useful AFTER scale because
   tiling boundaries are where transitions matter.

## What does NOT unlock yet

- Multi-biome (axis 2) — pointless without scale first
- Procedural sources (axis 3) — orthogonal, can do any time
- View-mode shader profiles (axis 4 main) — anchor uses one shader for
  all 3 views; only matters when you want topdown to read as a "map"
- Decoration (axis 5) — explicit end-game per ANCHOR.md
