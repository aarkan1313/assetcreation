# pipelines/terrain — runtime + provenance

## Lane contents

Scripts in this directory cover:

- OpenTopo cache I/O: `bulk_fetch_to_cache.py`, `bulk_pull.py`,
  `fetch_regional_stac.py`, `import_dem.py`, `tile_stitch.py`,
  `pull_megastack_queue.py`, `megastack_tracker.py`.
- Data catalog: `build_master_catalog.py`, `catalog_search.py`,
  `mystery_sampler.py`.
- Procedural erosion (M19-M24 prep): `landlab_smoke_test.py`.

The cache itself lives at `d:/assets/dems/` and is indexed by
`docs/MASTER_DATA_CATALOG.md` plus `world3/data_catalog.json`.

## .venv (Python 3.12)

This lane has its own isolated venv at `pipelines/terrain/.venv/`,
following the [`isolated_venv_per_lane`](../../README.md) convention.

Installed:

- `landlab` 2.11.0 (fluvial + diffusion erosion solver, M19-M24)
- numpy 2.4.4, scipy 1.17.1, matplotlib 3.10.9, pandas 3.0.2, xarray
  2026.4.0, netcdf4 1.7.4, py-richdem 2.2.0rc2, bmipy 2.0.1
- statsmodels 0.14.6 (corpus distribution fitting for M19)

Created with:

```
"C:\Program Files\Python312\python.exe" -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip wheel
.venv\Scripts\python.exe -m pip install landlab
```

No system compiler needed. Landlab 2.11.0 ships pre-built win_amd64
wheels for py312; all Cython/native deps come prebuilt.

## Landlab smoke test

```
.venv\Scripts\python.exe landlab_smoke_test.py
```

Builds a 128x128 @ 30m FastNoise-style heightmap (3.84 km square),
runs `FlowAccumulator(D8)` + `FastscapeEroder(K_sp=2e-4)` +
`LinearDiffuser(D=0.01)` for 60 steps x dt=500, and writes a
before/after/drainage triptych to
`output/landlab_smoke/before_after.png`.

Verified 2026-05-10:

- import time ~1.5 s (cold), sim ~3 ms/step
- relief reduced from 135.8 -> 109.2 (p99-p1, m)
- mean elevation 83.6 -> 22.7 (erosion removes mass)
- max drainage cell collects ~2690 upstream cells (dendritic network)
- output PNG shows believable carved valleys + ridge structure

This validates the M20 erosion backbone before any production wiring.

## Why this lane has Landlab

Landlab is the only new dependency for the M19-M24 hybrid procedural
infinite-world roadmap. Plan:
[`world3/docs/M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](../../world3/docs/M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md).

Production wiring is gated on M13-M18 closure. Until then, this venv
is for feasibility spikes only: corpus statistics (M19), erosion
calibration per biome (M20), and one-off bake experiments.
