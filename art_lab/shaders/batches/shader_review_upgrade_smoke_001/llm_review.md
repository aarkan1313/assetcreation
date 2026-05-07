# Shader Batch Review - shader_review_upgrade_smoke_001

Use this as the LLM handoff. Scores are computed from image data, not screenshot OCR.

## Top candidates

### shader_review_upgrade_smoke_001_shield_ripple_2d_004 - 87.76 (review)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_review_upgrade_smoke_001_shield_ripple_2d_004/flipbook.png`
- Metrics: coverage `0.759`, motion `0.006`, contrast `0.050`, color `0.150`, edge `0.035`
- Gates: none
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold

### shader_review_upgrade_smoke_001_dissolve_fire_2d_003 - 87.70 (review)

- Template: `dissolve_fire_2d`
- Role: `dissolve`
- Preview: `shader_review_upgrade_smoke_001_dissolve_fire_2d_003/flipbook.png`
- Metrics: coverage `0.595`, motion `0.109`, contrast `0.165`, color `0.040`, edge `0.096`
- Gates: none
- Hints: color weak: switch palette or push core/edge/glow colors farther apart

### shader_review_upgrade_smoke_001_beam_lightning_2d_007 - 81.49 (review)

- Template: `beam_lightning_2d`
- Role: `beam`
- Preview: `shader_review_upgrade_smoke_001_beam_lightning_2d_007/flipbook.png`
- Metrics: coverage `0.361`, motion `0.027`, contrast `0.057`, color `0.242`, edge `0.006`
- Gates: role coverage far above target
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_upgrade_smoke_001_portal_swirl_2d_005 - 80.22 (review)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_upgrade_smoke_001_portal_swirl_2d_005/flipbook.png`
- Metrics: coverage `0.110`, motion `0.002`, contrast `0.018`, color `0.139`, edge `0.004`
- Gates: weak contrast; motion below role target
- Hints: contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width; motion low: increase speed/pulse/spin/scroll parameters

### shader_review_upgrade_smoke_001_ring_field_2d_006 - 77.66 (review)

- Template: `ring_field_2d`
- Role: `aura`
- Preview: `shader_review_upgrade_smoke_001_ring_field_2d_006/flipbook.png`
- Metrics: coverage `0.950`, motion `0.080`, contrast `0.072`, color `0.165`, edge `0.010`
- Gates: role coverage far above target
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_upgrade_smoke_001_dissolve_fire_2d_008 - 72.39 (maybe)

- Template: `dissolve_fire_2d`
- Role: `dissolve`
- Preview: `shader_review_upgrade_smoke_001_dissolve_fire_2d_008/flipbook.png`
- Metrics: coverage `0.098`, motion `0.023`, contrast `0.038`, color `0.032`, edge `0.006`
- Gates: weak contrast
- Hints: contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; color weak: switch palette or push core/edge/glow colors farther apart; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_upgrade_smoke_001_beam_lightning_2d_002 - 71.40 (maybe)

- Template: `beam_lightning_2d`
- Role: `beam`
- Preview: `shader_review_upgrade_smoke_001_beam_lightning_2d_002/flipbook.png`
- Metrics: coverage `0.492`, motion `0.010`, contrast `0.050`, color `0.256`, edge `0.004`
- Gates: role coverage far above target
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_review_upgrade_smoke_001_ring_field_2d_001 - 55.36 (reject)

- Template: `ring_field_2d`
- Role: `aura`
- Preview: `shader_review_upgrade_smoke_001_ring_field_2d_001/flipbook.png`
- Metrics: coverage `0.995`, motion `0.091`, contrast `0.089`, color `0.173`, edge `0.016`
- Gates: nearly full-screen alpha coverage
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold

## Next iteration

Mutate locally around the top `keep` and `review` candidates. Reject low-coverage, full-screen, low-contrast, or over-noisy outputs automatically before human review.