# Phase C — Iso/Topdown Scale Review Captures (2026-05-07)

Captures from the 4 Phase C zoom-level scenes against Tetons heightmap (4km
region, elev 2497-4059m, alpine kit). All use `PlayerAnchor` at world XZ
origin (terrain center) with snap-to-terrain — Y resolves to ~3500m+ alpine
snow zone for this region.

| Capture | Mode | Diameter | Notes |
|---------|------|----------|-------|
| `iso_arpg_40m.png` | Iso | 40m | Tight close-up of snow blend at anchor; shows surface texture detail |
| `iso_strategy_300m.png` | Iso | 300m | Multi-biome cross-section: snow → grass → sand at strategy zoom |
| `topdown_game_tile_50m.png` | Topdown | 50m | Straight-down snow texture; per-screen play area |
| `topdown_minimap_10km.png` | Topdown | 10km | Full 4km Tetons region with all biome blends visible |

## Selecting "good" framings

The minimap is unambiguously the right framing for whole-region nav. The
other 3 are zoom-level reference points; their framing depends on where the
anchor sits. Picking a more representative anchor (e.g. mid-elevation slope
rather than alpine snow center) yields more biome-diverse captures.

To re-shoot with a different anchor position, edit the `PlayerAnchor` node
in the relevant scene and set `transform.origin` to the desired XZ:

```gdscript
# in scene: PlayerAnchor.transform = Transform3D(Basis(), Vector3(x, 0, z))
# then snap-to-terrain resolves Y on _ready
```

## Re-running the captures

```powershell
foreach ($scene in @("iso_arpg_40m","iso_strategy_300m","topdown_game_tile_50m","topdown_minimap_10km")) {
  Remove-Item world3/_codex_snap.png -ErrorAction SilentlyContinue
  & "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet `
    --script "$PWD/world3/scripts/_codex_render_runner.gd" `
    -- --scene "res://scenes/capture_phase_c/$scene.tscn" `
       --out res://_codex_snap.png --wait-frames 30 --width 1280 --height 720
  Move-Item world3/_codex_snap.png "world3/docs/captures/phase_c/$scene.png"
}
```

**Important:** do NOT pass `--headless`. With the SceneTree-script runner
pattern, headless mode causes process_frame awaits to never resume in some
configurations — captures hang indefinitely. The non-headless run takes
~2s per scene and produces correct output.
