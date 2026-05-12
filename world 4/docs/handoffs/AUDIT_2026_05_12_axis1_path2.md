# Audit prompt — Axis 1 Path 2 current state (2026-05-12)

> Drop this into a fresh session. The agent should NOT continue
> implementation — they should produce a structured assessment of
> what we have, what's broken, what's working, and recommend whether
> to refactor / continue forward / step back. Apply systematic-
> debugging discipline: gather evidence before judgment.

---PROMPT START---

I'm auditing W4 Axis 1 Path 2 (clipmap renderer). The current
session-driver shipped a lot of code, got tangled in shader bugs,
and the user is no longer confident in the implementation. Don't
trust their summary or my summary — re-derive ground truth from
the code, captures, and editor.

**Don't write new code.** This is a read-only audit pass.

## Read these in order

1. `world 4/CLAUDE.md` — project ethos. Quality ≥ Performance >
   anything > time-to-ship.
2. `world 4/docs/README.md` — doc structure.
3. `world 4/docs/STATE.md` — what we claim to have right now.
4. `world 4/docs/ROADMAP.md` — strategic shape.
5. `world 4/docs/reference/PITFALLS.md` — every known bug class,
   especially #6b (headless hides what editor shows), #7 (skirt
   clobber), #8 (half-texel UV), #9 (ring overlap math), #10 (worker
   shutdown), #11 (morph zones).
6. **Recent build-notes for Axis 1 Path 2:**
   - `build-notes/AXIS1_PATH2_STAGE3_BUILD_NOTES_2026_05_12.md`
   - `build-notes/MORPH_ZONES_BUILD_NOTES_2026_05_12.md`
   - `build-notes/STAGE4_1_BUILD_NOTES_2026_05_12.md`
7. `docs/superpowers/specs/2026-05-12-clipmap-splat-biomes-design.md`
   — Stage 4 parent spec (Stage 4.1 just shipped; 4.2+ pending).
8. **`docs/plans/AXIS1_PATH2_PLAN_2026_05_12.md`** — the original
   master plan. Compare what shipped against what was promised.

## Files to inspect (the active surface)

- `the world 4/scripts/ClipmapWorld.gd` — runtime root.
- `the world 4/scripts/ClipmapRing.gd` — one ring.
- `the world 4/scripts/AnchorCameraRig.gd` — camera (Node3D, no
  physics — the user is asking about walking collision).
- `the world 4/shaders/terrain_world_v3.gdshader` — the lit
  fragment shader. Read EVERY uniform decl, EVERY function. Look
  for: missing sampler hints, wrong UV math, hard-coded constants
  that should be tier knobs, fragment cost.
- `the world 4/worlds/scale_v2/material_world_v3.tres` — the
  material defaults. Check every uniform value.
- `the world 4/worlds/scale_v2/biome_catalog.json` — only 2 biomes;
  no kit_dir validation; check whether the materials actually exist.
- `the world 4/config/quality_tiers.json` — every perf knob.

## Reproduce + capture before judging

1. Reimport: `"C:/Godot/Godot_v4.5-stable_win64.exe" --headless
   --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -3`.
   Expect no errors.

2. Run all 4 capture scenes (walk + topdown × morph-on/off):
   ```
   for scene in capture_clipmap_morph_on capture_clipmap_morph_on_topdown \
                capture_clipmap_morph_off capture_clipmap_morph_off_topdown; do
     "C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 \
       --path "D:/assets/world 4/the world 4" --single-window \
       --disable-crash-handler "res://scenes/${scene}.tscn"
   done
   ```
   Read every output PNG via the Read tool.

3. Toggle `shader_parameter/show_debug_color = true` in
   `material_world_v3.tres` and re-capture. The ring-colored captures
   tell you which fragments are from which ring. Compare to
   production captures to identify what's geometry vs what's empty
   space.

## Specific suspicions to investigate

The session-driver has these concerns:

- **"Editor crash on exit"** — user-reported. The Stage 3.6 fix
  (`_shutting_down` flag + `_drain_pending_workers` in `_exit_tree`)
  should catch headless quit AND editor F6 stop. User says still
  crashes. Either the fix is bypassed, or the crash has a different
  source. Check `_exit_tree`, `_notification`, `_drain_pending_workers`
  in ClipmapWorld.gd. Look for: other code paths that might write to
  `_ring_tasks` or read `_composer` after teardown begins. Try
  running the editor manually and screenshotting `%APPDATA%/Godot/
  app_userdata/the_world_4/logs/` after a crash.

- **"Textures don't tile right"** — was fixed earlier today via
  `repeat_enable` + `source_color` on `pbr_ground_array`. Verify
  these hints are still on the shader. Run a capture and confirm
  texture extends continuously across all rings. (Note: alpine
  ground albedo legitimately looks like washed-out snow — see
  `materials/biome_alpine/ground/albedo.png` directly to confirm.)

- **"Ring is replacing ground, not part of ground"** — user said
  this earlier; was traced to the missing `repeat_enable`. Should
  be fixed. Verify with topdown capture.

- **"Banding"** — user described the alpine texture's dotted pattern
  as banding. May not be a bug — just the texture's appearance. Look
  at `materials/biome_alpine/ground/albedo.png` directly.

- **"View-based LOD too aggressive — everything disappears looking
  up"** — there's no view-based LOD in our code. Likely the user
  walked the camera above all 4 rings' Y range, or tilted up to look
  at the sky and there's no skybox. AnchorCameraRig has no Y clamp.

- **"No walking collision"** — confirmed. `AnchorCameraRig extends
  Node3D` — it's a free-cam, no `CharacterBody3D`, no gravity, no
  collision body. The Stage 3.5 `HeightMapShape3D` collision shapes
  exist but there's nothing to collide WITH them. Walking requires
  building a player controller. Never existed in any W4 scene.

## What to assess (your audit deliverables)

For each item below, give:
- ✅/⚠️/❌ status verdict
- Evidence (file + line OR capture path OR command output)
- Recommendation: keep / refactor / replace / defer

### A. Stage 1 — Kernel system
- Was promised: pure-function `NoiseStackKernel` + `KernelComposer`,
  Python ↔ GDScript bit-equivalent (max delta < 1e-4 m), preview CLI.
- Verify: run `pytest tests/test_kernel_*.py -v`. All should pass.
- Open question: is the cross-impl delta still under 1e-4 m?

### B. Stage 2 — Clipmap geometry
- Was promised: 4 nested rings with skirts, camera-snap, sine-wave
  debug shader.
- Verify: read `ClipmapRing.gd` `_build_donut_mesh`. Confirm
  PITFALLS #7 (skirt += not =) and #9 (inner_grid_n round down) are
  applied. Run `capture_clipmap_debug.tscn` if it still exists.

### C. Stage 3 — Heightmap stack + async + collision
- Was promised: kernel-driven heightmaps, async via
  WorkerThreadPool with double-buffer, HeightMapShape3D collision
  on inner rings (tier knob).
- Verify: walk capture shows real procedural terrain (not sine wave).
  Topdown capture shows variation across the world. Collision shapes
  exist on ring 0 (and ring 1 on high+ tier) — inspect with editor
  if possible. **Crucial:** does the collision actually work?
  Spawn a RigidBody3D and see if it lands.
- The Stage 3 capture is in
  `captures/axis1_clipmap_stage3_*` or the morph-on captures.

### D. Stage 3.6 — Morph zones
- Was promised: heightmap morph blend at ring boundaries
  eliminating the cliff. A/B captures.
- Verify: read the `morph_off` vs `morph_on` topdown captures with
  debug color enabled. Cliff visible with off → smooth with on?

### E. Stage 4.1 — Single-biome rendering
- Was promised: per-ring splat array (single layer full-weight) +
  global PBR ground array. Real biome texture renders.
- Verify: production capture (debug off). Texture visible, tiles
  smoothly across the world, no horizontal/vertical streaks at
  outer ring boundaries.

### F. Tier system
- Was promised: `quality_tiers.json` resolves to typed dict on both
  Python and GDScript. Default `high` for 3060 class. Cross-impl
  tests pass.
- Verify: `pytest tests/test_quality_tiers*.py -v`. Check
  `ClipmapWorld._resolve_config` prints the tier values in the log.

### G. Cross-cutting concerns
- **Test coverage**: count tests, sanity check what's actually
  being tested (per `STATE.md` should be 56 passing).
- **Documentation drift**: does STATE.md reflect current state?
  Does TOOLS.md mention every CLI/script/shader/class? Are there
  build-notes for every stage shipped?
- **PITFALLS coverage**: every new bug we hit got a PITFALLS
  entry? 11 should be the current count.
- **Shutdown discipline**: does the editor crash on F6 stop? If
  yes, gather the actual crash output (Godot logs, stderr) — DON'T
  guess at fixes.
- **Player controller gap**: no walking collision. Is this OK for
  Stage 4.2-4.5 to proceed, or is it blocking? Should we spec a
  PlayerController task?

### H. Architectural concerns to flag if you see them

- Code smell: duplicated logic between sync `_refresh_ring_heightmap`
  and worker `_worker_compute_heightmap` (shared via
  `_compute_heightmap_floats` — verify this is actually shared and
  not drifting).
- Code smell: `_per_ring_shader_material(r)` walks children every
  call. Should be cached on the ring.
- Performance: outer rings sample the same PBR texture but at very
  coarse mesh density. Is the per-fragment normal cost worth it on
  outer rings? Could swap to per-vertex on rings 2-3 to reclaim.
- Streaming: nothing exists. World is 4km × 4km hardcoded. Adding
  more terrain past that = ring 3 still renders but at Y=0 (the
  composer keeps producing values past any "bound"). Is this OK?

## What you should output

A markdown report with:

1. **Pass/fail per shipped stage** (sections A-F above) with
   evidence-cited verdicts.
2. **Outstanding bugs** with severity (blocker / major / minor /
   cosmetic) and recommended path: fix now / fix during Stage 4.2 /
   defer to Stage 5+ / wontfix.
3. **Documentation drift** — concrete edits the session-driver
   should make to STATE.md, TOOLS.md, PITFALLS.md.
4. **Architectural assessment**: are we on a solid foundation for
   Stage 4.2 (biome culler + multi-biome shading), or do we need to
   refactor first?
5. **Top 3 priority items** if the user could only fix three things
   before continuing.

Don't recommend "more tests" generically — point at SPECIFIC
behaviors that lack coverage. Don't recommend "more docs" generically
— point at SPECIFIC missing entries. Be useful, not safe.

---PROMPT END---
