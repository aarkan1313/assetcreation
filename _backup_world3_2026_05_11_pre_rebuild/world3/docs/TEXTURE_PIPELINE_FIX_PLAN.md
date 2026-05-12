# Texture Pipeline Fix Plan (Phase 1a)

Status of `D:/assets/pipelines/textures/` after a skeptical re-read on
2026-05-07. The audit on 2026-05-07 said "80% there, deploy and tune." That
was wrong. Four real defects make every "passed" texture untrustworthy.

This doc lists every defect, the fix, and the order to apply them.

## Scope

- Pipeline lives at `D:/assets/pipelines/textures/`
- 26 scripts, orchestrated by `aaa_texture.py`
- 30 textures previously produced sit at `D:/assets/world/textures/library/`
- All AI-generated outputs are suspect until re-graded against the new metric

We are **not** rewriting from scratch. The framing (variant_select → delight
→ PBR → repair → QA → gate → catalog) is reasonable. The implementations of
several stages are wrong.

## Defects

### Defect 1 — QA seam grade is a vanity metric — FIXED 2026-05-07

**Where**: [`texture_qa.py:52-84`](../../pipelines/textures/texture_qa.py#L52)

**What it does**: scores a texture's tileability as the mean-squared-error
between the leftmost 1-pixel column and the rightmost 1-pixel column (and
top/bottom). Grade A < 0.003.

**What's wrong**: a 1-pixel-wide check measures wrap-around continuity at
the borders, not whether the texture *tiles well*. Visible defects 8+ pixels
in from any edge (lattice patterns, healed-but-still-visible center seams,
periodic structure) all score grade A.

**Why this matters most**: every "passed" texture passed this metric. The
metric is the reason we have textures we don't trust.

**Fix**: replace the score with three orthogonal checks, all of which must
pass:

1. **Edge continuity** (keep the existing 1-pixel MSE, rename
   `edge_continuity_mse`). Catches pure border discontinuities.
2. **Tile-junction visibility**: tile the texture 2×2, run a Laplacian-of-
   Gaussian over the cross-shaped seam region, compare to the same metric on
   the texture's interior. If the seam region has measurably more high-
   frequency content than the interior, it's visible.
3. **Periodic-artifact check** (lattice / FLUX center bias): take the FFT
   power spectrum, check whether there's a dominant peak at a frequency
   matching the texture's half-width or quarter-width (or any small integer
   fraction). If yes, the texture has a repeating structure that will read
   as a grid when tiled.

Output a per-check pass/fail plus a grade letter. Grade A requires all
three pass. Grade B passes 2/3. Grade C 1/3. Grade D 0/3. Manifest records
all three numbers, not just the overall grade.

**Calibration result (2026-05-07)**: ran the new metric across all 30
textures in `world/textures/library/`. Thresholds:
- `edge_continuity_pass = 0.005` (1-pixel border MSE)
- `junction_ratio_pass = 1.35` (LoG seam vs. interior)
- `periodic_locality_pass = 18.0` (FFT peak vs. local neighborhood)

Grade distribution:
- A (all three pass): Rock035, biome_desert, biome_lava_field, biome_swamp,
  biome_underwater, biome_ice_cavern, cobblestone_sm, biome_mana_crystal_green_stars,
  biome_mana_crystal_v1_artifact, rock035_derived
- B (one fail): most AI sets — usually edge_continuity (un-repaired FLUX
  output)
- C (two fails): cobblestone_klein, cobblestone_aaa_detail, cobblestone_sm_std,
  forest_floor_oak_bark
- D (all fail): none

Visual sanity-check: Rock035 (real photo, known-good) grades A. The four
C-grade cobblestones have visible repetition when tiled. v2_test_saltflat
flagged for edge_continuity correctly — its tile_2x2 shows a vertical
band of denser cracks right of center. Metric agrees with eye.

### Defect 2 — Seam repair output is never used — FIXED 2026-05-07

**Where**: [`seam_repair.py:167`](../../pipelines/textures/seam_repair.py#L167)
writes to `<material>/repaired/`. Nothing copies those files back over the
originals.

**What's wrong**: even when repair runs and improves the texture, consumers
read the un-repaired originals. The catalog manifest's `passed_gate` reflects
the un-repaired state too (because QA runs *before* the orchestrator could
have copied repaired files anywhere).

**Fix**: when seam_repair runs successfully, copy each repaired map back
over the original. Keep the original as `<id>_<map>.pre_repair.png` so we
can A/B and revert. Update the catalog to record `repaired: true` and the
backup paths.

### Defect 3 — Seam repair always skips on first run — FIXED 2026-05-07

**Where**: [`seam_repair.py:163-164`](../../pipelines/textures/seam_repair.py#L163)
calls `load_manifest_for(args.material)`, which reads
`world/textures/catalog/materials.jsonl`. The orchestrator writes the
catalog *after* QA, *after* seam_repair — so on every first run, the
manifest doesn't exist and seam_repair raises `SystemExit`.

**What's wrong**: the orchestrator catches the error and logs
`"stage": "seam_repair", "skipped": true`. Repair has only run on second
attempts (and even then its output goes to `repaired/` per Defect 2).

**Fix applied**: rewrote `seam_repair.py` to discover maps by filename
suffix (`<id>_<map>.png` for albedo/normal/roughness/metallic/height/ao).
No catalog dependency. Same change also handled Defect 2 — repaired maps
overwrite originals, with `<id>_<map>.pre_repair.png` backups so we can
A/B compare or revert via `--restore`. Repair record written to
`repair_record.json` documenting pre/post scores.

Verified on `forest_floor_loam`: pre 0.0169 → post 0.0093 (44% reduction
in edge MSE). Junction ratio 1.02 → 0.76 (seam region now has *less*
high-frequency content than interior — repair worked). The new tile_2x2
preview shows leaves blending naturally across boundaries with no
visible cross-seam. Restored cleanly from backups, leaving library
unchanged for now.

### Defect 4 — StableMaterials called with wrong size — FIXED 2026-05-07

**Where**: [`stablematerials_image2pbr.py:51`](../../pipelines/textures/stablematerials_image2pbr.py#L51)
defaults to 512 because that's StableMaterials' native training resolution.
[`aaa_texture.py:148-152`](../../pipelines/textures/aaa_texture.py#L148)
passes `--size 1024`.

**What's wrong**: SM either downsamples 1024 input to 512, runs at 512, and
returns 512 (then claims 1024 in its output filename) — or runs at 1024
outside its training distribution. Either way, every "default" and "strict"
texture has been size-mismatched against the model.

**Fix applied**: simpler than originally planned. Generate everything
at 512 throughout — `flux_seamless` produces a 512 albedo, SM consumes
it and produces 512 PBR maps natively, no LANCZOS upscale or post-
process. This avoids the "size mismatch lie" entirely. For our terrain
use (world_triplanar at 5–20m repeats), 512 supplies enough pixel
density at any of our camera ranges and FLUX 2 klein at 512 still
produces good tileable albedos at ~4x the speed of 1024.

`flux_upscale.py` exists for hero materials that need 2K/4K. We just
don't need it for the standard pipeline.

Presets now own `flux_size` and `pbr_size`, both 512. `--size` on the
CLI is an explicit override that sets both uniformly. The log dict
records both sizes for provenance.

### Defect 5 — `passed_gate` is a single boolean over a single weak metric — FIXED 2026-05-07

**Where**: [`aaa_texture.py:217-220`](../../pipelines/textures/aaa_texture.py#L217)
sets `passed = final_score <= seam_max`.

**What's wrong**: the underlying `final_score` is the broken metric from
Defect 1. Even with Defect 1 fixed, a single number compresses real failure
modes (visible lattice, bad PBR ranges, broken normal map) into one yes/no.

**Fix applied**: gate is now a logical AND of three independent passes:

1. **grade pass** — seam grade meets the preset's `min_grade`. Each preset
   carries a minimum: `fast` accepts C, `default` requires B, `strict`
   requires A. Failing this records *which* of the three sub-checks
   (edge_continuity / junction_visibility / periodic_artifact) caused
   the grade to drop, in the failure list.
2. **sanity pass** — `sanity_ok` from QA's sanity check (map presence +
   value ranges).
3. **maps pass** — at least 4 of {albedo, normal, roughness, height}
   present.

The orchestrator prints the failures in the gate stage and writes them
to the manifest under `gate.failures`. The catalog records `seam_grade`
+ all three check numbers + `gate_failures` so a downstream consumer
can see exactly why a texture was rejected (or accepted).

The old `final_score` field is gone everywhere; replaced by
`seam_checks.{edge_continuity_mse, junction_ratio, periodic_locality}`.

## Order to apply fixes

The order matters because fixes 1 and 5 (the gate) are how we'll *verify*
that 2, 3, 4 actually do anything. So:

1. **Fix 1**: write the new QA metric. Run it against the existing 30
   textures in `world/textures/library/` and produce a real grade
   distribution. Sanity check: real-photo sets (Rock035, rocks_ground_06)
   should grade A. Known-bad ones (`_biome_ice_cavern_v1_lattice`,
   `_biome_mana_crystal_*`) should grade D.

2. **Fix 5**: rewrite the gate to use the new metric + sanity + map
   completeness. No regenerations yet; just confirms the verdicts make
   sense on existing textures.

3. **Fix 3**: make `seam_repair.py` self-contained (read filenames from
   disk, no catalog dependency).

4. **Fix 2**: make `seam_repair.py` copy repaired maps over originals.
   Backup originals. Update orchestrator to record this in the manifest.

5. **Fix 4**: orchestrator runs SM at 512 + upscale to 1024. Validates
   against the new gate.

6. **Pick test cases**. Regenerate one of: rock, grass, dirt — using the
   fixed pipeline. Compare against the existing version visually and via
   the new metric.

7. **Regenerate the 5 world3 textures** (rock_dark, rock_light, grass,
   desert, forest_floor) with the fixed pipeline. Replace the symlinked
   copies in `world3/textures/`.

## What this doesn't fix

- **Prompt engineering**. FLUX listens better to some words than others.
  Going to leave `flux_seamless.py`'s prompt suffix alone for now and
  see if the new metric + working repair are enough.
- **Structured patterns** (bricks, tiles, planks). The offset method
  fundamentally doesn't work for directional content. We'll discover this
  when we try to make a brick texture; not blocking world3.
- **`palette_lock.py` / `patina_adapter.py` integration**. Useful for
  biome cohesion but not an active defect. Defer until we need a
  multi-texture biome set.
- **Material Anything**. The audit confirmed it's broken for 2D. Not
  touching.

## Exit criteria

- New QA metric runs cleanly on all 30 existing textures and produces
  grades that match what we *see* (real-photo = A, generated bad-tiling =
  D).
- A regenerated texture set passes the new gate and visibly tiles cleanly
  in the existing `tile_2x2.png` preview.
- The 5 world3 textures all grade A on the new metric.
- `pipelines/textures/PIPELINE.md` documents the fixed workflow in one
  page.
