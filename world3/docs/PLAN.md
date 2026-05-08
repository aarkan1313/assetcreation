# world3 — Current Iteration Plan: Phase F

**Phases B/C/D/E are done.** This iteration is **Phase F — multi-tile /
continuous world**, the long-term goal of the project. The grassland
"quality gap" surfaced during the C/D/E session was investigated and
locked as design-intent (DECISIONS.md 2026-05-07: grassland is
biologically near-uniform; loose bands are correct).

## Operating principles for Phase F

1. **Research before coding.** Phase F is structurally different from
   B/C/D/E — it's chunk streaming + LOD-adjacent terrain-engine work,
   not texture/shader work. We don't have prior code in this area. Spend
   the first ~half of session 1 on a survey before writing anything.
2. **Test workflow first, production look second.** This is a pipeline
   test. Get the seamless-tile mechanics working on identical Tetons
   tiles before worrying about real DEM stitching across region
   boundaries.
3. **Don't reinvent.** Godot 4.5 has built-in LOD + LightmapGI; the
   community has Terrain3D and HTerrain. Survey what they do before
   designing our own chunk streaming.

## Phase F checklist (revised 2026-05-08 after F.1 + F.3)

F.2 is now an **output of the F.4 sweep**, not a precondition for it.
The user's call: chunk size has to be picked from real performance +
quality data under streaming load, not from back-of-envelope numbers.
Sweep multiple sizes, compare, then lock.

- [x] **F.1 — Research existing approaches**
  - Findings at `world3/docs/PHASE_F_RESEARCH_2026_05_07.md`.
  - Verdict: hand-roll on Terrain.gd (Option A) for the prototype;
    Terrain3D (Option B) on standby if A surfaces fundamental issues.

- [x] **F.3 — Stitch test (Tetons 2x2)**
  - 4 Terrain instances, same Tetons heightmap, ±2000m XZ
    translation. Topdown view confirms continuous 8km square.
  - Caveat: per-chunk normal calc uses one-sided finite differences
    at borders → faint shading seam. F.4 needs 1-2 pixel overlap
    sampling to fix.
  - Captures + verdict at `world3/docs/captures/phase_f/`.

- [ ] **F.4 — Streaming harness (parameterized chunk size)**
  - Build a minimal walker-driven streaming scene that loads/unloads
    chunks around the walker's XZ position. Must take `chunk_size_m`
    as a runtime parameter so the same harness re-runs at multiple
    sizes.
  - Tile a single Tetons heightmap across an arbitrary grid to
    simulate "infinite world" without needing real DEM stitching
    (DEM-stitch is a follow-up; we want streaming mechanics first).
  - Fix the F.3 normal seam by sampling 1-2 pixel overlap from the
    source heightmap when building each chunk's hgrid.
  - Walker moves on a fixed deterministic path so runs at different
    chunk sizes are comparable.
  - Output: scene + walker script + chunk loader. Document in
    `world3/docs/PHASE_F_HARNESS.md`.

- [ ] **F.4-sweep — Run the harness at multiple chunk sizes**
  - Sweep `chunk_size_m` ∈ {256, 512, 1024}. Maybe 128 + 2048 if
    early data suggests they're interesting boundary cases.
  - Capture per size:
    - GPU memory steady-state (Godot's monitor + nvidia-smi).
    - Frame time mean + p95 + p99 (Godot's perf monitor) over the
      walker's deterministic path.
    - Number of chunks loaded simultaneously at peak.
    - Worst-case load latency (chunk-load triggered → mesh visible).
    - Visible seam quality: a screenshot at a known chunk crossing
      under each size.
  - Output: `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md` with per-size
    table + screenshots + recommended winner with rationale.

- [ ] **F.5 — Budget audit (digest sweep into decision)**
  - From the sweep table, pick the chunk size that hits acceptable
    framerate at acceptable memory at acceptable seam quality.
  - Document the trade-offs ("we lose X by choosing 512m over 256m,
    we gain Y").
  - Note any chunk-size ranges that are clearly broken (memory
    explosion, unacceptable seams, load stutter).

- [ ] **F.2 — Chunk-size + format decision (LOCKED)**
  - Once F.5 picks a winner, commit the decision to DECISIONS.md
    with the sweep evidence as justification.
  - Decide: keep one heightmap per region, OR split regions into
    multiple chunks at build time? (This is the "format" half of
    the decision; the chunk size is the "size" half. May be coupled
    if a chunk size doesn't divide region size cleanly.)

- [ ] **F.6 — Wire streaming into game scenes + handoff**
  - Update walk.tscn (the highest-impact mode for streaming) to use
    the chunk loader. iso.tscn and topdown.tscn at their current
    zoom levels (Phase C lock) probably don't need streaming at all
    — single-region load is fine.
  - Decide: gallery / capture scenes stay on auto-AABB single-load,
    or also use streaming?
  - Handoff doc at `docs/handoffs/HANDOFF_phase_f_*.md`.

## Exit criteria

- Walking off the edge of one tile and into another works without
  visible discontinuity.
- Documented streaming budget (how many tiles loadable at once
  before frame budget breaks).
- Decision-locked on chunk size + format.

## Sequencing rationale (revised 2026-05-08)

- **F.1 + F.3 first** (DONE) because we needed an architectural
  recommendation and a basic stitch verification before sinking
  effort into streaming.
- **F.4 (parameterized streaming harness) before F.4-sweep** so the
  sweep can compare chunk sizes against the same scene + walker
  path.
- **F.4-sweep before F.5** because the sweep IS the budget audit;
  F.5 just digests its data.
- **F.5 before F.2** because the chunk-size decision must be
  evidence-backed, not assumption-based. User's call (2026-05-08):
  "we need to see how performance changes when it's an infinite
  world, how quality changes with different sizes."
- **F.6 last** because wiring streaming into game scenes requires
  the chunk size + format to be locked first.

## Open polish items (parked, not blocking F)

- **Non-alpine per-mode visual review.** Phase E's emit tool covers
  all 5 kits; only alpine has dedicated capture scenes. Other kits
  validated only through the gallery's per-mode swap.
- **Walk-mode shared-anchor decision.** Phase C deferred whether walk
  shares a `PlayerAnchor` with iso/topdown or each gets its own.
  Decide when walk-mode wires into the anchor system. Phase F's walk
  test scene may force this decision.
- **Region gallery walk shot.** Gallery currently produces iso +
  topdown per region; could add a walk shot using the walk-tuned
  material. Walk needs an eye-level Camera3D, not the existing
  ortho one.
- **Texture contrast on grassland kit.** DECISIONS-locked as
  intentional 2026-05-07; revisit only if a specific region needs
  rocky landform variation, in which case generate replacement
  rock/snow textures with darker prompts (don't widen height bands).

## What changed last iteration (B/C/D/E recap)

| Phase | What | Status |
|-------|------|--------|
| B  | SR + mip-ladder + per-tier QA in `aaa_texture.py --ladder` | DONE (`84ed00e`, `6e62b37`) |
| C  | Anchor-mode framing on IsoCam/TopDownCam + PlayerAnchor + 4 zoom captures | DONE (`1dee0f8`, `eca28ba`, `8ca2ec0`) |
| D  | All 5 biome kits with bound `.tres` (chaparral fix); `deploy_kit_to_world3.py` | DONE (`ca171e9`, `4b53a0f`, `2d92cd1`) |
| E  | Per-game-mode material variants + `emit_per_mode_materials.py` + gallery swap + scene wiring | DONE (`c4d68c0`, `75b15d1`, `2346acf`) |
| Doc pass | Refresh PLAN/NEXT_SESSION/README/PIPELINE_DIRECTORY/TOOLS_INDEX/DOCS_INDEX/ROADMAP after C/D/E | DONE (`aff3882`, `b72bc50`) |
| Grassland tuning probe | Tested tighter bands, found texture albedos all yellow-tan; reverted + locked in DECISIONS | DONE (this commit) |

## Reading list before starting Phase F

1. `world3/docs/ROADMAP.md` — full roadmap, especially "Phase F" section.
2. `world3/docs/captures/phase_e_gallery/README.md` — see what 5 kits +
   per-mode tuning look like in their current state.
3. Godot docs: `https://docs.godotengine.org/en/stable/tutorials/3d/index.html`
   — chunked terrain, LOD, mesh streaming.
4. Terrain3D + HTerrain plugin pages (search for the latest releases
   targeting Godot 4.5).
