# Next-Session Prompt

Copy/paste this as the opening message in a fresh session. It contains the
minimum context to pick up where this session left off.

---

## Session opener

You are picking up `world3` in `D:/assets/world3` as the single-stream
orchestrator. The user asked this chat to keep worker/orchestrator work
consolidated for now.

The project framing matters: `world3` and `assets` are a pipeline/workflow
creation set. Current content is primarily workflow-validation material for
AAA-quality pipelines; production promotion is a separate review.

Read first:

1. `world3/docs/WORLD3_STATE_2026_05_08.md`
2. `world3/docs/PLAN.md`
3. `world3/docs/WORKFLOW_SNAPSHOT_2026_05_08.md`
4. `world3/docs/M2_TRANSITION_MATERIAL_PROTOTYPE.md`
5. `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`
6. `world3/docs/M4_SPLAT_SHADER_PROTOTYPE.md`
7. `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`
8. `world3/docs/M6_RUNTIME_HARDENING.md`
9. `world3/docs/M7_M12_NEAR_ROADMAP.md`
10. `world3/docs/M7_BOUNDARY_RUNTIME_INTEGRATION.md`
11. `world3/docs/M1_M7_VISUAL_AUDIT_PLAN_2026_05_08.md`

## Current status

Recent scoped commits:

- `6e31107` - `world3: add material catalog`
- `23933a3` - `world3: add chunk size sweep`
- `3a7317d` - `world3: start transition strip prototype`
- `116766f` - `world3: record transition visual review`
- `680b22c` - `world3: refresh workflow docs`
- `ae31568` - `world3: add transition review scoring`
- `a2cc5fc` - `world3: add transition boundary contract`
- `dfb2bdd` - `world3: checkpoint opentopo worktree`
- `edc9902` - `world3: tune transition boundary assets`
- `62c5736` - `world3: add splat shader prototype`
- `2bf0942` - `world3: add chunk splat material contract`
- `4db433a` - `world3: wire walk scene to splat streaming`
- `b74d109` - `world3: record m5 streaming budget`
- `1cc9fda` - `world3: close m1 m5 final audit`
- `0cc4349` - `world3: record final audit hash`
- `18d6bac` - `world3: harden streamed runtime`

M1 is done:

- `world3/materials/CATALOG.md`
- `world3/materials/catalog.json`
- `world3/jobs/biome_kits.json` references catalog IDs.
- Kit material generation and representative renders were verified.

M3 is done:

- `world3/scripts/ChunkLoader.gd`
- `world3/scripts/ChunkSweepRunner.gd`
- `world3/scenes/capture_phase_f/chunk_size_sweep.tscn`
- 256 m is locked as the synchronous base chunk size at 8 m mesh spacing.

M2 is done for workflow/M4 input:

- `pipelines/textures/build_transition_strip.py` builds deterministic
  transition strips from catalog IDs and writes score hints into each manifest.
- Boundary rules live in `world3/jobs/biome_transition_rules.json`.
- Contract note: `world3/docs/M2_BOUNDARY_TRANSITION_CONTRACT.md`.
- Rule-level tuning has been applied for width, mask noise, albedo matching,
  frequency dampening, roughness matching, and normal-energy dampening.
- Four pairs were generated under `world3/textures/transitions/`.
- Comparison sheets live under `world3/docs/captures/transitions/`.
- Clean Godot scene:
  `world3/scenes/capture_phase_m2/transition_strip_review.tscn`
- In-engine capture:
  `world3/docs/captures/transitions/godot_transition_strip_review.png`
- User visual review: transitions are promising/good.
- Caveat: grass/leaves are too noisy for production. Track that as source
  texture quality/prompt QA, not transition workflow failure.

M4 prototype pass 2 is done:

- `world3/shaders/terrain_splat_unified.gdshader`
- `world3/pipeline/build_m4_splat_prototype.py`
- Generated alpine RGBA splat weights:
  `world3/textures/m4_splat/alpine_height_slope_weights_rgba.png`
- Generated materials:
  - `world3/textures/wgv3/terrain_splat_alpine.tres`
  - `world3/textures/wgv3/terrain_splat_alpine_fallback.tres`
  - `world3/textures/wgv3/terrain_splat_scrub_sparse_single.tres`
  - `world3/textures/wgv3/terrain_hex_detail_scrub_sparse_reference.tres`
- Captures:
  - `world3/docs/captures/m4/splat_shader_review.png`
  - `world3/docs/captures/m4/opentopo_unified_review.png`
  - `world3/docs/captures/m4/chunk_splat_stream_review.png`
- OpenTopo reference-vs-unified sampled panel delta is about 5.3 / 255.
- Chunk contract:
  - `world3/jobs/m4_chunk_material_contract.json`
  - `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`
  - `ChunkLoader.gd` has `splat_weights_path` for dynamic runtime binding.
- Known prototype caveat: fresh splat PNGs bind dynamically because a new
  unimported PNG is not loadable from `.tres` as a `Texture2D` in runtime
  Godot.

M5 is complete at prototype final form:

- `world3/scenes/walk.tscn` now uses visible 256 m `ChunkLoader.gd` chunks with:
  - `terrain_material = res://textures/wgv3/terrain_splat_alpine.tres`
  - `splat_weights_path = res://textures/m4_splat/alpine_height_slope_weights_rgba.png`
  - `chunk_size_m = 256`
  - `chunk_resolution_m = 8`
  - `view_radius_chunks = 1`
- The legacy single `Terrain.gd` is hidden; M6 defers its build and uses
  streamed chunk collision instead.
- The player spawn was lowered so smoke captures and interactive use start
  near the terrain instead of high in the sky.
- `ChunkLoader.gd` writes UVs with `_wrapped_fraction(...)`, matching height
  sampling. This fixed the first M5 smoke-test material split at a chunk edge.
- Static capture:
  `world3/docs/captures/m5/walk_chunk_splat_smoke.png`
- Scripted crossing runner:
  `world3/scripts/M5WalkStreamRunner.gd`
- Scripted crossing capture and metrics:
  - `world3/docs/captures/m5/walk_stream_after_crossing.png`
  - `world3/docs/captures/m5/walk_stream_smoke_metrics.json`
- Crossing result: 900 m along +Z, chunk path `[0,5] -> [0,9]`, 9 peak loaded
  chunks, 12 builds, 12 removals, 18.816 ms worst synchronous update.
- Long sampled walk review:
  - `world3/docs/captures/m5/walk_long_contact_sheet.png`
  - `world3/docs/captures/m5/walk_long_metrics.json`
- Long result: 1536 m along +Z, chunk path `[0,5] -> [0,11]`, 9 peak loaded
  chunks, 18 builds, 18 removals, 18.317 ms worst synchronous update.
- Evidence doc:
  `world3/docs/M5_WALK_SPLAT_STREAMING.md`
- Budget note:
  `world3/docs/M5_STREAMING_BUDGET.md`
- Final audit:
  `world3/docs/M1_M5_FINAL_AUDIT_2026_05_08.md`

M6 is complete for the primary walk/runtime hardening pass:

- Runtime image cache builder:
  `world3/pipeline/build_runtime_image_cache.py`
- Runtime loader:
  `world3/scripts/RuntimeImageCache.gd`
- Generated runtime caches:
  - `world3/runtime_cache/heightmap_rf32.json`
  - `world3/runtime_cache/heightmap_rf32.bin`
  - `world3/runtime_cache/alpine_splat_rgba8.json`
  - `world3/runtime_cache/alpine_splat_rgba8.bin`
- `walk.tscn` now uses export-safe height/splat cache paths and streamed
  collision chunks.
- `M5WalkStreamRunner.gd` records collision metrics and can rebuild after reset
  for clean measurement.
- `terrain_splat_unified.gdshader` has an opt-in transition-strip sampler.
- Runtime transition review scene:
  `world3/scenes/capture_phase_m6/transition_runtime_review.tscn`
- M6 captures:
  - `world3/docs/captures/m6/walk_stream_collision_cache.png`
  - `world3/docs/captures/m6/walk_stream_collision_cache_metrics.json`
  - `world3/docs/captures/m6/transition_runtime_review.png`
- M6 walk result: 900 m, 9 peak loaded chunks, 21 collision chunks built,
  60.433 ms total collision build time, 5.033 ms max collision build time,
  28.675 ms worst update, 4.594 ms p95 frame time.
- Source-material audit:
  `world3/docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.md`
- Source QA result: 10 of 17 green/organic materials flagged. Treat grass/
  leaves noise as source-material production-promotion work, not transition
  workflow failure.

M7-M12 near roadmap is now explicit:

1. M7 boundary-runtime integration.
2. M8 organic source-material cleanup.
3. M9 runtime performance and interaction polish.
4. M10 cross-source blending.
5. M11 corner and junction transitions.
6. M12 walk/iso/topdown view-mode parity.

Deferred systems remain after this lane: scatter, vegetation, props, buildings,
POIs, fantasy biome expansion, full procedural infinite-world extension, and
production asset promotion.

M7 pass 1 is complete for workflow/runtime validation:

- `ChunkLoader.gd` generates per-chunk transition masks from
  `world3/jobs/biome_transition_rules.json`.
- Boundary rules select catalog `from_material` / `to_material` IDs and
  transition manifests instead of scene-hardcoded shader placement.
- `terrain_splat_unified.gdshader` samples generated masks with
  `use_transition_mask`.
- Captures:
  - `world3/docs/captures/m7/boundary_runtime_review.png`
  - `world3/docs/captures/m7/boundary_runtime_biome_stress.png`
  - `world3/docs/captures/m7/boundary_walk_after_crossing.png`
  - `world3/docs/captures/m7/boundary_walk_metrics.json`
- Metrics: 9 peak loaded chunks, 12 chunks built, 6 transition masks built,
  83.454 ms total transition-mask build time, 14.142 ms max transition-mask
  build time, 26.599 ms worst update, 4.873 ms p95 frame time over 384 m.
- Honest visual read: M7 proves runtime placement, but not final terrain-art
  quality. The same-source control is calm but subtle; the biome stress case
  exposes known grassland/organic noise.

## Next best move

Run the M1-M7 visual audit before M8:

1. Use `world3/docs/M1_M7_VISUAL_AUDIT_PLAN_2026_05_08.md`.
2. Classify each current visual output as `PASS`, `PIPELINE_ONLY`, `REWORK`, or
   `DEFER`.
3. Decide whether M8 starts with organic material cleanup, or whether M7 needs a
   visual-targeted boundary pass first.
4. Keep streamed collision metrics active. If interactive play shows hitching,
   start async/background mesh+collision build.
5. In parallel or immediately after, regenerate/filter the flagged organic
   source materials before production promotion.

## Operating reminders

- Godot binary: `C:/Godot/Godot_v4.5-stable_win64.exe`.
- Captures generally need visible/windowed Godot; headless capture can hang.
- After deploying or regenerating `.tres`/PNG assets, run Godot import:
  `Godot --path world3 --quiet --headless --editor --import`
- Use surgical `git add <path>`. The worktree has preexisting OpenTopo worker
  dirt; do not stage unrelated `OPENTOPO_*`, toporeview, or pipeline files.
- Be careful with old review utilities that still use direct image loading.
  The primary `walk.tscn` runtime path is cache-safe; migrate legacy capture
  scripts as touched.
