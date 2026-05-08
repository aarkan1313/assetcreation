# world3 — Project State (2026-05-08)

**Operating model**: single-stream orchestrator. The world3 main chat
owns the unified roadmap, sequencing, and most of the work. The
OpenTopo chat is a worker that takes scoped handoffs in their
domain (real-data sourcing, master-stack assembly, real-source
material extraction, transition tile authoring, anything where their
existing tooling is the cheaper path). All architectural decisions
flow through the orchestrator.

This doc is the orchestrator's project-state inventory: what
exists, what works, what's the next focused thing to do, and where
the worker's existing infrastructure lives so we can point at it
without absorbing it.

Long-term scope (props / decoration / buildings / POIs / fantasy
biomes) is **acknowledged as future** — kicks in once chunk-to-chunk
+ biome-to-biome + tile-to-tile is ~80% solved (per user 2026-05-08).
NOT planned in this doc.

---

## 1. The world-generation knob-space

Each game built on this system picks a point in this knob-space.
A 2D fantasy strategy game uses one combination; a 3D realistic
walking sim uses another. The system needs to support orthogonal
movement along each axis without forcing changes to the others.

| Knob | Values | What it controls |
|------|--------|------------------|
| **Source** | `real` ⇄ `procedural` ⇄ `fantasy` | Where heightmaps + textures come from. Real = OpenTopo DEM + orthophoto. Procedural = ComfyUI/FLUX/StableMaterials. Fantasy = procedural + handcrafted style overrides. Mixable per-region or per-chunk. |
| **View** | `2D` ⇄ `iso` ⇄ `walk` | Camera mode. Implemented as the per-mode `terrain_blend_<kit>_<mode>.tres` swap (Phase E). 2D mode not yet wired but is the same knob. |
| **Style** | `photoreal` ⇄ `stylized-realistic` ⇄ `fantasy` | Visual treatment. Distinct from Source — a real DEM can be rendered photoreal OR stylized. Phase E `macro_value_strength` partially hits this. |
| **Granularity** | `whole-region kit` ⇄ `within-region kit-mix` ⇄ `per-pixel splat` | How material assignment is decided. Iso/topdown/gallery remain whole-region kit; walk has a first per-pixel splat prototype through M5. |
| **Decoration** | `bare-terrain` ⇄ `+scatter` ⇄ `+structures` | Props, vegetation, buildings, POIs. **NOT in scope** for this doc. |

---

## 2. What exists today

### 2A. Runtime + per-mode tuning + chunk-stitch (orchestrator-built)

| Piece | Knob coverage | Files / commits |
|-------|---------------|-----------------|
| **`Terrain.gd`** — single-heightmap mesh builder | Source: real (any DEM PNG). View: any. | `world3/scripts/Terrain.gd` |
| **5 biome kits** — alpine, desert, tundra, temperate_forest, grassland | Source: procedural. Style: photoreal. Granularity: whole-region kit. | `world3/jobs/biome_kits.json`, `world3/textures/wgv3/<kit>_<slot>/` |
| **Per-mode `terrain_blend_<kit>_<mode>.tres`** (15 files) | View: walk/iso/topdown. | `pipelines/textures/emit_per_mode_materials.py`, commits `c4d68c0` `75b15d1` |
| **Anchor-mode framing** (IsoCam/TopDownCam + PlayerAnchor + CamFraming) | View: iso/topdown at configurable diameter. | Phase C, commits `1dee0f8` `eca28ba` |
| **Region gallery** with per-mode swap | Granularity: whole-region kit. | `world3/scripts/RegionGalleryCapture.gd` |
| **`deploy_kit_to_world3.py`** | Tooling for building kit `.tres` from `biome_kits.json`. | `pipelines/textures/deploy_kit_to_world3.py` |
| **2x2 stitch test** | Granularity: chunk-stitched (4× same heightmap). | Phase F.3, `world3/scenes/capture_phase_f/`, commit `f76fde1` |
| **ComfyUI texture generation** (`aaa_texture.py` + 9-stage pipeline) | Source: procedural. | `pipelines/textures/aaa_texture.py`, Phases A/A-polish/B |

### 2B. Worker (OpenTopo chat) infrastructure — referenced, not absorbed

The worker has built a substantial real-data pipeline and material
library. Their full runbook lives in their doc set; from the
orchestrator's view, what matters is the pointer to that infrastructure
and what it produces.

| Capability | Where it lives | What we get out |
|-----------|----------------|------------------|
| Real DEM + orthophoto fetch / mosaic / fusion | `world3/pipeline/build_opentopo_*.py`, `world3/opentopo/` | Master stacks (DEM + orthophoto + masks aligned) |
| Real-source tileable PBR materials | `build_opentopo_tileable_texture.py` (early single-crop / baseline products) → `build_opentopo_texture_variant_atlas.py` (multi-crop variants) → `finish_opentopo_soft_materials.py` (final 6 classes via the soft-composite path) | 6 finished material classes: `bare_soil`, `bright_rock`, `dry_wash`, `rocky_slope`, `scrub_dense`, `scrub_sparse` (Guadalupe Cypress). Finishing tool wrote balanced albedo + neutral source-derived detail maps + `terrain_hex_detail`-bound `.tres` per class. |
| Multi-crop variant atlases | `world3/pipeline/build_opentopo_texture_variant_atlas.py` | Within-class variation for sibling-tile review |
| Master stacks (production-facing real-place review scenes) | `world3/opentopo/processed/master_stacks/` | Gloss Mountain (textured 0.6×1.1km), Zion (4-call USGS10m 36×37km no-color). Production-facing structure, not final production assets — still need runtime chunking, compression policy, and game-side integration before they ship. |
| Hard-adjacency biome transition QA | `world3/toporeview/biome_tile_transition_review.tscn` | Failure-view scene with both kits + OpenTopo materials side-by-side |
| HD inspection (4096 / 8192 / 16K stress) | `world3/toporeview/phase2_fusion_*_review.tscn` | Close-range view limits documented |
| Worker docs | `world3/docs/OPENTOPO_*.md` | Their detailed runbook, source-of-truth for real-data work |

The worker's docs (read-only from orchestrator's perspective):

```
world3/docs/OPENTOPO_GUIDE.md
world3/docs/OPENTOPO_DATA_TYPES.md
world3/docs/OPENTOPO_TOOLING_KNOBS_GUIDE.md
world3/docs/OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md
world3/docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md  (worker's roadmap; superseded by this doc for direction)
world3/docs/OPENTOPO_MASTER_STACKS_AUDIT.md
world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md
world3/docs/OPENTOPO_TILEABLE_TEXTURE_PILOT_AUDIT.md
world3/docs/OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md
world3/docs/OPENTOPO_PHASE2_HD_REVIEW.md
world3/docs/OPENTOPO_PHASE2_MAX_REVIEW.md
world3/docs/OPENTOPO_LARGE_4CALL_PLAN.md
world3/docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md
world3/docs/OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md
world3/docs/OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md
world3/docs/OPENTOPO_BC_COAST_DTM_DSM_AUDIT.md
world3/docs/OPENTOPO_RENDER_REPAIR_WORKFLOW.md
world3/opentopo/STATUS.md
```

### 2C. Shader stack - prototype unified path exists

The production/runtime scenes are mid-migration. Iso/topdown and the region
gallery still use the old whole-kit shader path, while M6 has hardened
`walk.tscn` on the prototype unified splat path:

- `world3/shaders/terrain_blend.gdshader` — height/slope-banded
  multi-slot blend. Bound by all `terrain_blend_<kit>_<mode>.tres`
  files (5 kits × 3 modes = 15) and by region-gallery materials.
  This is what the orchestrator-side `walk.tscn` / `iso.tscn` /
  `topdown.tscn` and `RegionGalleryCapture.gd` use.
- `world3/shaders/terrain_hex_detail.gdshader` — hex-tile + macro/
  detail layered. Bound by the worker's 6 finished OpenTopo
  material classes' `material_hex_detail_finished.tres` files. The
  worker's master-stack review scenes use this for finished
  source-real materials; review-only scenes use yet other shaders
  for layer/heightmap inspection.
- `world3/shaders/terrain_splat_unified.gdshader` - M4 prototype.
  Supports the current five semantic terrain slots, height/slope fallback,
  RGBA splat weights with fifth-slot remainder, and the OpenTopo macro/detail
  material path. Review materials, chunk contract, and captures are documented
  in `world3/docs/M4_SPLAT_SHADER_PROTOTYPE.md` and
  `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`.
- `world3/scenes/walk.tscn` - M6-hardened runtime wiring. Visible terrain now
  comes from `ChunkLoader.gd` with `terrain_splat_alpine.tres`, export-safe
  runtime height/splat caches, and streamed chunk collision. Evidence:
  `world3/docs/M5_WALK_SPLAT_STREAMING.md` and
  `world3/docs/M6_RUNTIME_HARDENING.md`.

The **shared runtime contract is started, not complete**. M6 proves the primary
walk-scene stream can use export-safe generated image caches, streamed
collision, and an opt-in transition-strip shader hook. Material indirection,
automatic boundary-mask generation, async/background chunk build, and broader
game-mode migration are still future hardening work.

---

## 3. Gaps (orchestrator-tracked)

| Gap | Status | Severity | Owner |
|-----|--------|----------|-------|
| **Aligned material taxonomy** (kit slots vs material classes) | Catalog exists with 25 procedural + 6 OpenTopo entries; material generation, import, and representative renders verified | HIGH — blocks M2/M4 until maintained | Consolidated in this chat |
| **Transition materials** between kits/classes | M2 generated four reviewed/tuned boundary strips; M6 adds an opt-in runtime sampler hook, but placement is still manual/prototype | HIGH — blocks tile-to-tile blending | Consolidated in this chat; use OpenTopo QA infrastructure |
| **Per-pixel splat shader** | M4 pass 2 prototype exists; M6 wires it through `walk.tscn` with export-safe splat cache and streamed chunks | HIGH - working prototype, still not final material indirection | Orchestrator |
| **Within-chunk material variation** | Prototype splat map generated from height/slope and consumed by both review chunks and the walk scene | HIGH | Orchestrator |
| **Cross-source style bridge** (real ↔ procedural ↔ fantasy adjacent) | Worker flagged it; no fix yet | MEDIUM | Consolidated in this chat |
| **Chunk size + format decision** | M3 sweep locks 256 m base chunks at 8 m mesh spacing | MEDIUM | Orchestrator |
| **Streaming load/unload + collision** | M6 stream in `walk.tscn`; scripted crossings build/remove visual chunks and streamed collision, with measured collision/update metrics | MEDIUM | Orchestrator |
| **Corner textures** (3-way junctions) | Not built; user flagged from past experience | HIGH long-term | Consolidated in this chat once pairwise transitions are validated |
| **Fantasy biome / fantasy material source** | Acknowledged future; no code yet | LOW (deferred) | TBD |
| **Provenance metadata** on procedural materials | Draft catalog now carries procedural + real-source provenance | LOW | Consolidated in this chat; keep expanding during M2/M4 |

---

## 4. Near-term focused plan (M1–M6)

**This is the orchestrator's plan.** It's the next sharp set of things,
not a multi-month roadmap. M1-M6 are now complete for workflow validation;
M7 is the next boundary-runtime integration layer.

### M1 — Material catalog (orchestrator-led, blocking)

Establish a single source of truth for "what materials exist."
Aligns kit-slot terminology with material-class terminology.

**Deliverables:**
- `world3/materials/CATALOG.md` plus machine-readable
  `world3/materials/catalog.json`. Each entry has: id, source
  (real/procedural/fantasy), provenance (DEM/orthophoto crop or
  prompt), scale, color family, current PBR maps path, validated
  views (close/mid/far ok or not).
- Refactor `biome_kits.json` so kit slots reference material-class
  IDs, not local texture paths. Existing per-mode `.tres` keep
  working — they resolve through the new lookup.
- Migrate the 6 OpenTopo-finished materials AND the 5×5 = 25 kit
  slot textures into one numbered catalog.

**Sequence:** consolidated in this chat for now. Draft catalog format,
migrate the 25 procedural kit-slot materials, migrate the 6 finished
OpenTopo materials, refactor `biome_kits.json`, then verify catalog
references and runtime material generation.

**Exit:** one source of truth for materials.

### M2 — Transition material prototype (consolidated)

Highest-leverage gap: pairwise material/biome boundaries need to read better
than hard cuts before M4 splat work.

**Status 2026-05-08:** DONE for workflow/M4 input. Prototype pass 3 generated
four catalog-driven transition strips, hard-cut comparison captures, score
hints, rule-level tuning, and a clean Godot review scene. Transition strips
are generated boundary assets referenced by
`world3/jobs/biome_transition_rules.json`, not base catalog materials.
Evidence: `world3/docs/M2_TRANSITION_MATERIAL_PROTOTYPE.md`.

**Deliverables:**
- Tool: `pipelines/textures/build_transition_strip.py` takes two material IDs
  from M1's catalog or the boundary rule file, emits a 6-8 repeat blended strip
  with PBR maps, noisy mask, tuning, score hints, and hard-cut comparison
  capture.
- Test pairs (4–6, hand-picked from current failure cases):
  - `desert_sand` ↔ `grassland_grass` (cross-biome high-style-delta)
  - `scrub_sparse` ↔ `dry_wash` (within-OpenTopo class neighbors)
  - `tundra_moss` ↔ `temperate_forest_grass` (cross-biome moderate)
  - One real ↔ procedural pair (e.g. `dry_wash` OpenTopo ↔
    `desert_dry_brush` procedural)
- Clean review scene:
  `world3/scenes/capture_phase_m2/transition_strip_review.tscn`.

**Sequence:** M1 catalog feeds transition rules; builder emits pair assets and
metrics; Godot review scene renders hard cut beside tuned strips.

**Exit:** at least 3 transitions read better than hard cuts in review.
Completed: all four improve over hard cuts. Residual normal-energy mismatch on
stress pairs is carried into M4/source-material QA.

### M3 — Chunk-size sweep (orchestrator-led, was Phase F.4-sweep)

Doesn't block M1/M2 (material-side). User's 2026-05-08 call: chunk
size needs evidence under streaming load.

**Status 2026-05-08:** DONE. Built `ChunkLoader.gd`, ran the
256/512/1024 m sweep at 8 m mesh spacing, and locked 256 m as the
synchronous base chunk size. Evidence:
`world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`.

**Deliverables:**
- `world3/scripts/ChunkLoader.gd` — walker-driven chunk
  load/unload around an XZ position. Takes `chunk_size_m` as a
  runtime parameter.
- Sweep at chunk sizes {256, 512, 1024} m on a synthetic infinite
  world (tile a single Tetons heightmap across an arbitrary grid).
  Measure: GPU memory steady-state, frame time mean/p95/p99, peak
  chunk count, worst-case load latency, seam quality screenshot.
- Document: `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md` — table per
  size + recommended winner with rationale.
- Fix the F.3 normal seam by sampling 1-2 pixel overlap from the
  source heightmap when building each chunk's hgrid.

**Exit:** chunk size + format committed to DECISIONS.md with sweep
evidence as justification. Completed with 256 m base chunks.

### M4 — Splat-shader prototype (orchestrator, after M1+M2)

Once M1 has aligned taxonomy and M2 has shown what transitions look
like, building a real splat shader becomes specific and bounded. M4
lets a chunk emit "this pixel is 40% dry_wash, 35% scrub_sparse,
25% rock_light" and resolve to a weighted blend.

Scope: extend `terrain_blend.gdshader` to take an N-channel weight
texture + N material-class refs, OR write a new shader that does.
Do NOT do this before M1 — without aligned taxonomy the inputs aren't
defined.

**Status 2026-05-08:** PROTOTYPE PASS 2 DONE. Added
`terrain_splat_unified.gdshader`, `build_m4_splat_prototype.py`, an alpine
height/slope splat map, splat/fallback/OpenTopo `.tres` materials,
`m4_chunk_material_contract.json`, and three Godot review captures. Evidence:
`world3/docs/M4_SPLAT_SHADER_PROTOTYPE.md` and
`world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`.

**Remaining work:** M4 prototype exit is met. M5 should wire this fixed
five-slot contract into `walk.tscn`; material indirection and transition-strip
sampling stay follow-up work unless M5 proves they are immediately needed.

### M5 — Streaming wired into walk.tscn (orchestrator, after M3)

Take M3's 256 m chunk-size winner and wire the chunk loader into
`walk.tscn`. Iso/topdown stay on auto-AABB (Phase C zoom levels fit
one chunk fine).

**Status 2026-05-08:** PROTOTYPE FINAL FORM COMPLETE. `walk.tscn` renders visible terrain
through `ChunkLoader.gd` with `terrain_splat_alpine.tres` and dynamic splat
weights. The original single `Terrain.gd` remains hidden for collision. The
first smoke capture exposed and then fixed a material UV mismatch at chunk
edges. `M5WalkStreamRunner.gd` now records both a 900 m crossing and a 1536 m
long-form sampled walk review. The long review crossed chunk rows `[0,5]` to
`[0,11]`, held 9 loaded chunks, built 18, removed 18, and saw an 18.317 ms
worst synchronous update.

Evidence: `world3/docs/M5_WALK_SPLAT_STREAMING.md` and
`world3/docs/M5_STREAMING_BUDGET.md`. Closure audit:
`world3/docs/M1_M5_FINAL_AUDIT_2026_05_08.md`.

**Remaining production work after M5:** export-safe generated image loading,
streamed collision, runtime boundary-strip sampling, and source-material QA for
noisy grass/leaves. These became the M6 scope below.

### M6 — Runtime hardening (orchestrator, after M5)

**Status 2026-05-08:** COMPLETE for the primary walk/runtime path. M6 added
runtime image caches for generated height/splat inputs, moved the walk scene to
streamed chunk collision, added collision metrics to the walk runner, added an
opt-in transition-strip sampler to the unified splat shader, and audited
green/organic source-material noise.

Evidence:

- `world3/docs/M6_RUNTIME_HARDENING.md`
- `world3/docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.md`
- `world3/docs/captures/m6/walk_stream_collision_cache.png`
- `world3/docs/captures/m6/walk_stream_collision_cache_metrics.json`
- `world3/docs/captures/m6/transition_runtime_review.png`

**Remaining production work after M6:** automatic biome-boundary mask
generation and transition-strip placement, async/background chunk build if
synchronous collision spikes show up interactively, material indirection beyond
the fixed five-slot prototype, and regeneration/filtering of flagged organic
materials before close-range production promotion.

---

## 5. Orchestrator / worker boundary

| Side | Owns | Doesn't own |
|------|------|-------------|
| **Orchestrator (this chat)** | Unified roadmap. Material catalog spec. Kit definitions. Shader stack + per-mode tuning. Chunk streaming + LOD. Procedural texture generation pipeline. Scene wiring. Runtime. Cross-cutting decisions (taxonomy, chunk size, sequencing). | Real-data fetch / processing. Master-stack assembly. Real-source material extraction. |
| **Worker (OpenTopo chat)** | Real-data sourcing (DEM, ortho, NIR, LAZ, masks). Master-stack assembly. Real-source material extraction. Transition tile authoring. Provenance metadata authoring. Anything in their existing tooling. | Architectural decisions. Roadmap direction. Runtime + scene wiring. Procedural texture generation. |

### Handoff protocol

Orchestrator writes a small spec at
`docs/handoffs/HANDOFF_to_opentopo_<topic>_<date>.md` containing:

1. **Task** (one paragraph: what + why).
2. **Inputs** (catalog refs, files to read, scenes to build against).
3. **Deliverables** (exact list: tool path, output paths, captures
   needed, any docs to update).
4. **Accept criteria** (how the orchestrator decides "done").
5. **Out of scope** (things they should NOT do as part of this).
6. **Deadline** (if any).

Worker executes, commits output, replies with: "done — here's what
landed, here are the surprises, here's anything I couldn't do."

Orchestrator reviews + integrates + marks the handoff closed in this
doc OR asks for revisions.

A template lives at `docs/handoffs/HANDOFF_TEMPLATE_to_worker.md`.

---

## 6. Acknowledged future scope (deferred — DO NOT plan here)

These exist and will land eventually. Listed so we don't architect
ourselves into a corner.

- **Props pipeline.** Each prop = mesh + texture + collision +
  placement metadata. Already partially exists in
  `pipelines/props/` + `world/props/library/`. Per-chunk placement
  masks once chunks exist.
- **Decoration pipeline.** Vegetation scatter, ground decals,
  small-scale debris. NDVI / canopy-derived in OpenTopo land for
  real placement; rule-driven for procedural / fantasy.
- **Buildings + POIs.** Whole separate pipeline (procedural +
  generated + handcrafted).
- **Fantasy biomes** as a Source-axis value. Blends procedural
  generation + handcrafted style overrides. Will need its own
  material classes and transition pairs.
- **Per-game knob presets.** Each game picks a point in the
  knob-space; a preset system lets games declare their combination.

These start when chunk + biome + tile + transition is ~80% solved
(per user 2026-05-08).

---

## Change log

- **2026-05-08**: Initial draft — switched from "two-chat parallel
  pipelines" to single-stream orchestrator/worker model. Worker
  retains its OpenTopo doc set as runbook; orchestrator owns
  direction.
- **2026-05-08 (later)**: Worker corrections applied to section 2B
  + 2C:
  - 6 finished OpenTopo material classes came from the
    variant/soft-composite path + `finish_opentopo_soft_materials.py`,
    not from `build_opentopo_tileable_texture.py` alone (that was
    earlier baseline products).
  - Master stacks (Gloss Mountain, Zion) are production-facing
    review scenes, not final production assets. Still need runtime
    chunking, compression policy, and game-side integration.
  - Shader stack is NOT fully unified today: orchestrator-side runs
    `terrain_blend.gdshader`; worker's finished OpenTopo materials
    use `terrain_hex_detail.gdshader`. Unified shader is the M4
    deliverable, not current state.
- **2026-05-08 (M1 start)**: Orchestrator drafted the material catalog
  contract at `world3/materials/CATALOG.md` and migrated the 25 procedural
  kit-slot materials into `world3/materials/catalog.json`. `biome_kits.json`
  now references catalog material ids; source generator ids remain preserved
  under catalog provenance. Added worker handoff
  `docs/handoffs/HANDOFF_to_opentopo_m1_material_catalog_migration_2026_05_08.md`
  for the six finished OpenTopo material classes.
- **2026-05-08 (direction clarification)**: Treat world3/assets as a pipeline
  and workflow creation set. Current content is primarily validation material
  for proving the workflow can reach AAA quality; production promotion requires
  separate camera-range, source/style-mix, and provenance review.
- **2026-05-08 (consolidated mode)**: User directed this chat to handle both
  orchestrator and worker work for now. The M1 OpenTopo migration handoff was
  marked DROPPED/superseded, and the six finished OpenTopo material classes
  were migrated directly into `world3/materials/catalog.json`.
- **2026-05-08 (M1 verification)**: Regenerated catalog-backed base kit
  materials and per-mode variants, ran Godot import, rendered a Phase E alpine
  smoke capture, and regenerated the region gallery. Grassland and
  temperate_forest catalog-id paths rendered nonblank images, so M1 is
  unblocked for M2/M4 inputs.
- **2026-05-08 (M3 sweep)**: Added `ChunkLoader.gd`, `ChunkSweepRunner.gd`,
  and `chunk_size_sweep.tscn`; measured 256/512/1024 m chunks with 8 m mesh
  spacing. 256 m is locked as the synchronous base chunk for M5 because it kept
  worst-case load latency near one 60 Hz frame while larger chunks spiked.
- **2026-05-08 (M2 prototype pass 1)**: Added catalog-driven transition-strip
  generation for four roadmap pairs and wrote hard-cut comparison captures under
  `world3/docs/captures/transitions/`. This starts M2 but does not close it;
  Godot review-scene integration and scoring remain.
- **2026-05-08 (M2 user visual review)**: User called the transitions pretty
  good/promising. Caveat: grass/leaves read too noisy for production; track that
  as source texture quality, not a transition workflow failure.
- **2026-05-08 (workflow docs refresh)**: Added
  `WORKFLOW_SNAPSHOT_2026_05_08.md` and refreshed `NEXT_SESSION_PROMPT.md`,
  `ROADMAP.md`, and `PLAN.md` so the pipeline/workflow state records M1 done,
  M3 done, and M2 prototype pass 1 as promising but still in review/scoring.
- **2026-05-08 (M2 review/scoring)**: Added transition score hints to
  `build_transition_strip.py`, regenerated the four transition manifests, and
  added a clean Godot review scene/capture for hard cuts beside generated
  strips. This exposed the transition asset contract question: catalog entries
  or generated boundary assets.
- **2026-05-08 (M2 boundary contract)**: Resolved the transition asset contract.
  Transition strips remain generated boundary assets referenced by
  `world3/jobs/biome_transition_rules.json`; base source materials stay in
  `world3/materials/catalog.json`. `build_transition_strip.py` can now build
  directly from the rule file.
- **2026-05-08 (dirty worktree checkpoint)**: User asked to commit all dirty
  files. Committed the accumulated OpenTopo docs/captures/review scenes and
  generated support files as `world3: checkpoint opentopo worktree`.
- **2026-05-08 (M2 tuning pass)**: Added rule-level tuning knobs for transition
  width, mask noise, albedo matching, local frequency dampening, roughness
  matching, and normal-energy dampening. Regenerated all four transition pairs;
  M2 is now done for workflow/M4 input.
- **2026-05-08 (M4 prototype pass 1)**: Added `terrain_splat_unified.gdshader`
  and `build_m4_splat_prototype.py`. Generated an alpine RGBA splat map plus
  splat/fallback/OpenTopo materials, then rendered terrain A/B and OpenTopo
  reference-vs-unified captures. M4 now has prototype evidence; next is the
  M5-facing chunk material/weight contract.
- **2026-05-08 (M4 prototype pass 2)**: Added
  `m4_chunk_material_contract.json`, `M4_CHUNK_MATERIAL_CONTRACT.md`, and
  `ChunkLoader.splat_weights_path`. Rendered
  `chunk_splat_stream_review.tscn` to prove a 256 m streamed chunk set can
  consume the unified splat material. M4 prototype exit is met; M5 wiring is
  next.
- **2026-05-08 (M5 pass 1)**: Wired `walk.tscn` to visible 256 m
  `ChunkLoader.gd` chunks using `terrain_splat_alpine.tres` and dynamic splat
  weights, while retaining hidden legacy terrain for collision. Fixed the
  first smoke-test chunk-edge material split by aligning chunk UVs with the
  height sampler's wrapped source fraction. Added `M5WalkStreamRunner.gd` plus
  static and moving smoke captures under `world3/docs/captures/m5/`.
- **2026-05-08 (M5 final audit)**: Lowered the walk start/runner clearance for
  a closer first-person review, added frame timing summaries to
  `M5WalkStreamRunner.gd`, rendered the 1536 m sampled long-walk contact sheet,
  and closed M1-M5 at prototype final form in
  `M1_M5_FINAL_AUDIT_2026_05_08.md`.
- **2026-05-08 (M6 hardening)**: Added export-safe runtime image caches and
  loader, moved the primary walk path to streamed collision chunks, added
  collision/frame metrics to the walk runner, added an opt-in runtime
  transition-strip sampler to `terrain_splat_unified.gdshader`, rendered M6
  walk/transition captures, and added source-material noise QA for green/
  organic materials. Evidence: `M6_RUNTIME_HARDENING.md` and
  `M6_SOURCE_MATERIAL_NOISE_AUDIT.md`.
