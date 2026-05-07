# Shader Batch Review - shader_review_smoke_001

Use this as the LLM handoff. Scores are computed from image data, not screenshot OCR.

## Top candidates

### shader_review_smoke_001_ring_field_2d_001 - 100.00 (keep)

- Template: `ring_field_2d`
- Role: `aura`
- Preview: `shader_review_smoke_001_ring_field_2d_001/flipbook.png`
- Metrics: coverage `0.460`, motion `0.007`, contrast `0.216`, color `0.298`, edge `0.023`
- Hints: good candidate: mutate locally around these params with smaller jitter

### shader_review_smoke_001_beam_lightning_2d_005 - 99.64 (keep)

- Template: `beam_lightning_2d`
- Role: `beam`
- Preview: `shader_review_smoke_001_beam_lightning_2d_005/flipbook.png`
- Metrics: coverage `0.168`, motion `0.022`, contrast `0.167`, color `0.290`, edge `0.009`
- Hints: too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_smoke_001_beam_lightning_2d_006 - 93.19 (keep)

- Template: `beam_lightning_2d`
- Role: `beam`
- Preview: `shader_review_smoke_001_beam_lightning_2d_006/flipbook.png`
- Metrics: coverage `0.316`, motion `0.023`, contrast `0.175`, color `0.345`, edge `0.008`
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_smoke_001_shield_ripple_2d_012 - 91.71 (keep)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_review_smoke_001_shield_ripple_2d_012/flipbook.png`
- Metrics: coverage `0.853`, motion `0.037`, contrast `0.126`, color `0.308`, edge `0.050`
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold

### shader_review_smoke_001_ring_field_2d_003 - 89.85 (keep)

- Template: `ring_field_2d`
- Role: `aura`
- Preview: `shader_review_smoke_001_ring_field_2d_003/flipbook.png`
- Metrics: coverage `0.482`, motion `0.015`, contrast `0.208`, color `0.252`, edge `0.020`
- Hints: good candidate: mutate locally around these params with smaller jitter

### shader_review_smoke_001_dissolve_fire_2d_007 - 87.54 (keep)

- Template: `dissolve_fire_2d`
- Role: `dissolve`
- Preview: `shader_review_smoke_001_dissolve_fire_2d_007/flipbook.png`
- Metrics: coverage `0.669`, motion `0.059`, contrast `0.139`, color `0.038`, edge `0.057`
- Hints: color weak: switch palette or push core/edge/glow colors farther apart

### shader_review_smoke_001_dissolve_fire_2d_008 - 86.18 (keep)

- Template: `dissolve_fire_2d`
- Role: `dissolve`
- Preview: `shader_review_smoke_001_dissolve_fire_2d_008/flipbook.png`
- Metrics: coverage `0.097`, motion `0.036`, contrast `0.085`, color `0.088`, edge `0.018`
- Hints: color weak: switch palette or push core/edge/glow colors farther apart; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_smoke_001_dissolve_fire_2d_009 - 82.75 (review)

- Template: `dissolve_fire_2d`
- Role: `dissolve`
- Preview: `shader_review_smoke_001_dissolve_fire_2d_009/flipbook.png`
- Metrics: coverage `0.160`, motion `0.052`, contrast `0.089`, color `0.042`, edge `0.028`
- Hints: color weak: switch palette or push core/edge/glow colors farther apart

## Next iteration

Mutate locally around the top `keep` and `review` candidates. Reject low-coverage, full-screen, low-contrast, or over-noisy outputs automatically before human review.