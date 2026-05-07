# Shader Batch Review - shader_review_mutate_001

Use this as the LLM handoff. Scores are computed from image data, not screenshot OCR.

## Top candidates

### shader_review_mutate_001_portal_swirl_2d_001 - 100.00 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_mutate_001_portal_swirl_2d_001/flipbook.png`
- Metrics: coverage `0.162`, motion `0.018`, contrast `0.156`, color `0.254`, edge `0.019`
- Hints: good candidate: mutate locally around these params with smaller jitter

### shader_review_mutate_001_portal_swirl_2d_005 - 100.00 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_mutate_001_portal_swirl_2d_005/flipbook.png`
- Metrics: coverage `0.173`, motion `0.017`, contrast `0.167`, color `0.243`, edge `0.022`
- Hints: good candidate: mutate locally around these params with smaller jitter

### shader_review_mutate_001_portal_swirl_2d_006 - 99.99 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_mutate_001_portal_swirl_2d_006/flipbook.png`
- Metrics: coverage `0.168`, motion `0.010`, contrast `0.158`, color `0.258`, edge `0.020`
- Hints: motion low: increase speed/pulse/spin/scroll parameters

### shader_review_mutate_001_portal_swirl_2d_004 - 99.97 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_mutate_001_portal_swirl_2d_004/flipbook.png`
- Metrics: coverage `0.182`, motion `0.010`, contrast `0.162`, color `0.249`, edge `0.022`
- Hints: motion low: increase speed/pulse/spin/scroll parameters

### shader_review_mutate_001_portal_swirl_2d_002 - 99.77 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_mutate_001_portal_swirl_2d_002/flipbook.png`
- Metrics: coverage `0.168`, motion `0.007`, contrast `0.151`, color `0.254`, edge `0.017`
- Hints: motion low: increase speed/pulse/spin/scroll parameters

### shader_review_mutate_001_portal_swirl_2d_003 - 99.37 (keep)

- Template: `portal_swirl_2d`
- Role: `portal`
- Preview: `shader_review_mutate_001_portal_swirl_2d_003/flipbook.png`
- Metrics: coverage `0.152`, motion `0.001`, contrast `0.159`, color `0.240`, edge `0.018`
- Hints: motion low: increase speed/pulse/spin/scroll parameters

## Next iteration

Mutate locally around the top `keep` and `review` candidates. Reject low-coverage, full-screen, low-contrast, or over-noisy outputs automatically before human review.