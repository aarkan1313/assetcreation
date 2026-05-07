# Shader Batch Review - shader_evolve_smoke_001

Use this as the LLM handoff. Scores are computed from image data, not screenshot OCR.

## Top candidates

### shader_evolve_smoke_001_g01_portal_swirl_2d_001 - 90.26 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_evolve_smoke_001_g01_portal_swirl_2d_001/flipbook.png`
- Metrics: coverage `0.093`, motion `0.013`, contrast `0.022`, color `0.123`, edge `0.006`
- Gates: weak contrast
- Hints: coverage low: increase radius/thickness/edge_width/opacity, or reduce dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_evolve_smoke_001_g00_portal_swirl_2d_001 - 89.95 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_evolve_smoke_001_g00_portal_swirl_2d_001/flipbook.png`
- Metrics: coverage `0.111`, motion `0.006`, contrast `0.022`, color `0.120`, edge `0.006`
- Gates: weak contrast; motion below role target
- Hints: contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width; motion low: increase speed/pulse/spin/scroll parameters

### shader_evolve_smoke_001_g01_portal_swirl_2d_004 - 89.08 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_evolve_smoke_001_g01_portal_swirl_2d_004/flipbook.png`
- Metrics: coverage `0.125`, motion `0.015`, contrast `0.023`, color `0.104`, edge `0.005`
- Gates: weak contrast
- Hints: contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_evolve_smoke_001_g01_portal_swirl_2d_006 - 87.49 (review)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_evolve_smoke_001_g01_portal_swirl_2d_006/flipbook.png`
- Metrics: coverage `0.070`, motion `0.016`, contrast `0.027`, color `0.080`, edge `0.003`
- Gates: weak contrast
- Hints: coverage low: increase radius/thickness/edge_width/opacity, or reduce dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; color weak: switch palette or push core/edge/glow colors farther apart; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_evolve_smoke_001_g00_portal_swirl_2d_005 - 87.40 (review)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_evolve_smoke_001_g00_portal_swirl_2d_005/flipbook.png`
- Metrics: coverage `0.074`, motion `0.009`, contrast `0.029`, color `0.067`, edge `0.003`
- Gates: weak contrast
- Hints: coverage low: increase radius/thickness/edge_width/opacity, or reduce dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; color weak: switch palette or push core/edge/glow colors farther apart; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width; motion low: increase speed/pulse/spin/scroll parameters

### shader_evolve_smoke_001_g01_portal_swirl_2d_003 - 87.11 (review)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_evolve_smoke_001_g01_portal_swirl_2d_003/flipbook.png`
- Metrics: coverage `0.075`, motion `0.006`, contrast `0.034`, color `0.063`, edge `0.003`
- Gates: weak contrast; motion below role target
- Hints: coverage low: increase radius/thickness/edge_width/opacity, or reduce dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; color weak: switch palette or push core/edge/glow colors farther apart; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width; motion low: increase speed/pulse/spin/scroll parameters

### shader_evolve_smoke_001_g00_portal_swirl_2d_003 - 83.68 (review)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_evolve_smoke_001_g00_portal_swirl_2d_003/flipbook.png`
- Metrics: coverage `0.102`, motion `0.006`, contrast `0.014`, color `0.049`, edge `0.002`
- Gates: weak contrast; motion below role target
- Hints: contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; color weak: switch palette or push core/edge/glow colors farther apart; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width; motion low: increase speed/pulse/spin/scroll parameters

### shader_evolve_smoke_001_g01_shield_ripple_2d_005 - 42.19 (reject)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_evolve_smoke_001_g01_shield_ripple_2d_005/flipbook.png`
- Metrics: coverage `0.826`, motion `0.031`, contrast `0.020`, color `0.139`, edge `0.005`
- Gates: weak contrast
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_evolve_smoke_001_g00_shield_ripple_2d_004 - 41.40 (reject)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_evolve_smoke_001_g00_shield_ripple_2d_004/flipbook.png`
- Metrics: coverage `0.836`, motion `0.030`, contrast `0.020`, color `0.153`, edge `0.005`
- Gates: weak contrast
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_evolve_smoke_001_g01_shield_ripple_2d_002 - 40.37 (reject)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_evolve_smoke_001_g01_shield_ripple_2d_002/flipbook.png`
- Metrics: coverage `0.827`, motion `0.027`, contrast `0.023`, color `0.127`, edge `0.008`
- Gates: weak contrast
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold; contrast low: widen color separation, add hotter core/edge, or reduce background-like colors; too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width

### shader_evolve_smoke_001_g00_shield_ripple_2d_006 - 36.38 (reject)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_evolve_smoke_001_g00_shield_ripple_2d_006/flipbook.png`
- Metrics: coverage `0.853`, motion `0.056`, contrast `0.069`, color `0.229`, edge `0.037`
- Gates: none
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold

### shader_evolve_smoke_001_g00_shield_ripple_2d_002 - 34.61 (reject)

- Template: `shield_ripple_2d`
- Role: `shield`
- Preview: `shader_evolve_smoke_001_g00_shield_ripple_2d_002/flipbook.png`
- Metrics: coverage `0.853`, motion `0.102`, contrast `0.064`, color `0.244`, edge `0.051`
- Gates: none
- Hints: coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold

## Next iteration

Mutate locally around the top `keep` and `review` candidates. Reject low-coverage, full-screen, low-contrast, or over-noisy outputs automatically before human review.