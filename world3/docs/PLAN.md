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

## Phase F checklist (from ROADMAP)

- [ ] **F.1 — Research existing approaches**
  - Godot 4.5 chunk-streaming patterns (built-in or community).
  - Terrain3D and HTerrain plugins — what they do, what they expect
    as input, do they integrate with our heightmap-PNG + meta.json
    + ShaderMaterial pattern.
  - Memory budget per chunk at our 256-subdiv resolution.
  - Output: `pipelines/textures/EXTERNAL_TECHNIQUES.md`-style survey
    doc at `world3/docs/PHASE_F_RESEARCH_2026_05_07.md`. Verdict on
    plugin vs. roll-our-own.

- [ ] **F.2 — Chunk-size decision**
  - Walk-mode visibility: ~500m circle around player at decent FPS
    requires ~9 chunks loaded if chunks are 256m, ~4 if chunks are
    512m. Pick based on memory budget from F.1.
  - Iso-mode: 300m diameter (Phase C lock) easily fits in a single
    512m chunk. Topdown minimap (10km) needs different streaming
    or the existing per-region heightmap.
  - Decide: keep one heightmap per region, OR split regions into
    multiple chunks at build time. Documented decision in
    DECISIONS.md.

- [ ] **F.3 — Stitch test (Tetons 2x2)**
  - Build a 2x2 grid of Tetons tiles (4km each = 8km total). Same
    heightmap repeated 4× to remove "real DEM seam" complications.
  - Expected: a single 8km terrain, no visible seam between the 4
    tiles, no double-load of shared edges.
  - Verify: mesh continuity at boundaries (vertex Y matches at the
    seam), no z-fighting, no normal discontinuity.
  - Output: capture scene + screenshot at
    `world3/docs/captures/phase_f/tetons_2x2_stitch.png`.

- [ ] **F.4 — Streaming prototype**
  - Replace static 4-chunk load with on-demand load/unload as the
    walker moves. Trigger: walker XZ enters a chunk's "warmup zone"
    (configurable; ~2 chunks ahead).
  - Verify: walking off the edge of one chunk and into another
    works without stutter, frame budget stays within target (need to
    define target).
  - Output: capture scene + a short timestamp log of load/unload
    events.

- [ ] **F.5 — Streaming budget audit**
  - How many chunks loaded simultaneously before frame budget breaks?
  - GPU memory used per chunk (mesh + .import textures + collision
    shape).
  - Documented numbers in `world3/docs/PHASE_F_BUDGET.md`.

- [ ] **F.6 — Decision lock + handoff**
  - Final chunk-size + format pick.
  - Update existing per-region scenes (walk/iso/topdown) to use
    streaming where it makes sense; auto-AABB/single-load stays
    available for region-gallery review.
  - Handoff doc at `docs/handoffs/HANDOFF_phase_f_*.md`.

## Exit criteria

- Walking off the edge of one tile and into another works without
  visible discontinuity.
- Documented streaming budget (how many tiles loadable at once
  before frame budget breaks).
- Decision-locked on chunk size + format.

## Sequencing rationale

- **F.1 first** because we don't know the right approach yet. A
  Terrain3D plugin investment or a roll-our-own decision should be
  made on evidence, not speculation.
- **F.3 (stitch test) before F.4 (streaming)** because if we can't
  get 2 stationary tiles to stitch cleanly, no amount of streaming
  logic helps.
- **F.5 (budget) before F.6 (decision lock)** because chunk size
  isn't picked from architecture alone; it has to fit GPU memory.

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
