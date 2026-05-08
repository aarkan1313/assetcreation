# world3 State + Convergence Document — 2026-05-08

This is the consolidated state document for both the **world3 main**
chat (Phases A–F: kits, runtime, per-mode tuning, chunk-stitch) and
the **OpenTopo** chat (real-data textures, transitions, master stacks).
Written after we recognized the two work-streams are converging on the
same problem space and need a unified picture before either side
builds more.

The intent is **not** a multi-month roadmap. It is:

1. A formal definition of the world-generation knob-space we're
   actually working in.
2. An inventory of what each chat has built, mapped to that
   knob-space.
3. The empty corners (gaps) and overlapping corners (reconciliation
   work).
4. A short focused near-term plan of 3–5 sharp things to do next.

Long-term scope (props / decoration / buildings / POIs / fantasy
biomes) is **acknowledged as future**, not planned here. That pipeline
kicks in once chunk-to-chunk + biome-to-biome + tile-to-tile is ~80%
solved (per user 2026-05-08).

---

## 1. The world-generation knob-space

Each game built on this system picks a point in this knob-space.
A 2D fantasy strategy game uses one combination; a 3D realistic
walking sim uses another. The system needs to support orthogonal
movement along each axis without forcing changes to the others.

### Knobs

| Knob | Values | What it controls |
|------|--------|------------------|
| **Source** | `real` ⇄ `procedural` ⇄ `fantasy` | Where heightmaps + textures come from. Real = OpenTopo DEM + orthophoto. Procedural = ComfyUI/FLUX/StableMaterials. Fantasy = procedural + handcrafted style overrides. Mixable per-region or per-chunk. |
| **View** | `2D` ⇄ `iso` ⇄ `walk` | Camera mode. Already implemented as the per-mode `terrain_blend_<kit>_<mode>.tres` swap (Phase E). 2D mode not yet wired but is the same knob. |
| **Style** | `photoreal` ⇄ `stylized-realistic` ⇄ `fantasy` | Visual treatment. Distinct from Source — a real DEM can be rendered photoreal OR stylized. Phase E `macro_value_strength` partially hits this. |
| **Granularity** | `whole-region kit` ⇄ `within-region kit-mix` ⇄ `per-pixel splat` | How material assignment is decided. Current Phase D = whole-region kit. OpenTopo transition work points at within-region kit-mix. Per-pixel splat is the splat-shader endgame, not built yet. |
| **Decoration** | `bare-terrain` ⇄ `+scatter` ⇄ `+structures` | Props, vegetation, buildings, POIs. Acknowledged but **NOT in scope for this doc** — kicks in at ~80% terrain completion. |

### Why this matters

The two-pipeline split (Materials / Chunks) the OpenTopo chat
proposed is actually a horizontal slice through the knob-space, not
the knob-space itself. Materials and Chunks are *implementation
concerns* that span all five knobs:

- Materials apply to all Source values, all Granularity values.
- Chunks apply to all Source values, all View values.

So we're not picking between "one pipeline" vs "two pipelines"; we're
deciding how to bound each implementation concern *within* the
knob-space. That's why "let's just commit to two pipelines now" felt
premature — we hadn't yet defined what the pipelines bound against.

---

## 2. Inventory: what's built, mapped to the knob-space

### A. world3 main chat — runtime + per-mode tuning + chunks

| Piece | Knob coverage | Files / commits |
|-------|---------------|-----------------|
| **`Terrain.gd`** — single-heightmap mesh builder | Source: real (any DEM PNG). View: any. | `world3/scripts/Terrain.gd` |
| **5 biome kits** — alpine, desert, tundra, temperate_forest, grassland | Source: procedural. Style: photoreal. Granularity: whole-region kit. | `world3/jobs/biome_kits.json`, `world3/textures/wgv3/<kit>_<slot>/` |
| **Per-mode `terrain_blend_<kit>_<mode>.tres`** (15 files) | View: walk/iso/topdown. | `pipelines/textures/emit_per_mode_materials.py`, commits `c4d68c0` `75b15d1` |
| **Anchor-mode framing** (IsoCam/TopDownCam + PlayerAnchor + CamFraming) | View: iso/topdown at configurable diameter. | Phase C, commits `1dee0f8` `eca28ba` |
| **Region gallery** with per-mode swap | Granularity: whole-region kit. | `world3/scripts/RegionGalleryCapture.gd` (Phase D + E) |
| **`deploy_kit_to_world3.py`** | Tooling for building kit `.tres` from `biome_kits.json`. | `pipelines/textures/deploy_kit_to_world3.py` |
| **2x2 stitch test** | Granularity: chunk-stitched (4× same heightmap). | Phase F.3, `world3/scenes/capture_phase_f/`, commit `f76fde1` |
| **ComfyUI texture generation** (`aaa_texture.py` + 9-stage pipeline) | Source: procedural. | `pipelines/textures/aaa_texture.py`, Phases A/A-polish/B |

### B. OpenTopo chat — real materials + master stacks + transitions

| Piece | Knob coverage | Files |
|-------|---------------|-------|
| **6 finished real-source materials** — `bare_soil`, `bright_rock`, `dry_wash`, `rocky_slope`, `scrub_dense`, `scrub_sparse` | Source: real. Style: photoreal. Granularity: per-tile material class. | `world3/opentopo/processed/textures/Guadalupe_Cypress_*/` + `tileable_finished_material_review.tscn` |
| **Soft-composite tileable workflow** | Source: real → tileable. | `OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md`, `world3/pipeline/build_opentopo_tileable_texture.py` |
| **Variant atlas** (multi-crop sibling tiles per class) | Source: real with within-class variation. | `world3/pipeline/build_opentopo_texture_variant_atlas.py` |
| **Master stacks**: Gloss Mountain (textured DSM+ortho 0.6×1.1km) + Zion (4-call USGS10m 36×37km no-color) | Source: real. Granularity: full-place scene. | `world3/opentopo/processed/master_stacks/`, `OPENTOPO_MASTER_STACKS_AUDIT.md` |
| **Mosaic + fusion** workflows | Source: real, multi-call stitching. | `OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md`, `world3/pipeline/build_opentopo_mosaic_streaming.py` |
| **Phase 2 HD review** (4096 / 8192 / 16K) | View: close inspection. | `OPENTOPO_PHASE2_HD_REVIEW.md`, `OPENTOPO_PHASE2_MAX_REVIEW.md` |
| **Biome tile transition review** (THE convergence point) | Granularity: hard-adjacency QA, both kits + OpenTopo materials side-by-side. | `OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md`, `world3/toporeview/biome_tile_transition_review.tscn` |

### C. Shared / overlapping work

Both chats are emitting `terrain_blend_*.tres` files into
`world3/textures/wgv3/` (or adjacent `opentopo/processed/textures/...`)
and both render through the same `terrain_blend.gdshader`. This is
already a *de facto* shared contract — neither side has formalized it.

Both have independently identified:

- Per-chunk normal-seam issue at chunk borders (mine: F.3 caveat;
  theirs: "generate normals after stitching, not before").
- Hard tile-to-tile boundaries look bad regardless of how good the
  individual materials are.
- Chunked delivery is needed for HD inspection (their Step 3) and
  for streaming (my Phase F).
- Material-mask + macro-color separation is the right architectural
  direction (their `macro / meso / micro` framing matches what my
  shader's `macro_scale` + texture-tile + detail-pass aspires to).

### D. Empty corners (gaps)

| Gap | Status | Severity |
|-----|--------|----------|
| **Transition materials** between kits/classes | NEITHER pipeline has them | HIGH — blocks within-chunk mixing AND tile-to-tile blending |
| **Per-pixel splat shader** | We have a height-banded shader; no splat shader exists | HIGH — required for the OpenTopo chat's "chunks emit splat weights, materials decide what" architecture |
| **Within-chunk material variation** (one chunk has desert in NW corner, scrub in SE corner) | NEITHER pipeline can do this today | HIGH — the actual chunk → material relationship needs this |
| **Cross-source style bridge** (real OpenTopo material adjacent to procedural FLUX kit material) | OpenTopo chat flagged it; no fix yet | MEDIUM — color normalization + transition tile per pair |
| **Aligned material taxonomy** (kit slots: grass/dirt/rock_light/rock_dark/snow vs OpenTopo classes: bare_soil/bright_rock/dry_wash/rocky_slope/scrub_dense/scrub_sparse) | Two parallel ontologies hitting the same shader | MEDIUM — need a unified tag-set, even if old names persist as aliases |
| **Fantasy biome / fantasy material source** | Acknowledged future; no code yet | LOW (deferred) — but worth keeping in mind so we don't architect ourselves out of it |
| **Corner textures** (3-way junctions) | Not built; user flagged from past experience | HIGH — exponentially harder than pairwise transitions |
| **Streaming load/unload** (chunks dynamically loaded as walker moves) | Not built; was Phase F.4 before pause | MEDIUM — needs a chunk-size sweep that we deferred (good call) |
| **Provenance metadata** on materials (source, scale, source_policy) | OpenTopo materials carry this; world3 kits don't | LOW — straightforward to add to `biome_kits.json` once taxonomies align |

### E. Disagreements / reconciliation work

| Topic | world3 main approach | OpenTopo approach | Reconciliation |
|-------|----------------------|-------------------|----------------|
| **Material grouping** | "Kit" = 5 fixed slots × 5 biomes | "Material class" — flat list, transitions are pair-wise | Both need to live. Kit = "preset of N material classes for a biome." Refactor `biome_kits.json` to reference material classes by ID, not local slot names. |
| **Chunk → material binding** | Chunk binds one whole-kit `.tres` (Phase D) | Chunk emits per-pixel splat weights against material library | The splat path subsumes ours. Migration: kits become "splat-weight presets" — alpine kit = `(slope-band → {grass:0.4, dirt:0.3, rock_light:0.3})`. Old whole-kit binding stays as a fast path for legacy / preview scenes. |
| **Transitions** | Implicit via `h_band_softness` height-band shader blend | Explicit: built transition strips / pair-blend tiles + masks | Need both: rule-based (height/slope) for material pairs that look ok rule-blended; hand-baked transition tiles for cross-style (real ↔ procedural ↔ fantasy) where rules fail. |
| **Shader stack** | One `terrain_blend.gdshader` (height/slope-banded over 5 fixed slots) | `terrain_hex_detail` finished materials in OpenTopo land + the shared blend shader | Long-term: a unified shader that handles N-slot splat + per-slot material refs. Short-term: keep both shaders; they target different scenes. |
| **Per-region material assignment** | `regions.json` → `biome_kit` → kit `.tres` | OpenTopo material classes don't tie to regions yet — they're free-floating tile sets | Once OpenTopo materials are added to a "material class library," kits can reference them by ID instead of by texture path. Region → kit → classes → textures becomes a 4-layer lookup. |

---

## 3. The transition problem (worth its own section)

User flagged this from past experience: corner textures get into the
hundreds-to-thousands fast.

### Why it's hard

For N material classes:
- Pairwise transitions: N × (N-1) / 2
- Three-way corners: O(N³) — at N=20, that's ~7,600 corners
- Style-axis multiplier: real × procedural × fantasy = 3× the count
  if each combination needs its own transition

Pure pre-baked transition tiles don't scale. Pure rule-blending fails
at high-style-difference boundaries (real-photoreal ↔ stylized fantasy
adjacent). Modern terrain engines use splat masks + rule blending,
which scales linearly with N but produces visible-but-acceptable
boundaries.

### What both chats already see as the answer (combined)

OpenTopo chat's "Recommended Transition Pipeline" (4 stages):
1. Hard adjacency QA (already built — `biome_tile_transition_review.tscn`)
2. Palette / value normalization within a kit
3. Transition bands: 2-8 tile wide bands using noisy masks +
   slope/wetness/elevation rules + optional edge materials
4. Runtime blend shader: macro / meso / micro layered, not one
   monolithic albedo

world3 main's de-facto transition approach (less articulated):
- Within-kit: shader's `h_band_softness` blends slot-to-slot
- Cross-kit: hard cut today (Phase D regions); no answer yet for
  walking from desert region into alpine region.

### Combined transition strategy (proposal, not locked)

Three transition mechanisms gated by knob:

1. **Rule-blend** (cheapest, scales linearly): height-band + slope
   based blend within a single material class set. Works when the
   two adjacent classes are visually similar (grass ↔ dirt, dry_wash
   ↔ scrub_sparse). This is what the existing `terrain_blend.gdshader`
   does and it's fine for that use case.
2. **Splat-mask blend** (medium cost): chunks emit per-pixel weights
   against N material classes; shader samples weighted blend.
   Works for moderate style differences. Needs a new shader (gap E2
   above) or extending the existing one.
3. **Authored transition tiles** (expensive, hand-touched): for
   cross-style boundaries (real ↔ procedural ↔ fantasy) and for
   any pair where (1) and (2) read wrong. Pre-baked transition
   strips selected by adjacency lookup. Don't do all N² up front —
   build them on-demand as actual game content surfaces specific
   bad-looking boundaries.

Corner textures fall under (3) — but only for the corners that
actually show up in real game content. Not all N³ combinations need
to exist; only the ones we hit.

---

## 4. Unified roadmap (focused near-term)

NOT a full multi-month roadmap. Three to five sharp things, in order
of leverage. Anything beyond this list is parked until these three
clarify scope.

### M1 — Align material taxonomy (small, blocking)

**Why first:** every other piece depends on us agreeing what a
"material" is. world3 main's "kit slot" and OpenTopo's "material
class" are talking past each other.

**Concrete deliverables:**
- A `world3/materials/CATALOG.md` (or extend `biome_kits.json`) that
  lists every material class with: id, source (real/procedural/
  fantasy), provenance, scale, color family, current PBR maps path,
  validated views (close/mid/far ok or not).
- Refactor `biome_kits.json` so kit slots reference material-class
  IDs, not local texture paths. Existing per-mode `.tres` keep
  working — they just resolve through the new lookup.
- Migrate the 6 OpenTopo-finished materials and the 5×5 = 25 kit
  slot textures into one numbered catalog.

**Owner suggestion:** OpenTopo chat drafts the catalog format
(they have more material-types in flight). world3 main reviews +
migrates the kit slots.

**Exit criteria:** one source of truth for "what materials exist."

### M2 — Transition-material prototype (proof-of-concept)

**Why second:** transitions are the single highest-leverage gap.
Both chats have flagged it; OpenTopo has the QA infrastructure
(`biome_tile_transition_review.tscn`) ready to consume them.

**Concrete deliverables:**
- Tool: `pipelines/textures/build_transition_strip.py` — takes two
  material IDs from M1's catalog, emits a 2-8 tile wide blended
  strip with: noisy mask, palette interpolation, edge feathering.
- Test pairs (start with 4–6, hand-picked from biome_tile_transition's
  failure cases):
  - `desert_sand` ↔ `grassland_grass` (cross-biome high-style-delta)
  - `scrub_sparse` ↔ `dry_wash` (within-OpenTopo class neighbors)
  - `tundra_moss` ↔ `temperate_forest_grass` (cross-biome moderate)
  - One real ↔ procedural pair (e.g. `dry_wash` OpenTopo ↔
    `desert_dry_brush` procedural)
- Drop generated transitions into the existing transition review
  scene; visually check that hard borders soften into believable
  bands.

**Owner suggestion:** OpenTopo chat — they have the review tooling
and the transition recipe. world3 main consumes the output (binds
transitions into kits via M1's catalog).

**Exit criteria:** at least 3 transitions read better than hard cuts
in `biome_tile_transition_review.tscn`. We learn how expensive a
transition is to build and roughly how many we'll need.

### M3 — Chunk-size sweep (the deferred F.4-sweep)

**Why third:** doesn't block M1/M2 (they're material-side) but is
the gating decision for runtime. User's 2026-05-08 call: chunk size
needs evidence under streaming load.

**Concrete deliverables:**
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

**Owner suggestion:** world3 main chat — Phase F infrastructure is
already there.

**Exit criteria:** chunk size + format committed to DECISIONS.md
with sweep evidence as justification.

### M4 (optional, after M1–M3) — Splat-shader prototype

Once M1 has aligned taxonomy and M2 has shown what transitions look
like, building a real splat shader becomes specific and bounded. M4
is the shader that lets a chunk say "this pixel is 40% dry_wash, 35%
scrub_sparse, 25% rock_light" and resolves to a weighted blend.

Scope: extend `terrain_blend.gdshader` to take an N-channel weight
texture + N material-class refs, OR write a new shader that does. Do
NOT do this before M1 — without aligned taxonomy the inputs aren't
defined.

### M5 (optional, after M3) — Streaming wired into walk.tscn

Take the chunk-size winner from M3 and wire the chunk loader into
the actual `walk.tscn` game scene. Iso/topdown stay on auto-AABB
(Phase C zoom levels fit one chunk fine).

---

## 5. Proposed split going forward

Stop framing this as "two pipelines" — instead, frame it as **two
chats sharing one repo, with a shared catalog as the contract**.

| Chat | Owns | Doesn't own |
|------|------|-------------|
| **OpenTopo chat** | Real-data sourcing (DEM, ortho, NIR, LAZ, masks). Real-source material extraction. Transition tile authoring. Master-stack assembly. Provenance metadata. | Runtime mesh builder. Per-mode `.tres` emission. Streaming. |
| **world3 main chat** | Runtime mesh + scene wiring. Per-mode shader tuning. Chunk streaming + LOD. Procedural texture generation pipeline. Kit definitions. | Real-data fetch/process. Real-material extraction. Master-stack assembly. |
| **Shared (M1 deliverable)** | Material catalog format. Transition pair list. Chunk-size sweep results. | — |

OpenTopo chat keeps its `OPENTOPO_*.md` doc set; world3 main keeps
the runtime + Phase A–F docs. Both update this `WORLD3_STATE_*.md`
when crossing the shared catalog.

---

## 6. Acknowledged future scope (deferred — DO NOT plan here)

These exist and will land eventually. Listing them so we don't
architect ourselves into a corner.

- **Props pipeline.** Each prop = mesh + texture + collision +
  placement metadata. Already partially exists in `pipelines/props/`
  + `world/props/library/` (Trellis2 + HY3D-2.1 routes). Will need
  per-chunk placement masks once chunks exist.
- **Decoration pipeline.** Vegetation scatter, ground decals,
  small-scale debris. NDVI / canopy-derived in OpenTopo land for
  real placement; rule-driven for procedural / fantasy.
- **Buildings + POIs.** Whole separate pipeline (procedural +
  generated + handcrafted). Picks per-chunk slots for "this chunk
  has a fort, this chunk has a ruin."
- **Fantasy biomes** as a Source-axis value. Blends procedural
  generation + handcrafted style overrides. Will need its own
  material classes and transition pairs.
- **Per-game knob presets.** Each game (2D fantasy strategy / 3D
  realistic walking sim / iso ARPG / etc.) picks a point in the
  knob-space; a preset system lets games declare "I want
  source=real+procedural mix, view=iso, style=stylized-realistic,
  granularity=within-chunk-mix, decoration=+scatter+structures."

These start when chunk + biome + tile + transition is ~80% solved
(per user 2026-05-08).

---

## Notes for the OpenTopo chat reading this

- I tried to reflect your work fairly. If I mis-stated anything
  about your master stacks, transition review, or 6 material
  classes, please correct in a follow-up edit to this doc.
- I propose `M2` (transition prototype) as your owned next-up
  because you've already built the QA infrastructure for it. Push
  back if you'd rather sequence differently.
- The "material catalog" deliverable in M1 is the actual contract
  between us. I'd suggest you draft the catalog format because
  you've already been doing this informally in your finished-materials
  index files.

## Notes for the user

- This doc is an **inventory + alignment** doc, not a roadmap. The
  M1–M5 list is a focused near-term plan, NOT a multi-month
  schedule.
- The 2-pipeline framing has been replaced with "shared catalog +
  parallel chat ownership." This is cheaper than commiting to a
  pipeline architecture before we have aligned material vocabulary.
- Phase F.4 (streaming harness) is not paused permanently — it
  becomes M3 with the same scope, just sequenced after taxonomy
  alignment.
