# world3 — Current Iteration Plan

**Phases B/C/D/E are done.** ROADMAP v2 path A→B→D→C→E→F is at the F
boundary. This iteration's work was the four mid-phases:

| Phase | What | Status |
|-------|------|--------|
| B  | SR + mip-ladder + per-tier QA in `aaa_texture.py --ladder` | **DONE** (`84ed00e`, `6e62b37`, 2026-05-07) |
| C  | Anchor-mode framing on IsoCam/TopDownCam + PlayerAnchor + zoom captures | **DONE** (`1dee0f8`, `eca28ba`, `8ca2ec0`, 2026-05-07) |
| D  | All 5 biome kits with purpose-built textures + bound `.tres` | **DONE** (`ca171e9`, `4b53a0f`, `2d92cd1`, 2026-05-07) |
| E  | Per-game-mode material variants (`terrain_blend_<kit>_<mode>.tres`) wired into game scenes + gallery | **DONE** (`c4d68c0`, `75b15d1`, `2346acf`, 2026-05-07) |
| F  | Multi-tile / continuous world | **NEXT** (research + prototype) |

## What changed this iteration

### Phase B (already in by start of session)

`aaa_texture.py --ladder` runs Stage 8: SR (Real-ESRGAN) → bake (re-derive
normal/AO/roughness from upscaled height) → mip ladder (2K/1K/512) →
per-tier QA + cross-tier contact sheet. Hero materials only — opt-in.

### Phase C — anchor-mode framing

Both `IsoCam.gd` and `TopDownCam.gd` got an anchor mode: when
`anchor_path` is set and `visible_diameter_m > 0`, the camera frames
around that anchor's world position at the configured diameter.
Falls through to legacy auto-AABB framing — non-breaking.

New `PlayerAnchor.gd` (Node3D marker) snaps Y to the actual terrain
surface by sampling the heightmap PNG (matches Terrain.gd's sampling
1:1).

`CamFraming.gd` exposes the locked zoom-level constants:
ARPG 40m, strategy 300m, game-tile 50m, minimap 10km.

4 capture scenes under `world3/scenes/capture_phase_c/` shoot the
Tetons region at each zoom level. Captures live at
`world3/docs/captures/phase_c/`.

### Phase D fix

The handoff before this session (`ca171e9`) updated `biome_kits.json`
to the new `wgv3_tf_*` and `wgv3_gl_*` texture IDs but didn't
regenerate the `terrain_blend_temperate_forest.tres` and
`terrain_blend_grassland.tres` ShaderMaterials — they still pointed
at alpine-default texture slots.

Fix: `pipelines/textures/deploy_kit_to_world3.py` reads
`biome_kits.json` and rebuilds the kit's `.tres` mechanically. After
deploy + Godot `--import`, chaparral and Tibet/Serengeti regions now
render with their assigned biome textures.

### Phase E — per-mode material tuning

`pipelines/textures/emit_per_mode_materials.py` reads each kit's base
`terrain_blend_<kit>.tres` and writes 3 mode-tuned variants:

| Param | walk | iso | topdown |
|-------|------|-----|---------|
| `world_uv_scale` | 0.4 | 0.1 | 0.02 |
| `normal_strength` | 1.2 | 1.0 | 0.4 |
| `macro_value_strength` | 0.05 | 0.15 | 0.35 |
| `blend_sharpness` | 12.0 | 8.0 | 4.0 |
| `h_band_softness` | 0.06 | 0.08 | 0.12 |

Texture refs, height bands, and slope thresholds are inherited
unchanged from the base.

Wiring:
- `walk.tscn` / `iso.tscn` / `topdown.tscn` now point at
  `terrain_blend_alpine_{walk,iso,topdown}.tres` (was `_tetons.tres`).
- `RegionGalleryCapture.gd` derives per-mode paths from
  `biome_kit_material` (e.g. `terrain_blend_alpine.tres` →
  `terrain_blend_alpine_iso.tres` for the iso shot,
  `terrain_blend_alpine_topdown.tres` for the topdown shot). When a
  per-mode variant is missing, falls back to the base kit material.
- Bug fix: when swapping ShaderMaterials between iso/topdown shots,
  `Terrain.rebuild`'s `elev_min_m` / `elev_range_m` push only hits
  the material bound at load time. Gallery now reads `meta.json`
  upfront and re-pushes those uniforms via `_bind_material()`. Without
  this, height-band thresholds compute against `[0..1]` instead of
  meters, hiding snow.

3 alpine sanity captures at `world3/docs/captures/phase_e/` show
clear visual differences across modes. 7-region gallery at
`world3/docs/captures/phase_e_gallery/` shows each kit through both
iso and topdown — Cascades topdown reads as green/brown/white color
blocks distinct from its detailed iso shot.

## What's next: Phase F

**Multi-tile / continuous world.** Walk off the edge of one region
into another seamlessly. Current "regions" are 4-20km tiles loaded
one at a time; we don't stream.

Per ROADMAP:

1. Research: Godot 4 chunk streaming patterns, existing terrain
   plugins (Terrain3D, HTerrain — feasibility of integrating with our
   heightmap+blend material approach), memory budget per chunk.
2. Design: what's a "chunk"? Current "region" is 4-20km — too big
   for walk-mode streaming. Chunks probably 256-512m.
3. Small test: 2x2 grid of identical Tetons tiles at 4km each,
   stitched. Verify no visible seam, no double-load of shared edge,
   mesh continuity at boundaries.
4. Decide: keep one heightmap per region, or split regions into
   multiple chunks at build time?

Exit criteria:
- Walking off an edge into the next tile works without visible
  discontinuity.
- Documented streaming budget.
- Decision-locked on chunk size + format.

This is a research + prototype phase, not a single-session item.

## Open polish items (not in scope; can pick up at session start)

- **Grassland slope/height tuning.** Tibet + Serengeti read as
  near-uniform tall_grass at iso/topdown. The kit binding is correct;
  `slope_threshold` / `h_grass_dirt` surface too little rock/dirt
  variation. ~half-session of param sweeping + recapture.
- **Non-alpine per-mode visual review.** Phase E's emit tool covers
  all 5 kits but only alpine got dedicated capture scenes. Other kits
  are rendered through the gallery's per-mode swap; could add
  kit-specific capture scenes for closer inspection.
- **Walk-mode shared-anchor decision.** Phase C deferred whether
  walk shares a `PlayerAnchor` with iso/topdown or each gets its own.
  Decide when walk-mode wires into the anchor system.
- **Region gallery: walk shot.** Gallery currently produces iso +
  topdown per region; could add a walk shot using the walk-tuned
  material. Walk needs a Camera3D pose (eye-level), not the existing
  ortho one.

## Operating principle (unchanged)

Build tools and workflow improvements before pushing more output
through the pipeline. Each step strengthens the foundation so we
don't have to redo work later. OpenTopo branch work continues in
parallel under another worker; not in scope here.
