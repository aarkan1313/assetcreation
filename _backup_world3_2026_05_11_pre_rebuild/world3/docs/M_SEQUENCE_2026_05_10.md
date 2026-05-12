# World3 M-Sequence Timeline (2026-05-10)

> ⚠️ **SUPPLEMENTARY TIMELINE — NOT THE CANONICAL ROADMAP.**
>
> **Canonical roadmap lives in [`ROADMAP.md`](ROADMAP.md).** If this
> doc disagrees with `ROADMAP.md` or the latest committed audit, the
> canonical roadmap wins.
>
> This doc is preserved as a flat sequence view for "what M number
> falls where in execution order across arcs." It is NOT the authority
> on the active milestone, gate state, or current-state language. The
> 2026-05-11 audit reset the active pointer to M19; canonical
> ROADMAP.md reflects that.

This doc answers: **what's the flat sequence of M numbers across arcs?**

It does NOT define scope (per-arc docs do that) and it does NOT define
current state (ROADMAP.md does that). Purely the M ordering when
multiple arcs interleave.

## The shape of the long-term plan

```
M14-M18  ─►  M19-M24  ─►  Atmosphere arc  ─►  Sky arc  ─►  Water arc  ─►  Weather arc  ─►  Conformance close
(active)     (committed)  (post-M24)         (post-A5)    (post-S5)     (post-W6)        (post-WX-13)
```

Conformance work runs **continuously** during arcs (each arc has a
final-conformance M); the Conformance arc proper closes everything out
at the end.

## Why this order

Per [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md)
dependency graph:

1. **Atmosphere first** — shared dependency for Sky + Weather; building it first means both build on a stable base
2. **Sky second** — cheap, isolated, gives early visible momentum; depends only on Atmosphere
3. **Water third** — depends on Terrain (erosion) + Atmosphere (mist coupling); benefits from Atmosphere being ready
4. **Weather fourth** — heaviest arc; couples to all three above; built on solid foundation
5. **Conformance close** — formalizes per-release validation once all arcs ship

## Active and near-term (M14-M24)

These were planned before this restructure. M-numbers stay; scope lives
in existing per-arc roadmaps.

### M14-M18 (Post-Parity)
M18 workflow-closed / visually conditional as of 2026-05-11
([`WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`](WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md)).
**Active pointer is now M19**, per
[`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md).

| M | Arc | Scope |
|---|---|---|
| M13 | Conformance & Gates | Production promotion gate (active, ongoing) |
| M14 | Material Catalog | Close-play terrain quality (conditional; FLUX 2 bakeoff staged, no winner yet) |
| M15 | Scatter & Features | Production scatter + feature layers (workflow pass; placeholder assets) |
| M16 | Conformance & Gates | Bulk region/gallery source-stack retrofit (workflow pass; iso sidecar) |
| M17 | Terrain Foundation | Real-data-guided procedural extraction (workflow pass; one proof) |
| M18 | All | Playable representative slice (workflow-closed / visually conditional) |

### M19-M24 (Hybrid Procedural)
Planned. Per [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md).

| M | Arc | Scope |
|---|---|---|
| M19 | Terrain Foundation | Corpus statistical analysis |
| M20 | Terrain Foundation | Erosion sim backbone (Landlab) |
| M21 | Terrain Foundation | Procedural neighbor streaming contract |
| M22 | Terrain Foundation | Real-DEM patch seeding |
| M23 | Terrain Foundation | Infinite streaming director |
| M24 | Terrain Foundation + Material Catalog | Style packs + playable infinite slice |

## Long-term sequence (post-M24)

**M-numbers below are restructured from the prior M25-M39 framing into
right-sized arc-internal Ms.** The flat sequence is purely ordering;
scope lives in arc docs.

### Atmosphere arc (A1-A5)
Runs first. ~5-15 sessions. [`ATMOSPHERE_ARC_2026_05_10.md`](ATMOSPHERE_ARC_2026_05_10.md).

| Sequence | Arc-M | Scope |
|---|---|---|
| 25 | A1 | Climate classification per region |
| 26 | A2 | Atmospheric color LUT (data only) |
| 27 | A3 | Reference atmospheric color shader |
| 28 | A4 | Atmospheric volumetrics data |
| 29 | A5 | Reference volumetric fog shader + conformance |

### Sky arc (S1-S5)
Runs second. ~5-15 sessions. [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md).

| Sequence | Arc-M | Scope |
|---|---|---|
| 30 | S1 | Stellar statistics extraction (HYG/AT-HYG) |
| 31 | S2 | Procedural starfield generator + reference shader |
| 32 | S3 | Sun + moon + planets manifest + shader |
| 33 | S4 | Milky way band + per-region orientation |
| 34 | S5 | Aurora (polar) + conformance |

### Water arc (W1-W6)
Runs third. ~6-18 sessions. [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md).

| Sequence | Arc-M | Scope |
|---|---|---|
| 35 | W1 | Drainage network extraction from erosion |
| 36 | W2 | Lake / pond detection |
| 37 | W3 | Ocean / coastal extension |
| 38 | W4 | Water type classification + flow direction |
| 39 | W5 | Water-aware scatter integration |
| 40 | W6 | Per-mode water materials + shaders + conformance |

### Weather arc (WX-1 through WX-13)
Runs fourth. ~13-39 sessions. [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md).

Largest single arc. Reference shader work + surface variant generation
across the catalog push upper bound.

| Sequence | Arc-M | Scope |
|---|---|---|
| 41 | WX-1 | Cloud-class statistics extraction (Track D1) |
| 42 | WX-2 | Per-climate cloud-type distribution |
| 43 | WX-3 | Reference volumetric cloud shader |
| 44 | WX-4 | Cloud × sky compositing rules |
| 45 | WX-5 | Precipitation manifest generator |
| 46 | WX-6 | Reference precipitation particle systems |
| 47 | WX-7 | Surface response: wet variants for catalog |
| 48 | WX-8 | Surface response: snow + ice variants |
| 49 | WX-9 | Surface response: mud + accumulation thresholds |
| 50 | WX-10 | Wind field + vegetation response data |
| 51 | WX-11 | Reference vegetation sway shader |
| 52 | WX-12 | Weather state machine manifest |
| 53 | WX-13 | Weather conformance + on/off equivalence |

### Conformance arc (C1-C4)
Closes the long-term plan. ~4-12 sessions. [`CONFORMANCE_ARC_2026_05_10.md`](CONFORMANCE_ARC_2026_05_10.md).

C4 runs continuously throughout; C1-C3 formalize at the end.

| Sequence | Arc-M | Scope |
|---|---|---|
| (ongoing) | C4 | Long-term conformance hygiene |
| 54 | C1 | Conformance scene library audit |
| 55 | C2 | Scripted bundle-validation runner |
| 56 | C3 | Per-release conformance report format |

At M56 (C3) close, world3 hits all six completion-bar conditions per
[`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md).

## How arc-internal Ms relate to old M-numbers

For navigating prior docs:

| Old M-number | New arc-M | Why renamed |
|---|---|---|
| M25-M30 (water track) | W1-W6 | Same scope; arc-named |
| M31 (climate class) | A1 | Was inside weather; moved to atmosphere arc |
| M32 (atmospheric color) | A2-A3 (split) | Was one M; split into data + shader |
| M33 (volumetric clouds) | WX-1, WX-2, WX-3, WX-4 (split into 4) | Was over-scoped; split into nebula-statistics, distribution, shader, compositing |
| M34 (precipitation) | WX-5, WX-6 (split) | Was one M; split into manifest + particle systems |
| M35 (surface response) | WX-7, WX-8, WX-9 (split into 3) | Was over-scoped — touched whole catalog in one M; split into wet, snow+ice, mud |
| M36 (vegetation response) | WX-10, WX-11 (split) | Was one M; split into data + shader |
| M37 (atmospheric volumetrics) | A4-A5 (split) | Was inside weather; moved to atmosphere arc, split into data + shader |
| M38 (state transitions) | WX-12 | Same scope, renamed |
| M39 (conformance + on/off) | WX-13 | Same scope, renamed |

The old `M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md` doc remains as
historical context but the **arc docs are now canonical**.

## Total scope

Across all post-M24 arcs:

- Atmosphere arc: 5 Ms / ~5-15 sessions
- Sky arc: 5 Ms / ~5-15 sessions
- Water arc: 6 Ms / ~6-18 sessions
- Weather arc: 13 Ms / ~13-39 sessions
- Conformance arc: 4 Ms / ~4-12 sessions

**Total post-M24 long-term work**: 33 right-sized Ms / ~33-99 sessions
/ ~6-20 months at current cadence.

Add M14-M24 (active + planned, ~20-30 sessions) → entire long-term
plan is ~53-129 sessions / ~10-26 months.

Previous estimate (M14-M39 in oversized Ms) was 55-80 sessions; the
right-sized split increases the *count* of Ms but the *total scope is
the same*. Smaller chunks just mean more review points, less risk per
M, easier handoff between sessions.

## Operability gaps (reaudit-gated, not in this sequence)

Separately from the content arcs above, several **operability gaps**
have been identified that affect "fast pipeline" goals more than
"content correctness" goals. See
[`WORLD3_OPERABILITY_GAPS_2026_05_10.md`](WORLD3_OPERABILITY_GAPS_2026_05_10.md).

Headline gaps:
- No single "make a region" command (G1)
- No declarative `region_request.json` schema (G2)
- Style packs unspecified (G3)
- No batch / overnight region generator (G12)

Sketched **Orchestration arc** (O1-O10) addresses most. **Promotion
deferred to M18 reaudit.** If promoted, runs in parallel with content
arcs since the runnable pipeline benefits every arc once it exists.

## Reviewing this timeline

This doc will get **stale** as work progresses. Specifically:

- M14-M18 progress shifts the "Active" pointer
- New arcs may surface (or be promoted from Tracks) and need slots
- M18 reaudit may rename/split/merge arcs entirely
- Specific sequence-numbers (25, 26, ...) are placeholders; final
  M-numbers assigned at promotion time

**Reaudit gate**: when M18 closes, this doc gets a full re-pass
alongside [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md).

## Cross-references

- Architecture (modules + dependency graph): [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md)
- Completion bar: [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md)
- Output contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- Executive summary: [`WORLD3_EXEC_SUMMARY_2026_05_10.md`](WORLD3_EXEC_SUMMARY_2026_05_10.md)
- Active milestone: [`M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`](M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md)
- Per-arc docs:
  - [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md) (M14-M18)
  - [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md) (M19-M24)
  - [`ATMOSPHERE_ARC_2026_05_10.md`](ATMOSPHERE_ARC_2026_05_10.md) (A1-A5)
  - [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md) (S1-S5)
  - [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md) (W1-W6)
  - [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md) (WX-1 to WX-13)
  - [`CONFORMANCE_ARC_2026_05_10.md`](CONFORMANCE_ARC_2026_05_10.md) (C1-C4)
- Historical (superseded by arc docs but kept for reference): [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md)
- Queued options: [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md), [`FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md)
