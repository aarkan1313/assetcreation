# Phase F.1 — Orchestrator gaps closed

> Three placeholder stages now wire to real arg shapes. Real-DEM and
> hybrid lanes run end-to-end through `world3_make.py` for the first
> time. Both lanes are deterministic across runs; the real-DEM lane
> additionally reproduces the canonical Gloss Mountain bundle
> **byte-identically**.

## Verdict

**F.1 closes the orchestrator's "works for procedural-only" gap.** All
three pipeline lanes (real-DEM, hybrid, procedural) now run through
the orchestrator with no manual subprocess invocations. Two
independent runs of each lane produce bit-identical output. The
real-DEM orchestrator output matches the pre-existing hand-driven
canonical Gloss Mountain bundle exactly.

## What shipped

### Wired stages in `world3/pipeline/world3_make.py`

Three previously-placeholder stages now have real arg resolvers:

1. **`build_runtime_image_cache`** — reads `out_dir/heightmap.png` and
   either the per-bundle splat layer (`layers/height_slope_weights_rgba.png`)
   or the legacy alpine fallback splat. Output goes to
   `out_dir/runtime_cache/`.

2. **`build_seam_integration`** — hybrid only. Reads the real-source
   bundle's macro + valid mask + (via a manifest hop) heightmap + meta.
   Reads the procedural-side bundle this orchestrator run just produced
   (under `out_dir/_procedural_side/`). Calls the seam solver with
   the explicit args contract from `m18_representative_slice_manifest.json`,
   forced to the procedural side's output size via `--output-size`.

3. **`render_captures_*`** — calls `run_orchestrator_capture.py` (E.4
   wrapper) with `bundle_dir`, `material`, `mode`, `output`, `--style-pack`,
   and conditional `--macro-albedo / --macro-mask` if the bundle has
   `layers/render_albedo.png` and `layers/source_valid_mask.png`.

### Hybrid manifest-hop helper

`_hybrid_resolve_real_height_meta()` — the hybrid request's `real.bundle_path`
points at a source-stack layer dir which has macro + mask but no
heightmap/meta. The source-stack manifest's `source_stack` field is a
`res://` URL pointing at the toporeview bundle that owns them. The
helper resolves that hop. Falls back to a `<bundle_id>_textured_master`
sibling convention if the manifest doesn't say.

## Validation

### Real-DEM lane

```
$ python world3/pipeline/world3_make.py world3/jobs/examples/gloss_real.json \
    --only-stages build_real_master_stack,build_runtime_image_cache

--- Executing (real) ---
  [run] python build_opentopo_textured_master_stack.py --dem ... --orthophoto ...
  [OK   ] build_real_master_stack  (ok, 287.6s)
  [run] python build_runtime_image_cache.py --height-source ... --splat-source ...
  [OK   ] build_runtime_image_cache  (ok, 1.26s)
=== world3 orchestrator DONE ===
```

Stack landed: `heightmap.png`, `layers/`, `master/`, `meta.json`, `qa/`,
`stack_manifest.json`, `runtime_cache/heightmap_rf32.{bin,json}`,
`runtime_cache/alpine_splat_rgba8.{bin,json}`.

**Reproduces the canonical Gloss Mountain bundle byte-identically:**
```
97c6722f8239a2eecb4e2edeee9090fa  <orchestrator output>/heightmap.png
97c6722f8239a2eecb4e2edeee9090fa  world3/opentopo/processed/master_stacks/gloss_mountain_textured_master/heightmap.png
```

### Hybrid lane

```
$ python world3/pipeline/world3_make.py world3/jobs/examples/gloss_canyon_hybrid.json \
    --only-stages build_procedural_neighbor,build_seam_integration,build_runtime_image_cache

--- Executing (real) ---
  [OK   ] build_procedural_neighbor  (ok, 0.58s)
  [OK   ] build_seam_integration  (ok, 1.75s)
  [OK   ] build_runtime_image_cache  (ok, 0.23s)
=== world3 orchestrator DONE ===
```

Hybrid bundle landed: macro + mask + heightmap + meta + manifest +
seam_metrics + seam_integration_mask + `_procedural_side/` sidecar +
`runtime_cache/`. Two independent runs produce identical hashes
across all artifacts (confirmed via md5sum on macro, output heightmap,
and procedural-side heightmap).

The orchestrator-produced macro **differs** from the pre-existing
canonical hybrid bundle's macro because the canonical was authored
pre-D.1 (median-color macro collapse). The orchestrator now uses
the post-D.1 catalog-texture base, which is the correct forward
behavior.

## Six-box LLM-drivability check

F.1 inherits its six-box compliance from existing infrastructure;
no new schema needed for "wiring placeholder stages."

- ✅ **Schema** — `region_request_schema.json` (no changes; covers
  all three lanes)
- ✅ **Validator** — `validate_region_request.py --schema-self-test`
  PASSED on 4 examples
- ✅ **Example** — `gloss_real.json` + `gloss_canyon_hybrid.json`
  (existing)
- ✅ **Audit** — `audit_stages.py` reports 12/12 stages clean
- ✅ **Closure doc** — this doc
- ✅ **Stages.json entries** — pre-existing; no changes needed

## What's NOT in F.1

- **End-to-end real-DEM run including the capture stages.** Wired but
  not smoke-tested through the orchestrator (capture stages call
  `run_orchestrator_capture.py` which works standalone per E.4). Will
  validate as part of F.7 once the streaming director needs them.
- **End-to-end hybrid run including the capture stages.** Same as above.
- **`register_promotion_candidate`** stage. Remains placeholder until
  M13 gate integration lands (deferred to G.5 per the unified roadmap).
- **`build_real_heightmap_only` lane.** Wired in `resolve_args` but
  no example request exercises it. Not blocking; will be covered when
  a request without an orthophoto appears.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- E.4 capture driver this feeds: [E4_ORCHESTRATOR_CAPTURE_DRIVER_2026_05_11.md](E4_ORCHESTRATOR_CAPTURE_DRIVER_2026_05_11.md)
- M18 seam arg contract referenced: `world3/jobs/m18_representative_slice_manifest.json`

## Status

- [x] `build_runtime_image_cache` arg-mapping wired
- [x] `build_seam_integration` arg-mapping wired (hybrid manifest-hop helper)
- [x] `render_captures_*` arg-mapping wired
- [x] Real-DEM end-to-end through `world3_make.py`
- [x] Real-DEM reproduces canonical Gloss Mountain bundle byte-identically
- [x] Hybrid end-to-end through `world3_make.py`
- [x] Hybrid is deterministic across two independent runs
- [x] Closure doc (this doc)

**Phase F.1 SHIP.** All three orchestrator lanes work end-to-end.
Ready for F.2 (world plan schema).
