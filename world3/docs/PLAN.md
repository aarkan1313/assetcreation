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
| **M1** | Material catalog: single source of truth aligning kit slots + OpenTopo material classes. | Consolidated in this chat for now. | M2, M4 | — |
| **M2** | Transition material prototype: 4–6 transitions across kit/class/source pairs, integrated into existing review scene. | Consolidated in this chat for now; use OpenTopo QA infra. | M4 | M1 |
| **M3** | Chunk-size sweep: parameterized streaming harness + sweep at 256/512/1024 m, evidence-backed chunk-size lock. | Orchestrator | M5 | — (parallel with M1/M2) |
| **M4** | Splat-shader prototype: chunk emits per-pixel weights against material-class library; shader resolves. | Orchestrator | M5 | M1, M2 |
| **M5** | Wire streaming + splat into `walk.tscn`. | Orchestrator | — | M3, M4 |

**Parallelism**: M1+M3 can start simultaneously. M2 starts as soon
as M1's catalog spec is drafted. M4/M5 wait on the others.

**2026-05-08 operating note**: user asked this chat to keep worker and
orchestrator work consolidated for now. Owner labels still describe natural
responsibility boundaries, but this chat may execute both sides directly.

## M1 — Material catalog (orchestrator-led)

**Goal**: one source of truth for "what materials exist." Aligns
kit-slot terminology with material-class terminology so M2, M4 have
a defined input.

**Deliverables**:
- `world3/materials/CATALOG.md` plus machine-readable
  `world3/materials/catalog.json`.
- Schema for each entry:
  - `id` — canonical name
  - `source` — real / procedural / fantasy
  - `provenance` — DEM/orthophoto crop reference OR generation prompt
  - `scale_m_per_repeat` — physical scale at which the texture
    naturally repeats (matters for shader UV scaling)
  - `color_family` — for transition planning (e.g. warm-tan,
    cool-grey, green-organic)
  - `pbr_maps` — paths to albedo/normal/roughness/height/ao
  - `shader_binding` — which shader the material was authored
    against today (`terrain_blend` for orchestrator-side kits,
    `terrain_hex_detail` for worker's finished OpenTopo materials).
    M4 unifies these; until then the catalog records reality.
  - `validated_views` — close/mid/far ok-or-not (worker's QA notes
    fold into this)
- Refactor `biome_kits.json` so kit slots reference material-class
  IDs, not local texture paths.
- Migrate the 6 OpenTopo-finished materials AND the 5×5 = 25 kit
  slot textures into the catalog.

**Sequence**:
1. Draft catalog format.
2. Migrate the 25 procedural kit-slot materials.
3. Migrate the 6 finished OpenTopo materials.
4. Refactor `biome_kits.json` to reference catalog ids.
5. Verify catalog references and runtime material generation.

**Exit**: every material in the system has one canonical id and one
catalog entry. `biome_kits.json` references catalog ids. Existing
runtime scenes still build + render. Verified 2026-05-08 for base/per-mode
material generation, Godot import, Phase E smoke capture, and region gallery.

## M2 — Transition material prototype (consolidated, using OpenTopo QA infra)

**Goal**: build 4–6 transition strips spanning the kit-class spectrum
to learn transition mechanics + cost.

**Status 2026-05-08**: DONE for workflow/M4 input. Prototype pass 3 generated
four catalog-driven transition strips, numeric score hints, score-informed
tuning, hard-cut comparison captures, and a clean Godot review scene isolated
from the dirty OpenTopo review harness. The asset contract is explicit:
transition strips are generated boundary assets referenced by
`world3/jobs/biome_transition_rules.json`, not base catalog entries. Evidence:
`world3/docs/M2_TRANSITION_MATERIAL_PROTOTYPE.md` and
`world3/docs/M2_BOUNDARY_TRANSITION_CONTRACT.md`.

User visual review: transition workflow reads promising/good. The noisy
grass/leaves issue is tracked as source material quality, not a transition
workflow failure.

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
- Clean Godot review scene:
  `world3/scenes/capture_phase_m2/transition_strip_review.tscn`.
- Boundary rule contract:
  `world3/jobs/biome_transition_rules.json`.
- Captures: each transition rendered hard-cut vs. transition-strip
  side-by-side at `world3/docs/captures/transitions/`.

**Sequence**:
1. M1 catalog references verified.
2. Build transition tool against catalog ids.
3. Generate the listed transitions from catalog ids.
4. Capture hard-cut vs. transition-strip comparisons, score material/channel
   mismatches, and flag redos.

**Exit**: at least 3 transitions read visibly better than hard cuts.
Completed 2026-05-08: all four improve over hard cuts, rule-level tuning clears
roughness/frequency flags on the tuned assets, and residual normal-energy
mismatch is preserved as an M4/source-material risk signal.

## M3 — Chunk-size sweep (orchestrator, parallel with M1/M2)

**Goal**: chunk size + format committed to DECISIONS.md with
evidence under streaming load.

**Status 2026-05-08**: DONE. `ChunkLoader.gd` + sweep scene landed,
256/512/1024 m were measured at 8 m mesh spacing, and 256 m is locked
as the synchronous base chunk size for M5. Evidence:
`world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`.

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

**Exit**: chunk size + format locked in DECISIONS.md. Completed
2026-05-08 with 256 m as the base chunk.

## M4 — Splat-shader prototype (orchestrator, after M1+M2)

**Goal**: replace whole-chunk-kit binding with per-pixel splat
weights AND consolidate the two existing shaders
(`terrain_blend.gdshader` + `terrain_hex_detail.gdshader`) into one
unified path.

**Why both at once**: today the orchestrator-side scenes run
`terrain_blend` and the worker's 6 finished OpenTopo materials run
`terrain_hex_detail`. M4's splat shader has to handle both source
classes (height/slope-banded procedural kits AND hex-detail finished
real materials) or we end up with three shaders, not one. Best
absorbed as one design pass.

**Deliverables**:
- New unified shader supporting:
  - N-channel splat weight texture + N material-class refs
    (per-pixel mix)
  - Per-slot hex-tile sampling (currently only in `terrain_hex_detail`)
  - Per-slot height/slope rule fallback when splat weights aren't
    provided (current `terrain_blend` behavior)
- Splat-mask generation: for one test chunk, produce an N-channel
  weight texture from height + slope + biome rules.
- A/B captures: same chunk rendered through old whole-kit `.tres`
  (height/slope-banded) vs. new splat path. Plus a worker finished
  material rendered through the new unified shader matches its
  current `terrain_hex_detail` look.

Scope: prove the splat path works on one chunk + the unified shader
matches both predecessors' looks. Wiring it into production scenes
is M5.

**Exit**: unified splat shader renders a synthetic chunk with
weighted material blends AND reproduces a worker finished-material
scene's current look. Comparison captures committed.

## M5 — Wire streaming + splat into walk.tscn (orchestrator, after M3+M4)

**Goal**: end-to-end "walk an infinite world with mixed materials per
chunk."

**Deliverables**:
- `walk.tscn` uses `ChunkLoader.gd` (M3) and the splat shader (M4).
- Walker can move across chunk boundaries with no visible seam.
- Documented streaming + memory budget at the locked 256 m base chunk size.
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
