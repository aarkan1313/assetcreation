# world3 — Decisions Log

Append-only. Each entry: date, decision, alternatives considered, why we
picked this. We don't re-litigate.

If a decision is later reversed, **add a new entry** that says so — don't
edit the original.

---

## 2026-05-07 — Clean rebuild, world3, no legacy

**Decision**: Start over in a fresh directory (`D:/assets/world3/`). Don't
revive `pipelines/worldgen_v2/`, `worldgen2/`, `original_workflow_godot/`, or
their specs/plans. Old code may stay on disk for reference but is not
imported, called, or trusted.

**Alternatives considered**:
- Diagnose and fix `worldgen_v2` in place — rejected; the architecture had
  collected too many bad assumptions and the user explicitly wanted no
  inherited code.
- Revive the older "good" workflow (`llm_fjord_original`, etc.) — rejected;
  user said the old code is gone and wanted a clean break.

**Why**: Clean slate is faster than understanding-then-fixing here. Risk of
re-making the same mistakes is mitigated by writing things down and going
slow.

---

## 2026-05-07 — OpenTopography is the only data source

**Decision**: All terrain data comes from OpenTopography (cached DEMs in
`D:/assets/dems/`). No FLUX-generated heightmaps, no procedural noise as a
*source* (we may use noise inside the generator later — different role).

**Alternatives considered**:
- FLUX-generated heightmaps — rejected; user wants real-world realism as the
  base.
- Procedural FBM as the world — rejected; lacks the natural variation real
  terrain has.
- Mixing OpenTopography + ESA WorldCover for color — deferred; user wanted
  to start simple.

**Why**: The whole point of the project is "realism from real data." Adding
other sources during MVP creates moving parts.

---

## 2026-05-07 — Heightmap PNG + meta.json is the only data contract

**Decision**: Everything downstream of `build_world.py` consumes a
`heightmap.png` (16-bit grayscale square) and a `meta.json` (elevation range,
world size, source bounds, material name). Real DEM, cropped DEM, hand-edited
DEM, kernel-generated heightmap — all the same to the renderer.

**Alternatives considered**:
- Pass the original GeoTIFF through to Godot — rejected; Godot doesn't read
  GeoTIFF, and we'd lose the option of substituting non-DEM heightmaps later.
- A binary format (raw float32) — rejected; PNG is universal and the loss
  to 16-bit fixed point is below DEM noise floor at this scale.

**Why**: This is the seam that lets Phase 4 (procedural generator) drop in
without rewriting the renderer.

---

## 2026-05-07 — Mesh built at runtime in GDScript, not pre-baked

**Decision**: `Terrain.gd` reads the heightmap and builds an `ArrayMesh` in
`_ready()`. No pre-exported `.mesh` file.

**Alternatives considered**:
- Bake the mesh in Python via Blender / trimesh — rejected; adds an external
  dependency and an extra step.
- Use `MeshLibrary` + `GridMap` — rejected; overkill for one terrain.
- Use a Godot terrain plugin (Terrain3D, HTerrain) — rejected for now; we'd
  rather understand and own the geometry. May reconsider in Phase 5 if
  streaming becomes painful.

**Why**: 131k tris build in <1s. Total control over winding, normals, UVs.
Easy to swap the heightmap and rebuild.

---

## 2026-05-07 — Fly mode is the default in walk scene

**Decision**: `Walker.gd` defaults to `fly_mode = true`. **F** toggles.

**Alternatives considered**:
- Default to walk mode — rejected; one collision bug and the player falls
  through and we waste a session debugging.
- Remove walk mode entirely — rejected; we want to validate collision still
  works.

**Why**: "Impossible to fall through" beats "realistic but broken." Once
collision is trusted on multiple DEMs, we can flip the default.

---

## 2026-05-07 — Three view modes are different games

**Decision**: Walk, iso, and topdown will not share one camera/material
config. They share the *data* (one heightmap, one biome ruleset) but each
scene gets its own material with its own tile size, sun strength, fog, and
shadow distance.

**Alternatives considered**:
- One material, scaled by camera height — rejected; mip-aliasing bites at
  the extreme zoom-outs and tile detail looks wrong at the close-ups.
- A single shader that auto-detects the camera and adjusts — rejected; too
  clever, and we want predictable per-scene rendering.

**Why**: 16 km of terrain at 0.5 m tile size is a tile-grid mess. Same
terrain at 100 m tiles is a clean strategic map. The dial belongs to the
scene, not the data.

---

## 2026-05-07 — Docs system: 4 lifetime classes, written rule per doc

**Decision**: With 18 markdown files and growing, formalize the
documentation system into 4 lifetime classes:
1. **Living runbooks** (update in place when behavior changes):
   WORKFLOW, PIPELINE, TOOLS, GODOT_SCREENSHOTS, OPENTOPO_*
2. **Append-only logs** (never edit history): DECISIONS, LESSONS,
   EXPERIMENTS, PROMPT_COOKBOOK
3. **Snapshots** (point-in-time, frozen): pilot audits, fix plans,
   archived roadmap versions
4. **Iteration plans** (rewritten each iteration, archive old): PLAN,
   ROADMAP

[DOCS_GUIDE.md](DOCS_GUIDE.md) is the new doc explaining the system,
including a flowchart for "I just learned X — where does it land?"
[README.md](README.md) is the question→doc index for finding things.

**Alternatives considered**:
- Consolidate to fewer files — rejected; each existing doc has a
  distinct role and write-rule. Merging would create the "drowning
  in one giant file" failure mode.
- Wiki-style hierarchy with subdirectories — rejected; flat is easier
  to scan and search, and we don't have enough docs to justify
  hierarchy yet.

**Why**: User concern that we'd lose findings between "too many docs"
and "didn't write enough" failure modes. The 4-class system makes the
write-rule per doc explicit so neither mode bites: append to the
right log, update the right runbook, never both.

---

## 2026-05-07 — ROADMAP v2: reframe around quality gaps, not ambition

**Decision**: Replace ROADMAP v1 (DEM analyzer → kernel synthesizer →
infinite world) with a v2 organized around the concrete quality gaps
we surfaced in Phase 1 + Phase 2. v1 archived as
`ROADMAP_v1_archived.md`.

v2 phase order:
- **A** — texture quality + prompt R&D (sweeps, external research, cookbook)
- **B** — upscaling + multi-resolution pipeline (research + build)
- **C** — iso/topdown scale review (target zoom levels, framing modes)
- **D** — biome generalization (fill out the partial kits, fix the wrong-looking regions)
- **E** — per-game-mode material tuning (walk/iso/topdown own their materials)
- **F** — multi-tile / continuous world (small test now, full later)

**Deferred** (intentional):
- LOD — decide when performance forces it
- DEM analyzer + kernels — strong long-term direction but no current pressure
- Procedural generator — depends on kernels

**Alternatives considered**:
- Stick with v1's kernel-direction Phase 3 — rejected; doesn't address
  any of the immediate quality gaps and bets the next iteration on a
  research-heavy direction.
- Skip the reframe and add new phases ad-hoc — rejected; the v1
  roadmap was being eroded entry-by-entry as our priorities shifted,
  and a clean v2 is easier to follow than a heavily-amended v1.

**Why**: User asked for a reframe after stocktake. The 5 areas of
honest concern (texture quality, upscaling, iso/topdown scale, biome
generalization, per-game tuning) all map directly to v2 phases. Long-
term direction (continuous world, possibly procedural) unchanged —
just not the next thing we work on.

---

## 2026-05-07 — Phase 2.5 — per-region biome kits

**Decision**: Each region declares which biome kit it uses; the
RegionGalleryCapture script binds the appropriate `terrain_blend_<kit>.tres`
material before loading the heightmap. Kits are defined in
`world3/jobs/biome_kits.json` and code-generated into
`terrain_blend_<kit>.tres` files by `world3/pipeline/build_kit_materials.py`.

5 kits defined: **alpine** (default — uses original wgv3 textures),
**desert**, **tundra**, **temperate_forest**, **grassland**. Each kit
specifies:
- 5 texture slot bindings (grass/dirt/rock_light/rock_dark/snow → kit-specific texture IDs)
- per-kit height-band thresholds (e.g. desert pushes snow to 0.92 since it doesn't have real snow; tundra pulls snow down to 0.60)
- per-kit slope_threshold

`regions.json` now carries `biome_kit` and `biome_kit_material` per
region. Hand-mapped 16 regions to kits using their landform tag
(`des_mojave_usa` → desert, `tgs_serengeti_tanzania` → grassland, etc.).

**Desert kit** generated end-to-end with the in-house pipeline as the
first real test of the multi-kit workflow:
- `desert_sand` (anchor, grade A)
- `desert_dry_brush` (palette-locked to anchor, grade A)
- `desert_canyon_rock` (grade B — periodic 37.8 from horizontal striations, expected)
- `desert_dark_rock` (grade A)
- `desert_salt_pan` (grade B — periodic 29.1 from hex pattern, expected)

Two of these (sand, dry_brush) the FLUX model interpreted off-prompt
(sand looks like decorated paper, dry_brush looks like cracked mud).
**Logged as a follow-up but not regenerated immediately** — the goal
of this iteration was the wiring, not the textures.

**Validation**: rendered 5 regions through the per-kit gallery —
Cascades + Appalachians (alpine, unchanged), Mojave (desert kit
fires correctly, no inappropriate snow on the ridge), Tibet + Serengeti
(grassland kit, mostly green with rock at rough edges).

**Alternatives considered**:
- Build the ShaderMaterial dynamically in GDScript per-region rather
  than emitting .tres files — rejected; static .tres makes the kit
  bindings inspectable in Godot's editor and decouples Python's kit
  config format from the renderer's runtime.
- Hand-author each kit's .tres — rejected; 5 kits × 16 lines of
  boilerplate × likely revisions = unmaintainable. Code-generate from
  the kit JSON.

**Why**: The single-kit case was trivially wrong on 11 of 16 regions
(snow on Mojave, grass over arctic permafrost, etc). Per-kit selection
is the natural unit for "biome-aware terrain" and the infrastructure
maps cleanly onto our existing palette_lock workflow.

---

## 2026-05-07 — Tangent-frame RNM in detail shader

**Decision**: Replaced the `normalize(mix(macro, detail, strength))`
"safe mix" in `terrain_hex_detail.gdshader` with a real Reoriented
Normal Mapping (RNM) blend in a derived tangent frame.

The tangent frame is built per-fragment from `dFdx(world_pos)` and
`dFdy(world_pos)` projected perpendicular to the world-space normal,
then orthonormalized with `cross(world_n, T)` for the bitangent.
RNM runs in this tangent frame and the result is rotated back to
world space.

**Alternatives considered**:
- Keep the safe mix — rejected after the review pass. Loses crispness
  on the detail layer compared to real RNM.
- Use a constant world-axis basis (e.g. `[+X, +Y, +Z]`) — rejected;
  not an actual tangent frame on tilted surfaces, would re-introduce
  the cliff-face distortion that the safe mix was avoiding.

**Why**: Closes the loose end from the review pass. The detail layer
now has the visual punch of real RNM without the cliff-face artifacts
that the original world-space-RNM-misuse caused.

---

## 2026-05-07 — Phase 2 done — region library via OpenTopo bundles

**Decision**: Skip building a region-fetch pipeline; the OpenTopo
workflow (other chat) had already produced 72 heightmap bundles in the
exact `heightmap.png + meta.json` schema we use. Built only the
indexer + Godot-side RegionLoader + gallery capture script.

The wiring:
1. `world3/pipeline/index_regions.py` walks
   `world3/opentopo/processed/heightmaps/<site>/<dataset>/`, picks a
   preferred dataset per site (COP30 > NASADEM > SRTMGL1 > CA_MRDEM
   > others), tags landform from a hand-coded hint table, emits
   `world3/jobs/regions.json`.
2. `RegionLoader.gd` looks up a region+dataset in regions.json and
   calls the existing `Terrain.load_dataset(hp, mp)` method.
3. `Terrain.gd` gained a `defer_initial_build` flag so external
   loaders can wire paths before the first rebuild.
4. `RegionGalleryCapture.gd` iterates regions, drives the iso camera
   to auto-frame each terrain's AABB, captures iso + topdown.

**Alternatives considered**:
- Build a job/preset format that ran build_world.py end-to-end per
  request — rejected. The OpenTopo workflow already populates the
  bundle directory; reimplementing the fetch on the world3 side
  would duplicate the other chat's work and create two sources of
  truth for the same data.
- Materialize each region's heightmap into the project tree
  (`res://regions/<id>/...`) — deferred. Godot's FileAccess accepts
  absolute paths at runtime, so we can read directly from
  `D:/assets/world3/opentopo/processed/heightmaps/...`. We may
  symlink in the future if export builds need them.

**Why**: The OpenTopo bundles already exist in our schema. Phase 2's
real work was the *renderer-side selector*, not data acquisition. The
indexer + loader + gallery capture is ~250 lines of code, took less
than an hour, and produced 5-region validation captures with no manual
intervention.

Validation: rendered 5 regions chosen for variety (alpine, desert,
rolling-mountain, plateau, tundra). All used the same single biome
kit (rock_dark + grass + snow). Result: alpine and rolling-mountain
look great; desert and tundra look wrong (snow on Mojave's high
ridge, grass over arctic permafrost). The slope+height shader's
biome assumptions don't generalize across climates. Per-region biome
kits are the next iteration.

---

## 2026-05-07 — Independent code review + 5 fixes shipped

**Decision**: Spawned `feature-dev:code-reviewer` agent to audit the
texture pipeline + shader stack. Five real issues surfaced, all
shipped. Captures regenerated to confirm no regressions on the happy
path; one shader change (RNM) is a deliberate visual tradeoff
(consistent-but-less-punchy beats inconsistent-and-buggy).

The five fixes:

1. **terrain_blend.gdshader**: gate threshold dropped from 0.005 to
   1e-4; added rock_dark unconditional fallback when wsum < 1e-4.
   Defends against black-pixel holes at layer-boundary intersections
   (theoretically impossible after normalization but defensive cost
   is one extra sample per pathological pixel).

2. **seam_repair.py**: refactored repair into
   `compute_repair_plan(albedo) → list[op]` and `apply_repair_plan(map,
   plan)`. The plan computed once on albedo is replayed on every other
   map. Previously each map ran its own MSE-minimized search and
   ended up patched from spatially inconsistent source regions —
   visible as albedo/normal misalignment in the seam region.

3. **terrain_hex_detail.gdshader**: replaced RNM-misuse-on-world-space-
   normals with a plain `normalize(mix(macro, detail, strength))`.
   Original RNM assumed tangent-space inputs; using it on world-space
   normals produced incorrect blending on non-horizontal surfaces.
   The new mix is mathematically correct on all orientations but
   visually less punchy. **Deferred follow-up**: real RNM in a derived
   tangent frame.

4. **palette_lock.py**: added `update_catalog_entry_from_qa()` to
   rewrite the catalog line after the post-match QA. Previously the
   catalog claimed the pre-match grade even though the albedo had
   been modified.

5. **aaa_texture.py**: replaced `grade_rank.get(grade, 0)` with an
   explicit assertion. The `.get(..., 0)` default would silently treat
   an unexpected grade as D, which combined with a min_grade='D'
   preset would pass corrupt QA output through the gate.

**Why**: Review-as-you-go. The five issues were genuine bugs, not
nits. Three of them (#1, #4, #5) were instances of the same meta-
pattern that already had LESSONS entries (L2, L3): "post-pipeline
transforms must propagate to downstream truth." LESSONS L12-L15
codify the new findings.

**Captures**: iso/topdown/walk Tetons unchanged (defensive code, no
visible diff). Detail-v2 rock_dark close-walk visibly different —
slightly less crisp because the RNM-misuse was producing extra
contrast that wasn't physically correct. Documented as a deliberate
tradeoff.

---

## 2026-05-07 — Texture pipeline preprocessing review (post-shader)

**Decision**: After Phase 1b shader iterations 2–5 made it clear how
much the renderer can compensate for, we did a focused review of the
texture pipeline. Four concrete changes shipped, all with verified
end-to-end tests.

1. **Per-category QA thresholds** (`CATEGORY_THRESHOLDS` in
   `texture_qa.py`). Brick/Tile/Cobble accept periodic up to 80;
   Rock 25; Ground 22; Snow/Water 18 (default). Categories where
   uniform roughness is normal (Snow/Water/Sand/Liquid) skip the
   sanity flag for flat roughness. Result: all 6 wgv3 textures now
   grade A under their proper categories.

2. **`palette_lock.py` modernized + wired up properly**. Cleaned up
   for the 512-native pipeline (no hardcoded 1024), re-runs QA
   post-match so the manifest reflects the final state. Verified by
   generating a 3-texture "alpine" kit (anchor=rock_dark, +moss,
   +scree) — the unmatched moss albedo was bright olive green, post-
   match it's the warm desaturated brown that fits the kit.

3. **`detail_variant.py` (new)** — generates a paired "detail"
   texture for the macro+detail shader pattern. Uses category-aware
   prompt suffixes ("extreme close-up macro, fine grain, high
   contrast"), a fresh seed, and palette-locks to the parent.
   Verified against `wgv3_rock_dark`: parent has sparse big features,
   detail variant has dense fine cracks; rendered side-by-side in the
   detail-v2 shader the rock looks substantially more like real rock.

4. **`LESSONS.md` written** — 11 surprises and gotchas captured for
   future-us. Things like "QA grade is meaningless without seeing the
   tile_2x2," "repair output must overwrite originals," "sanity needs
   per-category exceptions," "tileable doesn't mean visually
   interesting at scale."

**Alternatives considered**:
- Generate per-iteration detail textures for every wgv3 set — deferred;
  one detail variant (`rock_dark_detail`) is enough proof of concept,
  others can come when needed.
- Make palette_lock work on normal/roughness too — rejected; matching
  geometry maps would corrupt the surface; albedo-only is correct.
- Bake per-category thresholds into the orchestrator's preset — kept
  in `texture_qa.py` instead so any QA invocation (standalone or via
  orchestrator) gets the same treatment.

**Why**: User framed assets as scaffolding for the tools. These four
changes harden the *tools* against real-world variety. Tested with
end-to-end runs producing visible improvements; archived in
`world3/docs/captures/iter4b_detail_variant/` and `iter_palette_lock/`.

---

## 2026-05-07 — Skeptical re-read of texture pipeline; audit was wrong

**Decision**: Treat the existing texture pipeline as broken in specific,
concrete ways rather than "deployment-ready." The 2026-05-07 audit
(structured report from a research agent) said "infrastructure is ~80%
there, deploy and tune." Skeptical re-read of the actual scripts found
four real defects, all of which cause "passing" textures to be
untrustworthy.

The defects (full detail in
[`TEXTURE_PIPELINE_FIX_PLAN.md`](TEXTURE_PIPELINE_FIX_PLAN.md)):

1. The QA seam metric measures only the outermost 1-pixel-wide column on
   each side, not anything 8+ pixels in. Center seams, lattice artifacts,
   and tile-period repetition all score grade A.
2. `seam_repair.py` writes to a `repaired/` sibling folder; nothing copies
   the repaired files back over the originals. Consumers read un-repaired
   textures even when repair "succeeded."
3. `seam_repair.py` reads the catalog manifest, but the orchestrator
   writes the catalog *after* repair runs. So repair always fails on
   first run and is silently skipped. Of 30 existing textures, only 2
   have any repaired output, and both are old hand-curated.
4. StableMaterials trains at 512; the orchestrator passes 1024. Every
   "default"/"strict" preset has been size-mismatched against the model.

**Alternatives considered**:
- Trust the audit's verdict and just run the pipeline more — rejected
  after reading the actual code.
- Replace AI generation with PolyHaven/AmbientCG real-photo only —
  rejected; user wants in-house generation working, not just usable
  output today.
- Rewrite from scratch — rejected; the framing (variant_select →
  delight → PBR → repair → QA → gate) is sound. The implementations of
  ~half the stages are wrong, but the structure is fine.

**Why**: User asked for in-house generation that works. The pipeline is
fixable in concrete steps. Fixing it means our generated textures become
trustworthy artifacts instead of "passing" lies.

---

## 2026-05-07 — Audit existing texture pipeline before building shader

**Decision**: Pause Phase 1 shader work. Audit and stabilize the existing
ComfyUI/FLUX texture pipeline (`pipelines/textures/aaa_texture.py` and ~26
support scripts) before wiring multiple textures into a slope/height-blend
shader. Two known quality issues block world3 use:

1. **Tileability** — current pipeline accepts grade B/C seams (1–2% edge
   error). At terrain scale this stacks across many visible tile copies
   and reads as visible seams. Need grade A consistently.
2. **Center seams / lattice artifacts** — FLUX.2-klein has center-bias on
   structured patterns. The offset+heal trick works for noise-like
   materials (rock, dirt, leaves) but fails on directional/structured
   content (bricks, ice lattice, crystals).

**Alternatives considered**:
- Build the shader against the 5 staged textures, accept current quality —
  rejected; if textures are the weak link, polishing the shader on top of
  bad input wastes effort and bad seams will dominate the look.
- Rebuild texture generation from scratch — rejected; the infrastructure
  is ~80% complete (variant selection, delight, seam repair, QA gates,
  manifests). It needs deployment and tuning, not a rewrite.
- Use only real-photo PolyHaven/AmbientCG textures — rejected as a
  long-term answer; we want biome-specific materials with controllable
  style. But it IS our short-term fallback while we tune the AI path.

**Why**: Shader work and texture work compound multiplicatively. Bad
textures + good shader = bad result. Good textures + adequate shader =
good result. Sequence matters.

**Key findings from the audit**:
- `pipelines/textures/aaa_texture.py` orchestrates: variant generation →
  best-by-edge-MSE selection → delight → PBR derivation → seam repair →
  QA gating → manifest. Mature.
- StableMaterials adapter exists but is unused. Designed for tileable
  output, would help with structured patterns where FLUX center-biases.
- `palette_lock.py`, `patina_adapter.py`, `detail_pyramid.py` exist but
  aren't wired into the orchestrator. Useful for biome cohesion.
- `aaa_pipeline.json` schema is consistent across all generated sets —
  good provenance.
- Real-photo sets (Rock035, rocks_ground_06) consistently grade A. AI
  sets vary B–C with occasional D for structured content.

---

## 2026-05-07 — Long-term direction: real DEMs as input to a procedural generator

**Decision** (intent only — implementation lives in Phase 4): real DEMs will
eventually be analyzed into "kernel packs" (small parameter sets describing
slope, ridge spacing, drainage, noise spectrum) that feed a procedural
generator. Original DEM data is reference, not shipped content.

**Alternatives considered**:
- Ship the actual DEM tiles as game content — rejected; locks us to fixed
  geography and a small library.
- Train a diffusion model on heightmaps — deferred; heavier, and a
  statistical generator will likely get us 80% there.

**Why**: Earth has a finite number of interesting tiles, but kernel + RNG
gives us infinite variations. Also legally simpler (no question of whether
we can ship a derivative of public-domain DEM data).

---

## 2026-05-07 — OpenTopo tooling must be documented as it ships

**Decision**: Any OpenTopo tooling, pipeline step, storage convention, or Godot
viewer behavior is not considered part of the workflow until it is documented in
the repo. The required update locations are:

- `world3/docs/OPENTOPO_GUIDE.md` for commands and tool behavior.
- `world3/docs/OPENTOPO_DATA_TYPES.md` for what each product is good for.
- `world3/opentopo/STATUS.md` for what was actually downloaded or generated.

**Why**: The OpenTopo work now includes direct Dataspace downloads, API-backed
DEM pulls, COG fallbacks, LAZ streaming, orthophoto exports, canopy mosaics, and
Godot overlay browsing. Without strict runbook updates, the pipeline becomes
chat-history-dependent and hard to reproduce.

---

## 2026-05-07 - Same-type mosaics use one canonical projected grid

**Decision**: For large same-product OpenTopography areas, fetch overlapping
raw tiles first, then reproject every tile to one projected meter CRS, one
snapped cell size, and one exact output grid before reducing into a mosaic.
The default reducer for DEM/DTM pilots is `mean`; every run writes
`coverage_count.tif`, `seam_delta.tif`, `tile_footprints.geojson`, and a JSON
report.

**Alternatives considered**:
- Directly concatenate tiles in source coordinates - rejected; source pixels
  can be close but still not share one transform.
- Skip overlap - rejected; without overlap we cannot measure seam disagreement.
- Start with `USGS1m` - rejected for the first pilot because it creates a much
  larger operational problem before the stitching logic is proven.

**Why**: Workflow 1 needs to prove stitching quality before Workflow 2 adds
orthophotos, canopy, and point-cloud products. The Grand Canyon `USGS10m` pilot
validated that this approach produces a coherent terrain mosaic with small seam
error across almost all overlap pixels.

---

## 2026-05-07 - Split OpenTopo follow-up into texture, scene, and HD delivery workflows

**Decision**: OpenTopo fused data will be developed along three related but
separate workflows:

- Baked ground textures: use real orthophoto and derived masks as source
  evidence for reusable seamless PBR materials.
- Fused real-place scenes/maps: preserve actual AOIs as layered Godot terrain
  stacks with DTM, orthophoto, NIR, canopy/CHM, slope, roughness, and QA layers.
- High-detail zoom/chunked delivery: push texture and mesh resolution, then
  split into chunks/LOD when a single texture no longer holds enough fidelity.

**Alternatives considered**:

- Treat orthophoto scenes and baked textures as one workflow - rejected; a
  seamless reusable material and a real-place map have different correctness
  rules.
- Jump straight to chunk streaming - rejected for now; a 4096/8192 single-tile
  stress test should tell us what actually limits close-up fidelity.
- Keep only overview scenes - rejected; overview screenshots can hide close-up
  texture, mesh, and material failures.

**Why**: Phase 2 showed that real color/canopy/fused layers are visually
valuable, but the current 1024 single-texture viewer fails close up. We need to
separate source-layer alignment from rendering delivery and from reusable
material baking, then measure each path independently.

---

## 2026-05-07 — Repo policy: track source, ignore generated content + caches

**Decision**: Git tracks source code, configs, schemas, docs, and the
*current* iteration's evidence captures. Generated content (PBR
texture binaries, heightmap PNGs, OpenTopo raw/processed DEMs, Godot
import caches, blender previews, historical iteration screenshots) is
gitignored. Reproducibility comes from the cookbook prompts +
seed-base + tool config, not from binary snapshots.

**Alternatives considered**:
- **Track all texture binaries in git**: rejected. Currently ~25
  materials × 6 maps × ~500KB = ~150MB just for `world3/textures/wgv3/`,
  plus parallel sets in `world/textures/library/`. Repo bloat would
  compound across iterations.
- **Use Git LFS for binaries**: deferred. Adds tooling overhead and a
  separate retention story; postpone until binaries become a real
  problem (e.g. for cross-machine sync).
- **Leave half-tracked / inconsistent**: rejected. The state inherited
  before this session — most of `world3/` and several
  `pipelines/textures/` files untracked despite being referenced by
  committed docs — was the failure mode driving this decision.
- **Track historical iteration captures (~96MB)**: rejected. They're
  evidence for past dev iterations; the docs that reference them stay
  readable, but the binaries themselves are gitignored. Current-
  iteration captures (`captures/phase_a/`) ARE tracked because they
  document active work.

**Why**: The failure mode we're guarding against is "doc says X but
git doesn't have X" — exactly what we found when this session
started. Now the rule is clear: if a committed doc references a file,
that file is either tracked or it's a generated artifact whose
prompt/seed/config IS tracked. The texture pipeline's reproducibility
contract (prompt + seed-base + ComfyUI version + FLUX 2 klein
weights) is the source-of-truth for textures, not the binaries.

**Implementation**: see `.gitignore`. The key new patterns are
`world3/.godot/`, `world3/textures/`, `world3/heightmap/`,
`world3/opentopo/{raw,processed}/`, `world3/toporeview/phase*_*/`,
`world3/docs/captures/iter*/`, `world3/**/*.import`.

---

## 2026-05-07 — CHORD as opt-in PBR backend (don't migrate)

**Decision**: Add CHORD (Ubisoft La Forge, SIGGRAPH Asia 2025) as a
third PBR estimation backend in `aaa_texture.py`, selectable via
`--pbr-backend chord`. **Default behavior unchanged** —
StableMaterials remains the default for `default`/`strict` quality
presets; `derive_pbr_v2` remains the `fast` preset's backend. Don't
migrate the existing `wgv3_*` shipping set to CHORD.

**Alternatives considered**:
- **Replace StableMaterials with CHORD as the default**: rejected.
  A/B testing (TEXTURE_RND "A.8") showed CHORD wins on hard-edge
  geometry but produces near-flat roughness on rock-class materials,
  fails our existing sanity check, and would visibly degrade
  in-engine lighting on those textures. The handoff brief recommended
  this swap; the swap is justified for materials where CHORD's
  strengths apply (sharper normals/heights), not as a blanket
  replacement.
- **Keep CHORD only as a separate hero-mesh lane (handoff #3)**:
  partial — but the wrapper is small and useful even for biome-tile
  materials with hard geometry. Better to expose it generically and
  gate use via the `--pbr-backend` flag than to silo it into a
  parallel lane that doesn't exist yet.
- **Use CHORD for everything except roughness** (post-process the
  roughness from a different source): plausible but adds complexity.
  Filed as a Phase B candidate ("CHORD + SM-roughness hybrid") rather
  than building it now.

**Why**: The handoff called CHORD the "single highest-leverage swap."
That overstated it — CHORD is a *high-leverage option for the right
materials*, not a universal upgrade. Our test runs show genuine
quality wins (rock normals, height tileability) and genuine
regressions (rock roughness flatness). Keeping it opt-in lets us
exploit the wins without paying the regressions.

**Implementation**:
- `pipelines/textures/chord_image2pbr.py` — HTTP-API wrapper to
  ComfyUI's CHORD nodes
- `pipelines/textures/aaa_texture.py` — `--pbr-backend {derive,sm,chord}`
  flag added; default = preset's existing backend (sm for default/strict)
- `D:/assets/animators/ComfyUI/custom_nodes/ComfyUI-Chord/nodes.py`
  — local patch for transformers 5.x compat (strip
  `text_encoder.text_model.` → `text_encoder.` from state dict
  before `load_state_dict`). Filed in TEXTURE_RND "A.8" so future-us
  can re-apply on a CHORD update.
- License: Ubisoft Machine Learning License (Research-Only Copyleft)
  — flagged in PIPELINE.md and TOOLS.md. Need to revisit before any
  commercial release.

---

## 2026-05-07 — CHORD + SM-roughness hybrid as a third opt-in backend

**Decision**: Add `--pbr-backend chord_sm_rough` to `aaa_texture.py`.
Runs CHORD for albedo/normal/height/metallic/ao, then SM separately,
then overwrites only the roughness map. ~25s extra wall-time over
pure CHORD. **Default and existing backends unchanged.**

**Alternatives considered**:
- **Add roughness-only mode to SM**: rejected — would require modifying
  `stablematerials_image2pbr.py` to skip non-roughness output. Doable
  but invasive, and the temp-dir approach is just as fast in
  practice (the model loads the same way regardless).
- **Use a heuristic roughness on top of CHORD**: rejected for rock —
  derive_pbr_v2's category-preset roughness is constant per pixel,
  even worse than CHORD's near-flat output. Heuristic doesn't add
  variation.
- **Switch the default to `chord_sm_rough` for default/strict**:
  rejected. Two reasons: (1) the existing wgv3_* shipping set was
  generated with pure SM and we're not migrating; (2) `chord_sm_rough`
  is only a clear win on Rock-class materials where CHORD's flat
  roughness was the specific regression. For sand/snow/water/liquid
  CHORD's flat roughness is *correct* (those are uniform surfaces),
  and the extra 25s is wasted. Per-material opt-in is the right
  default.
- **Drop CHORD entirely now that we have SM**: rejected. CHORD's
  normal + height advantages on hard-edge geometry are real wins
  that SM doesn't replicate. The hybrid keeps both available; pure
  CHORD stays for cases where the user wants its 1024-native
  geometry without the SM roughness pass.

**Why**: A.11 A/B verified the hybrid lifts the gate from FAIL → PASS
on rock_dark while preserving CHORD's geometric strengths. Roughness
std jumps 0.011 → 0.029, range expands 0.58–0.71 → 0.44–1.00. This
is a clean "best of both" outcome for Rock-class materials. Keeping
all four backends (derive / sm / chord / chord_sm_rough) gives us
per-material flexibility without a forced migration.

**Implementation**:
- `pipelines/textures/aaa_texture.py` — new branch in the stage 3
  PBR dispatch. CHORD writes 6 maps; SM runs into a temp dir; SM's
  roughness overwrites CHORD's. CHORD's pre-swap roughness saved as
  `<id>_roughness.pre_sm_swap.png` for inspection/restore.
- Pipeline log records `'method': 'chord_v1+sm_roughness'` so it's
  traceable in `aaa_pipeline.json`.
- Recommended use: hero rock materials at `--quality strict
  --pbr-backend chord_sm_rough`. Defer for non-rock categories
  unless A/B shows a roughness regression in some other case.

---

## 2026-05-07 — Grassland kit's loose height bands are decision-locked

**Decision**: The grassland kit's `biome_kits.json` height_bands are
`h_grass_dirt=0.4`, `h_dirt_rockdark=0.75`, `h_rockdark_snow=0.95`
and `slope_threshold=0.5`. These are looser than alpine
(0.2/0.55/0.85, slope 0.45) by design.

**Alternative considered**: Tighten to alpine cadence (0.2/0.5/0.8,
slope 0.35) so Tibet + Serengeti show rock/dirt variation instead of
uniform tall_grass. Tested 2026-05-07 evening; rejected.

**Why**: Real grassland imagery (Serengeti, Tibetan plateau, Great
Plains, Pantanal) is biologically near-uniform tall_grass with rare
rocky outcrops. Tightening the bands surfaces different slot textures
(`dry_thatch`, `hardpan_soil`, `grass_rock`) but they all read
yellow-tan because all 5 grassland slots share a warm color family —
the textures don't *visually* differentiate even when triggered. Result
of the tighter test: actually *more* uniform-looking, not less, because
yellow-on-yellow blending averages out the macro tint variation.

**Implication**: If a region needs visible rocky variation (e.g. East
African kopjes, Tibetan buttes), the right fix is **either**:

1. A region-specific kit override (one-off `terrain_blend_<region>.tres`).
2. Regenerate `wgv3_gl_grass_rock` and `wgv3_gl_weathered_stone` with
   darker/greyer prompts so they actually contrast against tall_grass.

Don't widen kit bands — that breaks the faithful reading on the four
other grassland regions which actually *should* look uniform.

**Locked in**: `world3/jobs/biome_kits.json` grassland kit's
`height_bands._comment` field carries the rationale inline so future
sessions don't fight this decision.

---

## 2026-05-07 - OpenTopo master stacks prioritize valid coverage over nominal size

**Decision**: A master-stack candidate must pass valid-source coverage review
before it becomes the recommended scene. High nominal resolution or a large API
bounding box is not enough.

**Why**: The Rainier `USGS1m` 4-call attempt looked ideal on paper, but two
tiles returned no raster and the partial mosaic had only about `7.4 percent`
valid terrain. The Chuculay textured candidate had real orthophoto color, but
after valid-footprint crop only about `50 percent` of the review rectangle had
source-valid elevation. Both are useful QA/failure cases, but bad primary
master stacks.

**Chosen endpoints**:

- Gloss Mountain for the real-textured stack because DSM and orthomosaic overlap
  well after crop, giving about `84 percent` valid DEM/texture coverage.
- Zion `USGS10m` for the large no-texture stack because all four API tiles
  downloaded cleanly and produced a broad 36.8 km review scene.

**Implementation**:

- `build_opentopo_textured_master_stack.py` adds valid-footprint crop,
  source-valid masks, texture coverage masks, and render-fill provenance.
- `export_heightmap_review_layers.py` adds QA raster overlays and sandstone
  review style.
- Full audit: `docs/OPENTOPO_MASTER_STACKS_AUDIT.md`.

---

## 2026-05-08 - world3/assets content is pipeline-validation material first

**Decision**: Treat `world3` and the broader `assets` work as a pipeline and
workflow creation set. The content generated during these phases is not
automatically production content; its first job is to prove that the workflow,
metadata, QA, transition, shader, and streaming contracts can support AAA
quality.

**Why**: The near-term work is interlocked infrastructure: material taxonomy,
real/procedural provenance, transition authoring, splat weights, shader
unification, and chunk streaming. Locking on "production asset" too early would
hide weak workflow contracts. Locking on "workflow validation" keeps the bar
high while allowing a material or stack to be regenerated, reauthored, or
replaced without invalidating the pipeline.

**Implications**:

- Catalog entries may use `asset_status = pipeline_validation`.
- AAA quality remains the target bar, but promotion to production candidate is
  a separate review at the target game camera ranges and source/style mix.
- Provenance, scale, shader binding, and validation state are part of the
  asset contract, not optional documentation.
- Real-source review scenes and procedural kits can be excellent workflow
  evidence even when they are not final shipped content.

---

## 2026-05-08 - M3 locks 256 m as the synchronous base chunk

**Decision**: Use `256 m` as the base runtime chunk size for the current
synchronous `walk.tscn` streaming path.

**Format**:

- Base chunk size: `256 m`.
- Mesh spacing: `8 m`.
- Subdivisions per base chunk: `32`.
- Initial loaded neighborhood: 3x3 chunks around the walker.
- Chunk border normals sample the global height source one mesh step outside
  the local chunk footprint.

**Why**: The M3 sweep measured 256/512/1024 m chunks at constant 8 m mesh
spacing. With the same 3x3 loaded neighborhood, 256 m kept worst-case
synchronous load latency to about `19 ms`; 512 m spiked to about `71 ms`; 1024 m
spiked to about `263 ms`. Video memory stayed close across all three, so load
latency is the deciding constraint.

**Implication**: 512 m can return later as an async-built mid/far tile or
offline cache unit. 1024 m is far-LOD/prebuilt-region scale, not a synchronous
near-field chunk. If M5 needs more visible horizon, increase chunk radius before
increasing base chunk size.

---

## 2026-05-08 - M6 uses runtime image caches for generated height/splat inputs

**Decision**: Primary runtime height/splat inputs should be loaded from small
JSON manifests plus raw binary blobs under `world3/runtime_cache/`, not direct
PNG file loads.

**Why**: Godot's direct image file loading is convenient in editor review, but
it is the wrong contract for exported/runtime generated terrain inputs. A cache
manifest makes format, dimensions, source path, and source hash explicit, and
the runtime can read it through `FileAccess` in both editor and export-oriented
paths.

**Current format**:

- Heightmap cache: `rf32` normalized float image.
- Splat cache: `rgba8` weight texture.
- Builder: `world3/pipeline/build_runtime_image_cache.py`.
- Loader: `world3/scripts/RuntimeImageCache.gd`.

**Implication**: New generated runtime rasters should get cache builders or
cache outputs before being wired into `walk.tscn` or future exported scenes.
Legacy review scripts may still load source PNGs directly until touched.

---

## 2026-05-08 - M6 collision is streamed per visual chunk

**Decision**: The primary walk scene should use collision built with each
loaded `ChunkLoader.gd` visual chunk, not a hidden full-terrain collision mesh.

**Why**: The M5 hidden-terrain collision workaround proved interaction shape but
was not the right scalable runtime model. Per-chunk collision keeps visual and
physical residency aligned and exposes the real cost in metrics.

**Evidence**: The M6 900 m crossing built 21 collision chunks, held 9 peak
loaded chunks, recorded 60.433 ms total collision build time, 5.033 ms max
collision-shape build time, 28.675 ms worst update, and 4.594 ms p95 frame
time.

**Implication**: Synchronous collision is acceptable for this prototype pass.
If interactive play reveals visible hitching, the next runtime target is
async/background chunk mesh and collision build, not larger chunks.

---

## 2026-05-08 - Transition strips are opt-in shader samples before automatic masks

**Decision**: M6 adds runtime transition-strip sampling as an opt-in uniform set
on `terrain_splat_unified.gdshader`, but does not yet make biome-boundary
placement automatic.

**Why**: We needed to prove M2 transition assets can be sampled in the streamed
terrain shader before committing to a full boundary-mask generator. The review
scene also caught a real band-mask bug, which was fixed by feathering the strip
in/out at its local edges.

**Implication**: M7 should generate per-chunk boundary masks from
`world3/jobs/biome_transition_rules.json` and feed those masks into the shader.
Manual `transition_center_u` / `transition_width_u` knobs are review/prototype
knobs, not production placement logic.

---

## 2026-05-08 - Noisy grass/leaves are source QA, not transition failure

**Decision**: Treat noisy grass/leaves and other green/organic close-range
materials as source-material QA failures before production promotion.

**Why**: User review and M6 metrics agree: the transition workflow reads
promising, but some source organic textures carry too much high-frequency
micro-contrast or speckle. Adding more transition/shader complexity would hide
the actual weak link.

**Evidence**: `world3/pipeline/audit_material_source_noise.py` flags 10 of 17
green/organic candidates, including `grassland_grass`, `grass`,
`temperate_forest_grass`, `tundra_moss`, and `tundra_lichen`.

**Implication**: Regenerate, filter, or downweight flagged green/organic
materials before calling them production candidates at walk-camera distance.
Keep using them as workflow-validation inputs where appropriate.

---

## 2026-05-08 - M7-M12 is the near roadmap before deferred systems

**Decision**: Do not start scatter, vegetation, props, buildings, POIs, fantasy
biome expansion, full procedural infinite-world work, or production promotion
until the M7-M12 terrain lane is proven.

**Near sequence**:

1. M7 biome-boundary runtime integration.
2. M8 organic source-material cleanup.
3. M9 runtime performance and interaction polish.
4. M10 cross-source blending.
5. M11 corner and junction transitions.
6. M12 walk/iso/topdown view-mode parity.

**Why**: The terrain pipeline now has a working spine, but it is not yet
automatic or view-mode consistent. Adding deferred systems now would multiply
unfinished contracts. The next six milestones keep the work focused on
chunk-to-chunk, biome-to-biome, source-to-source, and view-mode parity.

**Implication**: When new ideas appear, classify them against this sequence.
If they do not strengthen M7-M12, park them unless they fix a blocker.

---

## 2026-05-08 - M7 transition placement uses generated per-chunk masks

**Decision**: Automatic transition placement in the streamed runtime uses
generated per-chunk RGBA mask textures sampled through `UV2`.

**Mask contract**:

- `R`: transition band strength.
- `G`: normalized transition-strip U across the boundary.
- `B`: transition-strip V along the boundary.
- `A`: reserved/opaque.

`ChunkLoader.gd` reads `world3/jobs/biome_transition_rules.json`, loads the
rule's catalog material pair and transition manifest, duplicates the chunk
material where needed, and enables `use_transition_mask` on
`terrain_splat_unified.gdshader`. The older manual `use_transition_strip`
uniforms remain for shader/prototype review.

**Alternatives considered**:

- Keep manual `transition_center_u` / `transition_width_u`: rejected for runtime
  use because placement would live in scene-specific knobs instead of boundary
  data.
- Encode transition placement only in the splat map: deferred. It may become the
  right broader contract, but M7 needed a small bridge from M2 rule assets into
  the already-working M5/M6 streamed chunk path.

**Why**: The mask texture makes boundary-space sampling explicit and lets each
chunk bind the same transition strip with local placement data. It also gives us
measurable build cost in the existing walk-stream metrics.

**Evidence**: `world3/docs/M7_BOUNDARY_RUNTIME_INTEGRATION.md`.

---

## 2026-05-08 - Run an M1-M7 visual audit before M8

**Decision**: Before starting M8, perform a formal visual audit across M1-M7.

**Why**: M7 proved the runtime boundary contract, but the capture review showed
that "technically working" and "visually good enough" are different gates. The
same-source boundary control is calm but subtle; the desert-to-grassland stress
case exposes the already-known grassland/organic texture noise. Moving straight
to more implementation without an audit would blur pipeline success with asset
quality.

**Audit doc**: `world3/docs/M1_M7_VISUAL_AUDIT_PLAN_2026_05_08.md`.

**Implication**: M8 should start only after current visuals are classified as
`PASS`, `PIPELINE_ONLY`, `REWORK`, or `DEFER`. If the audit says M7 needs a
visual-targeted boundary pass before organic cleanup, do that before M8.

---

## 2026-05-08 - M7 is workflow pass, visual rework

**Decision**: Keep the M7 runtime boundary-mask implementation, but do not
close M7 as a visual milestone.

**Why**: The M1-M7 visual audit found that rule-driven masks, catalog material
pair selection, shader sampling, and metrics are working. The visible result is
not strong enough for AAA-target terrain sign-off because it inherits noisy
green/organic source materials, prototype splat/material context, and weak
terrain-context transition evidence.

**Evidence**: `world3/docs/M1_M7_VISUAL_AUDIT_2026_05_08.md`.

**Implication**: Normal M8 work is paused until visual remediation is done or
explicitly scoped as the M8 starting work. Current M4/M5/M7 captures are
diagnostics only. Nonblank captures and runtime metrics are no longer allowed
to imply visual approval.

---

## 2026-05-08 - OpenTopo stack quality is the visual reference bar

**Decision**: Use the best stacked photo/topo OpenTopo captures as the near-term
visual reference. A terrain milestone should reach roughly `70 percent` of that
quality before visual closure.

**Why**: The M1-M7 vision review showed that the procedural runtime captures are
not near-miss art passes. They read as debug material assignment: harsh
procedural color, visible rectangles, repeated object-like textures, and weak
landform anchoring. The OpenTopo stack captures are still imperfect, but they
have the right foundation: real/source-derived macro color and material detail
that follows the terrain.

**Evidence**: `world3/docs/M1_M7_VISION_GAP_REVIEW_2026_05_08.md`.

**Implication**: The remediation path should pivot toward an OpenTopo-style
source stack: source-derived macro albedo first, procedural/tileable detail
second. Tuning the current debug-looking procedural captures is not enough.

---

## 2026-05-08 - Quarantine repaired organic materials until terrain review

**Decision**: Repaired procedural organic materials live in a sidecar candidate
catalog and are not promoted into the canonical material catalog until close,
mid, and far terrain-context captures pass.

**Why**: The deterministic repair pass sharply reduced high-frequency/green
noise metrics, but runtime source-stack review showed that repaired organic
normals/details can still damage the terrain read. The source macro albedo path
is stronger than the repaired procedural organic detail, so bad organic content
must be albedo-only and very low strength until it earns more influence.

**Evidence**:
`world3/docs/M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md` and
`world3/docs/SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md`.

**Implication**: Future M2/M5/M7 rerenders should prefer real/source-derived
OpenTopo detail controls first. Procedural organic repair candidates can be
tested, but they must remain `repair_candidate` until visual review promotes
them explicitly.

---

## 2026-05-08 - Treat OpenTopo and ComfyUI as peer texture-source lanes

**Decision**: The source-stack remediation model has two first-class material
sources. OpenTopo provides the current visual reference/control lane for real
macro terrain and real-ground classes. ComfyUI/`aaa_texture.py` provides the
procedural generation lane for scalable biome materials, missing-biome fill,
controlled variants, and future fantasy materials.

**Why**: The M1-M7 visual audit proved the pipeline can move data, but the
weakest visible failures come from generated organic texture content. Treating
ComfyUI as a secondary cleanup path would leave the procedural lane under-gated.
It needs the same inventory, QA, and terrain-context promotion rules as the
OpenTopo-derived materials.

**Evidence**:
`world3/docs/COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md`,
`world3/jobs/comfy_texture_regen_candidates.json`, and
`world3/docs/M1_M7_VISUAL_REMEDIATION_PLAN_2026_05_08.md`.

**Implication**: M8 starts with ComfyUI regeneration for the five priority
organic blockers, then tests those candidates through the source-stack runtime
gate. Deterministic organic repair remains a quarantine/candidate tool, not a
canonical promotion path by itself.

---

## 2026-05-08 - Source macro color must be validity-masked

**Decision**: Runtime source-stack review must bind a source-valid mask beside
source macro albedo. Invalid source macro pixels are repaired with edge bleed at
build time, and shader contribution falls back to procedural/tileable terrain
where the mask is invalid.

**Why**: The visual remediation target is roughly 70 percent of the best
stacked photo/topo OpenTopo reference. That target is not measurable if runtime
captures are allowed to inherit filled, wrapped, or invalid source-stack pixels.
The source macro is the visual anchor, so it needs an explicit coverage
contract.

**Evidence**: `world3/docs/SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`.

**Implication**: Future M4/M5/M7 source-stack rerenders should use
`pipeline/build_source_stack_runtime_review.py` outputs with
`source_macro_valid_mask.png`. Wider review scenes still need finite-footprint
framing cleanup, but invalid macro pixels are no longer an accepted artifact in
source-stack terrain review.

---

## 2026-05-09 - Unlike-biome M10 must be runtime layer data, not RGB strip tuning

**Decision**: Unlike-biome evidence cannot be promoted from a baked RGB
transition strip or final macro blend alone. The M10 path must emit and review
runtime layer data: biome weights, material splat weights, source macro masks,
feature/scatter masks, and continuous height.

**Why**: The rejected Gloss-to-grassland attempt proved that a soft RGB blend can
remove a hard seam while still looking like a synthetic muddy strip. That is not
the same problem as same-source seam integration. AAA-oriented terrain needs
readable material ownership, intermediate ecotone materials, and eventual object
distribution, not only albedo interpolation.

**Evidence**:
`world3/docs/M10_UNLIKE_BIOME_METHOD_REVIEW_2026_05_09.md` and
`world3/docs/M10_ECOTONE_LAYER_PROOF_2026_05_09.md`.

**Implication**: The current ecotone proof is allowed to remain in-progress even
though its visuals are not accepted yet. Future work should harden
height/material-biased blending, debug views, and scatter-mask population before
calling unlike-biome M10 complete.

---

## 2026-05-09 - M10 unlike-biome proof accepts macro-guided runtime layers

**Decision**: Accept the revised Gloss-to-grassland ecotone as M10
unlike-biome workflow evidence, but not as production-final AAA terrain.

**Why**: The revised pass changed the architecture, not just the colors. Macro
color now acts as broad landcover/photo guidance across the proof while runtime
splat/material weights stay as the material truth. That removes the hard seam
and the previous muddy RGB-strip failure while keeping readable source scrub,
grassland, soil, and rock ownership.

**Evidence**:
`world3/docs/M10_ECOTONE_LAYER_PROOF_2026_05_09.md`,
`world3/docs/captures/review/source_stack_ecotone_layer_tour_topdown.png`,
`world3/docs/captures/review/source_stack_ecotone_layer_tour_iso.png`,
`world3/docs/captures/review/source_stack_ecotone_layer_tour_medium.png`, and
`world3/docs/captures/review/source_stack_ecotone_layer_tour_close.png`.

**Implication**: M10 can proceed to M11 junction/corner logic using this
macro-guidance plus runtime-splat contract. Production promotion remains
blocked on scatter/object population, stronger real adjacent sources, better
grassland material candidates, and gameplay-zoom detail/normal review.

---

## 2026-05-10 - Ecotone scatter must be mask-driven and LOD-aware

**Decision**: The first M10 ecotone scatter pass uses the pipeline-emitted
feature masks as the source of truth for shrub, dry-grass, rock, soil, wash,
and no-scatter placement. Topdown review hides 3D scatter by default.

**Why**: The visual improvement we need is object breakup tied to the terrain
logic, not hand-placed decoration. At the same time, raw 3D scatter makes
topdown captures read as noise, so the review scene needs camera-band behavior
even at prototype stage.

**Evidence**:
`world3/scripts/EcotoneScatterOverlay.gd`,
`world3/scenes/review/source_stack_ecotone_layer_tour.tscn`, and
`world3/docs/M10_ECOTONE_LAYER_PROOF_2026_05_09.md`.

**Implication**: Future scatter work should replace placeholder meshes with
authored assets and add real distance bands, but should keep mask-driven
placement and topdown/iso/3D parity as part of the workflow contract.

---

## 2026-05-10 - Ecotone scatter review assets use composite shapes first

**Decision**: Improve the M10 ecotone scatter proof with composite low-poly
review shapes and simple per-class visibility ranges before starting M11.

**Why**: The first scatter pass proved mask-driven placement but still read too
much like one primitive per point. Composite shrub lobes, slab-style rocks, low
grass clumps, and camera distance bands make the proof more useful for visual
review without pretending we have production vegetation assets.

**Evidence**:
`world3/scripts/EcotoneScatterOverlay.gd` and refreshed captures under
`world3/docs/captures/review/source_stack_ecotone_layer_tour_*.png`.

**Implication**: The next scatter step is no longer "prove masks can place
objects"; that is done. The next scatter step is an asset-library pass:
authored scrub/grass/rock variants, per-biome density presets, and gameplay
camera LOD.

---

## 2026-05-10 - M11 junctions use generated domain fields, not RGB corner strips

**Decision**: Accept the first M11 three-way source/grassland/canyon Y junction
as workflow evidence. Junctions should be generated as domain fields plus
runtime splat weights, macro guidance, and feature masks. Do not build M11 as a
painted RGB corner strip.

**Why**: The first draft over-relied on neutral soil and read like a muddy beige
band. The accepted pass keeps a small soil/triple-core blend but preserves
source, grassland, and canyon ownership. Using the Zion master-stack terrain
texture as a canyon macro reference also keeps the canyon branch legible at
gameplay-review distance.

**Evidence**:
`world3/docs/M11_JUNCTION_LAYER_PROOF_2026_05_10.md`,
`world3/pipeline/build_m11_junction_layer_proof.py`,
`world3/scenes/review/source_stack_m11_junction_tour.tscn`, and captures under
`world3/docs/captures/review/source_stack_m11_junction_tour_*.png`.

**Implication**: M11 can continue to four-way/corner cases using this
domain/splat/macro contract. Production promotion remains blocked on authored
scatter assets, stronger grassland material candidates, production landform
geometry, and gameplay camera parity.

---

## 2026-05-10 - M11 four-way corner proof uses all four RGBA splat channels

**Decision**: Accept the four-way M11 proof that composes photoreal source, the
current grassland sidecar, controlled fantasy lava/basalt, and canyon rock
through one generated domain-field/splat/macro contract.

**Why**: A four-way proof should stress the actual runtime contract, not just
repeat a same-source blend. The chosen fantasy material is intentionally
controlled: mana crystal was too saturated and ice cavern was blown out, while
lava/basalt can read as a fantasy terrain stress case without dominating the
whole scene.

**Evidence**:
`world3/docs/M11_FOURWAY_CORNER_PROOF_2026_05_10.md`,
`world3/pipeline/build_m11_fourway_corner_proof.py`,
`world3/scenes/review/source_stack_m11_fourway_corner_tour.tscn`, and captures
under `world3/docs/captures/review/source_stack_m11_fourway_corner_tour_*.png`.

**Implication**: M11 can move to a small junction-case matrix, then M12
view-mode parity. T-junction, L-corner, and island variants are future
case-library work, not blockers.

---

## 2026-05-10 - M12 starts with an evidence inventory before new parity scenes

**Decision**: Start M12 with a repeatable audit of source-stack review scenes,
their camera-band captures, and whether they bind the runtime splat/source-stack
contract.

**Why**: We already have many review scenes, but they are not equivalent. Some
are current M10/M11 workflow evidence with close/medium/iso/topdown captures;
older cross-source scenes are historical evidence and usually lack close-band
captures; gallery/walk paths still diverge from the source-stack review contract.

**Evidence**:
`world3/pipeline/audit_m12_view_mode_parity.py`,
`world3/docs/M12_VIEW_MODE_PARITY_AUDIT_2026_05_10.md`, and
`world3/docs/captures/review/m12_view_mode_parity_audit.json`.

**Implication**: The next M12 implementation should build one parity
scene/template around an accepted proof before globally updating gallery or walk
mode.

---

## 2026-05-10 - M12 representative runtime parity can close before bulk gallery retrofit

**Decision**: Use a representative runtime parity scene as the M12 closure
target: true walk close/medium plus gallery-style iso/topdown over one
source/material/height/splat contract. Do not block M12 on retrofitting the
entire legacy bulk `RegionGalleryCapture.gd` path.

**Why**: M12 is about proving that the workflow contract can be shared across
gameplay bands. The old bulk gallery is useful, but it is a region screenshot
tool with per-kit material swaps. Retrofitting it is valuable scale work, not
the proof that the source-stack runtime contract works.

**Evidence**:
`world3/scripts/M12SourceStackParityRuntime.gd`,
`world3/scenes/review/source_stack_m12_runtime_fourway_tour.tscn`,
`world3/docs/M12_RUNTIME_PARITY_PROOF_2026_05_10.md`, and captures under
`world3/docs/captures/review/source_stack_m12_runtime_fourway_*.png`.

**Implication**: If live review passes, M12 can close as representative parity.
Bulk gallery retrofit moves to the post-parity roadmap.

---

## 2026-05-10 - Production promotion is gated separately from workflow acceptance

**Decision**: Add an explicit production-promotion gate before opening broad
post-parity content work. Workflow evidence, sidecar candidates, negative
evidence, production candidates, and production-promoted assets are separate
states.

**Why**: M10/M11/M12 now have impressive workflow proofs, but the docs
correctly repeat that most are not production-final. Without a gate, it becomes
too easy to treat "looked good in a review scene" as "safe for production."

**Evidence**:
`world3/jobs/production_promotion_candidates.json`,
`world3/pipeline/audit_production_promotion_candidates.py`, and
`world3/docs/PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`.

**Implication**: Post-parity work starts with M13 promotion tracking, then moves
to close-play materials, production scatter/features, gallery scaling,
real-data-guided procedural extraction, and a playable representative slice.

---

## 2026-05-10 - Iso optimization is a renderer sidecar, not a separate art path

**Decision**: Explore cached iso cards, cached chunk impostors, 2D heightfield
shaders, and hybrid tactical rendering as M16 sidecar work. These approaches
may avoid live 3D terrain rendering for iso/tactical gameplay, but they must
consume or reference the same source-stack contract as the 3D validation scene.

**Why**: Iso performance matters, but M12 proved that 3D, iso, and topdown must
stay aligned. A fast iso renderer is useful only if it does not fork terrain
ownership, masks, source macro, or promotion status.

**Evidence**:
`world3/docs/M16_ISO_IMPOSTOR_RESEARCH_PLAN_2026_05_10.md`,
`world3/scripts/M16IsoImpostorCardReview.gd`, and
`world3/scenes/review/source_stack_m16_iso_impostor_card.tscn`.

**Implication**: The first iso sidecar rung can use cached 2D playback of an
accepted M12 iso bake. Later rungs can test chunked impostors and 2D
heightfield shaders, but all must remain traceable to the same
height/macro/mask/splat data contract.

---

## 2026-05-10 - M14 close-play texture work uses three active model lanes

**Decision**: Use FLUX.2-klein, AuraFlow v0.3, and SD 3.5 Large as the active
M14 generated-ground bakeoff lanes. Park Qwen-Image and reject Chroma1-HD for
this phase.

**Why**: User review and the diversity comparison showed FLUX as the reliable
reference, Aura as useful for calmer organic variants, and SD 3.5 as a viable
photoreal experiment if prompts avoid central composition. Qwen produced
hero-shot/DOF imagery and is too slow for batch ground work right now. Chroma
failed the current terrain material target badly enough to stop spending M14
time on it.

**Evidence**:
`pipelines/textures/DIVERSITY_COMPARE_2026_05_09.md`,
`world3/jobs/m14_texture_bakeoff_plan.json`, and
`world3/docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`.

**Implication**: M14 candidates still need seam/PBR QA, visual veto,
gameplay-band terrain-context review, and explicit M13 promotion-state changes
before any production promotion.
