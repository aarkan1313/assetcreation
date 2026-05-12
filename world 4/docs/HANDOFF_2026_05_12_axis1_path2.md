# Handoff prompt — Axis 1 Path 2 execution (real-game scale + procedural amplification)

> Paste this into a fresh chat to pick up Axis 1 Path 2 in mid-flight.
> Self-contained — the agent should be able to start from this alone.

---

I'm continuing **W4 Axis 1 Path 2 execution**. Working directory:
`D:\assets\world 4\`. Branch: `main` (Path 2 work commits directly to
main — the previous Axis 6 work merged 2026-05-12).

## Read these docs in order before doing anything

1. `docs/HANDOFF.md` — the stable W4 takeover prompt (read first).
2. `docs/plans/AXIS1_PATH2_DESIGN_2026_05_12.md` — the design spec.
3. `docs/plans/AXIS1_PATH2_PLAN_2026_05_12.md` — the implementation
   plan. **This is what you're executing.** Stages 1-6, each with
   tasks broken into checkbox steps.
4. `docs/reference/PITFALLS.md` — 6 documented terrain artifact
   classes. Especially #3 (PBR-at-scale → use `unshaded`), #5
   (Texture2DArray layer uniformity), and #6 (per-tile splat
   boundaries — solved by world-splat in Axis 6, the lesson is "test
   visually in the editor, not just headless").
5. `docs/ROADMAP.md` — what's done, what's next.

## How to work

- **Execute the plan one stage at a time.** Each stage's exit gate
  is a specific verifiable result. Don't move on until it's met.
- **Each task in the plan is bite-sized** (write test, run test
  fail, write code, run test pass, commit). Mark checkboxes as you
  go but don't write empty steps — if a step doesn't change
  anything, skip it.
- **Tests are pytest** for Python (run from `world 4/` dir).
  GDScript has no test framework — rely on `--import` parsing,
  headless captures, and user editor verification.
- **Editor verification is required** for any visual change per
  PITFALLS #6b. Print the launch command for the user to run
  manually — DO NOT background-launch the editor from the harness
  (see memory `editor_launch_workflow.md` — backgrounded GUI
  launches fire "completed" notifications immediately and break the
  verify-then-iterate loop).
- **One change at a time** during visual debugging. Headless +
  editor captures both per significant change.
- **Methodological hard rules** (`COMPACTION_HANDOFF.md`): drive
  tactics; ask only on destructive / anchor-breaking / W3-touching
  changes. The user wants long-term-best architecture (memory
  `feedback_best_long_term_default.md`).

## Where we are right now

**Just shipped (2026-05-12 sessions, all merged to main):**
- Axis 1 first expansion (1024m scale_demo, 16 tiles).
- Axis 2 (5 biomes, per-tile materials, then world-splat
  architecture as the canonical multi-biome path).
- Axis 4 first expansion (walk/iso/topdown view shaders).
- Axis 6 transitions: kernel-system-precursor (per-biome catalog,
  PBR Texture2DArray, world-spanning splat Texture2DArray sampled
  at world XZ).

**About to start — Axis 1 Path 2:**
- 4 km × 4 km world. 256 tiles equivalent, but rendered as 4 nested
  clipmap rings (~525k tris total regardless of world size).
- Kernel-based procedural terrain generation. `NoiseStackKernel` is
  v1's only kernel; `Kernel` interface + `KernelComposer` set up
  so Path 3 (erosion, DEM-patch, river-network kernels) plug in as
  additive subclasses.
- World bound is one config value — removing it later = the
  renderer keeps working (note: "infinite worlds" also need
  camera-relative origin, persistence, collision paging — those are
  separate sub-projects; this plan is the renderer-readiness only).

**5-7 sessions estimate.** Six stages:

| Stage | Goal | Exit |
|---|---|---|
| 1 | Kernel system foundation (Python + GDScript impls, cross-impl test pinning them numerically) | 4 pytest files passing + preview PNG sensible |
| 2 | Clipmap geometry (4 rings, donut meshes WITH SKIRTS, camera-snap, debug shader with sine-wave) | Rings line up cleanly, debug capture clean, user editor confirms no boundary gaps |
| 3 | Heightmap stack — wire `KernelComposer` to ring heightmaps. Tasks: 3.1 displacement slot, 3.2 v3 shader, 3.3 synchronous integration, **3.4 async/double-buffer via WorkerThreadPool**, **3.5 HeightMapShape3D collision proxy** | Real procedural terrain renders, async eliminates hitches, character physics works on terrain |
| 4 | Clipmap splat — per-ring biome splat array, biome materials render | Biomes render correctly, smooth boundaries, no hitches |
| 5 | World seed + bound + new scene (scale_v2.tscn) + view-mode hotkeys | scale_v2 playable, world extends to horizon, no grey |
| 6 | Build-note + ROADMAP/AXES/TOOLS + memory + final regression captures | All docs current; anchor + scale_demo regression-unchanged |

## Critical context (don't relearn)

- **Spec/plan revised after external review.** The original draft
  had 5 real technical issues (FORMAT_RH precision was wrong, ring
  boundary cracks weren't addressed, no collision plan, async upload
  was hand-waved, "remove bound = one config" was oversold). All
  fixed in commit `8e2b89d` on main. The current docs are correct;
  re-read them, not earlier versions in git history.
- **R32F for displacement textures** — not R16F. Half-float doesn't
  give "cm precision at ±32 km" (the original wrong claim).
- **Skirts ARE required** for ring boundaries. Clipmap docs that
  say "no seams by construction" are wrong without skirts. Spec
  section "Ring boundary stitching (REQUIRED)" + Tasks 2.1/2.2 in
  the plan implement them.
- **Async + double-buffer is required** for ring heightmap regen
  (PackedFloat32Array off-thread, ImageTexture upload on main).
  `RenderingServer` is main-thread-only.
- **Collision via `HeightMapShape3D` per ring**, sharing the worker's
  heightmap array. Without this, characters fall through GPU-
  displaced terrain.
- **Kernels run on CPU only.** Shaders never call into kernels —
  kernels produce textures; shaders sample textures. New kernel =
  new Python + GDScript classes, no shader changes.
- **Python + GDScript kernel impls must agree bit-equivalent**.
  Stage 1.6 has the cross-impl test. The `_hash2` constants and
  the gradient math are pinned to match across the two impls.
- **Existing world-splat (Axis 6) lives at `worlds/scale_demo/`** —
  do not break it. Axis 1 Path 2's new world is `worlds/scale_v2/`,
  a fresh bundle. The existing 1024m scale_demo stays as legacy
  reference.

## What's already on disk

- `pipeline/biome_catalog.py` (Axis 6) — reuse as-is for scale_v2's catalog.
- `pipeline/build_biome_arrays.py` (Axis 6) — reuse for scale_v2's
  layer_manifest.json.
- `the world 4/scripts/ScaleWorld.gd` — Axis 6's runtime, **do NOT
  break it.** New `ClipmapWorld.gd` is a separate file.
- `the world 4/shaders/terrain_world_v2.gdshader` — Axis 6's shader,
  **do NOT break it.** New `terrain_world_v3.gdshader` is separate.
- `the world 4/scenes/scale_demo.tscn` — Axis 6's scene, **do NOT
  break it.** New `scale_v2.tscn` is separate.
- `the world 4/scripts/AnchorCameraRig.gd` — used by both worlds.
  May need minor edits to support both ScaleWorld and ClipmapWorld
  (Stage 5 will handle).

## Start with Stage 1, Task 1.1

Open the plan. Stage 1, Task 1.1 ("Create the pipeline kernel package
+ abstract base") is the first thing. Steps are bite-sized: write
failing test → run it fail → write code → run pass → commit. Follow
the plan literally.

When you finish Stage 1's last task (1.7 — KernelComposer GDScript),
all 4 pytest files should pass, and the kernel system is ready for
Stage 2's clipmap geometry.

---

If you're picking this up after a context break:

1. Read all of `AXIS1_PATH2_PLAN_2026_05_12.md` (it's long; the
   stages are independent enough to skim once and refer back).
2. Check `git log --oneline -20` for the last commits. Match against
   the plan's task list (commit messages reference task numbers like
   "axis1: 1.4 build_kernel_preview.py").
3. Continue from the next un-checked task.

Good luck.
