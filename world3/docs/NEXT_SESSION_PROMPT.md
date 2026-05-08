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
- `HEAD pending` - M5 walk-scene stream wiring

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

M5 pass 1 is wired:

- `world3/scenes/walk.tscn` now uses visible 256 m `ChunkLoader.gd` chunks with:
  - `terrain_material = res://textures/wgv3/terrain_splat_alpine.tres`
  - `splat_weights_path = res://textures/m4_splat/alpine_height_slope_weights_rgba.png`
  - `chunk_size_m = 256`
  - `chunk_resolution_m = 8`
  - `view_radius_chunks = 1`
- The legacy single `Terrain.gd` is hidden and retained for collision only.
- The player spawn was lowered so smoke captures see terrain instead of sky.
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
  chunks, 12 builds, 12 removals, 20.096 ms worst synchronous update.
- Evidence doc:
  `world3/docs/M5_WALK_SPLAT_STREAMING.md`

## Next best move

Continue M5 from pass 1:

1. Let the user visually review `walk.tscn` and the M5 captures.
2. Run or build a longer user-facing walk capture if the pass 1 view is
   accepted.
3. Write the concise streaming budget note for the wired `walk.tscn` path.
4. Choose the next hardening target: export-safe generated image import/cache,
   streamed collision, or boundary-strip sampling.

## Operating reminders

- Godot binary: `C:/Godot/Godot_v4.5-stable_win64.exe`.
- Captures generally need visible/windowed Godot; headless capture can hang.
- After deploying or regenerating `.tres`/PNG assets, run Godot import:
  `Godot --path world3 --quiet --headless --editor --import`
- Use surgical `git add <path>`. The worktree has preexisting OpenTopo worker
  dirt; do not stage unrelated `OPENTOPO_*`, toporeview, or pipeline files.
- `world3/docs/DECISIONS.md` currently has unrelated unstaged OpenTopo edits in
  the worktree. Stage only explicit hunks if adding decisions.
