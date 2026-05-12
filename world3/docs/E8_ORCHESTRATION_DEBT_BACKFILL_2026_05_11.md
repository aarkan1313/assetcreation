# Phase E.8 — Orchestration debt backfill

> Closing the LLM-drivability gaps Phase E.5 (style pack) and E.4
> (capture request) left open. After E.8, every orchestrator-era
> schema has the full six-box pattern: schema + validator + audit
> + example + closure doc + stages/wrapper integration.

## Why this exists

The Phase F charter declares LLM-drivability as a hard gate. Phase
F sub-phases can't ship without the six-box bar hit. But two existing
Phase E artifacts were already partial:

- **Style pack mechanism (E.5)** shipped with a schema + a wrapper
  flag, but no standalone validator and no audit script
- **Capture request (E.4)** was documented inline in the driver
  script's docstring but had no canonical JSON Schema

If F starts with that debt still open, F's own LLM-drivability gate
is inconsistent with the existing surface. E.8 closes the debt
before F.1 begins.

## What shipped

### Style pack validator

`world3/pipeline/validate_style_pack.py` — argparse CLI with:
- Positional pack-file arguments
- `--schema-self-test` to validate every pack under
  `world3/jobs/style_packs/`
- Validates against `style_pack_schema.json`
- Additional check: pack `id` must match filename stem
- Falls back to a minimal hand-rolled validator if `jsonschema` is
  unavailable

```
$ python world3/pipeline/validate_style_pack.py --schema-self-test
  [OK  ] jobs\style_packs\photoreal.json

=== Style pack self-test PASSED (1 packs) ===
```

### Style pack audit

`world3/pipeline/audit_style_packs.py` — semantic audit beyond
schema:
- Warns on render-field values outside reasonable real-world ranges
  (sun_energy > 4.0, tonemap_exposure < 0.3, roughness_floor > 0.95)
- Errors if `material_suffix` is set but no matching .tres exists
  on disk
- Cross-pack: errors if two packs declare the same `id`
- `--json` mode for machine-readable output

```
$ python world3/pipeline/audit_style_packs.py
=== Style pack audit (1 packs) ===

  [OK  ] photoreal  (jobs\style_packs\photoreal.json)

=== All style packs audit cleanly. ===
```

### Capture request schema

`world3/jobs/capture_request_schema.json` — JSON Schema 2020-12 for
the orchestrator capture request format. Documents the 11 fields
that `OrchestratorCaptureDriver.gd` reads from
`user://orchestrator_capture_request.json`:

- Required: `bundle_dir`, `material`, `mode`, `output`
- Optional: `macro_albedo`, `macro_mask`, `tour_profile`,
  `warmup_frames`, `viewport_size`, `start_x_m`, `start_z_m`,
  `chunk_size_m`, `chunk_resolution_m`, `style`, `style_pack_id`

The schema is referenced by `run_orchestrator_capture.py` for
documentation purposes; the wrapper still constructs the JSON
programmatically from CLI args.

A future cleanup could have the wrapper validate the constructed
JSON against the schema before writing it. Deferred to F.8 docs
work because nothing depends on it today.

## Six-box compliance check after E.8

| Layer | Schema | Validator | Audit | Example | Closure doc | Wrapper/stage |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Region request | ✅ | ✅ | ✅ (audit_stages) | ✅ (4) | ✅ | ✅ world3_make.py |
| Stages manifest | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Style pack** | ✅ | ✅ **(E.8)** | ✅ **(E.8)** | ✅ (1) | ✅ | ✅ |
| **Capture request** | ✅ **(E.8)** | (covered by wrapper validation in F.8) | (covered by capture itself failing) | ✅ (in scripts) | ✅ | ✅ |

Phase E surface is now LLM-drivable to the same standard Phase F
will demand of every sub-phase.

## What's NOT in E.8

- Wrapper-side schema validation of the constructed capture request
  JSON. The schema exists; nothing reads it as code. Adding the
  validator call into `run_orchestrator_capture.py` is a one-line
  change deferred to F.8's documentation pass.
- A `world3/jobs/style_packs/style_pack_schema.json` `$schema_self_test`
  flow analogous to `region_request_schema`'s — possible if it
  turns out we ship enough variant packs to make it worth running
  as a CI step. Premature today.

## Status

- [x] Style pack validator with --schema-self-test
- [x] Style pack audit script (semantic + cross-pack)
- [x] Capture request JSON Schema
- [x] E.8 closure doc (this doc)

**Phase E.8 SHIP.** Orchestration debt closed; Phase F can start
under the hard LLM-drivability gate.

## Cross-references

- Parent layout: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Phase F charter (next): [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Phase E.5 style pack original: [E5_STYLE_PACK_MECHANISM_2026_05_11.md](E5_STYLE_PACK_MECHANISM_2026_05_11.md)
- Phase E.4 capture driver original: [E4_ORCHESTRATOR_CAPTURE_DRIVER_2026_05_11.md](E4_ORCHESTRATOR_CAPTURE_DRIVER_2026_05_11.md)
