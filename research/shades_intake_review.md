# Intake Review - shades.md

Date: 2026-05-06  
Source research: `D:\assets\research\shades.md`

## Short Verdict

The survey is useful and mostly agrees with the direction already chosen for the
shader lab: no turnkey AI spell-shader generator exists; the workable path is a
constrained shader/template system, renderer-in-loop validation, reference
scoring, and evolutionary search.

The researcher did not have access to the work already done in `art_lab`, so a
lot of the proposed architecture is now already covered locally:

- Batch generation from Godot templates.
- Non-OCR pixel/motion scoring.
- Reference image scoring.
- Evolution over valid shader template parameters.
- Promotion queues for human review.
- A recovered copy of the older Shader Cauldron HTML workflow.

The useful new deltas are:

- Treat **AI Co-Artist** as a direct research validation of the evolutionary
  shader workflow.
- Add a **ShaderToy/RAG/importer lane** as a research branch, not as the mainline.
- Track **ShaderToy-MCP**, `shaders21k`, and `shadermatch` as possible external
  source/evaluation components.
- Add **StableMaterials** and **Chord** to the texture/material test backlog.
- Watch **Godot AI MCP** as a possible editor-control layer once Godot rendering
  is validated.

## What We Already Have

### Evolutionary Loop

The survey recommends an AI Co-Artist-style population loop. We now have the
first practical local version:

`D:\assets\art_lab\tools\shader_evolve.py`

It evolves template parameters toward reference images while keeping the normal
role/quality gate. This is more constrained than AI Co-Artist, which evolves GLSL
through LLM mutation/crossover, but that constraint is intentional. Valid Godot
templates produce fewer dead ends than arbitrary generated GLSL.

Current output:

- `gallery.html`
- `batch_summary.json`
- `evolution_summary.json`
- `llm_review_packet.json`
- PNG previews and flipbooks
- `.gdshader`, `.tscn`, and `request.json` per candidate

### Render-And-Review Harness

The survey repeatedly points at render-in-the-loop evaluation. We have that
structure now:

- CPU proxy previews for broad search.
- Non-OCR pixel/motion scoring in `shader_batch_review.py`.
- Reference image matching in `shader_reference_score.py`.
- Godot CLI render wrapper in `shader_godot_render.py`, pending actual Godot exe
  validation.

The biggest remaining issue is that the engine-rendered Godot pass has not been
validated on this machine yet.

### Path A / Path B Split

The survey's Path A / Path B framing maps cleanly to the existing repo:

- Path A: editable procedural shader/template source in `art_lab/shaders`.
- Path B: PBR texture-map generation and extraction in `pipelines/textures`.

The shader lab should not absorb the whole PBR material stack. It should link to
it and use generated maps as references or inputs where needed.

## New Items Worth Acting On

### 1. AI Co-Artist

Status: adopt the pattern, do not depend on the prototype.

Why it matters:

- It is the closest cited research match to the desired workflow: animated GLSL,
  population-based evolution, and LLM mutation/crossover.
- It validates the idea that shader search should be interactive/evolutionary,
  not one-shot prompt-to-code.

Local action:

- Keep `shader_evolve.py` as the production-safe version.
- Add LLM-authored mutation prompts later, but only after code generation is
  fenced inside templates or a DSL.
- Add crossover once candidates can declare reusable blocks or parameter groups.

Verified source:

- https://huggingface.co/papers/2512.08951

### 2. ShaderToy-MCP, shaders21k, and shadermatch

Status: test as a separate external-reference lane.

Why it matters:

- ShaderToy is a rich source of idioms for fire, lightning, portals, water,
  raymarching, SDFs, holograms, and dissolves.
- ShaderToy-MCP gives an LLM read/search access to ShaderToy.
- `shaders21k` is a large shader corpus.
- `shadermatch` is a render-based similarity metric for Shadertoy-style code.

Risks:

- License hygiene is the main risk. Shadertoy code is per-shader licensed and
  cannot be treated as a free production corpus.
- Multi-pass Shadertoy shaders may not port cleanly to Godot.
- `shadermatch` is designed for shader-code similarity/function completion, not
  gameplay or art-direction quality.

Local action:

- Create a future `shader_shadertoy_import.py` only after license rules are
  explicit.
- Store source URL, author, license, and transformation notes for every imported
  shader.
- Use Shadertoy examples for RAG and inspiration first, not direct shipping code.
- Consider `shadermatch` later as an optional scoring backend for Shadertoy-style
  candidates, not as the main Godot shader judge.

Verified sources:

- https://mbaradad.github.io/shaders21k/
- https://huggingface.co/datasets/Vipitis/Shadereval-inputs
- https://huggingface.co/spaces/Vipitis/shadermatch
- https://mcpservers.org/servers/wilsonchenghy/ShaderToy-MCP

### 3. StableMaterials

Status: test for PBR material generation, not spell shaders.

Why it matters:

- Generates tileable PBR maps: basecolor, normal, height, roughness, metallic.
- Has public Hugging Face weights and pipeline code.
- The LCM path can run in a small number of steps.

How it overlaps:

- The repo already has a strong AAA texture pipeline and Material Anything path.
- StableMaterials is a candidate alternative or ensemble member for static
  surface materials.

Local action:

- Add it to the texture pipeline backlog, not the shader lab mainline.
- Test it on 3 materials that are hard for current tools: magical metal, rune
  stone, and wet organic ground.
- Compare against current `aaa_texture.py` outputs using existing seam/PBR QA.

Verified source:

- https://huggingface.co/gvecchio/StableMaterials

### 4. Chord / Ubisoft Generative Base Material

Status: test when installing ComfyUI nodes/weights is worth the time.

Why it matters:

- Open prototype for PBR material estimation from generated texture images.
- Uses MatSynth-trained open weights.
- Explicitly targets game base-material workflows.

Limitations:

- Ubisoft's own writeup says output is promising but not AAA-production-ready.
- Strong specular/metal cases remain difficult.
- The system is material-map generation, not live animated shader generation.

Local action:

- Put it behind current texture QA.
- Treat it as a candidate Path B material extractor/generator.
- Do not let it distract from spell shader template expansion.

Verified sources:

- https://ubisoft-laforge.github.io/world/chord/
- https://www.ubisoft.com/en-us/studio/laforge/news/1i3YOvQX2iArLlScBPqBZs/generative-base-material-an-open-source-prototype-for-pbr-material-estimation-debuting-at-siggraph-asia-2025

### 5. Godot AI MCP / Hi-Godot

Status: watch/test after Godot CLI rendering is validated.

Why it matters:

- It is Godot-specific and recent.
- The asset library entry claims MCP tools for scenes, nodes, materials,
  particles, themes, tests, and editor data.
- It could become useful for higher-level scene/VFX assembly and live editor
  inspection.

Why it is not first:

- Our current blocker is not "can an agent create nodes in the editor"; it is
  shader quality, preview fidelity, and ranking.
- Adding an MCP editor bridge before the render harness is stable would increase
  moving parts.

Local action:

- Revisit after `shader_godot_render.py` successfully renders promoted queues.
- If tested, limit first pass to creating a scene with a generated `ShaderMaterial`
  and a `GPUParticles` preset.

Verified source:

- https://godotengine.org/asset-library/asset/5050

## Items To Deprioritize

- Commercial text-to-VFX image/video generators for live shader code. They may be
  useful for flipbook sprites or references, but they do not produce maintainable
  Godot shaders.
- Unity Shader Graph generators as a main path. They validate demand, but add a
  translation layer and do not solve Godot runtime acceptance.
- Full VLMaterial/MultiMat dependency in the short term. They matter for material
  research, but current outputs target Blender/Substance-style graphs rather than
  direct Godot spell VFX.
- Arbitrary GLSL evolution before a DSL exists. It will produce novelty and many
  compile/runtime failures, but not a controlled asset library.

## Changes To Make In The Local Roadmap

Add these near-term backlog items:

1. **ShaderToy external-reference lane**
   - Define license rules.
   - Prototype read-only ShaderToy candidate ingestion.
   - Render through a Shadertoy/WebGL/WGPU runner.
   - Convert only permissive, simple single-pass examples into Godot templates.

2. **LLM mutation/crossover layer**
   - Let LLMs propose parameter-group mutations first.
   - Add code-block mutation only after a DSL/include system exists.
   - Keep compile/render checks mandatory.

3. **Better critic**
   - Add CLIP/DINO or LPIPS scoring as an optional dependency.
   - Add temporal reference features over flipbooks.
   - Keep deterministic scoring as the baseline.

4. **PBR material candidate tests**
   - StableMaterials.
   - Chord.
   - MaterialPalette if photo-to-PBR becomes a priority.

5. **Godot editor integration**
   - Test Godot AI MCP only after CLI render acceptance is stable.

## Bottom Line

The survey does not overturn the current plan. It strengthens it.

Current pipeline:

`Godot templates -> batch render -> metric review -> reference/evolution -> promotion queue -> human review`

Research-backed future:

`Godot templates + constrained DSL + ShaderToy/RAG inspiration + optional learned critic + Godot engine acceptance`

The immediate engineering work is still template quality, Godot render
validation, and a cleaner external-reference lane.
