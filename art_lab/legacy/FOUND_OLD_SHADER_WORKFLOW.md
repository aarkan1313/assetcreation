# Found Legacy Shader Workflow

Date found: 2026-05-06

## Closest match

`C:\Users\josep\Downloads\shader-cauldron-v6.html`

A preserved copy now lives at:

`D:\assets\art_lab\legacy\shader-cauldron-v6.html`

Metadata from the original file:

- `shader-cauldron.html` - 66,650 bytes - 2026-02-11 22:08:33
- `shader-cauldron (1).html` - 66,650 bytes - 2026-02-11 22:16:34
- `shader-cauldron-v6.html` - 87,713 bytes - 2026-02-11 23:09:47

## Why this appears to be the old app

`shader-cauldron-v6.html` contains:

- WebGL live shader preview.
- Random shader generation from a procedural expression grammar.
- Style presets for arcane, fire, frost, lightning, holy, poison, shield, enchant, nature, blood, void, necro, chrono, and more.
- Buttons for Randomize, Mutate, Auto, Copy, Save, and background toggling.
- Sliders/knobs generated from shader parameters.
- Saved shaders, history thumbnails, screenshots, and auto-cycling.
- GLSL preview and Godot `canvas_item` / `spatial` export.

Important lines found during inspection:

- Line 401: `function genShader(seed,complexity,style)`
- Line 407: `// 2D SHADER GENERATOR (expanded)`
- Lines 374-395: style-to-pattern pools.
- Lines 648-657: Godot shader output path for 2D/3D.
- Lines 987-999: mutation/tweak behavior.
- Lines 999-1021: auto-generation loop.
- Lines 1071-1078: randomization retries until GLSL compiles.

## Related older assets

Likely related but less exact:

- `C:\Users\josep\Downloads\spell-effect-library*.html`
- `C:\Users\josep\Downloads\tlte-spell-vfx-pack*.html`
- `C:\Users\josep\jk engine\archived\spells\...`
- `C:\Users\josep\Documents\Newest\shader-training-pipeline`
- `C:\Users\josep\moom\lenovo build\ShaderViewer`

The `shader-training-pipeline` folder is especially relevant for future work. It is a November 2025 Qwen2.5-VL/LoRA experiment with Shadertoy scraping, screenshots, preprocessing, training, and inference scripts. It may be useful as a dataset/reference-mining source, but should not become the primary production path until licensing, data quality, and evaluation are audited.

## Lessons to carry forward

The old Cauldron got several things right:

- Seeded procedural generation is more reliable than free-form LLM shader code.
- Knobs/sliders are essential; most quality comes from tuning, not one-shot generation.
- Exporting Godot code directly is the right target.
- Auto-cycling is useful only if it compiles and stores history.

The gaps to fix in the new Art Lab:

- Add deterministic batch output folders, not only in-browser state.
- Score by pixels and motion metrics before human review.
- Promote only a diverse shortlist.
- Add Godot-rendered previews as final acceptance.
- Add reference-set scoring for style direction.
- Keep LLMs operating on structured JSON, metrics, and commands instead of screenshot OCR.
