# Intake Review - deep-research-report (5)

Date: 2026-05-06  
Original path: `C:\Users\josep\Downloads\deep-research-report (5).md`  
Preserved copy: `D:\assets\research\deep_research_report_5_image_to_shader.md`

## Short Verdict

This report is useful, but it is mostly about **image-to-material** and
**image-to-bounded-representation** work, not animated spell/VFX shader creation.
Its core recommendation is correct: do not think of "2D image -> shader" as one
task. Treat it as a ladder of possible representations.

For this project, that ladder maps cleanly to the pipeline we already started:

| Representation | Local equivalent | Action |
|---|---|---|
| Parameter set for an existing shader | `request.json` params for `.gdshader` templates | Already implemented; expand it |
| PBR/SVBRDF maps | `pipelines/textures` AAA material workflow | Already strong; test extra generators there |
| Bounded procedural graph/DSL | Future Cauldron-derived shader DSL and possible MaterialX/Material Maker path | Build after templates |
| Raw GLSL/HLSL/Slang source | External/RAG branch plus compile/render checks | Keep constrained |
| Neural material | Research watchlist | Do not build around yet |

The report strengthens the current plan rather than changing it. It says the
same thing in more material-focused language: **a handcrafted library plus
retrieval, repair, validation, and review is more defensible than one-shot
image-to-code generation.**

## What Is Already Covered Locally

### Parameter-Set Generation

The report says parameter sets for existing shaders are the highest-feasibility
target. This is exactly what the current shader lab does.

Current files:

- `D:\assets\art_lab\tools\shader_batch_review.py`
- `D:\assets\art_lab\tools\shader_evolve.py`
- `D:\assets\art_lab\tools\shader_promote.py`
- `D:\assets\art_lab\shaders\templates\*.gdshader`

Current local representation:

- `template`
- `params`
- `preview`
- `role`
- `review`
- `reference_review`

Needed improvement:

- Make parameter schemas more explicit and versioned.
- Store performance expectations and intended use per template.
- Add tags for effect family, silhouette, motion type, palette, and runtime cost.

### PBR Maps

The report spends a lot of time on image-to-PBR and SVBRDF systems. This should
not be folded into the live spell shader pipeline. It belongs mostly in:

`D:\assets\pipelines\textures\`

The current texture workflow already covers the practical "image/prompt -> PBR
maps -> Godot material" path better than the shader lab does.

Useful additions from the report:

- Add **MaterialPicker** to the watch/test list for multimodal material-map
  generation.
- Keep **ControlMat** as a research reference for tileability/noise rolling, but
  do not depend on it unless code/weights are available.
- Treat **Generative Neural Materials** as a watch item, not a production target.

### Template-Driven Shader Code

The report says raw shader-code generation has low feasibility without
verification. That matches the local decision:

- Do not ask an LLM to write arbitrary Godot shader code as the default path.
- Let LLMs fill request JSON and propose bounded template/DSL changes.
- Compile and render every code-bearing candidate.

Current gap:

- We still need a true DSL/expression layer ported from Shader Cauldron.

## Useful New Deltas

### 1. Add A Formal "Representation Ladder"

The status docs should explicitly separate these lanes:

1. **Effect parameter lane**: current Godot templates and `request.json`.
2. **Effect DSL lane**: future Cauldron-style expression grammar compiled to
   Godot.
3. **External GLSL lane**: Shadertoy/RAG/import with license tracking.
4. **PBR material lane**: texture maps and StandardMaterial3D inputs.
5. **Material graph lane**: MaterialX / Material Maker / Blender nodes.
6. **Neural material lane**: research only.

This prevents future research from collapsing everything into "shader
generation."

### 2. Consider MaterialX/OpenPBR For Surface Materials, Not Spells

MaterialX/OpenPBR are real standards and should be tracked, but they are not the
right immediate IR for animated 2D spell effects.

Recommended split:

- Use the **internal Godot template schema** as the canonical IR for spell/VFX,
  UI effects, decals, and quick runtime shaders.
- Evaluate **MaterialX/OpenPBR** for surface materials, generated PBR libraries,
  terrain/world materials, and interchange.

Do not make MaterialX a blocker for the current shader lab. It would slow down
the live effect workflow without improving immediate output quality.

Verified sources:

- https://materialx.org/Specification.html
- https://developer.nvidia.com/blog/unlock-seamless-material-interchange-for-virtual-worlds-with-openusd-materialx-and-openpbr/

### 3. Add MaterialPicker To The PBR Test Backlog

MaterialPicker is a SIGGRAPH 2025 Adobe Research system for multimodal material
generation using a Diffusion Transformer. It treats material maps like frames in
a video sequence and supports text and image-crop conditioning.

Why it matters:

- Stronger fit for real photos with perspective distortion, off-angle surfaces,
  and partial occlusion.
- Good candidate for future photo-to-PBR material work.

Why it is not immediate:

- It is research, not a confirmed local CLI tool in this repo.
- It generates material maps, not animated spell shaders.

Verified source:

- https://research.adobe.com/publication/materialpicker-multi-modal-dit-based-material-generation/

### 4. Add Generative Neural Materials To Watchlist

Generative Neural Materials is notable because it generates a neural material
representation rather than only PBR maps. Adobe reports a universal 16-channel
feature-texture basis, a 150k neural-material dataset, and real-time decoding at
1024x1024.

Why it matters:

- This is the closest item in the report to "learned runtime shader material."

Why it is not immediate:

- Editability is weaker than graphs/templates.
- Godot runtime integration would be custom.
- It does not solve spell/VFX authoring.

Recommended action:

- Watch. Do not build around it until code/weights/runtime constraints are clear.

Verified source:

- https://research.adobe.com/publication/generative-neural-materials/

### 5. Track Slang/Slang.D For Future Cross-Backend Or Differentiable Work

The report mentions Slang as a more modern low-level code path than old
translation chains. This is valid, especially for HLSL/Vulkan/DirectX-oriented
work or differentiable shader experiments.

For this project:

- Godot is the target, so Slang is not first-week work.
- Slang may matter later if we build a cross-backend shader DSL or
  differentiable optimization tools.
- Slang.D is research-credible for differentiable shader programming, but not
  needed for current Godot `canvas_item` effect generation.

Verified sources:

- https://github.com/shader-slang/slang
- https://research.nvidia.com/labs/rtr/publication/bangaru2023slangd/

## Backlog Changes From This Report

### Add To Shader Lab

- Versioned template parameter schema.
- Per-template metadata:
  - intended role
  - supported render target
  - expected coverage range
  - motion type
  - exposed parameter ranges
  - rough performance tier
  - known failure modes
- Representation ladder in docs.
- Future source-code validation hooks:
  - Godot compile result
  - render result
  - frame-time/performance estimate if available

### Add To Texture/PBR Pipeline

- MaterialPicker watch/test entry.
- ControlMat watch entry.
- Generative Neural Materials watch entry.
- Optional MaterialX/OpenPBR export experiment for generated PBR surfaces.

### Add To Dataset/Future Training Plan

The report makes one important dataset point: if we want image-to-template,
image-to-graph, or image-to-shader behavior, we should synthesize our own paired
data from our own library.

Local implication:

- Once we have enough accepted templates/candidates, render them under randomized
  palettes, camera crops, scales, lighting/backgrounds, and masks.
- Store `(reference image, params, template, shader source, render metrics)`.
- Use that as the clean local corpus for retrieval, ranking, or fine-tuning.

This is much safer than training on unclear Shadertoy/community data.

## Items To Avoid

- Do not treat arbitrary image-to-GLSL as feasible production tech.
- Do not force MaterialX/OpenPBR into the live spell shader path.
- Do not spend near-term engineering on neural materials for Godot runtime.
- Do not build a cross-engine shader-code exporter before the Godot path works.
- Do not train on noncommercial material datasets if commercial use is a goal.

## Recommended Next Actions

1. Update `SHADER_WORKFLOW_STATUS.md` with the representation ladder.
2. Add template metadata/schema files beside the current `.gdshader` templates.
3. Keep `shader_evolve.py` focused on parameter search until the DSL exists.
4. Add MaterialPicker / Generative Neural Materials / Slang to the watchlist.
5. Test MaterialX/OpenPBR only through the material/PBR surface pipeline, not the
   spell shader pipeline.

## Bottom Line

This report is strongest as a **materials architecture** reference. Its central
message is useful: image-to-shader should mean choosing the right intermediate
representation, then validating the output.

For the Godot art lab, the immediate representation remains:

`template + params + preview + score + reference/evolution + promotion`

The future representation should become:

`template + params + bounded DSL blocks + provenance + performance metadata`

MaterialX/OpenPBR and neural materials belong on the surface-material roadmap,
not in the critical path for animated spell/effect shader generation.
