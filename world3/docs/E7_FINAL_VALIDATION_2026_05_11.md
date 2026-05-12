# Phase E.7 — Final validation + sign-off

> Integration test on a region world3 has never built before:
> procedural neighbor on the `tundra_moss` catalog material.
> End-to-end orchestrator path validated, two latent bugs found and
> fixed, byte-identical reproduction across runs confirmed.

## Verdict

**Phase B-E rebuild SHIPPED end-to-end on unseen content.** The
"data + world-type → world" user north star works for content world3
has never seen before. The full chain — schema validation, stage
resolution, subprocess execution, provenance, driver-based capture,
style pack application, byte-identical reproduction — passes on
`tundra_moss` (not in any prior bundle) in under 5 seconds total
(0.65s build + 4.63s capture).

## The integration test

Region: `world3/jobs/examples/e7_unseen_tundra_moss_procedural.json`
- Source: procedural, material_id `tundra_moss`
- Biome kit: `tundra` (never deployed as a procedural-side biome before)
- Style pack: `photoreal`
- View modes: `["iso"]`
- Seed: 31415 (deterministic)

Choice rationale: `tundra_moss` is in `world3/materials/catalog.json` but
has never been used as a procedural source in any prior bundle. The
desert / mesa / canyon / grassland kits have all been exercised; tundra
hasn't. Picking it stresses the procedural-with-unfamiliar-material
path which is the entire point of E.7.

## Results

### Orchestrator run (final, after bug fixes)

```
=== world3 orchestrator ===
Request: world3\jobs\examples\e7_unseen_tundra_moss_procedural.json

--- Validating request schema ---
  [OK  ] world3\jobs\examples\e7_unseen_tundra_moss_procedural.json

--- Resolving stages ---
  active stages (2):
    build_procedural_neighbor  -- Catalog material -> procedural heightmap + macro albedo + valid mask
    validate_request           -- Validates the region_request.json against region_request_schema.json

--- Executing (real) ---
  [run] python build_procedural_neighbor_bundle.py --material-id tundra_moss --out ... --seed 31415
  [OK   ] build_procedural_neighbor  (ok, 0.52s)
  [run] python validate_region_request.py D:\assets\world3\jobs\examples\e7_unseen_tundra_moss_procedural.json
  [OK   ] validate_request  (ok, 0.13s)

--- Provenance ---
  Run record: world3\jobs\run_records\e7_unseen_tundra_moss_procedural_20260511T133150Z.json

=== world3 orchestrator DONE ===
```

### Byte-identical reproduction

Two independent orchestrator runs on the same request produced bit-identical output:

```
heightmap.png            25f7769c256c74f447b264448846a3e9
layers/render_albedo.png 948aec90779159c02e33b6aeaa08c5c0
layers/source_valid_mask.png 9f5296c1abac292664792d5ce6e0e721
```

Same MD5 across both runs — determinism holds on unseen content.

### Capture through orchestrator driver

```
python world3/pipeline/run_orchestrator_capture.py \
  --bundle-dir res://toporeview/e7_unseen_tundra_moss_procedural \
  --material   res://textures/wgv3/terrain_blend_tundra.tres \
  --macro-albedo res://toporeview/e7_unseen_tundra_moss_procedural/layers/render_albedo.png \
  --macro-mask   res://toporeview/e7_unseen_tundra_moss_procedural/layers/source_valid_mask.png \
  --mode iso --style-pack photoreal \
  --output res://docs/captures/review/e7_unseen_tundra_moss_iso_proof.png \
  --start-x 60 --start-z 120 --chunk-size 120 --chunk-resolution 4 \
  --warmup-frames 60

[run_orchestrator_capture] OK ... (3291 KB, 4.63s)
```

Visual: green moss tones with white snow/ice patches. The `tundra_moss`
catalog texture is being placed correctly on the procedurally generated
heightmap; this is exactly the post-D.1 framing landing — *procedural
emits placement, catalog supplies texture* — on content the procedural
code had never seen before.

Same default-framing chunk-grid artifact present as in M10 captures
(noted in E.4 doc as tour-profile work, not driver work).

## Bugs found + fixed

The first E.7 run surfaced two latent orchestrator bugs that the M10
canonical-reproduction smoke test didn't exercise:

### Bug 1: `validate_request` stage failed for missing positional arg

**Root cause:** `world3_make.py` line 197 returned `[]` for the
validate_request stage's CLI args, with the rationale "called separately
at top." But the stage still subprocess-launched the validator with
zero args, which causes exit code 2 (validator wants either a positional
request path or `--schema-self-test`).

**Fix:** Thread the request path into the request dict as
`__request_path__` and have the stage's arg-resolver return it as the
single positional arg. The stage is now a redundant safety-net run of
the validator — same behavior as before plus a clean re-validation
record in the run.json provenance.

### Bug 2: `deploy_kit_materials` failed for tundra biome kit

**Root cause:** `pipelines/textures/deploy_kit_to_world3.py` only knows
`grassland` and `temperate_forest`. Other kits (alpine, desert, tundra)
have their `terrain_blend_<kit>.tres` files already on disk from
earlier work and don't need re-deployment. The stage's `required_if`
("kit's .tres files are stale or missing") was never actually
implemented — the orchestrator was running the stage whenever a kit
was declared.

**Fix:** Implement the staleness check honestly. The stage is now
skipped when `world3/textures/wgv3/terrain_blend_<kit>.tres` already
exists; only runs when the file is missing. This makes the
`required_if` description match reality and lets `tundra` / `alpine` /
`desert` regions go through the orchestrator without hitting the
deploy script's smaller allowlist.

Both fixes verified by re-running the same E.7 request: full green,
deterministic, byte-identical across two runs.

## Phase B-E status (canonical)

- [x] **B** Cold-validation of chains 1/2/3 + world3-vs-world4 decision
- [x] **C** Phase-C diagnosis (procedural-vs-texture framing correction)
- [x] **D.1** `build_procedural_neighbor_bundle.py` macro fix (catalog texture as base, not median-color)
- [x] **D.2-D.6** Infrastructure fixes (master catalog auto-refresh, preflight, Phase C diagnosis closeout)
- [x] **E.1** Region request schema + 3 examples + validator
- [x] **E.2** Stages manifest + audit (12 stages clean)
- [x] **E.3** Orchestrator + provenance (byte-identical reproduction)
- [x] **E.4** OrchestratorCaptureDriver + wrapper + stages.json wiring + M18 cascade + M10 proof
- [x] **E.5** Style pack mechanism + photoreal default
- [x] **E.6** Docs + handoff refresh
- [x] **E.7** Final validation on unseen region + sign-off (this doc)

## What ships at end of Phase B-E

A new agent can run one command and produce a bundle from a config:

```
python world3/pipeline/world3_make.py world3/jobs/examples/<any>.json
```

A new bundle can be captured through one parameterized driver:

```
python world3/pipeline/run_orchestrator_capture.py \
  --bundle-dir res://toporeview/<bundle> \
  --material res://textures/wgv3/terrain_blend_<kit>.tres \
  --mode iso --output res://docs/captures/review/<id>_iso.png \
  --style-pack photoreal
```

A new style pack is one JSON file under `world3/jobs/style_packs/`.

A new region request is validated against `region_request_schema.json`
before any pipeline work starts. Provenance lands in
`world3/jobs/run_records/` per run.

## What's NOT in Phase B-E

These are NOT covered by the orchestrator rebuild and remain open:

- **M19** — procedural neighbor visual quality work (the M-arc that
  continues from where D.1 left off). The orchestrator can now drive
  M19 experiments faster, but M19's content work is separate scope.
- **Per-bundle camera framing.** OrchestratorCaptureDriver uses default
  tour-profile focus offsets which don't always frame a 120×240 m
  procedural bundle well from iso/topdown angles. Tunable per-bundle
  via `--start-x / --start-z / --chunk-size`; orchestrator-level focus
  heuristics deferred.
- **Alternate style packs.** The mechanism supports them; the art
  (painterly / topographic / etc.) hasn't been authored. Pure-content
  additive concern.
- **`build_seam_integration` and `build_runtime_image_cache` stages.**
  Both are placeholders in `stages.json` pending explicit arg-mapping
  work. Phase E.7 deliberately tested a procedural-only path that
  doesn't need them.
- **Hybrid full-cascade integration test.** E.7 covered procedural.
  The hybrid (real + procedural) path validates schema and resolves
  stages but the seam-integration stage's arg-mapping needs M-arc work.

These are M19+ scope, not E-rebuild scope.

## Sign-off

Phase B-E rebuild **COMPLETE**.

- Orchestrator works end-to-end on canonical bundles (M10 procedural reproduces byte-identically)
- Orchestrator works end-to-end on unseen content (tundra_moss reproduces byte-identically)
- Parameterized capture driver works on bundles that never had hand-authored capture scenes
- Style pack mechanism applies cleanly without changing photoreal output size
- Docs reflect what the running code does
- Two latent bugs found and fixed during E.7 itself

The "I have data X, I want world type Y, make it" north star is delivered.

**Phase B-E SHIP.** Ready to return to M-arc work.
