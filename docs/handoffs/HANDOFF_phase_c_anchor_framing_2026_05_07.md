# Phase C — Iso/Topdown Anchor Framing Handoff (2026-05-07 evening)

**Branch:** main
**Last commits:** `1dee0f8` (phase C anchor mode + capture scenes), `22cb479` (repo-wide checkpoint)
**Next work:** review captures, lock framings, then move to Phase D remainder (region gallery recapture) or Phase E (per-mode material variants)

---

## What was built

### Anchor-mode framing on IsoCam + TopDownCam

Both cameras now support two framing modes:

1. **Auto-AABB** (default, unchanged): frames the whole Terrain mesh by reading
   its AABB. Original behavior, used by review/gallery scenes.
2. **Anchor**: frames around `anchor_path.global_position` at
   `visible_diameter_m`. Falls through to auto-AABB when `anchor_path` isn't
   set, so existing scenes are unaffected.

`world3/scripts/IsoCam.gd` — `_try_anchor_mode()` short-circuits when anchor +
diameter are configured, else `_auto_aabb_mode()` runs the legacy path.
`iso_dir` is exposed for non-default azimuth/elevation.

`world3/scripts/TopDownCam.gd` — same pattern. `anchor_height_m` controls the
camera's Y offset above the anchor (ortho means it doesn't change framing,
just depth-clipping).

### Player anchor

`world3/scripts/PlayerAnchor.gd` — a `Node3D` marker. With `snap_to_terrain =
true` it clamps XZ into the terrain footprint and sets Y to the AABB midpoint
on `_ready`. For ortho captures the Y precision doesn't matter; the clamp
guarantees the anchor isn't outside the terrain.

The walk-mode shared-anchor decision is deferred until walk wires in.

### Zoom-level constants

`world3/scripts/CamFraming.gd` exposes the locked diameters:

| Mode | Diameter | Reference |
|------|----------|-----------|
| Iso ARPG | 40m | Diablo, Path of Exile |
| Iso strategy | 300m | Civ, RTS |
| Topdown game-tile | 50m | Stardew-ish |
| Topdown minimap | 10000m | whole-region nav |

These are reference points — capture scenes set `visible_diameter_m` directly
to one of these values. Capture scenes don't reference the constants
(GDScript constants need autoload to be readable from .tscn property text).

### Capture scenes

Under `world3/scenes/capture_phase_c/`:

- `iso_arpg_40m.tscn`
- `iso_strategy_300m.tscn`
- `topdown_game_tile_50m.tscn`
- `topdown_minimap_10km.tscn`

Each has `Terrain` (Tetons heightmap, 4km region), `PlayerAnchor` at world
origin (snaps to terrain center), and the iso/topdown camera in anchor mode.
Lighting/environment matches the parent `iso.tscn` / `topdown.tscn`.

These scenes do NOT contain the legacy `HeadlessCapture` node — that node
errors in `--headless` because `get_viewport().get_texture()` returns null
without a window. Capture is handled externally by
`pipelines/godot_export/screenshot_scenes.py`'s SceneTree runner, which uses
`get_root().get_texture()` (the Window root) instead.

---

## How to render the captures

```powershell
# From d:/assets:
python pipelines/godot_export/screenshot_scenes.py `
  --project world3 `
  --scenes scenes/capture_phase_c/iso_arpg_40m.tscn `
           scenes/capture_phase_c/iso_strategy_300m.tscn `
           scenes/capture_phase_c/topdown_game_tile_50m.tscn `
           scenes/capture_phase_c/topdown_minimap_10km.tscn `
  --out-dir d:/tmp/world3_screens/phase_c
```

**Known wrapper bug:** `screenshot_scenes.py` had a 12-minute hang on the
2026-05-07 evening run before any subprocess fired — root cause unclear
(filesystem stat? hung subprocess inheritance?). If it stalls, fall back to
direct invocation:

```powershell
foreach ($scene in @("iso_arpg_40m","iso_strategy_300m","topdown_game_tile_50m","topdown_minimap_10km")) {
  Remove-Item world3/_codex_snap.png -ErrorAction SilentlyContinue
  & "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet --headless `
    --script "$PWD/world3/scripts/_codex_render_runner.gd" `
    -- --scene "res://scenes/capture_phase_c/$scene.tscn" `
       --out res://_codex_snap.png --wait-frames 90 --width 1280 --height 720
  Move-Item world3/_codex_snap.png "d:/tmp/world3_screens/phase_c/$scene.png"
}
```

Per-scene capture takes ~30-60s on a Tetons-class region (256-subdiv mesh
build dominates).

---

## What's next

### Phase C remaining

- [ ] Review captures, pick "good" framings per mode, document in
      `world3/docs/PHASE_C_FRAMINGS.md` (or fold into ROADMAP).
- [ ] If a framing looks wrong, tune the camera defaults (iso_dir,
      anchor_height_m) or the diameter and re-shoot.
- [ ] Decide walk/iso/topdown shared-anchor (deferred).

### Then

Per ROADMAP order: **Phase D remainder** (region gallery recapture with all 5
biome kits) → **Phase E** (per-mode material variants
`terrain_blend_<kit>_<mode>.tres`) → **Phase F** (multi-tile streaming).

Phase D's recapture wants the iso/topdown framing locked first so the gallery
captures use consistent zoom levels — Phase C's exit unblocks D's exit.

---

## Files touched

| File | Change |
|------|--------|
| `world3/scripts/IsoCam.gd` | Added `_try_anchor_mode()` + `iso_dir` export |
| `world3/scripts/TopDownCam.gd` | Added `_try_anchor_mode()` + `anchor_height_m` export |
| `world3/scripts/PlayerAnchor.gd` | New — Node3D marker with snap-to-terrain |
| `world3/scripts/CamFraming.gd` | New — zoom-level constants |
| `world3/scenes/capture_phase_c/*.tscn` | 4 new capture scenes |
| `world3/docs/ROADMAP.md` | Phase C marked IN PROGRESS, 5/6 items checked |
