# D.3 / D.4 / D.5 — Infrastructure Fixes

> Phase D.3 (catalog auto-regen hook), D.4 (textures preflight), and
> D.5 (venv + docs cleanup) consolidated. All three are small Bucket B
> fixes; each closes one operability gap from Phase B.

## D.3 — Catalog auto-regen hook

**Problem (Bucket B, B.1 finding follow-up)**: `data_catalog.json` went
stale at 292 DEMs after the 2026-05-09 mega-stack pull added 365 more.
The catalog refresh is a manual one-line command (`python
pipelines/terrain/build_master_catalog.py`) that operators were
expected to remember to run; it was forgotten for two days.

**Fix**: post-success hook on both `bulk_pull.py` and
`pull_megastack_queue.py`. After successful pulls, run
`build_master_catalog.py` automatically. Operators can opt out:
- `bulk_pull.py --no-catalog-refresh` (explicit flag)
- `WORLD3_NO_CATALOG_REFRESH=1` env var (for `pull_megastack_queue.py`)

**Behavior**: subprocess invocation, 60s timeout, surfaces last 12
lines of `build_master_catalog.py` output for visibility, warns on
failure (doesn't fail the parent pull).

**Verification**: both scripts import cleanly; `bulk_pull.py --help`
shows the new flag with explanatory text.

**Files patched**:
- `pipelines/terrain/bulk_pull.py` (added `--no-catalog-refresh` arg + `refresh_master_catalog()` helper + post-success call)
- `pipelines/terrain/pull_megastack_queue.py` (added env-var opt-out + `refresh_master_catalog()` helper + post-success call)

---

## D.4 — Textures pipeline preflight

**Problem (Bucket B, B.2 findings)**: `aaa_texture.py` assumes ComfyUI
is running at `127.0.0.1:8188`, the required model files are on disk,
and the StableMaterials backend is reachable via `animators/mesa-env/venv`.
None of this is checked before queuing work. Cold-start operators get
generic "connection refused" errors mid-flow.

**Fix**: new script `pipelines/textures/preflight.py` that probes every
prereq and prints clear, actionable errors per failure.

**Checks**:
1. Python modules (`numpy`, `PIL`, `requests`)
2. ComfyUI server health (HTTP probe to `/system_stats`)
3. FLUX 2 klein-4B model file on disk
4. StableMaterials backend (mesa-env venv has `diffusers`) — runs only when backend is `sm` or unspecified
5. ComfyUI-Chord custom node + chord_v1 model — runs only when backend is `chord` or `chord_sm_rough`
6. ComfyUI-GGUF custom node (needed for diversity_compare quants)

**Modes**:
- `python preflight.py` — human-friendly output with repair instructions per failure
- `python preflight.py --backend chord` — limit checks to one backend's prereqs
- `python preflight.py --json` — machine-readable for orchestrator consumption

**Exit codes**: 0 = all good, 1 = checks failed, 2 = internal error.

**Verification**:
- `--help` shows all flags
- Run against current state (ComfyUI offline): 4 of 5 checks pass, ComfyUI fails with explicit "start ComfyUI with..." instructions
- Exit code 1 as expected
- JSON mode produces valid JSON

**Files created**:
- `pipelines/textures/preflight.py`

---

## D.5 — Venv + docs cleanup

**Problem (Bucket B, B.2 findings)**: Texture pipeline Python env was
undocumented (`aaa_texture.py` runs on system Python 3.12 — not
documented anywhere). Older `PIPELINE.md` was correct on the ComfyUI
prereq but did not explain the env split (system Python for orchestrator
+ mesa-env for StableMaterials + ComfyUI for FLUX 2).

**Fix**:
- Updated `pipelines/textures/PIPELINE.md`:
  - Added "Python environment" section explaining the no-venv approach
    + the rationale (orchestrator is a thin HTTP client; heavy lifting
    is in subprocess venvs)
  - Added "Preflight" section pointing at the new D.4 script
  - Fixed stale reference to `TEXTURE_PIPELINE_FIX_PLAN.md` (now
    at `world3/docs/_archived_2026_05_11/retired_planning/`)
- Updated `world3/docs/README.md`:
  - Added stale-warning banner at the top pointing at canonical `ROADMAP.md`
  - Fixed one TEXTURE_PIPELINE_FIX_PLAN.md reference to point at archive
  - Note that the full README rewrite is queued for Phase E.6

**Files patched**:
- `pipelines/textures/PIPELINE.md` (added Python env + Preflight sections)
- `world3/docs/README.md` (banner + one link fix)

**Deferred**:
- Full `README.md` rewrite — needs Phase E.6 timing (after orchestrator exists, docs reflect new entry-point)
- `pipelines/textures/.venv` — not creating one because the orchestrator's deps are minimal and the system Python pattern works; documented as a deliberate choice in PIPELINE.md

---

## Summary

| Phase | Effort | Bucket | Outcome |
|---|---|---|---|
| D.3 | ~15 min | B (manual-step gap) | Catalog auto-refreshes after pulls; no more 365-DEM drift |
| D.4 | ~1 hour | B (manual-step gap) | Preflight script gives operators clear errors before any queue |
| D.5 | ~30 min | B (manual-step gap) | Texture pipeline env documented; PIPELINE.md current |

**Total D.3-D.5**: ~2 hours real-time. Closes 4 of the 5 Bucket B
findings from Phase B (B-1, B-2, B-3, B-4; B-5 "documented start sequence"
is now in PIPELINE.md).

## What's left for Phase D

- **D.6**: validation pass — re-run B.1, B.3 cold-runs against the
  patched code to verify D.1 didn't break determinism on unchanged
  chains; run B.2 end-to-end now that prereqs are documented + preflight
  exists.

After D.6 ships, **Phase E starts** with E.1 (region request schema).

## Cross-references

- Phase plan: [`REBUILD_PLAN_PHASES_B_E_2026_05_11.md`](REBUILD_PLAN_PHASES_B_E_2026_05_11.md)
- Phase C bucketing: [`PHASE_C_DIAGNOSIS_2026_05_11.md`](PHASE_C_DIAGNOSIS_2026_05_11.md)
- D.1 macro fix: [`D1_BUILD_MACRO_TUNE_2026_05_11.md`](D1_BUILD_MACRO_TUNE_2026_05_11.md)
- D.4 preflight script: `pipelines/textures/preflight.py`
- Patched pipelines: `pipelines/terrain/bulk_pull.py`, `pipelines/terrain/pull_megastack_queue.py`
- Updated pipeline docs: `pipelines/textures/PIPELINE.md`, `world3/docs/README.md`
