# Phase H — Content production + catalog scaleup

> Phases F and G build the pipeline. Phase H uses it: scales the
> catalog beyond the 5-biome starter, lands the long-deferred
> procedural/erosion/POI/atmospheric work, and produces enough
> content to clear the completion bar.

## Why Phase H is different

F and G are pipeline phases. **H is content production work** that
the pipeline enables. The line shifts in H:

- F+G: every artifact is a script or schema
- H: every artifact is content (textures, biome kits, plot landmarks,
  water bodies, atmospheres) that the pipeline produces

This doesn't mean Phase H is "do art." It means Phase H is "drive
the pipeline at scale to fill out the catalog + the world." Most
H sub-phases will still ship scripts (catalog expansion drivers,
batch processors), but their *output* is content rather than
infrastructure.

## Sub-phases

### H.1 — Catalog scaleup beyond 5-biome starter

**Goal:** Catalog covers the full intended biome range (15-20+ biomes
including alpine variants, dry forests, wet forests, savannas,
tundras, coastals, etc.).

**Scope:**
- Per-biome kit authoring driven by F.5 catalog requisition
- F.4 transition audit + F.6 in-context audit gate every new biome
- M13 promotion advanced systematically per biome
- Closure doc with the new biome roster + per-biome gate state

**Exit:** All in-scope biomes are at `production_candidate` minimum
in M13 gate.

Absorbs FUTURE_WORLD_SOURCES and the catalog-side of FUTURE_PROCEDURAL_STRUCTURES.

### H.2 — Erosion sim integration

**Goal:** Procedural heightmaps go through a real erosion simulation
(fluvial + diffusion via Landlab) before they reach the procedural
neighbor builder. Realism of procedural terrain materially improves.

**Scope:**
- Wire Landlab (already smoke-tested in `pipelines/terrain/.venv/`)
  as an optional pre-step in `build_procedural_neighbor_bundle.py`
- Plan schema gets `procedural.erosion: {enabled, iterations, kr, kd}`
- Audit captures before/after erosion for procedural bundles in
  each biome
- Closure doc with the erosion gallery

**Exit:** Procedural bundles look like terrain that has weathered,
not like noise.

Absorbs M20 from the retired hybrid procedural roadmap.

### H.3 — Spectral analysis (procedural-from-real corpus)

**Goal:** Procedural neighbor builder learns from the cached real-DEM
corpus (657 DEMs as of 2026-05-11). Per-biome FastNoise parameter
distributions get fit from real terrain rather than hand-tuned.

**Scope:**
- Corpus statistical analysis script (run once per biome)
- Per-biome statistical fingerprint (FFT bands, slope distribution,
  drainage density, curvature distribution)
- Procedural neighbor builder reads the fingerprint and reproduces
  matching statistics
- Closure doc with statistical comparison: procedural vs real for
  the 5-biome starter, then 10-biome, then full catalog

**Exit:** Procedural bundles measure the same as real bundles on
per-biome statistical metrics.

Absorbs M19 from the retired hybrid procedural roadmap.

### H.4 — POI / landmark layer

**Goal:** A world plan can declare points of interest (named
landmarks, plot points, special structures) and the pipeline
produces them as patches (G.3) with handcraft hooks.

**Scope:**
- `world_plan.json` gets a `poi: [...]` array
- POI schema: world-coord + type + content reference
- Each POI emits as a patch bundle via G.3 / G.6 mechanism
- POI types: real-DEM landmark, hand-authored procedural patch,
  structure-generator output (trees, scree, fractal lattices,
  crystal formations — from FUTURE_PROCEDURAL_STRUCTURES)
- Closure doc with a POI roster in the starter world

**Exit:** Starter world has 3+ named POIs each rendered cleanly.

Absorbs G7 from operability gaps + the world-placement side of
FUTURE_PROCEDURAL_STRUCTURES.

### H.5 — Water + atmosphere + sky + weather

**Goal:** The four queued ARC modules land as plan-driven optional
layers. A plan can declare "this world has water + clear-sky
atmosphere + no weather" and the pipeline produces it.

**Scope:**
- Water track: river/lake mask emission tied to drainage analysis,
  shader work for water rendering
- Atmosphere track: per-biome ambient + tonemapping + fog defaults
  drive Environment node setup
- Sky track: per-style skybox + sun/lighting profiles
- Weather track: optional weather state as a runtime layer
- Each ARC ships its own schema + validator + audit per the
  LLM-drivability gate
- Closure docs per ARC (4 docs)

**Exit:** Starter world renders with water (where the plan says so),
weather (per plan), and biome-appropriate atmospheres/skies.

Absorbs the 5 retired ARC docs (Atmosphere / Sky / Water / Weather /
Conformance — Conformance moves to H.6).

### H.6 — Conformance suite

**Goal:** Every emitted bundle automatically renders through a
conformance suite that captures it under standardized conditions
and audits against contract expectations. Catches drift.

**Scope:**
- Conformance scenes that render any bundle through a fixed
  camera + lighting + style pack
- Audit script diffs new captures against a baseline (committed
  in `world3/docs/captures/conformance/`)
- Runs in CI-style mode: produce a green/red verdict per bundle
- Closure doc with the conformance gallery for the starter world

**Exit:** Re-rendering the starter world is byte-deterministic in
conformance output (or fails loudly with a contract diff).

Absorbs CONFORMANCE_ARC.

## Cross-cutting concerns

### Scale enforcement remains hard

H lands the most ambitious scale work (continent-scale procedural,
real-DEM patches with global landmarks, atmosphere across the whole
world). Scale discipline from F+G is non-negotiable in H.

### Catalog gate becomes the primary work product

By H.6 end, the M13 gate has per-biome × per-mode × per-bundle
states. The gate snapshot is the deliverable.

### LLM-drivability hard gate (carried from F+G)

Even in content phase, every sub-phase ships with the six-box bar
hit.

## Exit criteria for the whole phase

Phase H is **done** when:

1. Catalog covers full intended biome range at `production_candidate`+ (H.1)
2. Procedural terrain is statistically + visually credible (H.2 + H.3)
3. POIs / landmarks land cleanly in worlds (H.4)
4. Water + atmosphere + sky + weather are plan-driven options (H.5)
5. Conformance suite is green on the starter world (H.6)

**That's most of the completion bar.** Phase I formalizes the rest.

Open-ended estimate: H is **sized by catalog ambition**. 5→15 biomes
might be 10-15 sessions for H.1 alone. The other H sub-phases are
~2-4 sessions each.

## Out of scope for Phase H

- A specific game built on world3 — that's a separate consumer
  project, NOT a world3 phase
- Real-time procedural generation at game-time — world3 stays
  pre-baked
- Gameplay / audio / animation — consumer-side
- The completion sign-off itself — that's Phase I

## Anti-duplication notes

| Retired item | Lands in |
|--------------|----------|
| M19 (Corpus spectral analysis) | H.3 |
| M20 (Erosion sim backbone) | H.2 |
| FUTURE_WORLD_SOURCES (NLCD, bathy, planetary, fantasy) | H.1 |
| FUTURE_PROCEDURAL_STRUCTURES (trees, crystals, scree, etc.) | H.4 |
| ATMOSPHERE_ARC | H.5 atmosphere track |
| SKY_ARC | H.5 sky track |
| WATER_ARC | H.5 water track |
| WEATHER_ARC | H.5 weather track |
| CONFORMANCE_ARC | H.6 |
| G7 (POI layer) from operability gaps | H.4 |

## Cross-references

- Parent: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Predecessors: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md), [PHASE_G_CHARTER_2026_05_11.md](PHASE_G_CHARTER_2026_05_11.md)
- Successor (sign-off only): Phase I via [WORLD3_COMPLETION_BAR_2026_05_10.md](WORLD3_COMPLETION_BAR_2026_05_10.md)

## Status

- [ ] H.1 — Catalog scaleup beyond 5-biome starter
- [ ] H.2 — Erosion sim integration (absorbs M20)
- [ ] H.3 — Spectral analysis / procedural-from-real (absorbs M19)
- [ ] H.4 — POI / landmark layer (absorbs G7 + structure generators)
- [ ] H.5 — Water + atmosphere + sky + weather (absorbs 4 ARC docs)
- [ ] H.6 — Conformance suite (absorbs CONFORMANCE_ARC)

**Phase H charter SHIPPED 2026-05-11.** Implementation begins after
Phase G closes.
