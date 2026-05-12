# Conformance Arc

Date: 2026-05-10

The Conformance & Gates module is **cross-cutting infrastructure** —
not content, but the spine that validates everything else. Covers the
M13 promotion gate, conformance scene library, contract validation
tools, and per-release audit reports.

This arc runs **continuously throughout** the post-M24 sequence. Some
work happens as part of M14-M18 closure; the formalization steps run
**last** in the long-term plan per
[`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md) — after every
other arc lands content, conformance closes by validating it all.

## What it produces

Tools + per-release artifacts, not content bundle entries:

```
world3/
├── jobs/production_promotion_candidates.json   ← M13 gate manifest (exists)
├── pipeline/audit_production_promotion_candidates.py  ← M13 audit tool (exists)
├── pipeline/conformance_runner.py              ← NEW (C2)
├── docs/CONFORMANCE_REPORT_<version>.md        ← NEW (C3, per-release)
└── scenes/conformance/                          ← NEW (C1)
    ├── terrain/
    ├── water/
    ├── atmosphere/
    ├── sky/
    ├── weather/
    └── full_stack/
```

## What it depends on

- Every other arc — Conformance validates content from all of them
- Existing M13 gate work (`production_promotion_candidates.json` +
  `audit_production_promotion_candidates.py`)

## What depends on it

- World3 completion bar — condition 6 ("Conformance suite renders every bundle") is owned by this arc

## Right-sized Ms

Smaller arc; the major work happens as Ms in other arcs (each arc's
final M includes its conformance scenes). This arc **formalizes** and
**closes**.

### C1 — Conformance scene library audit

**Goal**: inventory existing review scenes; classify by module + mode + state coverage; identify gaps.

Inputs:
- Existing `world3/scenes/review/` and `world3/scenes/capture_*` scenes
- Per-arc conformance scenes from Atmosphere, Sky, Water, Weather arcs

Deliverables:
- `world3/docs/CONFORMANCE_SCENE_INVENTORY_<date>.md` — full inventory
- `world3/scenes/conformance/` directory structure created
- Migration plan: which existing scenes promote to canonical conformance, which retire as diagnostic-only

Exit:
- Every (module × mode × state) cell has either a conformance scene or an open ticket
- No duplicate scenes covering the same cell
- Clear separation of "diagnostic / engineering" scenes from "canonical conformance" scenes

### C2 — Scripted bundle-validation runner

**Goal**: programmatic conformance runner that loads any bundle, renders all conformance scenes, reports pass/fail.

Inputs:
- C1 inventory
- Bundle layout per `WORLD3_CONTRACT_2026_05_10.md`

Deliverables:
- `world3/pipeline/conformance_runner.py` — loads bundle, validates contract files present + valid, renders canonical conformance scenes, computes per-scene pass/fail
- Failure mode catalog (missing valid mask, splat manifest references unknown catalog id, water_height NaN, etc.)
- Per-failure recovery documentation

Exit:
- Runner validates every cached bundle without false positives
- Failure modes correctly categorized + recovery documented
- Runner output is machine-readable (JSON report) for downstream automation

### C3 — Per-release conformance report format

**Goal**: per-release artifact "world3 v0.X.Y conformance report" that proves a build is shippable.

Inputs:
- C2 runner
- M13 gate state (`production_promotion_candidates.json`)

Deliverables:
- `world3/docs/CONFORMANCE_REPORT_<version>.md` template
- Reproducible "run conformance" entry point in world3 toolchain
- Documentation: how to generate, what passing looks like, what failing looks like
- Optional CI hook for conformance regression detection

Exit:
- First conformance report generated for current build
- Process documented + reproducible

### C4 — Long-term conformance hygiene

**Goal**: ongoing conformance work as new arcs ship; ensure every new module's M-final-conformance scenes hook into the runner.

Inputs:
- Every shipping arc's final-conformance M (A5, S5, W6, WX-13)
- Existing C1-C3 infrastructure

Deliverables:
- Per-arc-completion review: are new conformance scenes integrated?
- Conformance runner updated for each new arc
- Cumulative `CONFORMANCE_REPORT` includes all arcs

Exit:
- Conformance suite renders every bundle from every arc
- World3 hits the 6th completion-bar condition

## Exit criteria (whole arc)

- Conformance scene inventory clean (no gaps, no duplicates)
- Scripted runner validates bundles end-to-end
- Per-release conformance report ships with each build
- Every arc's M-final-conformance scenes hook into the runner
- World3 hits completion-bar condition 6

## Risks

- **R1 — Conformance scope creeps as new arcs ship.** Each arc adds scenes; runner must handle them. Mitigation: C4 ongoing work; per-arc-completion review prevents drift.
- **R2 — Conformance runner becomes a bottleneck.** If rendering all scenes for every bundle takes hours, conformance becomes per-release not per-commit. Mitigation: C2 includes performance budget; "minimal conformance" subset for fast iteration vs "full conformance" for releases.
- **R3 — Conformance scenes age out as modules evolve.** Mitigation: scenes versioned alongside `generator_version`; regen at version bumps.

## Estimated effort

4 Ms × 1-3 sessions each = ~4-12 sessions / ~1-3 months.

Smaller arc. C1-C3 happen near end of long-term plan; C4 is ongoing
hygiene that runs continuously.

## Cross-references

- Output contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- Completion bar: [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md) condition 6
- Architecture: [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md) Module 9
- M-sequence timeline: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md)
- M13 gate (active): `world3/jobs/production_promotion_candidates.json`, `world3/pipeline/audit_production_promotion_candidates.py`
- Sister arcs (validated by conformance): [`ATMOSPHERE_ARC_2026_05_10.md`](ATMOSPHERE_ARC_2026_05_10.md), [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md), [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md), [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md)
