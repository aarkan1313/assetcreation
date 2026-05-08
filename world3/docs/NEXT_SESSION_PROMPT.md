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
- `HEAD at handoff` - M2 tuned transition assets

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

## Next best move

Start M4:

1. Build the unified splat shader prototype against catalog material IDs and
   the boundary rule contract.
2. Keep transition strips as generated boundary assets referenced by
   `biome_transition_rules.json`; do not add them to the base material catalog.
3. Preserve residual normal-energy mismatch on stress pairs as a shader/source
   QA signal, not something to hide.

Then start M4:

- Unified splat shader.
- Chunks emit per-pixel weights against catalog materials.
- Shader supports both current `terrain_blend` behavior and the OpenTopo
  `terrain_hex_detail` material style.

## Operating reminders

- Godot binary: `C:/Godot/Godot_v4.5-stable_win64.exe`.
- Captures generally need visible/windowed Godot; headless capture can hang.
- After deploying or regenerating `.tres`/PNG assets, run Godot import:
  `Godot --path world3 --quiet --headless --editor --import`
- Use surgical `git add <path>`. The worktree has preexisting OpenTopo worker
  dirt; do not stage unrelated `OPENTOPO_*`, toporeview, or pipeline files.
- `world3/docs/DECISIONS.md` currently has unrelated unstaged OpenTopo edits in
  the worktree. Stage only explicit hunks if adding decisions.
