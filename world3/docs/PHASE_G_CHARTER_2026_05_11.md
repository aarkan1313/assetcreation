# Phase G — Polish + consumer integration

> Phase F ships a working pipeline that produces tile-able worlds.
> Phase G makes those worlds *survive contact with consumers* — LOD
> for distance, alternate perspectives, handcraft overrides for plot
> points, and an integration kit that lets external runtimes consume
> bundles cleanly.

## Why Phase G exists

Phase F's exit state is "one command produces a 5km tile-able world
the player can walk across." That's a pipeline win, but it doesn't
yet ship something a game can use. Phase G closes the gap between
"working pipeline" and "useful pipeline":

- The 5km world looks fine at walk distance but the procedural
  geometry doesn't hold up at 1km (no LOD layer)
- It's 3D only; 2.5D + topdown perspectives are stubbed but not
  parameterized
- Special zones (plot points, real-DEM landmarks) have no clean
  override path
- An external game runtime has no documented contract for consuming
  bundles end-to-end

## Sub-phases

### G.1 — LOD-aware capture + zoom-level emission

**Goal:** Bundles emit multiple LOD layers; captures auto-frame
per zoom level (close ~5-20m, mid ~100m, far ~1km).

**Scope:**
- Extend bundle contract with optional LOD layers (downsampled
  heightmap, macro albedo at lower resolution, simplified mesh
  hints)
- Capture driver learns `--zoom-level {close|mid|far}` → auto-computes
  framing from `meta.json`'s `world_size_*_m` + the zoom band
- Audit script for "are LOD layers consistent with the base layer"
- Closure doc with before/after captures at three zooms

**Exit:** Three-zoom captures of the F.7 starter world look clean
at every band on every existing perspective.

### G.2 — 2.5D perspective

**Goal:** A first-class 2.5D view mode (locked angle, orthographic
or near-ortho, suited to RPG / strategy hybrids).

**Scope:**
- `terrain_blend_<kit>_25d.tres` material variants
- 2.5D tour profile in `World3AutoReviewTour.gd`
- `view_modes` schema enum extended to `walk|iso|topdown|25d`
- Per-mode quality bar entry (feeds G.5)

**Exit:** 5-biome starter world renders cleanly in 2.5D, all five
biomes captured + reviewed.

### G.3 — Handcraft override path (patch bundles)

**Goal:** A "patch bundle" type that overlays a region of a plan
without rebuilding the whole world.

**Scope:**
- New `bundle_type: "patch"` in the request schema
- Patch bundles can override heightmap + macro albedo + scatter
  masks for a specified world-rect within an existing world plan
- Seam logic re-runs at patch borders (uses F.4 transition audit
  math); patch borders are first-class consumers of the audited
  catalog quality
- World map updated to declare patch precedence over base tiles
- Streaming director respects patch precedence at runtime

**Exit:** Run the starter world, hand-author a patch bundle for one
zone, verify the patch shows up correctly with clean seams to the
surrounding procedural tiles.

This absorbs the M22 "real-DEM patch seeding" scope from the
retired roadmap.

### G.4 — Consumer integration kit

**Goal:** An external game runtime (or tool) can consume world3
bundles end-to-end without reading world3's internal source.

**Scope:**
- `world3/contracts/` — versioned schemas for every artifact a
  consumer reads (heightmap PNG bit depth + range encoding,
  meta.json field stability, layer naming, world_map.json semantics)
- Reference consumer: a minimal Godot project (or library) that
  reads world3 bundles and renders them, lives outside `world3/`
- Compatibility audit script that diffs current emitted bundles
  against the declared contract
- Closure doc with the consumer integration walkthrough

**Exit:** A new engineer (or LLM) can write a consumer for world3
bundles using only the contracts/ directory + the reference consumer.

### G.5 — Per-mode quality bars measured at gate time

**Goal:** M13 promotion gate explicitly measures + reports quality
per view mode (walk vs iso vs topdown vs 25d), not just bundle-wide.

**Scope:**
- Extend `production_promotion_candidates.json` schema with per-mode
  state (a bundle can be `production_promoted` for iso but only
  `production_candidate` for walk)
- Per-mode capture metric extraction (OCR + structural delta against
  prior promoted captures)
- Audit script emits per-mode verdicts
- Closure doc with the new gate report shape

**Exit:** Running the audit script on the starter world produces
per-mode verdicts for every bundle, with quantified gates.

Absorbs G10 from the retired operability gaps register.

### G.6 — Real-DEM patch seeding refinement

**Goal:** The G.3 patch path works for real-DEM patches as the
primary case (not just hand-authored procedural overrides). Real-world
landmarks (a known mountain, a specific canyon) get pulled from
the OpenTopo cache and dropped into a plan as patches.

**Scope:**
- `patch_bundle_request.json` schema with `source.type == "real"`
  pointing at an OpenTopo-cached DEM
- Patch builder reuses Phase B chain-1 (build_opentopo_textured_master_stack)
- Patch borders re-run F.4 transition audit against neighboring
  procedural materials
- Closure doc with a real-DEM patch in the starter world

**Exit:** One real DEM (e.g. a famous landmark) embedded as a patch
in the procedural 5-biome world, all seams clean.

Absorbs the remaining M22 scope after G.3 lands the generic patch
mechanism.

## Cross-cutting concerns

### Scale (carried from F)

LOD work is scale's hardest stress test. G.1's zoom-level emission
must use `meta.json`'s `world_size_*_m` for camera framing, never
implicit cell counts. The reference consumer in G.4 documents the
exact scale conventions so external games don't drift.

### Catalog gate (carried from F)

G.5 makes the gate per-mode. Existing M13 gate logic stays compatible
(bundle-wide states still work); per-mode is additive.

### LLM-drivability hard gate (carried from F)

Same six-box requirement applies to every G sub-phase.

## Exit criteria for the whole phase

Phase G is **done** when:

1. The F.7 starter world renders cleanly at three zoom bands
   (G.1)
2. The starter world renders cleanly in all four perspectives
   including 2.5D (G.2)
3. At least one handcrafted patch is in the starter world with
   clean seams (G.3)
4. The reference consumer can load and render any bundle in the
   starter world (G.4)
5. The M13 gate reports per-mode verdicts for every bundle (G.5)
6. At least one real-DEM patch lands in the starter world (G.6)

Estimated 8-10 sessions total.

## Out of scope for Phase G

- Catalog scaleup beyond the 5-biome starter — that's Phase H
- Erosion sim integration — that's Phase H
- POI / landmark layer (decorative props, named structures) — that's
  Phase H
- Authored art — pipelines through G; content production starts in H
- Specific game built on world3 — separate consumer project

## Anti-duplication notes

- M22 "real-DEM patch seeding" from the retired hybrid procedural
  roadmap: split between G.3 (generic patch mechanism) and G.6
  (real-DEM specifics)
- G9 from the retired operability gaps: G.4 directly
- G10 from the retired operability gaps: G.5 directly

## Cross-references

- Parent: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Predecessor: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Successor: [PHASE_H_CHARTER_2026_05_11.md](PHASE_H_CHARTER_2026_05_11.md)
- Completion bar this phase contributes to: [WORLD3_COMPLETION_BAR_2026_05_10.md](WORLD3_COMPLETION_BAR_2026_05_10.md)

## Status

- [ ] G.1 — LOD-aware capture + zoom-level emission
- [ ] G.2 — 2.5D perspective + .tres variants
- [ ] G.3 — Handcraft override path (patch bundles)
- [ ] G.4 — Consumer integration kit
- [ ] G.5 — Per-mode quality bars at gate time
- [ ] G.6 — Real-DEM patch seeding refinement

**Phase G charter SHIPPED 2026-05-11.** Implementation begins after
Phase F closes.
