# Shader Batch Review - shader_review_smoke_002

Use this as the LLM handoff. Scores are computed from image data, not screenshot OCR.

## Top candidates

### shader_review_smoke_002_portal_swirl_2d_005 - 99.90 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_smoke_002_portal_swirl_2d_005/flipbook.png`
- Metrics: coverage `0.169`, motion `0.009`, contrast `0.159`, color `0.252`, edge `0.019`
- Hints: motion low: increase speed/pulse/spin/scroll parameters

### shader_review_smoke_002_beam_lightning_2d_007 - 99.62 (keep)

- Template: `beam_lightning_2d`
- Role: `beam`
- Preview: `shader_review_smoke_002_beam_lightning_2d_007/flipbook.png`
- Metrics: coverage `0.116`, motion `0.007`, contrast `0.184`, color `0.270`, edge `0.009`
- Hints: too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_smoke_002_beam_lightning_2d_002 - 99.50 (keep)

- Template: `beam_lightning_2d`
- Role: `beam`
- Preview: `shader_review_smoke_002_beam_lightning_2d_002/flipbook.png`
- Metrics: coverage `0.191`, motion `0.005`, contrast `0.146`, color `0.271`, edge `0.008`
- Hints: too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width; motion low: increase speed/pulse/spin/scroll parameters

### shader_review_smoke_002_portal_swirl_2d_010 - 97.29 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_smoke_002_portal_swirl_2d_010/flipbook.png`
- Metrics: coverage `0.048`, motion `0.003`, contrast `0.163`, color `0.216`, edge `0.004`
- Hints: coverage low: increase radius/thickness/edge_width/opacity, or reduce dissolve threshold; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width; motion low: increase speed/pulse/spin/scroll parameters

### shader_review_smoke_002_dissolve_fire_2d_003 - 88.06 (keep)

- Template: `dissolve_fire_2d`
- Role: `dissolve`
- Preview: `shader_review_smoke_002_dissolve_fire_2d_003/flipbook.png`
- Metrics: coverage `0.584`, motion `0.085`, contrast `0.120`, color `0.044`, edge `0.054`
- Hints: color weak: switch palette or push core/edge/glow colors farther apart

### shader_review_smoke_002_dissolve_fire_2d_008 - 87.85 (keep)

- Template: `dissolve_fire_2d`
- Role: `dissolve`
- Preview: `shader_review_smoke_002_dissolve_fire_2d_008/flipbook.png`
- Metrics: coverage `0.480`, motion `0.070`, contrast `0.135`, color `0.041`, edge `0.041`
- Hints: color weak: switch palette or push core/edge/glow colors farther apart

### shader_review_smoke_002_shield_ripple_2d_009 - 74.60 (review)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_review_smoke_002_shield_ripple_2d_009/flipbook.png`
- Metrics: coverage `0.752`, motion `0.084`, contrast `0.257`, color `0.076`, edge `0.204`
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; color weak: switch palette or push core/edge/glow colors farther apart

### shader_review_smoke_002_shield_ripple_2d_004 - 72.23 (review)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_review_smoke_002_shield_ripple_2d_004/flipbook.png`
- Metrics: coverage `0.817`, motion `0.093`, contrast `0.256`, color `0.079`, edge `0.172`
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; color weak: switch palette or push core/edge/glow colors farther apart

## Next iteration

Mutate locally around the top `keep` and `review` candidates. Reject low-coverage, full-screen, low-contrast, or over-noisy outputs automatically before human review.