# Phase E.4 — Orchestrator capture driver + M18 cascade validation

> One parameterized Godot scene replaces N hand-authored `capture_*.tscn`.
> The driver consumes a JSON request, instantiates `World3AutoReviewTour`,
> runs warmup, saves a PNG, quits. Wired into `stages.json` so the
> orchestrator drives captures from a region request.

## Verdict

**Driver works end-to-end on bundles that never had a hand-authored
capture scene.** Validated on the M10 procedural bundle (`procedural_desert_canyon_rock_m10`)
in all four modes — close, medium, iso, topdown. The M18 representative-slice
cascade was also re-rendered through the standard per-bundle scenes after
the D.1 macro fix to confirm the fix lands at the runtime layer.

## What shipped

### Driver

- `world3/scripts/OrchestratorCaptureDriver.gd` — reads `user://orchestrator_capture_request.json`, instantiates `World3AutoReviewTour` with the request's bundle paths / material / mode, awaits `warmup_frames` process frames, saves `get_viewport().get_texture().get_image()` to the requested output path, quits. Applies style overrides from `request["style"]` when present.
- `world3/scenes/review/orchestrator_capture_driver.tscn` — bare `Node` root with the driver script attached. Runs as a regular scene under `Godot.exe --rendering-driver opengl3 --path . res://scenes/review/orchestrator_capture_driver.tscn`.

### Python wrapper

`world3/pipeline/run_orchestrator_capture.py` — writes the JSON request to
`C:/Users/josep/AppData/Roaming/Godot/app_userdata/world3/orchestrator_capture_request.json`,
invokes Godot with the canonical flag set, verifies the output PNG was refreshed.
Exposed args:

```
--bundle-dir res://...           --material res://...
--mode {close,medium,iso,topdown} --output res://...
--macro-albedo res://...         --macro-mask res://...
--style-pack <id>                 (default 'photoreal'; see E.5)
--warmup-frames N                 --viewport-size W,H
--start-x M --start-z M           --chunk-size M --chunk-resolution M
```

### stages.json wiring

The three `render_captures_*` stages in `world3/jobs/stages.json` were
placeholders pointing at the string `"godot scenes capture (Phase E.4
orchestrator_capture_driver)"`. They now point at
`world3/pipeline/run_orchestrator_capture.py` with proper input args
declared. `python world3/pipeline/audit_stages.py` reports all 12 stages clean.

### WORKFLOW.md addendum

Added "Orchestrator capture driver (E.4)" section to
`world3/docs/WORKFLOW.md` with the request schema, validated PowerShell
invocation, and the binary-choice trap (must use the regular binary at
`C:/Godot/`, not the mono binary).

## The mono-binary trap

The mono build at `C:/Users/josep/Downloads/Godot_v4.5-stable_mono_win64/...`
exits 0 in ~3 seconds with no log file, no PNG, no errors — only the
OpenGL header in stdout. The regular `C:/Godot/Godot_v4.5-stable_win64.exe`
with the same args works first try. Cause is likely the .NET project
assembly load failure visible in the mono binary's verbose output. The
working invocation pattern (also documented in WORKFLOW.md):

```powershell
& "C:/Godot/Godot_v4.5-stable_win64.exe" `
  --rendering-driver opengl3 `
  --path "D:/assets/world3" `
  --single-window `
  --disable-crash-handler `
  --log-file "D:/tmp/orchestrator_capture_<run-id>.log" `
  "res://scenes/review/orchestrator_capture_driver.tscn"
```

`--log-file` is essential for debugging because the `user://logs/` files
only land on success — a failed run produces no usable log otherwise.

## M18 cascade re-render (the D.1 macro fix validation)

The procedural-side macro albedo fix from Phase D.1
(`build_procedural_neighbor_bundle.py` rewrite: catalog texture as base,
not median-color collapse) was re-rendered through the M18 representative-slice
cascade to confirm it lands at the runtime layer.

Cascade:

1. `build_m17_real_data_rule_extraction.py` (~2.17s) — re-runs `build_procedural_neighbor_bundle.py` and writes `world3/toporeview/m17_guided_desert_canyon_neighbor/`
2. `build_terrain_seam_integration_proof.py` with explicit args (defaults DO NOT match M18; see `world3/jobs/m18_representative_slice_manifest.json` for the arg contract) — produces `world3/textures/source_stack/m18_guided_neighbor_slice_proof/` and `world3/toporeview/m18_guided_neighbor_slice_proof/`
3. `build_m18_slice_feature_masks.py` — writes the M15 feature masks
4. Four hand-authored M18 capture scenes (close/medium/iso/topdown) — re-rendered through the regular-binary capture path

Result: the M18 procedural side that previously read as broad smooth tan/sand
now reads as warm rocky scrub matching the gloss_scrub catalog material.
User visually confirmed 2026-05-11. Pre-fix captures preserved at
`D:/tmp/e4_m18_prefix_backup/`; post-fix captures live at
`world3/docs/captures/review/source_stack_m18_guided_neighbor_{close,medium,iso,topdown}.png`.

## Driver proof on M10

After E.5 landed the photoreal pack:

```
python world3/pipeline/run_orchestrator_capture.py \
  --bundle-dir res://toporeview/procedural_desert_canyon_rock_m10 \
  --material   res://textures/wgv3/terrain_blend_desert.tres \
  --macro-albedo res://toporeview/procedural_desert_canyon_rock_m10/layers/render_albedo.png \
  --macro-mask   res://toporeview/procedural_desert_canyon_rock_m10/layers/source_valid_mask.png \
  --mode iso --style-pack photoreal \
  --output res://docs/captures/review/orchestrator_e5_photoreal_smoke_m10_iso.png \
  --start-x 60 --start-z 120 --chunk-size 120 --chunk-resolution 4

[run_orchestrator_capture] OK ... (1969 KB, 3.96s)
```

The M10 bundle never had a hand-authored capture scene. The fact that the
driver renders it correctly is the proof of E.4's design intent — bundles
are decoupled from their capture scaffolding.

## What's NOT in E.4

- Tuning per-bundle camera framing. The proof captures of M10 reveal that
  the tour profile's default focus offsets don't always frame a 120×240 m
  bundle well from the iso/topdown angles (chunk-grid texture visible in
  the topdown proof). That's tour-profile work, not driver work; can be
  addressed by per-bundle `start_x_m / start_z_m / chunk_size_m` tuning
  or by adding orchestrator-level focus heuristics later.
- A "matrix" of multi-mode captures in one invocation. Today
  `run_orchestrator_capture.py` is one PNG per call (clean for stages.json).
  A higher-level wrapper that captures all 4 modes in one Godot launch
  would amortize the ~3.5s startup cost; deferred.

## Status

- [x] E.1 schema + 3 examples + validator
- [x] E.2 stages manifest + audit (12 stages clean)
- [x] E.3 orchestrator + provenance (byte-identical output)
- [x] E.4 OrchestratorCaptureDriver + wrapper + stages.json wiring + M18 cascade validated + M10 proof
- [x] E.5 style pack mechanism + photoreal default
- [ ] E.6 docs + handoff (in progress)
- [ ] E.7 final validation + sign-off

**Phase E.4 SHIP.** Parameterized capture path replaces hand-authored
capture scenes; orchestrator can drive captures end-to-end.
