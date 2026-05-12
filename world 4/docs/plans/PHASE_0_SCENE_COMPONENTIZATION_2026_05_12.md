# Phase 0 — Scene Componentization

> **Do this first**, before any Tier 1 roadmap work. The new roadmap
> adds more test scenes (skybox testing, infinite-world testing,
> stochastic-texture testing, decoration testing). Without a
> componentization pass the duplication cost compounds with every
> new feature.
>
> Owner: whoever picks up the new roadmap. Estimate: 1-2 sessions.
> Outcome: future scene work is "instance the prefab + add the
> test bits" instead of "copy-paste 25 lines + edit one param."

## The problem, concretely

W4 has 19 `.tscn` files today. The clipmap-world ones are nearly
clones:

| Pair | Lines | Diff |
|---|---|---|
| `clipmap_debug.tscn` vs `test_harness/clipmap_walk_test.tscn` | 27 each | **1 line** (root node name) |
| `capture_clipmap_morph_on.tscn` vs `capture_clipmap_morph_off.tscn` | 31 each | **3 lines** (name, `debug_disable_morph`, `output_path`) |
| Same 4-pair pattern across `capture_clipmap_morph_{on,off}_topdown` | 31 each | similar |

Every clipmap scene re-wires the same boilerplate:
- `World` node with ClipmapWorld script + 4 export params
- `CameraRig` node with AnchorCameraRig script + path back to World
- `Sun` DirectionalLight3D with fixed transform + lighting params
- Optionally: PlayerBody, HeadlessCapture, AutoWalker, PerfHUD

**This is real friction**, not a hypothetical:
- New ClipmapWorld export param? Edit 6+ scenes.
- New shared component (e.g. skybox)? Edit 6+ scenes.
- New capture variant? Copy-paste a 30-line scene, edit 3 lines.
- Cross-scene visual debugging (e.g. "why does walk_test look different
  from debug?") gets answered by `diff` rather than by reasoning about
  one canonical setup.

**The code is universal — only the scenes are tangled.** ClipmapWorld /
AnchorCameraRig / PlayerBody are scripts that self-configure from
exports. The infrastructure is right; the *wiring* is duplicated.

## The fix

Godot's idiomatic answer: `PackedScene` instancing. Factor the shared
wiring into one or two reusable scene-level components, then have all
test/capture scenes instance them.

### Architecture sketch

Three componentized scenes ship under `scenes/components/`:

```
scenes/components/
  clipmap_world.tscn      — World + CameraRig + Sun + default lighting
  scale_world.tscn        — ScaleWorld + CameraRig + Sun (for scale_demo
                            and its capture variants)
  anchor_world.tscn       — AnchorTerrain + CameraRig + Sun
                            (for anchor regression captures)
```

Each component scene:
- Exposes the same export params as the underlying world script
  (forwarded via `@export var` properties on a root script)
- Has internal node paths wired correctly (camera_path, terrain_path)
- Is a `Node3D` that consumer scenes drop in as a child

Consumer scenes shrink to "instance the component + add the
test-specific bits":

```tscn
# clipmap_debug.tscn (NEW SHAPE — ~10 lines instead of 27)
[ext_resource type="PackedScene" path="res://scenes/components/clipmap_world.tscn" id="world"]

[node name="ClipmapDebugScene" type="Node3D"]
[node name="World" parent="." instance=ExtResource("world")]
world_seed = 42

# (that's it — Sun, CameraRig, default ClipmapWorld config all
# come from the component)
```

```tscn
# capture_clipmap_morph_on.tscn (NEW SHAPE — ~14 lines)
[ext_resource type="PackedScene" path="res://scenes/components/clipmap_world.tscn" id="world"]
[ext_resource type="Script" path="res://scripts/HeadlessCapture.gd" id="cap"]

[node name="CaptureMorphOn" type="Node3D"]
[node name="World" parent="." instance=ExtResource("world")]
world_seed = 42
debug_disable_morph = false

[node name="Capture" type="Node" parent="."]
script = ExtResource("cap")
output_path = "res://captures/axis1_clipmap_morph_on_2026_05_12.png"
warmup_frames = 60
viewport_size = Vector2i(1280, 800)
force_camera_mode = "walk"
```

### Why three components, not one universal one

Anchor, scale_demo, and clipmap_v3 are **architecturally different
renderers** (single-mesh / tile-paged / clipmap-rings). They share
CameraRig and Sun but the world node is different. One component
per renderer keeps the contract clean.

`scenes/components/` is the namespace for the shared prefabs. Could
end up being just `clipmap_world.tscn` if anchor + scale_demo are
considered "legacy / don't touch." Decide in Task 1.

## Plan — 9 tasks across 1-2 sessions

### Task 1: Decide scope

Open question: how aggressive is the componentization?

- **Minimal**: only build `clipmap_world.tscn`, leave anchor + scale_demo
  scenes untouched. New tests benefit; old scenes pay no cost.
  **Recommended starting point.**
- **Full**: build all three components, migrate every test scene.
  Bigger payoff long-term, more churn now.
- **Conservative**: build `clipmap_world.tscn` AND migrate the 6
  clipmap-related scenes (debug, walk_test, 4× morph captures).
  Sweet spot for current state. **Probably the right call.**

Lock in the choice before writing any code.

### Task 2: Build `clipmap_world.tscn` component

Create `the world 4/scenes/components/clipmap_world.tscn` containing:
- Root `Node3D` named `ClipmapWorldComponent`
- Child `World` (Node3D + ClipmapWorld.gd script) with default
  exports matching the current usage (`bundle_dir`, paths, seed=42)
- Child `CameraRig` (Node3D + AnchorCameraRig.gd) with
  `terrain_path = NodePath("../World")` pre-wired
- Child `Sun` (DirectionalLight3D) with the existing transform +
  light_energy=1.2 + shadow_enabled=false

**Key**: the `camera_path` on World must point to `../CameraRig/WalkCamera`
**relative to the consumer scene's root**, not relative to the component.
This is the Godot gotcha — when you instance a scene, the relative paths
inside the instance still resolve relative to the instance's root.
Validate by loading the component standalone in the editor and confirming
no missing-node errors.

If the camera_path needs to be authored per-consumer, expose a script-
level `@export var camera_path` on the component root and forward it
to the World node in `_ready()`.

### Task 3: Migrate `clipmap_debug.tscn`

Replace contents with the new instance-based shape (see "Architecture
sketch" above). Headless-import the project, open the scene in the
editor, verify no errors. Should look identical.

### Task 4: Migrate `test_harness/clipmap_walk_test.tscn`

Same migration. The PlayerBody stays as a sibling of the instanced
component (not inside it — PlayerBody is opt-in per-scene).

### Task 5: Migrate the 4 morph capture scenes

`capture_clipmap_morph_{on,off}{,_topdown}.tscn`. Each one shrinks
to ~14 lines. Run a headless capture round on each to make sure the
output paths still resolve and the captures match the pre-migration
baseline. Compare bytewise — content should be identical.

### Task 6: Validate captures unchanged

Run all 4 morph capture scenes headless. Compare output PNGs
bytewise (or visually) against the pre-migration committed captures.
**Anything not bit-identical is a bug** — the component should be a
pure refactor.

### Task 7: Document the component contract

Add `scenes/components/README.md` describing:
- What each component is for
- What exports each one surfaces
- How to instance one in a consumer scene
- The camera_path / terrain_path gotcha if it survives

Also update `docs/reference/TOOLS.md` to list the component prefabs.

### Task 8: Update HANDOFF.md to mention the pattern

So future sessions know to instance components, not copy-paste scenes.

### Task 9: Stretch — migrate scale_demo + anchor capture scenes

Only if Task 1 picked "Full". Otherwise defer.

## Verification checklist

Before declaring Phase 0 done:

- [ ] All migrated scenes load without errors in the editor.
- [ ] All migrated capture scenes produce bit-identical (or visually
      identical) output PNGs compared to pre-migration baseline.
- [ ] Walk-test scene still functions (G-toggle, walk, fly-cam swap).
- [ ] Clipmap debug scene still renders the same way.
- [ ] No script changes — only `.tscn` edits + one new component scene.
- [ ] `scenes/components/README.md` exists.

## What this enables (and doesn't)

**Enables:**
- New test scenes for Tier 1+ work (skybox testing, infinite-world
  testing, stochastic-texture testing, decoration testing) are
  5-minute drops instead of 30-minute copy-paste-and-rewire jobs.
- Changes to default lighting / camera / world bootstrap apply
  everywhere by editing the component.
- Less visual-debugging-by-diff because there IS one canonical setup.

**Doesn't enable:**
- A "drop W4 into any Godot project" experience. That's a separate
  effort (per-game packaging, Tier 4).
- Universal anchor + scale_demo + clipmap interop. Each renderer
  still has its own component because they're architecturally
  different.
- Eliminating the per-test-scene-specific bits (capture path,
  AutoWalker config, etc.). Those are inherent.

## Why this is Phase 0 and not Tier 0 cross-cut

Tier 0 cross-cuts are *ongoing concerns* (performance, LLM-drivability)
that every feature must honor forever. Phase 0 is a **one-time
prerequisite** — fix the foundation, then never touch it again.
Different category. Keeping them named separately so future-us doesn't
confuse "we should refactor scenes" (one-shot) with "we should benchmark
on 3060" (forever).

## After Phase 0 lands

Resume Tier 1 of `docs/ROADMAP.md`:

1. Finish Axis 1 Path 2 — Stage 4.2 (multi-biome culler) + editor
   verification of stages 1-3.6 + 4.1.
2. Remove world-bound for infinite world.
3. Skybox + atmosphere. **(Will benefit from Phase 0 — new test scene
   for atmosphere lighting becomes trivial.)**
4. Intra-biome regional variation v0 — tile scale.

Phase 0 specifically de-risks #3 onward because each new visual
system wants its own test scene. With the component pattern in
place, "make a test scene for skybox time-of-day" is a 5-minute
job, not a 30-minute boilerplate copy.
