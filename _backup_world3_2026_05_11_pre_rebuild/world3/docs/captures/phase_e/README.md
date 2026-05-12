# Phase E — Per-Game-Mode Material Tuning Captures (2026-05-07)

Captures from `world3/scenes/capture_phase_e/` showing the alpine kit
rendered through the 3 mode-tuned `terrain_blend_alpine_<mode>.tres`
variants. Same Tetons heightmap, same anchor, only the bound material
differs.

| Capture | Mode | Diameter | Material | What it reads as |
|---------|------|----------|----------|------------------|
| `alpine_walk.png` | walk | 8m | `terrain_blend_alpine_walk.tres` | Tight close-up, sharp normals, near-zero macro tint — clean surface detail |
| `alpine_iso.png` | iso | 300m | `terrain_blend_alpine_iso.tres` | Mid-range grass/snow/rock blend with moderate normal strength (current default) |
| `alpine_topdown.png` | topdown | 4km | `terrain_blend_alpine_topdown.tres` | Muted-normal color blocks (brown/green/white) — color-blocking dominates |

## Per-mode shader-param table

These overrides are applied by `pipelines/textures/emit_per_mode_materials.py`
when generating each `_<mode>.tres`. All other params (slope thresholds,
height bands, texture references) are inherited from the kit's base .tres.

| Param | walk | iso | topdown |
|-------|------|-----|---------|
| `world_uv_scale` | 0.4 | 0.1 | 0.02 |
| `normal_strength` | 1.2 | 1.0 | 0.4 |
| `macro_value_strength` | 0.05 | 0.15 | 0.35 |
| `blend_sharpness` | 12.0 | 8.0 | 4.0 |
| `h_band_softness` | 0.06 | 0.08 | 0.12 |

`world_uv_scale` is multiplied by world position to drive sampling, so
HIGHER = more repeats per meter = closer-feeling detail. walk's 0.4 gives
~2.5m repeat; topdown's 0.02 gives ~50m repeat.

## Re-running

```powershell
# 1) Emit per-mode .tres (run after any kit param changes)
python pipelines/textures/emit_per_mode_materials.py

# 2) Re-import (Godot picks up new .tres files)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet --headless --editor --import

# 3) Capture each mode
foreach ($scene in @("alpine_walk","alpine_iso","alpine_topdown")) {
  Remove-Item world3/_codex_snap.png -ErrorAction SilentlyContinue
  & "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet `
    --script "$PWD/world3/scripts/_codex_render_runner.gd" `
    -- --scene "res://scenes/capture_phase_e/$scene.tscn" `
       --out res://_codex_snap.png --wait-frames 30 --width 1280 --height 720
  Move-Item world3/_codex_snap.png "world3/docs/captures/phase_e/$scene.png"
}
```

## Open work

- Wire the per-mode .tres into the game-mode capture scenes (walk.tscn,
  iso.tscn, topdown.tscn currently use the default `terrain_blend_*.tres`).
- Add capture scenes for the other 4 kits to verify per-mode tuning works
  across the kit set, not just alpine.
- Consider per-kit per-mode overrides if a default mode-table value reads
  wrong on a specific kit (e.g. desert at topdown might want even higher
  macro_value to read as a single sand mass).
