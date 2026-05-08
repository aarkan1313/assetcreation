# world3 — Phase C/D/E Complete Session Arc Handoff (2026-05-07 night)

**Branch:** main
**Last commits:** `2346acf` (Phase E ROADMAP), `75b15d1` (Phase E wiring), `c4d68c0` (Phase E emit), `2d92cd1` (Phase D ROADMAP), `4b53a0f` (Phase D fix), `8ca2ec0` (Phase C ROADMAP), `eca28ba` (Phase C iter 2), `1dee0f8` (Phase C scaffold), `22cb479` (repo-wide checkpoint)
**Next work:** Phase F — multi-tile / continuous world (research + prototype)

---

## What was done this session

Three world3 phases shipped in one arc:

### Phase C — Iso/topdown anchor framing

Added a "framing target" mode to both cameras: when `anchor_path` is set
and `visible_diameter_m > 0`, the camera frames around that anchor's
world position at the configured diameter. Falls through to legacy
auto-AABB when unset, so existing scenes are unaffected.

| Component | Path |
|-----------|------|
| Iso camera | `world3/scripts/IsoCam.gd` (added `_try_anchor_mode()` + `iso_dir` export) |
| Topdown camera | `world3/scripts/TopDownCam.gd` (same pattern + `anchor_height_m`) |
| Player anchor | `world3/scripts/PlayerAnchor.gd` (Node3D with snap-to-terrain via heightmap sample) |
| Zoom constants | `world3/scripts/CamFraming.gd` (ARPG 40m, strategy 300m, game-tile 50m, minimap 10km) |
| Capture scenes | `world3/scenes/capture_phase_c/{iso_arpg_40m,iso_strategy_300m,topdown_game_tile_50m,topdown_minimap_10km}.tscn` |
| Captures | `world3/docs/captures/phase_c/` (4 PNGs against Tetons) |

### Phase D — Region gallery + kit-binding fix

The earlier Phase D handoff (`ca171e9`) updated `world3/jobs/biome_kits.json`
to the new `wgv3_tf_*` and `wgv3_gl_*` texture IDs but didn't regenerate
the kit `.tres` ShaderMaterials — they still pointed at alpine-default
texture slots. Bug surfaced when the region gallery ran and chaparral
regions still had snow caps.

Fix: `pipelines/textures/deploy_kit_to_world3.py` reads `biome_kits.json`
and rebuilds kit `.tres` mechanically, copying library textures into
per-kit slot dirs (`world3/textures/wgv3/<kit>_<slot>/{albedo,normal,roughness}.png`).

After deploy + Godot `--import` + gallery rerun, all 5 kits render with
their assigned biomes:

- alpine (Cascades, Appalachians) — grass + rock + snow caps ✅
- desert (Mojave) — sand-tan everywhere ✅
- tundra (Arctic Alaska) — moss + frost patches ✅
- temperate_forest (Chaparral) — brown rocky chaparral, no snow ✅ (fix payoff)
- grassland (Tibet, Serengeti) — uniform tall_grass yellow ⚠️ (binding correct, slope/height tuning is the open polish task)

### Phase E — Per-game-mode material tuning

`pipelines/textures/emit_per_mode_materials.py` reads each kit's base
`terrain_blend_<kit>.tres` and emits 3 mode-tuned variants
(`_walk.tres`, `_iso.tres`, `_topdown.tres`) with these overrides:

| Param | walk | iso | topdown |
|-------|------|-----|---------|
| `world_uv_scale` | 0.4 | 0.1 | 0.02 |
| `normal_strength` | 1.2 | 1.0 | 0.4 |
| `macro_value_strength` | 0.05 | 0.15 | 0.35 |
| `blend_sharpness` | 12.0 | 8.0 | 4.0 |
| `h_band_softness` | 0.06 | 0.08 | 0.12 |

Texture refs, height bands, and slope thresholds inherit from the base.

15 .tres files committed (5 kits × 3 modes).

Wiring:
- `walk.tscn` / `iso.tscn` / `topdown.tscn` now point at
  `terrain_blend_alpine_{walk,iso,topdown}.tres` (was `_tetons.tres`).
- `RegionGalleryCapture.gd` derives per-mode paths from
  `biome_kit_material` and swaps `material_override` between iso and
  topdown shots. Falls back to base kit material if a per-mode variant
  is missing.

Captures:
- 3 alpine sanity captures at `world3/docs/captures/phase_e/`.
- 7-region gallery (all 5 kits × iso + topdown) at
  `world3/docs/captures/phase_e_gallery/`. Cascades topdown reads as
  green/brown/white color blocks distinct from its detailed iso shot
  — visible payoff of per-mode tuning.

---

## Bug fixes worth remembering

### `RegionGalleryCapture` elev push

`Terrain.rebuild()` pushes `elev_min_m` / `elev_range_m` into the
ShaderMaterial bound at load time. When the gallery swaps
`material_override` between iso and topdown shots, the new material
doesn't have these uniforms set — height-band thresholds compute
against `[0..1]` instead of meters, and topdown's lower band-softness
pushes snow off-screen.

Fix: gallery now reads `meta.json` upfront and re-pushes `elev_min_m` /
`elev_range_m` via `_bind_material()` on every swap. Documented in
`world3/docs/captures/phase_e_gallery/README.md`.

### `--headless` capture trap

The SceneTree-script runner pattern in
`pipelines/godot_export/screenshot_scenes.py` hangs in `--headless`
mode (`process_frame` awaits never resume reliably; `get_root().get_texture()`
returns null). All captures must run with a real window:

```
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet \
  --script "$PWD/world3/scripts/_codex_render_runner.gd" \
  -- --scene "res://scenes/capture_phase_c/iso_arpg_40m.tscn" \
     --out res://_codex_snap.png --wait-frames 30 --width 1280 --height 720
```

~2s per scene. Documented in `world3/docs/captures/phase_c/README.md`.

### `Write` tool UTF-16 on Windows

The deploy script's first version used a `→` arrow in print output;
crashed on cp1252 stdout. Replaced with `->`. (Memory: this matches
the existing memory entry on Windows encoding.)

---

## Files to track

```
world3/scripts/
  IsoCam.gd                            # +anchor mode
  TopDownCam.gd                        # +anchor mode
  PlayerAnchor.gd                      # NEW
  CamFraming.gd                        # NEW
  RegionGalleryCapture.gd              # +per-mode swap +elev re-push

world3/scenes/
  walk.tscn / iso.tscn / topdown.tscn  # repointed to alpine_<mode>.tres
  capture_phase_c/                     # NEW (4 zoom-level scenes)
  capture_phase_e/                     # NEW (3 alpine sanity scenes)

world3/textures/wgv3/
  terrain_blend_<kit>.tres             # base kits (5)
  terrain_blend_<kit>_<mode>.tres      # per-mode (15: 5 kits x 3 modes)
  <kit>_<slot>/{albedo,normal,roughness}.png  # deployed kit textures
  <kit>_<slot>/*.png.import            # Godot import metadata

world3/docs/captures/
  phase_c/                             # NEW (anchor zoom captures)
  phase_e/                             # NEW (alpine per-mode sanity)
  phase_e_gallery/                     # NEW (7 regions x iso+topdown)

pipelines/textures/
  deploy_kit_to_world3.py              # NEW (Phase D fix)
  emit_per_mode_materials.py           # NEW (Phase E)
```

---

## Phase F — what comes next

**Multi-tile / continuous world.** Walk off the edge of one region
into another seamlessly. Current "regions" are 4-20km tiles loaded
one at a time; we don't stream.

Per ROADMAP:
1. Research: Godot 4 chunk streaming patterns; existing terrain plugins
   (Terrain3D, HTerrain) and feasibility of integrating with our
   heightmap + ShaderMaterial + meta.json approach; memory budget per
   chunk.
2. Design: chunks probably 256-512m for walk-mode (regions are too big).
3. Small test: 2x2 grid of identical Tetons tiles at 4km each, stitched.
   Verify no visible seam, no double-load of shared edge, mesh
   continuity at boundaries.
4. Decide: keep one heightmap per region, or split regions into
   multiple chunks at build time?

This is a research + prototype phase, not a single-session item.

---

## Open polish items (parked, not blocking F)

- Grassland slope/height tuning (Tibet + Serengeti read uniform tall_grass).
- Non-alpine per-mode visual review (emit tool covers them; only alpine
  has dedicated capture scenes).
- Walk-mode shared-anchor decision (deferred from Phase C).
- Region gallery walk shot (gallery only does iso + topdown; walk needs
  eye-level Camera3D).

---

## How to re-run from scratch

```powershell
cd D:/assets

# (Re)deploy temperate_forest + grassland kits if biome_kits.json changes
python pipelines/textures/deploy_kit_to_world3.py --kit temperate_forest
python pipelines/textures/deploy_kit_to_world3.py --kit grassland

# Emit per-mode .tres for all kits
python pipelines/textures/emit_per_mode_materials.py

# Godot import (after any deploy / emit)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet --headless --editor --import

# Region gallery (iso + topdown per region with per-mode swap)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet res://scenes/region_gallery.tscn

# Phase C zoom-level captures (one at a time)
foreach ($scene in @("iso_arpg_40m","iso_strategy_300m","topdown_game_tile_50m","topdown_minimap_10km")) {
  Remove-Item world3/_codex_snap.png -ErrorAction SilentlyContinue
  & "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet `
    --script "$PWD/world3/scripts/_codex_render_runner.gd" `
    -- --scene "res://scenes/capture_phase_c/$scene.tscn" `
       --out res://_codex_snap.png --wait-frames 30 --width 1280 --height 720
  Move-Item world3/_codex_snap.png "world3/docs/captures/phase_c/$scene.png"
}
```
