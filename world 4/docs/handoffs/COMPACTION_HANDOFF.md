# W4 Compaction Handoff — for myself

> When my context compacts, this is the doc that resumes me. Different
> from `HANDOFF.md` — that one is for a fresh chat starting cold from
> the user's perspective. This one is for ME continuing with operator
> authority that the user just granted.

## What changed in operator mode (2026-05-11)

The user explicitly said: **"make decisions and help review and stuff."**

This means:

- I make the architectural and tactical calls myself instead of asking
  "which one do you want?" on every fork.
- The user reviews and course-corrects rather than directs.
- I still ask the user before:
  - **Destructive operations** (deleting work, force pushes, dropping data)
  - **Genuinely 50/50 calls where I have no opinion**
  - **Anything that breaks the anchor regression baseline**
  - **Anything that touches W3 (it's archive — read-only)**
- I do NOT ask the user about:
  - Which axis to expand next when one is obviously next
  - Whether to write a plan first vs. iterate (decide based on scope)
  - Texture/shader/material choices when one is clearly best
  - File organization
  - Doc updates after work lands

## What the user values (and what they got tired of)

**Values:**
- Quality > performance > organization (in that order, per AXES.md principles)
- Honest assessment, including "I don't know yet"
- Methodical, one-change-at-a-time iteration when something's broken
- Editor screenshots as ground truth, not headless captures
- KISS / YAGNI in service of quality

**Got tired of in prior sessions:**
- Asking permission for every routine decision
- "Which one do you want?" when I should have just picked
- Tweaking 5 parameters at once during debugging (the multi-knob flail)
- Trusting headless captures over user screenshots
- Big bursts of autonomous doc creation without checking in
- Guessing at root causes instead of running minimal isolation tests

The operator-mode shift means **less asking permission**, but the
**multi-knob flail and trust-headless mistakes are STILL prohibited** —
those weren't permission-related, they were methodological.

## State of W4 at this handoff

**Anchor demo is working at mockup quality, locked as the regression baseline.**

Last verified 2026-05-11. Don't break this:

- DEM: USGS1m Blue Ridge (Shenandoah, VA), 256m × 256m crop
- Shader: `terrain_anchor_v2.gdshader` (3-slot slope-blended, no procedural splat/macro)
- Materials: `scrub_dense` + `tundra_lichen` + `rocky_slope` (real-ortho mix with ComfyUI lichen)
- Shader has all the guardrails documented (luma_floor, ao_floor, NaN guards, tangents)
- 3 cameras working, water plane sized properly, sky procedural
- Mesh `cast_shadow = OFF`

**Pipeline state:**
- v1 files (`build_splat_and_macro.py`, `write_material_tres.py`,
  `terrain_anchor.gdshader`, v1 .tres backup) are legacy/dead but kept
  on disk for reference. Don't run them.
- v2 is current. Build path is: `pick_dem_crop.py` →
  `write_material_tres_v2.py` → Godot `--import` → open scene.

## Next decision I just made

**Next axis: Scale (Axis 1) — multi-tile streaming.**

The user offered to delegate this decision to me and I'm picking it.
Reasoning:

1. It's the W3 wall — the architectural step W4 was built to cross.
2. Currently every other axis is constrained to a 256m sandbox; after
   streaming works, every axis becomes more interesting because there's
   actually a world to put things in.
3. Concrete, bounded work: ~half a session to a session.
4. The shader/material work doesn't need to change — it just needs to
   render correctly across multiple meshes. That's a small surface area
   to debug.

**View axis (Google Maps zoom) is the second pick** if the user pushes
back on Scale or after Scale ships. Smallest visible-wow-per-hour ratio.

**I do not start coding before:**
- Writing a brief plan (Plan tool / plan-mode) — Scale is non-trivial
  enough to deserve one
- Confirming with the user what minimum proof-of-concept satisfies the
  axis exit criterion ("walk the camera across the world, chunks
  load/unload seamlessly, no visible seams")

## Resumption checklist (run when compaction lands)

1. Read this file (you are doing it now)
2. Read `ANCHOR.md` to remember the anchor invariants
3. Read `ANCHOR_BUILD_NOTES.md` top section — the black-speckle lesson
4. Read `AXES.md` Axis 1 (Scale) section — the planned next experiment
5. Read `ORCHESTRATOR_GUIDE.md` — how the pipeline runs
6. Check current state with: `ls "D:/assets/world 4/the world 4/worlds/anchor/"` (should have heightmap.png, meta.json, material.tres, layers/)
7. Continue from "Next decision I just made" above (start Scale axis,
   plan first since it's non-trivial)

## Critical landmines (the hard-won lessons)

These cost hours in prior sessions. Don't repeat them:

### 1. The black-speckle bug
- Not a shader bug. Source textures had near-black texels (esp.
  `tundra_lichen/albedo.png` and `tundra_lichen/ao.png`).
- Fix is **guardrails** in shader (luma_floor, ao_floor, NaN guards on
  weights, no normalize on potentially-zero vectors, mesh tangents via
  SurfaceTool, mesh cast_shadow=OFF) PLUS validating new textures for
  near-black islands before binding.
- Don't tune shader params when source data is the issue.
- Full lesson: `ANCHOR_BUILD_NOTES.md` top section.

### 2. Headless vs editor render divergence
- Godot's headless OpenGL Compatibility renderer ≠ editor's Forward+
  Vulkan renderer. Bugs in editor often invisible in headless captures.
- **Always trust user editor screenshots over my own headless captures.**
- If I want to verify something I built, ask the user for an editor
  screenshot, don't run a headless capture and declare success.

### 3. The multi-knob flail
- When debugging visual artifacts, change ONE thing per iteration.
- Capture/verify, accept or reject, then change the next thing.
- Never change 5 params at once "just to see."
- W3 had this exact methodology (`review_*` exports on
  World3AutoReviewTour.gd, each a separate knob).

### 4. Godot import caching
- After editing shader / texture / .import / script files from outside
  Godot, run `--headless --import` or right-click in Godot's
  FileSystem → Reimport. Without this, edits don't take effect.
- This is the #1 reason "nothing is changing" — it's not the code,
  it's the cache.

### 5. The plan-as-N-biomes primitive (W3 wall)
- Don't ever build a streaming system where each tile is an independent
  height generator with its own elev_min/elev_range. That was W3's wall.
- The scale axis MUST use one continuous heightfield source, sliced
  into tiles. F.3.1-style "thread edges between independent generators"
  is the wrong primitive.
- Per the memory entry `w4_kickoff_decision.md` and the AXES.md
  Scale axis "Notes" section.

## User contract (operator mode rules)

- I decide tactics and axis order
- I propose architecture; user accepts or pushes back
- I write plans before non-trivial work (Scale, Textures workflow, etc.)
- I capture and post results after each meaningful step
- I update docs as state changes (don't let docs go stale)
- I commit (when user asks) with clear messages

I do NOT:
- Start coding without a plan for non-trivial work
- Make changes that break the anchor regression baseline
- Touch W3 (archive, read-only)
- Burn a session on visual tuning before doing minimal isolation tests
- Run more than 2-3 changes without a checkpoint capture

## What success looks like at end of next axis (Scale)

`AXES.md` Axis 1 exit criterion: "walk the camera across the world,
chunks load/unload seamlessly, no visible seams at tile boundaries
(source is continuous — slicing one heightmap, not stitching N)."

Concrete acceptance test:
- Take the existing Blue Ridge USGS tile, crop a 1024m × 1024m region
  (4x bigger than anchor)
- Slice into 4×4 = 16 tiles at 256m each
- One streaming loader pages tiles in/out around the camera
- Shader/material unchanged from anchor v2
- Walk camera across full world, no visible cliffs or texture seams at
  tile boundaries
- Anchor 256m demo still works as regression baseline

If Scale ships clean: pick the next axis based on what unblocks the
most. Default suggestion order if user doesn't say otherwise:
View → Textures workflow → Biomes → Source kernelization → Decoration.
