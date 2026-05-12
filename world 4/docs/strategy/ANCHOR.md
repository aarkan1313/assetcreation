# Anchor Demo

> The smallest, most-magical version of World 4. The floor we don't go
> below. Every axis expansion has to keep the anchor demo working — if it
> breaks the anchor, the expansion is wrong.

## What the anchor demo is (v2 — current)

A re-creation of the original "magical version" we built early in World 1:
a mountainous heightmap with a valley and river, distinct sub-regions
showing different materials, walkable in 3D, viewable in iso and topdown.

- **One real DEM crop.** USGS1m Blue Ridge (Shenandoah, VA) tile —
  256m × 256m at 1m native resolution. See `pipeline/pick_dem_crop.py`.
- **Three PBR texture slots, mixed real + ComfyUI.** Currently
  `scrub_dense` (real-ortho-derived from W3's `_soft_composite` pipeline),
  `tundra_lichen` (ComfyUI-generated), `rocky_slope` (real-ortho-derived).
  Bound by `pipeline/write_material_tres_v2.py` → `worlds/anchor/material.tres`.
- **Slope-blended in the shader.** `shaders/terrain_anchor_v2.gdshader`
  computes slot weights from the surface normal's Y component at every
  fragment. No procedural splat texture, no macro layer, no per-pixel
  baked composite — the shader handles all blending.
- **Safety guardrails in the shader** (hard-won, see
  `ANCHOR_BUILD_NOTES.md` black-speckle lesson): `luma_floor()` on each
  albedo, `ao_floor` clamping AO, NaN guards on blend weights, clamped
  NORMAL_MAP output, `SurfaceTool.generate_tangents()` on the mesh.
- **One Godot scene with 3 cameras.** 3D walk, 2.5D iso, 2D topdown —
  all looking at the same world at the same scale. Hotkey toggles
  between them. Single shader profile; per-view shader stripdown is
  an axis 4 expansion.
- **Water plane.** Sized to actual below-threshold region (computed
  at scene load), not the whole world. Custom water shader with
  fresnel + animated normals.

## What it intentionally is NOT

- **Not streaming.** One world, one heightmap, one bundle.
- **Not multi-biome.** Different regions show different materials via
  the splat, but there's no "biome layout" schema or per-tile material
  override. (One biome, internal variation.)
- **Not view-tuned.** All 3 cameras share the same shader. Looking
  noisy in topdown? That's expected — view-axis-1 expansion fixes it.
- **Not a game framework.** No characters, props, gameplay systems.
- **Not modular yet.** One concrete thing. Modularity is what we extract
  from it later, not design upfront.
- **Not LLM-driven.** A human runs it.

## Why we anchor here

W3 broke because we built infrastructure on top of an *idea* of the
magical version without re-proving it. Every session drifted further.
The anchor demo is the contract: **if it doesn't work, nothing else
matters; if it does work, we have a known-good base to expand from.**

The anchor demo is the regression check for every axis expansion. If
expanding an axis breaks the anchor, the expansion is wrong.

## Status

**WORKING — verified 2026-05-11.** See `ANCHOR_BUILD_NOTES.md` for the
full build log: decisions made, what worked, what didn't, known issues.

### Resolved decisions

- **DEM region:** USGS1m_-78.3520_+38.5147_-78.1980_+38.6500.tif
  (Shenandoah / Blue Ridge area, ~982m relief, 1m native). Anchor crop
  is the 232m-relief slope at offset (1536, 6336).
- **Texture set:** all 5 slots from W3's temperate_forest kit
  (grass / dirt / rock_light / rock_dark / snow). Snow slot is dense
  forest undergrowth — used as the "highest elevation" material.
- **Splat rule:** D8 drainage + height + slope, 5 zones, gaussian
  smoothed, power-normalized. Worked first try.
- **Water threshold:** `min_elev + 25m` — covers ~2-3% of terrain.
- **World scale:** 256m × 256m at 1m/px = 256×256 px heightmap.

### Known issues going forward

- Water shader reads dark from topdown angle (fresnel minimum). Mostly
  cosmetic; fixable in a water-polish sub-experiment under axis 4.
- Iso view depends on sun direction vs slope orientation; current crop's
  dominant slope happens to face away from the sun, leaving the iso
  view darker than walk/topdown. Either pick crops with sun-facing
  slopes or compute the sun direction from the crop.

### Definition of done — verified 2026-05-11 (after polish pass)

1. ✅ `python build_anchor.py` produces a complete bundle in
   `worlds/anchor/` in one command.
2. ✅ Opening the Godot project and running `anchor.tscn` displays
   the terrain.
3. ✅ Hotkey switches between 3 cameras (1/2/3 keys; walk has WASD
   + mouse-look, Shift = sprint).
4. ✅ All 3 views show the same world with the same materials in the
   same places. Heightmap is continuous by construction.
5. ✅ Water fills low areas — water plane sized to actual underwater
   region, transparent, reads as water from all angles.
6. ✅ Visual quality matches M11 fourway — per-pixel material
   variation, biplanar projection prevents slope-stretching, baked
   macro carries detail at distance.

**Anchor demo is the regression baseline for all axis expansion.**

## What the anchor demo unlocks

Once it's working, axis expansions can start. See `AXES.md`. The anchor
stays running as the regression check — every axis change has to keep
the anchor demo passing its 6 done-criteria.

## What we learn from building it

- Whether the texture flow (W3 catalog + maybe a few fresh) is workable
  end-to-end without the banned transition workflows
- Whether the height+slope splat is good enough or needs to be more
  sophisticated
- Whether the M11 render path (5-slot shader + per-bundle .tres + macro
  preview) carries cleanly into a fresh Godot project
- Whether "vanilla PBR only, no transition-workflow textures" is the
  right line, or if we're missing capability we'll need to rebuild
  (axis 6 — Textures — covers re-figuring-out the blending workflow)
- What chunk size, world scale, and view setup feel right at human scale

Those learnings inform what goes into the axes' "next experiments" and
what gets promoted from the wishlist.

## Links

- `ANCHOR_BUILD_NOTES.md` — what we actually built + lessons learned
  (the "working log" companion to this doc)
- `AXES.md` — 6 axes of expansion (scale / biome / source / view /
  decoration / textures) + principles
- `WISHLIST.md` — parking lot of ideas not yet promoted to axes
- W3 carry-forward inventory: `D:/assets/W4_KICKOFF_2026_05_11.md`
