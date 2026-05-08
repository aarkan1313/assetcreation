# world3 — Current Iteration Plan: M1–M5

**Operating model change (2026-05-08)**: switched from two-chat
parallel pipelines to **single-stream orchestrator + worker**. The
world3 main chat (this one) is the orchestrator; the OpenTopo chat
is a worker that takes scoped task handoffs. State + boundary +
handoff protocol live in
[`WORLD3_STATE_2026_05_08.md`](WORLD3_STATE_2026_05_08.md).

This iteration replaces "Phase F end-to-end" with the M1–M5 plan
because:

1. The world is bigger than just chunks. Material taxonomy,
   transitions, splat shader, and chunk size are all interlocked
   gating problems. Each one alone is a phase-sized commitment.
2. Aligning material taxonomy is a precondition for the rest. Build
   the catalog first; then transitions and splat shader can talk to
   each other.
3. Phase F.4-sweep (chunk size) is independent of M1/M2 and fits as
   M3 in parallel.

## Phase ledger (where we are)

| Phase | Status |
|-------|--------|
| A — texture quality + prompt R&D | DONE |
| A polish — pipeline foundation hardening | DONE |
| B — upscaling + multi-resolution pipeline | DONE |
| C — iso/topdown anchor framing | DONE |
| D — biome generalization (5 kits) | DONE |
| E — per-game-mode material variants | DONE |
| F.1 — research findings | DONE |
| F.3 — 2x2 stitch test | DONE |
| F.2/F.4/F.5/F.6 | absorbed into M3/M5 below |

## M1–M5 sequence (current iteration)

| ID | What | Owner | Blocks | Blocked by |
|----|------|-------|--------|------------|
| **M1** | Material catalog: single source of truth aligning kit slots + OpenTopo material classes. | Orchestrator drafts spec; worker handoff for migrating their 6 materials. | M2, M4 | — |
| **M2** | Transition material prototype: 4–6 transitions across kit/class/source pairs, integrated into existing review scene. | Worker (handoff, has the QA infra) | M4 | M1 |
| **M3** | Chunk-size sweep: parameterized streaming harness + sweep at 256/512/1024 m, evidence-backed chunk-size lock. | Orchestrator | M5 | — (parallel with M1/M2) |
| **M4** | Splat-shader prototype: chunk emits per-pixel weights against material-class library; shader resolves. | Orchestrator | M5 | M1, M2 |
| **M5** | Wire streaming + splat into `walk.tscn`. | Orchestrator | — | M3, M4 |

**Parallelism**: M1+M3 can start simultaneously. M2 starts as soon
as M1's catalog spec is drafted. M4/M5 wait on the others.

## M1 — Material catalog (orchestrator-led)

**Goal**: one source of truth for "what materials exist." Aligns
kit-slot terminology with material-class terminology so M2, M4 have
a defined input.

**Deliverables**:
- `world3/materials/CATALOG.md` (or `catalog.json` — decide during
  drafting).
- Schema for each entry: id, source (real/procedural/fantasy),
  provenance, scale, color family, current PBR maps path,
  validated views (close/mid/far ok or not).
- Refactor `biome_kits.json` so kit slots reference material-class
  IDs, not local texture paths.
- Migrate the 6 OpenTopo-finished materials AND the 5×5 = 25 kit
  slot textures into the catalog.

**Sequence**:
1. Orchestrator drafts catalog format (~half session).
2. Orchestrator writes M1-migration handoff for worker (their 6
   materials → catalog format).
3. Worker executes migration; replies with done.
4. Orchestrator does kit-slot refactor + verifies build.

**Exit**: every material in the system has one canonical id and one
catalog entry. `biome_kits.json` references catalog ids. Existing
runtime scenes still build + render.

## M2 — Transition material prototype (worker handoff)

**Goal**: build 4–6 transition strips spanning the kit-class spectrum
to learn transition mechanics + cost.

**Deliverables**:
- Tool: `pipelines/textures/build_transition_strip.py` — takes two
  catalog ids, emits a 2–8 tile wide blended strip (noisy mask,
  palette interpolation, edge feathering).
- Test transitions:
  - `desert_sand` ↔ `grassland_grass` (cross-biome, high style delta)
  - `scrub_sparse` ↔ `dry_wash` (within-OpenTopo neighbors)
  - `tundra_moss` ↔ `temperate_forest_grass` (cross-biome moderate)
  - One real ↔ procedural pair (e.g. `dry_wash` OpenTopo ↔
    `desert_dry_brush` procedural)
- Integrate into `biome_tile_transition_review.tscn`.
- Captures: each transition rendered hard-cut vs. transition-strip
  side-by-side at `world3/docs/captures/transitions/`.

**Sequence**:
1. M1 catalog format drafted.
2. Orchestrator writes M2 handoff with catalog ids + accept criteria.
3. Worker builds tool + transitions + captures.
4. Orchestrator reviews + integrates + flags any that need redo.

**Exit**: at least 3 transitions read visibly better than hard cuts.
We have a ballpark cost-per-transition (minutes, ComfyUI calls,
hand-touched steps).

## M3 — Chunk-size sweep (orchestrator, parallel with M1/M2)

**Goal**: chunk size + format committed to DECISIONS.md with
evidence under streaming load.

**Deliverables**:
- `world3/scripts/ChunkLoader.gd` — walker-driven chunk
  load/unload around an XZ position. `chunk_size_m` runtime parameter.
- Synthetic infinite-world scene (single Tetons heightmap tiled
  across an arbitrary grid).
- Sweep at `chunk_size_m` ∈ {256, 512, 1024}. Per size, capture:
  - GPU memory steady-state
  - Frame time mean / p95 / p99
  - Peak chunk count loaded
  - Worst-case load latency
  - Seam quality screenshot at a known chunk crossing
- F.3 normal-seam fix: 1-2 pixel overlap from source heightmap when
  building each chunk's hgrid.
- `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md` with table + winner.

**Exit**: chunk size + format locked in DECISIONS.md.

## M4 — Splat-shader prototype (orchestrator, after M1+M2)

**Goal**: replace whole-chunk-kit binding with per-pixel splat
weights.

**Deliverables**:
- New shader (or extension of `terrain_blend.gdshader`) supporting
  N-channel splat weight texture + N material-class refs.
- Splat-mask generation: for one test chunk, produce a 4-channel
  weight texture from height + slope + biome rules.
- Side-by-side comparison: same chunk rendered through old
  whole-kit `.tres` vs. new splat path.

Scope: prove the splat path works on one chunk. Wiring it into
production scenes is M5.

**Exit**: splat shader renders a synthetic chunk with weighted
material blends; comparison capture committed.

## M5 — Wire streaming + splat into walk.tscn (orchestrator, after M3+M4)

**Goal**: end-to-end "walk an infinite world with mixed materials per
chunk."

**Deliverables**:
- `walk.tscn` uses `ChunkLoader.gd` (M3) and the splat shader (M4).
- Walker can move across chunk boundaries with no visible seam.
- Documented streaming + memory budget at the locked chunk size.
- Handoff doc closing M1–M5 iteration.

Iso/topdown game scenes stay on auto-AABB single-load (Phase C zoom
levels fit one chunk fine).

**Exit**: long-form walk demo (~30s capture) shows continuous
terrain with mixed materials and acceptable framerate.

## Open polish items (parked)

- **Non-alpine per-mode visual review.** Phase E covers all 5 kits
  but only alpine has dedicated capture scenes.
- **Walk-mode shared-anchor decision.** Deferred from Phase C.
- **Region gallery walk shot.** Gallery only does iso + topdown.
- **Texture contrast on grassland kit.** DECISIONS-locked as
  intentional 2026-05-07. Revisit if a region needs visible rocky
  variation.
- **Corner textures (3-way junctions).** Defer until pairwise
  transitions (M2) are validated and we know which corners actually
  show up in real game content.

## What changed last iteration (B/C/D/E recap)

| Phase | What | Status |
|-------|------|--------|
| B  | SR + mip-ladder + per-tier QA in `aaa_texture.py --ladder` | DONE (`84ed00e`, `6e62b37`) |
| C  | Anchor-mode framing on IsoCam/TopDownCam + PlayerAnchor + 4 zoom captures | DONE (`1dee0f8`, `eca28ba`, `8ca2ec0`) |
| D  | All 5 biome kits with bound `.tres` (chaparral fix); `deploy_kit_to_world3.py` | DONE (`ca171e9`, `4b53a0f`, `2d92cd1`) |
| E  | Per-game-mode material variants + `emit_per_mode_materials.py` + gallery swap + scene wiring | DONE (`c4d68c0`, `75b15d1`, `2346acf`) |
| Doc pass | Refresh after C/D/E | DONE (`aff3882`, `b72bc50`) |
| F.1 + F.3 | Research + 2x2 stitch test | DONE (`f76fde1`) |
| Grassland tuning probe | Tested tighter bands; reverted + locked in DECISIONS | DONE (`d9a231c`) |
| Operating-model switch + state doc | Single-stream orchestrator/worker | THIS ITERATION |
