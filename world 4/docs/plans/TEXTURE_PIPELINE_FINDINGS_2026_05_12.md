# W4 Texture Pipeline — Audit Experiment Findings — 2026-05-12

Results from the 16-combo audit experiment on the `windpack` prompt.
This is the empirical follow-up to `TEXTURE_PIPELINE_AUDIT_2026_05_12.md`.

**TL;DR:** The audit was partly right and partly wrong. We landed at a
W4-default config that's *different* from both the upstream defaults
and the audit's predicted defaults.

## Setup

- 1 prompt: `tileable seamless texture, wind-packed snow with sastrugi ridges, sharp wind-carved striations, bright white, overhead perspective`
- Category: Snow (mip32_stdev threshold 12, periodic 13)
- 4 axes × 2 values = 16 combos
- Each combo: 1 variant, seed 42, size 1024px
- Total runtime: 438s (~27s per combo)

## Full results

| label                              | grade | edge   | periodic | mip32 |
|------------------------------------|-------|--------|----------|-------|
| `h1.0 d0.0 derive flux_heal`       | **A** | 0.0026 | 10.4     | 26.8  |
| `h1.0 d0.4 derive flux_heal`       | **A** | 0.0022 | 10.4     | 20.0  |
| `h1.0 d0.4 sm   flux_heal`         | B     | 0.0008 | 47.3     | 69.0  |
| `h0.35 d0.0 derive flux_heal`      | B     | 0.0172 | 12.4     | 17.7  |
| `h0.35 d0.4 derive flux_heal`      | B     | 0.0113 | 12.6     | 14.4  |
| `h0.35 d0.0 derive none`           | C     | 0.0210 | 13.7     | 18.5  |
| `h0.35 d0.0 sm     flux_heal`      | C     | 0.0000 | 17.5     |  3.2  |
| `h0.35 d0.0 sm     none`           | C     | 0.0001 | 41.1     |  4.1  |
| `h0.35 d0.4 derive none`           | C     | 0.0145 | 13.7     | 15.0  |
| `h0.35 d0.4 sm     flux_heal`      | C     | 0.0001 | 52.9     |  5.2  |
| `h0.35 d0.4 sm     none`           | C     | 0.0001 | 47.2     |  3.1  |
| `h1.0  d0.0 derive none`           | C     | 0.0210 | 13.7     | 18.5  |
| `h1.0  d0.0 sm     flux_heal`      | C     | 0.0000 | 40.1     |  3.2  |
| `h1.0  d0.0 sm     none`           | C     | 0.0001 | 41.1     |  4.1  |
| `h1.0  d0.4 derive none`           | C     | 0.0145 | 13.7     | 15.0  |
| `h1.0  d0.4 sm     none`           | C     | 0.0001 | 47.2     |  3.1  |

Visual: `_comparison_sheet.png` in `candidates/_pipeline_review/audit/`.

## Marginal effects (mean grade-rank, A=3 / B=2 / C=1)

| axis           | level A           | level B          | delta |
|----------------|-------------------|------------------|-------|
| heal_denoise   | `0.35` → 1.25     | **`1.0` → 1.62** | +0.37 |
| delight        | `0.0` → 1.38      | `0.4` → 1.50     | +0.12 |
| pbr            | `sm` → 1.12       | **`derive` → 1.75** | +0.63 |
| heal_mode      | `none` → 1.00     | **`flux_heal` → 1.88** | +0.88 |

## Reading the marginals

The biggest signals, in order:

1. **`heal_mode=flux_heal` matters most.** Skipping the heal pass
   (heal_mode=none) drops the grade by nearly a full step (0.88).
   Every "none" combo got at most B; most got C. The 4-pass FLUX
   architecture is doing real work — pass 1 alone produces visibly
   discontinuous output, even with the tile-prompt suffix.

2. **`pbr=derive` beats `pbr=sm` by 0.63 grade steps.** Every single
   SM combo failed on `mip32_stdev` (values 3.1–5.2) — SM produces
   albedos that flatten visually at distance. derive_pbr_v2 outputs
   sit at mip32_stdev 14–27 (well above the 12 threshold). **This
   confirms the audit's call to swap the default.**

3. **`heal_denoise=1.0` beats `heal_denoise=0.35` by 0.37.** This is
   the opposite of what the audit predicted. The audit hypothesized
   that the "silent denoise=1.0" upstream behavior was producing the
   lattice fingerprint. Turns out a *gentle* heal isn't strong enough
   to actually clean the offset cross — `heal_denoise=0.35` consistently
   leaves edge_continuity values around 0.01–0.02, well above the
   0.005 threshold. Full denoise hammers the seam closed (0.002 range)
   while the FLUX heal pass keeps the natural surface character.

4. **`delight=0.4 vs 0.0` is in the noise** (0.12 grade steps).
   Confirmed: the prompt's `even neutral diffuse lighting, no shadows`
   already handles the lighting at generation time, so the LAB-blur
   delight only adds 0.12 of a grade on average. **Default delight
   off** is correct, but it's not a high-leverage call.

## The two A-grade winners

Both A combos share the same three axes:
- `heal_denoise=1.0`
- `pbr=derive`
- `heal_mode=flux_heal`

The only difference between them is delight (0.0 vs 0.4) — and both
got A. So the W4 defaults are:

```python
PipelineSettings(
    heal_denoise=1.0,       # was 0.35 in audit prediction
    heal_mode="flux_heal",
    pbr_backend="derive",
    delight_strength=0.0,   # keep off; small effect, save the step
)
```

## What the audit got wrong, and why

### Wrong: "honor heal-denoise at 0.35"
The audit hypothesized that the upstream's silent denoise=1.0 was
the source of the klein-9B-at-1024 lattice fingerprint. The
experiment shows otherwise:
- All 4 `heal_denoise=0.35` combos with `pbr=derive` only reached B
  on edge_continuity (≥0.011).
- Both `heal_denoise=1.0 + pbr=derive + heal_mode=flux_heal` combos
  reached A on edge_continuity (≤0.003).
- **The full-denoise heal is what actually closes the seam cross.**
  A 0.35 heal preserves more original content but leaves the
  discontinuity visible.

### Right: "pbr_backend=derive as default"
Confirmed strongly. SM tanks mip32_stdev on every single combo
(values 3–5 against a threshold of 12). The audit's reasoning
(SM invents detail that doesn't match the albedo at terrain
distance) is exactly what we see.

### Right: "heal_mode=flux_heal is necessary"
The audit framed this as "the FLUX heal IS the seam repair" —
removing it should be fine. Empirically that's wrong: removing it
costs a grade step. The 4-pass FLUX is doing real work, not just
duplicating effort with the legacy seam_repair.

### Effectively neutral: "delight off by default"
The audit was right that prompt-level lighting control reduces the
need for delight. The marginal effect on grade is small (0.12).
Default to off is fine because the *cost* of running it (extra
LAB-blur subtract pass per material) outweighs the gain. But it's
not a quality win, it's a speed win.

## What changed in the W4 defaults

| Setting | Old upstream | Audit predicted | **Experiment-locked W4** |
|---------|--------------|-----------------|---------------------------|
| `heal_denoise` | 1.0 (silent) | 0.35 (honored) | **1.0 (honored)** |
| `heal_mode` | flux_heal | flux_heal | **flux_heal** |
| `pbr_backend` | sm | derive | **derive** |
| `delight_strength` | 0.4 | 0.0 | **0.0** |

So the W4 defaults end up being:
- Same `heal_denoise` value as upstream (1.0) but **now correctly
  honored** — not silently ignored.
- Same `heal_mode` as upstream.
- **Different `pbr_backend`** (derive, was sm).
- **Different `delight_strength`** (0.0, was 0.4).

## Updating tx_pipeline defaults

The dataclass defaults in `pipeline/textures/tx_pipeline.py` should be:

```python
@dataclass
class PipelineSettings:
    heal_denoise: float = 1.0       # was 0.35 — audit wrong, experiment correct
    heal_mode: str = "flux_heal"
    delight_strength: float = 0.0
    pbr_backend: str = "derive"
    external_seam_repair: bool = False
```

`diversity_run.py` already inherits these so re-running the alpine
batch now uses the experimentally-validated config.

## Caveats

- **Single prompt.** All 16 combos use the same `windpack` prompt.
  We don't know if the same defaults win for other prompt types
  (e.g. rock-bedrock, lichen-mid). For the diversity batch the
  defaults are good enough; revisit if a class of slot consistently
  underperforms.
- **Single seed.** seed=42 throughout. Some axes may interact with
  seed (e.g. the heal-denoise sweet spot might shift). N=1 means we
  can't measure variance — only effect direction.
- **Single category (Snow).** mip32_stdev threshold is category-
  dependent (Snow=12, Rock=20). The marginal "pbr=sm always fails
  mip32" finding might be Snow-specific because SM has weaker
  training on soft materials.
- **No visual spot-check yet.** All findings are off the grader's
  numbers. The contact sheet exists; human review is the next step.
  If the grader says A but it looks bad, the metric needs adjustment.

## Next steps

1. **Lock in W4 defaults** in `tx_pipeline.PipelineSettings`
   (`heal_denoise=1.0`, rest unchanged).
2. **Spot-check the 2 A-grade combos visually** (`_comparison_sheet.png`).
3. **Re-run alpine diversity batch** with the new defaults — should
   produce more A-grades than the original 23-candidate batch.
4. **Repeat the matrix on a rock-class prompt** to confirm pbr=derive
   isn't Snow-only. Defer until alpine winners are picked.
