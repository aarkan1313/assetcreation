# M19-M24 Hybrid Procedural Infinite World Roadmap

Date: 2026-05-10. **Critical framing correction 2026-05-11** — see below.

This roadmap opens after the M13-M18 post-parity lane closes (production
promotion gate, close-play quality, scatter/features, gallery retrofit,
real-data-guided procedural extraction, and a playable representative slice).

The framing is the long-stated direction: **use real OpenTopo data to inform
procedural generation, not to be stretched into infinity**. We do not invent
new art; we re-arrange and extend the foundation already built in M1-M18 using
configuration data extracted from the real-source corpus.

## 2026-05-11 framing correction (READ FIRST)

**Procedural is the placement engine, not the texture generator.**

User clarification 2026-05-11 after live-reviewing the M18 procedural
side: *"we made the good textures to be our floor/ground textures, the
procedural thing was supposed to be how the world is built, how textures
are placed, heightmap, all that stuff."*

This means:

- **Textures come from the textures pipeline** — `pipelines/textures/`,
  the FLUX 2 9B + dev bakeoff, the M14 close-play work, the M1 catalog.
  Textures are NOT a procedural responsibility.
- **Procedural is the world-building system** — heightmap generation
  (M19 spectral fit + M20 erosion + M22 patch seeding), biome placement,
  splat weight emission, transition placement, scatter mask emission,
  region stitching. M19-M24 owns this.
- **Procedural zones consume catalog materials** via the M4 unified
  splat shader, same way real-source regions do. They emit the
  data; the catalog supplies the look.

The M18 procedural side currently reads as smooth tan/sand because
the implementation either (a) emitted splat weights biased to a single
broad material, (b) emitted heightmap topology too smooth for the
slope/height rules to pick varied materials, or (c) bypassed the
catalog. M19's first job is the audit that identifies which is true.

This correction does NOT change the M19-M24 sequence below. It changes
the **win condition** for each M:

- M19 success = the right splat weights + biome labels emerge from
  corpus statistics (so the catalog can do its job)
- M20 success = erosion produces topology variation that the splat
  shader can read into varied material placement
- M21 success = procedural chunks stream through ChunkLoader with
  correct material binding via the catalog
- M22 success = real-DEM patches seed plausible **placement
  structure**, not texture appearance
- M23 success = the director picks the right per-chunk source (real
  or procedural placement data); catalog handles the visual layer
- M24 style packs = different shader/material parameter sets over
  the **same procedural placement data**

Read every "procedural quality" reference below through this lens.
"Procedural quality" = quality of the placement/topology/labeling
data, not quality of generated textures.

## Why this exists / what it is not

**It IS**: a hybrid infinite-world placement engine that consumes the
existing material catalog, splat shader, transition rules, junction
layers, scatter masks, and source-stack contract. Real DEMs serve dual
roles: hero zones at runtime, and reference/training data for
procedural placement-rule extraction.

**It is NOT**:

- A rewrite of M1-M18.
- A new shader, new material taxonomy, or new chunk format.
- A "kernel" or neural-field approach. The technique stack is classical:
  spectral fitting + erosion sim + patch-based seeding + the M2/M10/M11
  transition/junction system.
- A bid for Google Earth quality. The realistic ceiling is the current
  source-stack scenes; the floor for procedural zones is ~85% of that.
- **A texture generator.** Procedural zones use catalog materials via
  the splat shader — they don't synthesize textures from scratch.

## Where it slots

```
M13 production gate ─┐
M14 close-play       │
M15 scatter/features │  → M17 real-data-guided procedural extraction
M16 gallery retrofit │     (one neighbor generator, source-stack contract)
                     │
                     └→ M18 playable slice
                             │
                             └→ M19-M24 (this doc)
                                hybrid infinite world
```

M17 is the direct upstream. M17 ships **one** procedural-neighbor generator
that emits the same height/macro/mask/splat contract as source-stack proofs.
M19-M24 generalize that into a corpus-driven generator that can fill arbitrary
neighbors around any cached real region.

A first-rung procedural-neighbor proof already exists at
`world3/pipeline/build_procedural_neighbor_bundle.py` (the M10 real-to-procedural
canyon-rock workflow proof from 2026-05-09). M17 promotes that one-shot
proof into a corpus-aware generator; M19-M24 generalize from there. New
M19-M24 tooling lives under `pipelines/terrain/` (corpus analysis, erosion,
director) so it sits next to the OpenTopo cache I/O it consumes; runtime
glue stays in `world3/pipeline/` next to `build_procedural_neighbor_bundle.py`.

## Sequencing Rules

- Inherits all M13-M18 sequencing rules. Production promotion is still a
  separate state; close/medium/iso/topdown bands still required for visual
  promotion.
- Procedural output flows through the source-stack contract, the M13 gate,
  and the same M12 view-mode parity audit.
- Real DEMs remain the authority. Procedural fills neighbors, ecotones, and
  out-of-coverage extensions; it does not replace cached regions.
- Erosion sim is the visual-quality backbone. Spectral fitting and patch
  seeding are supporting techniques, not equal phases.
- The master data catalog (`docs/MASTER_DATA_CATALOG.md`) is the corpus.
  Adding sources is a data-pull task, not a generator-code task.

## M19 - Corpus Statistical Analysis

**Goal**: derive per-biome procedural parameters from the cached DEM corpus.
This is the spectral-fitting backbone done correctly: not "fit FastNoise to
one DEM" but "fit a parameter distribution across the cached biome class."

Inputs:

- `docs/MASTER_DATA_CATALOG.md` and `world3/data_catalog.json`. As of
  2026-05-10 disk holds 659 DEM TIFs, but the catalog last regenerated
  at 292; rerun `pipelines/terrain/build_master_catalog.py` before M19
  starts so corpus statistics see the full pulled set including the
  in-flight mega-stack queue results.
- `world3/jobs/biome_kits.json` for biome class assignments.
- Cached mega-stacks per biome (alpine, desert, tundra, temperate_forest,
  grassland; plus the M17 unlike-biome ecotone work).

Deliverables:

- `pipelines/terrain/corpus_spectral_fit.py`: per-DEM radial-power-spectrum +
  hypsometric + slope-distribution + curvature-distribution extraction.
- `world3/jobs/procedural_biome_params.json`: per-biome distributions, not
  single point values. Each biome gets ranges for fractal dimension, ridge
  density, base elevation, relief amplitude, drainage density.
- Review notebook: 8-panel per-biome page (real samples vs. fitted FastNoise
  draws) for human visual review. The fit only passes when a viewer cannot
  reliably pick the real one.
- M13-gate-friendly metrics: KL divergence between real and synthesized
  height histograms, slope histograms, and ridge spacing.

Exit:

- Each biome has a parameter distribution with at least 5 real DEMs behind
  it and a human review pass that rates the FastNoise draws "plausibly same
  biome family."
- Honest limitations recorded: spectral fitting captures large-scale
  statistics but misses hydrology and rare features. Documented as design
  constraint feeding M20.

## M20 - Erosion Sim Backbone

**Goal**: install the visual-quality unlock. Erosion is the reason real DEMs
look real and FastNoise does not; ridges drain coherently, valleys widen
downstream, alluvial fans appear where slope breaks.

Inputs:

- M19 fitted FastNoise base fields.
- Landlab (new dependency; permissive license; pip-installable).
- M14 close-play quality bar.

Deliverables:

- `pipelines/terrain/erosion_chunk_generator.py`: takes a FastNoise base
  heightmap and runs Landlab fluvial + diffusion erosion until drainage
  network stabilizes. Per-biome erosion params from M19.
- A 1 km x 1 km eroded-FastNoise demo per biome, captured in close, medium,
  iso, and topdown bands, run through the M13 promotion-gate template.
- Performance budget: per-chunk erosion is offline-bake, not runtime. Caches
  to disk as a normal source-stack height bundle. Document chunk-bake time
  vs. tile count.

Exit:

- For at least 3 biomes, eroded procedural chunks pass M13 workflow review
  side-by-side against real cached chunks of the same biome at medium/iso/
  topdown bands. Close-play remains conditional pending M22 patch seeding.

## M21 - Procedural Neighbor Streaming Contract

**Goal**: integrate the erosion backbone with `ChunkLoader.gd` so procedural
chunks stream alongside real chunks under the same M10 seam integration and
M11 junction system.

Inputs:

- M10 terrain seam integration
  (`world3/pipeline/build_procedural_neighbor_bundle.py` and its
  successor).
- M11 junction layer + four-way/corner work.
- M20 erosion bake.
- `world3/scripts/ChunkLoader.gd` mirrored finite-source policy and
  source-stack contract.

Deliverables:

- Streamed scene: walk off the edge of Gloss Mountain (real) into a
  procedurally-eroded canyon-rock neighbor (procedural), then again across a
  second seam into a different procedurally-eroded biome.
- Per-chunk provenance metadata so runtime knows whether height/macro/splat
  came from a cached source-stack bundle or a procedural bake.
- Stream-time budget under M5 streaming policy (sync chunk size 256 m).
- M12 view-mode parity captures across all four bands.

Exit:

- Two seam crossings (real -> procedural, procedural -> procedural) at the
  same close/medium/iso/topdown bands as the M18 playable slice, scored
  against the M13 gate.

## M22 - Real-DEM Patch Seeding

**Goal**: the highest-leverage technique on top of erosion. Take small real
DEM patches and tile them into procedural fields as boundary conditions or
"detail injections," then let erosion blend them. This is closer to how
flight-sim terrain mods reach indistinguishable quality.

Inputs:

- M19 fitted base fields.
- M20 erosion solver.
- Cached real DEMs at sub-region resolution (USGS1m patches are ideal).
- M11 ecotone/junction workflow for soft blending.

Deliverables:

- `pipelines/terrain/patch_seed_synthesis.py`: takes a target biome,
  generates a FastNoise base, samples N real DEM patches of that biome,
  splices them in with feathered boundaries, then runs erosion to harmonize.
- Per-biome patch library indexed by ridge/valley/fan/plateau type so the
  synthesizer can pick patches that match local procedural conditions.
- Close-play band review for at least 2 biomes: real patches should pull
  procedural-zone close-play quality from ~80% (erosion only) to ~90% of
  the real cached scene.

Exit:

- Close-play band passes M13 review for 2 biomes. The "procedural" zones
  contain real DEM fragments but only at sub-chunk scale and only when an
  appropriate patch exists in the corpus.

## M23 - Infinite Streaming Director

**Goal**: convert the per-chunk procedural pipeline into a director that
can stream arbitrarily far from any cached real region without coverage
gaps.

Inputs:

- M21 streamed procedural neighbor proof.
- M22 patch-seeded synthesis.
- Master data catalog for "what real regions exist near here" lookups.

Deliverables:

- Director module: given a player XZ position, decides per chunk whether to
  serve cached source-stack bundle, procedural-neighbor bake, or on-demand
  patch-seeded synthesis. Caches bakes to disk under a quota.
- Biome-field map: a coarse world-space biome assignment that the director
  consults for which procedural params to use per chunk. Reuses M11
  ecotone/junction rules at biome boundaries.
- Cache-eviction policy + offline-bake queue so a player walking in a
  straight line does not stall on erosion solves.

Exit:

- A representative 10 km x 10 km test region streams without seams, with at
  least one cached real region inside it, surrounded by procedural neighbors
  and ecotones. Performance pass at the M5 streaming budget.

## M24 - Style Lane and Playable Infinite Slice

**Goal**: prove the long-term-vision style axis works on top of the hybrid
generator, and assemble a playable infinite slice.

Inputs:

- M23 streaming director.
- M14 close-play textures.
- M15 scatter/features.
- The `LONG_TERM_VISION.md` style axis (photoreal / painterly / Katamari /
  topographic).

Deliverables:

- Style packs that swap shaders/materials/scatter at the per-mode `.tres`
  layer without touching height or splat: photoreal (default), painterly,
  topographic. Same heightmap, three looks. Katamari left as future work.
- One playable infinite slice scene: cached Big Bend region surrounded by
  procedural neighbors at full quality, streamed under the director, with
  scatter, ecotones, and junctions.
- M13 gate full pass across all four bands for the slice.

Exit:

- A user can walk from a cached real region into procedural neighbors for
  at least 5 km in any direction without visible quality breaks at
  close/medium/iso/topdown. The slice renders under all shipped style packs.
- Honest review note: identify which biomes still read as procedural to a
  trained eye and where corpus expansion (more cached real patches) would
  raise the bar.

## Realistic End-State Expectation

When M24 closes, the system can:

- Stream infinitely from any cached real region anchor.
- Produce procedural zones at ~85-90% of cached-region visual quality across
  walk close/medium and iso/topdown bands.
- Switch style packs without re-baking terrain.
- Honor the long-term-vision constraints around 2.5D iso framing,
  source-stack contract, and per-mode material variants.

It cannot:

- Match Google Earth (no satellite imagery diversity, no NLCD-driven
  vegetation distribution, no real road/settlement networks).
- Fool an expert in that biome at close range without a corresponding real
  patch available.
- Generate new biome classes beyond the corpus. Adding a biome means adding
  cached real DEMs and rerunning M19.

The realistic end-state is **"current scene quality, but infinite, with
believable biome transitions across the whole field."**

## Doability Check Against Existing Workflows

Each M19-M24 piece composes with already-built infrastructure; no new lanes
required.

| Need | Existing piece |
|------|----------------|
| Heightmap source | OpenTopo cache (585+ tiles, 9 mega-stacks at last check) |
| Per-pixel materials | M4 unified splat shader |
| Material library | M1 catalog + 5 biome kits + 6 finished OpenTopo classes |
| Transitions | M2/M7 transition rules + boundary contract |
| Cross-source seams | M10 seam integration |
| Junctions/corners | M11 layer system |
| View-mode parity | M12 + per-mode `.tres` (Phase E) |
| Streaming | `ChunkLoader.gd` + 256 m chunks (M3/M5) |
| Source-stack contract | M5/M6 finite-source policy + valid-mask gating |
| Scatter masks | M15 production scatter + feature layers |
| Procedural neighbor proof | M17 real-data-guided extraction |
| Style swap | Per-mode `_<mode>.tres` template (Phase E) |
| Texture pipeline | `aaa_texture.py` FLUX/Aura/SD bakeoff (M14) |
| Prop pipeline | Trellis + `pipelines/props/lod_chain.py` |
| Material/region authoring GUI | Long-term factory-ops direction in `LONG_TERM_VISION.md` |

**Only new dependency**: Landlab for fluvial/diffusion erosion. Clean pip
install, permissive license, single import surface. Not a 17-engine
spell-lab situation.

## Risk Register

- **R1 - Erosion solve time at scale.** Landlab on a 256 m chunk at 1 m
  spacing is ~5-30s per chunk depending on iteration count. Mitigation:
  offline bake + cache; director uses pre-baked tiles. Direct streaming of
  fresh erosion is not in scope.
- **R2 - Corpus skew.** The cache leans alpine/canyon/desert. Tropical,
  boreal, and steppe biomes are under-sampled. M19 will quantify the gap;
  M23 will prioritize cache pulls.
- **R3 - Patch tells.** Real patches inside procedural fields can read as
  "spot the satellite photo." Mitigation: erosion harmonization pass after
  splice, M22 review explicitly looks for this.
- **R4 - Biome boundary illusions.** The M11 ecotone work assumes nearby
  cached real boundaries. Pure procedural ecotones may need their own
  rule mining. Tracked as an M23 risk; flag if it emerges.
- **R5 - Performance budget creep.** Streaming an infinite world raises
  GPU/memory budgets above the 256 m sync chunk size assumption. M21 and
  M23 each need an explicit budget capture.

## Honest Timeline / Effort Notes

Time is not the constraint; doability is. Effort estimates if pursued
back-to-back:

- M19: ~1-2 sessions (corpus analysis script + review).
- M20: ~2-3 sessions (Landlab wiring, per-biome calibration, three-biome bake).
- M21: ~1-2 sessions (integrate with existing streaming + seam integration).
- M22: ~2-3 sessions (patch index + splice + erosion harmonization).
- M23: ~2-3 sessions (director + cache policy + biome-field map).
- M24: ~1-2 sessions (style packs are a per-mode `.tres` permutation;
  playable slice is a scene assembly).

Total: ~10-15 sessions if M13-M18 lands cleanly first. Comparable to the
M7-M12 lane that already shipped.

## What Triggers Re-planning

- M17 procedural-neighbor proof fails M13 gate at any band -> revisit the
  M19 fitting approach before continuing.
- Corpus coverage for a target biome is too thin -> pause and run a
  cache pull (existing mega-stack queue tooling), not a generator-code
  workaround.
- A long-term-vision pivot (e.g. fantasy-axis source per Track A) lands
  before this roadmap starts -> realign M19 corpus split.

## Cross-References

- Foundation: `M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`.
- Closure audit gating this work: `M7_M12_CLOSURE_AUDIT_2026_05_10.md`.
- Long-term constraints: `../../docs/plans/LONG_TERM_VISION.md`.
- Top-level roadmap: `../../docs/plans/ROADMAP.md`.
- Data corpus: `../../docs/MASTER_DATA_CATALOG.md`.
- Direct upstream: M17 in `M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`.

## Current Status

NOT STARTED. Gated by:

1. M13-M18 closure (M14 currently in progress; M15-M18 pending).
2. M17 procedural-neighbor proof shipping at least one accepted bake.

Pre-work that can start any time without violating gates:

- Skim Landlab docs for fluvial+diffusion API surface. **Done 2026-05-10**
  — Landlab 2.11.0 installed in `pipelines/terrain/.venv` via clean
  pip wheels, no compiler needed. Smoke test at
  `pipelines/terrain/landlab_smoke_test.py` runs
  FlowAccumulator+FastscapeEroder+LinearDiffuser on a 128x128 @ 30m
  FastNoise base; before/after/drainage triptych in
  `pipelines/terrain/output/landlab_smoke/before_after.png`. Verified
  carved valleys + dendritic drainage network at ~3 ms/step. Per-lane
  install notes in `pipelines/terrain/README.md`.
- Run a one-off radial-power-spectrum extraction on the existing alpine
  mega-stacks as a feasibility check for M19.
- Identify corpus coverage gaps using the master data catalog as a hint for
  the next mega-stack pull queue refresh.
