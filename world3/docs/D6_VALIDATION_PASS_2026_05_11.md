# D.6 — Phase D Validation Pass

> Final step of Phase D rebuild. Re-runs the Phase B cold-validations
> against the patched code to confirm Phase D didn't break determinism
> on unchanged chains, and to document the cascade of artifacts that
> need re-rendering as a follow-up.

## Verdict

**PASS for code-level determinism. Cascade work queued for Phase E
integration.**

- **Chain 1 (Real DEM → bundle)**: 18/18 files byte-identical
  reproduction after Phase D patches. Unchanged.
- **Chain 3 (Procedural neighbor)**: 3/3 binary files byte-identical
  across two re-runs with the new `build_macro()`. Deterministic.
- **M18 representative scene captures**: still show the pre-fix smooth
  tan/sand. **Re-render queued** as a Phase E.7 task (after orchestrator
  exists, all-modes render driver makes this one command instead of
  manually launching Godot).

## D.6.1 — Chain 1 byte-identical re-validation

Re-ran `build_opentopo_textured_master_stack.py` against Gloss Mountain
DEM + orthophoto with the same args from Phase B.1. Phase D didn't
touch this script, but it touched files in adjacent paths
(`pipelines/terrain/bulk_pull.py`, `pull_megastack_queue.py`) so
re-verifying determinism is honest hygiene.

- Wall time: 3 min 59.9 sec (≈ same as B.1's 3 min 59.8 sec)
- Exit: 0
- Same warning (NodataShadowWarning at line 132) — already documented
- Output: 18/18 files

**MD5 hash diff vs canonical**: every file identical. Worker
discipline on determinism remains exemplary across Phase D.

| File | MD5 match |
|---|---|
| `heightmap.png` | ✅ |
| `layers/*.png` (10 files) | ✅ all 10 |
| `master/*.tif` (4 files) | ✅ all 4 |
| `meta.json` | ✅ |
| `stack_manifest.json` | ✅ |
| `qa/textured_master_report.json` | ✅ |

## D.6.2 — Chain 3 determinism with new `build_macro()`

Re-ran `build_procedural_neighbor_bundle.py` with same args as B.3.
Compared against the in-place-regenerated M10 bundle
(`world3/toporeview/procedural_desert_canyon_rock_m10/`) produced as
part of D.1.

- Wall time: < 1 sec
- Exit: 0
- 3 of 4 binary files byte-identical (heightmap, render_albedo, valid mask)
- `meta.json` differs only in embedded path strings (the `--out` path
  was different); content otherwise identical

**MD5 hash diff vs in-place M10 bundle**:

| File | MD5 match |
|---|---|
| `heightmap.png` | ✅ |
| `layers/render_albedo.png` | ✅ |
| `layers/source_valid_mask.png` | ✅ |

Confirms the new `build_macro()` is fully deterministic: same seed +
same args + same catalog material → bit-exact output.

## D.6.3 — M18 capture cascade

The D.1 macro fix changes the byte-content of all downstream procedural
artifacts. Without re-rendering Godot scenes, captures referenced by
the M13 gate still show the pre-fix "broad smooth tan/sand" weakness.

### Affected captures

Located in `world3/docs/captures/review/`:

| File | Content | Status |
|---|---|---|
| `source_stack_m18_guided_neighbor_close.png` | M18 close band, real + procedural | shows pre-fix tan |
| `source_stack_m18_guided_neighbor_medium.png` | M18 medium band | shows pre-fix tan |
| `source_stack_m18_guided_neighbor_iso.png` | M18 iso band | shows pre-fix tan |
| `source_stack_m18_guided_neighbor_topdown.png` | M18 topdown band | shows pre-fix tan |
| `source_stack_m18_guided_neighbor_contact_sheet.png` | 4-band composite | shows pre-fix tan |
| `source_stack_m18_closure_review.png` | M18 closure picker grid | partially affected |
| `source_stack_real_procedural_tour_*.png` (4 bands) | M10 real-to-procedural tour | shows pre-fix tan on procedural side |
| `world3_m1_m18_audit_contact_sheet.png` | 2026-05-11 audit sheet | reference: shows the veto |

### Why not re-render now

Re-rendering each capture requires:
1. Launching Godot 4.5 manually with the specific scene path
2. Each scene runs ~10-30 seconds in non-headless mode
3. Coordinating 4 bands × multiple scenes = a focused 1-2 hour pass

This is **exactly what Phase E.4 (all-modes render driver) is supposed
to fix** — `python world3_make.py --bundle <path> --render-captures` runs
all bands automatically.

### When to re-render

**Option A**: as part of Phase E.4 implementation. Build the all-modes
driver, then use it to re-render the M18 cascade as its first real
integration test. Two birds, one stone.

**Option B**: in a focused 1-hour session before E.4. Open each scene
in Godot, render, save. Higher manual cost but unblocks visible-improvement
review sooner.

**Recommendation**: Option A. The macro fix is correct; the visible
quality improvement is documented in the D.1 comparison sheet; the
gate state can wait for the orchestrator's automated render to confirm
across all bands at once.

### M13 gate state during the cascade

The gate manifest at `world3/jobs/production_promotion_candidates.json`
contains two entries that reference now-stale captures:

- `m10_real_procedural_gloss_canyon` (state: `sidecar_candidate` —
  conditional)
- `m18_representative_slice_first_pass` (state: `ready_for_live_review`
  — conditional)

Both were already in conditional/sidecar states because of the
pre-fix veto. **Their gate state doesn't change** based on D.1; they
remain conditional pending live re-review of the new captures.

A note will land in the gate manifest during E.4 to mark the captures
as "pre-D1-fix; re-render pending E.4 orchestrator." That metadata
keeps the audit honest without claiming victory before the user has
seen the new captures.

## Phase D end-state

All Phase D items complete:

| Phase | Outcome |
|---|---|
| D.0 | `data_catalog.json` refreshed (657 DEMs, was 292) |
| D.1 | `build_macro()` tuned (v2: catalog texture as base + organic wash) |
| D.2 | `res_path()` crash fix |
| D.3 | Catalog auto-regen hook on `bulk_pull` + `pull_megastack_queue` |
| D.4 | `preflight.py` for textures pipeline prereqs |
| D.5 | `PIPELINE.md` updated + `README.md` stale-warning banner |
| D.6 | Phase B cold-validations re-run; Chain 1 + Chain 3 still byte-identical-deterministic |

**Bucket totals after Phase D**:
- A (trivial config): 0 (none surfaced)
- B (manual-step gaps): 5 → **all addressed** (3 closed by D.3/D.4/D.5; 2 documented as deferred to Phase E orchestrator coverage)
- C (real code bugs): 2 → **both fixed** (D.1 macro tune; D.2 path crash)
- D (architectural gaps): 2 → **handed to Phase E** (orchestrator + batch wrapper)

## What's deferred to Phase E

- E.4 re-renders the M18 + M10 procedural-side captures with the new
  build_macro
- E.6 updates `world3/docs/README.md` (currently has stale-warning
  banner only) and verifies/updates `WORKFLOW.md` against current
  pipeline reality
- E.7 final integration test uses M18 re-render as the proof that the
  orchestrator works

## What we know now that we didn't know at start of Phase B

1. **World3 stays.** Three independent chains tested showed exemplary
   determinism and worker discipline. No world4 case.
2. **The "smooth tan/sand" issue was one function.** Not a
   placement-vs-texture architectural confusion; a parameter choice in
   `build_macro()` that collapsed the catalog albedo to its median
   color and suppressed the texture under noise. Fixed in 30 lines.
3. **Texture pipeline operates correctly**, but assumes a running
   ComfyUI + a separately-installed mesa-env venv. Preflight surfaces
   the prereqs clearly.
4. **Catalog drift was real** — 365 DEMs stale for two days because
   `build_master_catalog.py` is a manual step. Post-hook closes that.
5. **The script catalog is the asset**. Phase B's byte-identical
   reproductions on real DEM build + procedural neighbor build prove
   the underlying scripts are valuable, deterministic, and worth
   building an orchestrator around — not throwing away.

## Cross-references

- Phase plan: [`REBUILD_PLAN_PHASES_B_E_2026_05_11.md`](REBUILD_PLAN_PHASES_B_E_2026_05_11.md)
- Phase B.1 (Chain 1 baseline): [`B1_CHAIN1_VALIDATION_2026_05_11.md`](B1_CHAIN1_VALIDATION_2026_05_11.md)
- Phase B.2 (texture partial): [`B2_CHAIN2_VALIDATION_2026_05_11.md`](B2_CHAIN2_VALIDATION_2026_05_11.md)
- Phase B.3 (procedural neighbor + root cause): [`B3_CHAIN3_VALIDATION_2026_05_11.md`](B3_CHAIN3_VALIDATION_2026_05_11.md)
- Phase C diagnosis: [`PHASE_C_DIAGNOSIS_2026_05_11.md`](PHASE_C_DIAGNOSIS_2026_05_11.md)
- Phase D.1 macro tune: [`D1_BUILD_MACRO_TUNE_2026_05_11.md`](D1_BUILD_MACRO_TUNE_2026_05_11.md)
- Phase D.3-D.5 infrastructure: [`D3_D5_INFRASTRUCTURE_FIXES_2026_05_11.md`](D3_D5_INFRASTRUCTURE_FIXES_2026_05_11.md)

## Phase D status

- [x] D.0 catalog regen
- [x] D.1 build_macro tune (v2, accepted)
- [x] D.2 res_path crash fix
- [x] D.3 catalog auto-regen hooks on bulk_pull + pull_megastack_queue
- [x] D.4 textures pipeline preflight script
- [x] D.5 PIPELINE.md + README.md updates
- [x] D.6 validation pass (Chain 1 + Chain 3 byte-identical)
- [ ] M18 cascade re-render (deferred to E.4)

**Phase D COMPLETE.** Ready for Phase E.
