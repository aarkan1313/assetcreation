# Axes of Expansion

> Once the anchor demo works, W4 grows by expanding along axes — never by
> committing to a fixed sequence of chapters. Each axis is independent;
> they can be expanded in any order based on what unblocks the most.
>
> **The rule:** an axis expansion is only valid if the anchor demo still
> passes its done-criteria after the expansion lands. If an expansion
> breaks the anchor, the expansion is wrong.

## Principles (apply to every axis)

These three outrank breadth of features. When forced to choose, choose
in this order:

1. **Quality** — visual bar is M11 fourway or better. Never ship something
   that looks worse than the anchor demo.
2. **Performance** — 60fps target in 3D walk view. The streaming axis
   bounds active load to what's near the camera, so total feature count
   doesn't directly cost perf — but in-view complexity does.
3. **Organization** — one source of truth per concern. No 200-doc sprawl.
   When two docs reference shared concepts, edit one and delete the other
   rather than risking drift.

KISS, YAGNI, ease of use, modularity are how we *achieve* these three —
not separate principles.

## How to read this doc

Each axis has three things:

- **Current state** — what level the axis is at right now (anchor demo,
  first expansion, etc.)
- **Next experiment** — the smallest meaningful step forward, with its
  exit criterion. Not a commitment to do it next; just the option on
  the table.
- **Notes** — anything we've learned, choices we want to remember, or
  open questions for that axis specifically.

When an axis expansion lands, we delete the old version of this file and
write a new one rather than editing in place — keeps doc-state consistent.

---

## Axis 1: Scale

**What this axis controls:** how much world is rendered at once. Anchor =
one bounded heightmap. Top of axis = streaming infinite-ish world that
loads as the camera moves.

**Current state:** *closed for current scope (2026-05-11).* 1024m × 1024m
world, 4×4 = 16 tiles at 256m each, scaled from one continuous Blue
Ridge DEM crop. `terrain_scale_v1.gdshader` (unshaded with manual
lighting) replaces the lit PBR pipeline at this scale — see
`PITFALLS.md` #3. Radius paging is on by default (3×3 window). Per-tile
build cost: 77ms wall-clock (~4ms main-thread) thanks to async
`WorkerThreadPool` mesh build + persistent unloaded-tile cache. 2
hitches per 200s autowalker (≈hitch-free). Full SCALE_BUILD_NOTES.md
captures what shipped + what's deferred.

**Next experiment (when ready):** Real-game scale. Bump world to 4-8 km
on a side (16×16 to 32×32 = 256-1024 tiles), implement LOD rings
(different mesh density per ring around camera), DEM stitching across
tile boundaries (multiple source DEMs in one world). See `WISHLIST.md`
"Axis 1 (Scale) follow-ups" for the full list. Not currently ranked
above Axis 2 wiring in ROADMAP.

*Original exit criterion (met):* walk the camera across the world,
chunks load/unload seamlessly, no visible seams at tile boundaries
(source is continuous — slicing one heightmap, not stitching N).

**Notes:**
- The W3 lesson: never let adjacent tiles have independent
  elev_min/elev_range. ONE source, sliced. **W4 followed this.**
- **Cross-tile sampling via shared world heightmap** is what eliminates
  seam discontinuities in finite-difference normals at tile borders.
  See SCALE_BUILD_NOTES.md and TileTerrain.gd's `_sample_height` for
  the implementation pattern.
- **Chunk size is view-dependent.** 3D walk wants smaller chunks (~64m)
  for detail+streaming responsiveness. 2.5D iso wants medium (~128m).
  Topdown wants large (~256m+). The streaming system needs to know which
  view it's serving. (First expansion picked 256m uniformly for
  simplicity; per-view is future work.)
- Far-away tiles get unloaded — performance scales with view radius, not
  total world size. (Mechanism shipped, disabled until async build
  lands.)

---

## Axis 2: Biome

**What this axis controls:** how many distinct material/texture
treatments appear across the world. Anchor = one material set varying
internally by height+slope. Top of axis = many biomes, possibly
auto-assigned from DEM features.

**Current state:** *first expansion landed, 2026-05-12.* 5 biomes
shipped end-to-end: textures (48 maps), materials (4 new
`material_<biome>.tres` + the existing forest), and per-tile assignment
in ScaleWorld. The scale_demo 4×4 world now renders 4-5 biomes with
hard borders at every tile boundary. See
`build-notes/BIOME_KITS_BUILD_NOTES_2026_05_12.md` (textures) and
`build-notes/AXIS2_WIRING_BUILD_NOTES_2026_05_12.md` (wiring).

**Next experiment (when ready):** Procedural biome assignment from
heightmap features (mean elevation, slope, aspect) instead of the
hand-coded 4×4 layout. Becomes meaningful at larger world sizes.
Currently parked — soft transitions (Axis 6) is the higher-impact
next move because biome seams are visibly ugly right now.

*Original exit criterion (met):* 2-3 distinct biome packs across
tiles, geometric continuity preserved (no cliffs), texture
transitions visible (and seamed — which is what justifies Axis 6).

**Notes:**
- Biomes are *style packs over geometry*, not generators of it. Never
  go back to per-biome height generators (the W3 wall).
- **Plan-first approach** (2026-05-11): we pin the biome list + texture
  variety doc BEFORE generating any new textures. This is so the texture
  generation session has a concrete target and we can ballpark cost
  before committing pipeline time.
- Soft blending at tile borders is its own sub-experiment, not required
  for first biome activation.

---

## Axis 3: Source

**What this axis controls:** where the heightmap comes from. Anchor =
one real DEM crop. Top of axis = real DEM + procedural amplification +
astro/moon/fantasy sources, all interchangeable.

**Current state:** *not started.* Anchor is working (mockup-quality); this axis is the next obvious expansion candidate.

**Next experiment (when ready):** "kernelized" procedural source informed
by DEM features. Extract features (drainage networks, ridge systems,
slope distributions) from real DEMs, use them to drive a synthesized
procedural heightmap that's tunable but reads as real.

*Exit criterion:* generate a procedural heightmap from real-DEM feature
extraction, render via the anchor flow, and **a viewer can't recognize
the source DEM in the output.** "Stole the Grand Canyon" is failure
mode — the kernel has to abstract, not crop.

**Notes:**
- "Kernel" is the operative word even if the exact technique is TBD
  (FFT, convolutional, rule-based feature library, etc.). Outcome
  matters more than method.
- Astro/moon/lunar maps generalize once the kernel works on DEMs.
- Source DEM is *training data for synthesis*, not output material.
  Hard constraint: outputs must not be visually traceable to sources.

---

## Axis 4: View

**What this axis controls:** how the world is rendered. Anchor = 3
cameras (3D walk + 2.5D iso + 2D topdown) at one scale. Top of axis =
scale-aware rendering across all three view modes, each tuned for its
viewing distance.

**Current state:** *first expansion landed (2026-05-11).* Three view
shaders for scale_demo, swapped at runtime via
`AnchorCameraRig` → `ScaleWorld.set_view_mode`. Hotkey 1/2/3 also bumps
the loaded-tile radius per view, so iso/topdown show the whole world
while walk uses the streaming-friendly narrow radius.

Three view treatments:
- **Walk** (`terrain_scale_v1.gdshader`): existing scale walk shader.
  Full lambertian, eye-level intent.
- **Iso** (`terrain_view_iso.gdshader`): flatter lambertian
  (lambert_floor 0.35 → 0.55), reduced sun intensity (1.0 → 0.5),
  brighter ambient (0.45 → 0.65), plus a "form light" term that
  brightens upward-facing fragments. Reads as stylized 2.5D.
- **Topdown** (`terrain_view_topdown.gdshader`): no lambertian.
  Replaced with cartographic hillshade (single dot product with a
  fixed virtual sun, clamped to [0.55..1.20]) + sepia bias (0.25 mix
  toward warm neutrals) + slight saturation gain. Reads as a topographic
  map, not lit terrain.

All three are `unshaded` (Pitfall #3) and share the 3-slot
slope-blended albedo pipeline.

*Exit criterion (met):* switching between the 3 cameras shows the same
world with appropriate detail per scale. No view looks broken or
unreadable.

**Next experiment (when ready):** Polish + content additions.
- Topdown contour lines (every N meters draw a thin line at height
  thresholds).
- Iso silhouette outline (subtle edge darken at slope discontinuities).
- Tunable per-view env tonemap.
- Fix the headless-capture topdown framing edge case where the
  orthographic camera doesn't cleanly capture all 16 tiles (visible
  as an L-shaped crop; appears correct in editor).

**Notes:**
- Build for 3D-walk first; 2.5D and topdown strip down from there.
  Cheapest path to view parity, and how AAA games handle view-swapping.
- True multi-scale zoom (smooth from 1km to 5m maintaining quality) is
  a stretch goal — see WISHLIST.md.
- Crimson Desert + 2-3 other titles do view-swapping successfully; the
  technique exists, we just have to apply it.
- **The per-view radius pattern is reusable.** Walk gets the narrow
  streaming radius; iso/topdown bump to "load the whole world" because
  the player wants the overview. ScaleWorld's
  `view_radius_walk` / `_iso` / `_topdown` exports drive this. Each
  view-mode swap forces a repage with the new radius.
- **Shader files are isolated.** Three .gdshader files + three .tres
  bindings instead of one shader with a view_mode uniform. Iterating
  on one doesn't affect the others.

---

## Axis 5: Decoration

**What this axis controls:** what's placed on top of terrain — props,
vegetation, scatter, POIs, structures. Anchor = bare terrain, no scatter.
Top of axis = full rule-based placement driven by biome + heightmap data.

**Current state:** *not started.* Explicit end-game per user; activates
after core map gen is stable, but works in parallel rather than strictly
after.

**Next experiment (when ready):** mask-based scatter for one biome.
E.g. "trees in grassland tiles, density driven by slope + drainage +
noise." Mask is a 2D texture per bundle indicating scatter density per
pixel. Procedural placement (not hero-quality assets — that's later
still).

*Exit criterion:* visible, biome-appropriate, non-repetitive scatter
across a tile. Doesn't clip into terrain. Performance acceptable at
view-radius bounds.

**Notes:**
- Climate, weather, POIs likely belong here OR as adjacent axes — TBD
  once we start thinking about them.
- "Hero quality" decorations (handcrafted props, landmarks) are not in
  this axis — that's content production, not world-gen.
- Mask-based scatter is the cheap proven approach; W3's
  M15FeatureScatterOverlay used it.

---

## Axis 6: Textures

**What this axis controls:** what materials exist and how they're made.
Anchor = vanilla PBR sets (some reused from W3 catalog, possibly a few
freshly generated). Top of axis = the full texture creation workflow
including blending/transitions/biome-cohesive kits.

**Current state:** *creation pipeline shipped; transition workflow
foundation (Stage 5a) landed 2026-05-12, soft-blend stages (5b-5f) in
flight on branch `axis6-transitions`.* The creation half — biome-
cohesive kit generation via FLUX2-klein 9B, real-ortho + ComfyUI mix,
palette discipline via prompt-encoded palettes — is working end-to-end.
5 biomes × 12 slots × 4 PBR maps rendered on the scale_demo world.

The transition architecture is now in place: one global terrain
material (`material_world_v2.tres`) + 8 `Texture2DArray`s (2 tiers ×
4 PBR maps) built at scene init + per-tile splat textures with
per-slot `(tier, layer)` indices. `terrain_world_v2.gdshader` does
the per-fragment weighted blend across up to 4 biomes. Stage 5a
shipped the foundation in hard-mode splats (every pixel = pure
channel 0 = this tile's own biome) — regression-equivalent to the
2026-05-12 per-tile-material baseline, validating the array+splat
plumbing end-to-end. Capture: `captures/axis6_5a_walk_2026_05_12.png`.

Three new Godot 4.5 pitfalls hit and documented as PITFALLS #5 +
#5b — Texture2DArray layer uniformity (format + mipmap state) and
the non-serialisable `Texture2DArray.tres` constraint that pushed
array construction into ScaleWorld at scene init rather than in the
pipeline.

**Next experiment (in flight):** Stage 5b. Switch the splat builder
from `--mode hard` to `--mode feather --feather-width-m N` so
boundary regions of adjacent tiles with different biomes get smooth
weight ramps. No shader change — the array+splat path is built to
consume those ramps once the splats encode them. Then 5c (slot-pool
indirection refactor — streaming-ready, identity in v1), 5d (two-tier
verification), 5e (portability doc), 5f (build-note + roadmap rewire).

*Exit criterion:* a multi-biome world has visually pleasant transitions
between adjacent biome materials. No hard color blocks, no smeared
intermediate states. Method documented.

**Notes:**
- Texture creation is **not** parking-lot or "future." It's the
  substrate — no world without it. This axis is active from anchor
  onward, even if next-experiment doesn't fire immediately.
- `pipelines/textures/aaa_texture.py` is the proven generation pipeline.
  FLUX2-klein-9B model stack staged. `palette_lock.py` does biome-cohesive
  kits.
- W3's blending workflow outputs banned because they bake transition
  assumptions into the texture itself. W4 needs transitions as a
  runtime/shader concern, not a pre-baked material variant — or to
  prove the W3 approach was actually right and we just lacked context.

---

## Adding or restructuring axes

We add new axes when an idea is:
- Significant enough to expand independently
- Doesn't fit cleanly into an existing axis
- Concrete enough to define a "next experiment"

Climate/weather, LLM-drivability, smooth-zoom-from-1km, world map vs.
local map split — all currently in WISHLIST.md. They promote to axes when
they meet those three tests.

This file evolves. Six axes is the current best decomposition. When an
axis splits, merges, or gets reframed, delete this file and write a
new one rather than editing in place.

## Links

- `ANCHOR.md` — the floor every axis has to keep working
- `WISHLIST.md` — parking lot of ideas not yet promoted to axes
- W3 carry-forward inventory: `D:/assets/W4_KICKOFF_2026_05_11.md`
