# world3 Pre-Rebuild Backup — 2026-05-11

This backup captures the state immediately before the world3 rebuild
that was initiated 2026-05-11 after the M1-M18 audit + orchestrator
stock-take revealed significant doc-tree divergence.

## What is here

- `world3/` — full world3 directory **minus** `opentopo/`, `toporeview/`,
  `runtime_cache/`, and `docs/captures/`. Those are large (16 GB +
  2.1 GB + 8 MB + 627 MB respectively) and are regenerable from the
  pipeline scripts. The 247 MB `textures/` directory IS included because
  it contains source-stack bundles tied to specific generation runs.
- `pipelines/textures/` — full code + docs (excludes .venv and __pycache__)
- `pipelines/terrain/` — code only (skips DEM cache + tmp output)
- `docs/` — top-level project docs (`plans/`, `MASTER_DATA_CATALOG.md`)
- `git_status_2026_05_11.txt` — git status output at backup time
- `git_log_recent_2026_05_11.txt` — last 50 commits at backup time
- `git_diff_stat_2026_05_11.txt` — diff stats of dirty state
- `git_full_diff_2026_05_11.patch` — full diff patch of all unstaged work

## What is NOT here (and why)

- `world3/opentopo/` (16 GB) — DEM cache, regenerable from `pipelines/terrain/`
- `world3/toporeview/` (2.1 GB) — generated review outputs, regenerable
- `world3/runtime_cache/` (8 MB) — runtime cache, rebuilt automatically
- `world3/docs/captures/` (627 MB) — review captures, regenerable from scenes

If you need to restore, the bulky directories rebuild from script. The
content of this backup is the irreplaceable code + manifests + planning
docs + source-stack bundle outputs.

## Last committed state at backup time

Most recent commit: `c5b0cff world3: m1-m18 audit report + matrix + contact sheet`

Major uncommitted work captured in the patch file:
- 17+ untracked orchestrator-side docs (ROADMAP rewrite, ORCHESTRATOR_HANDOFF,
  arc docs, contract, completion bar, exec summary, operability gaps, etc.)
- 18 modified files (orchestrator planning edits + worker audit-script
  regenerations)

## Restore

Worst-case restore: extract `world3/` from this backup over a fresh
`world3/` directory, run `pipelines/terrain/build_master_catalog.py` to
regenerate the data catalog, then re-run any pipeline scripts whose
output landed in the skipped directories (opentopo, toporeview, runtime_cache,
captures).

To restore the uncommitted dirty state from before rebuild:
```
cd /d/assets
git apply /d/assets/_backup_world3_2026_05_11_pre_rebuild/git_full_diff_2026_05_11.patch
```
(may need `--3way` if subsequent commits land first)

## Authority

This backup is the ground truth for "what world3 looked like immediately
before the 2026-05-11 rebuild." Don't modify files inside this directory.
