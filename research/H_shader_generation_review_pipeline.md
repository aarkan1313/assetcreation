# H - Shader Generation And Review Pipeline Deep Dive

Date: 2026-05-06

## Executive Recommendation

Do not build the asset factory around a hosted "AI shader generator." Build a
first-party shader generation and review lab: seeded procedural templates,
LLM-written parameter/request JSON, local mutation, engine rendering, non-OCR
image metrics, reference-set scoring, and small promotion queues for human
review.

The old `shader-cauldron-v6.html` was directionally right. It generated GLSL
from a procedural expression grammar, exposed knobs, mutated parameters, compiled
in WebGL, exported Godot code, saved screenshots, and auto-cycled. The missing
piece was a rigorous review harness. It let a human browse many outputs, but it
did not create durable batch artifacts, did not rank from objective pixel/motion
signals, did not compare against style references, and did not separate broad
exploration from short human review.

The new Art Lab should be "Cauldron plus CI": every shader candidate becomes a
folder with `.gdshader`, `.tscn`, `request.json`, PNG frames, flipbook, metrics,
and provenance. LLMs operate on these structured artifacts. Human review sees
only promoted shortlists.

## What Current SOTA Actually Offers

### LLM Shader Generators

ShaderGPT by 14islands is the clearest public current example. The live site
generates GLSL from natural language, previews it in WebGL, exposes model choice
and temperature, and provides copyable code. Their own February 2025 writeup is
more useful than the tool marketing: they report syntax errors, performance
issues, and the core failure mode that LLMs can assemble shader code but cannot
judge whether the visual output is aesthetically good. They found Claude most
consistent, prompt tuning important, and "plan first, then code" helpful.

Source: https://www.14islands.com/journal/ai-generated-glsl-shaders  
Live tool: https://shadergpt.14islands.com/

This supports using LLMs as code/template assistants, not as autonomous final
judges. It also supports the old Cauldron pattern: generate many variations,
compile immediately, and let parameters do much of the work.

ShadAR is a 2026 research paper about LLM-generated shaders for AR visual
perception transforms. It demonstrates real-time natural-language shader
generation and compilation, but the scope is viewport perception filters, not
game-ready spell/world/UI effects with art-direction ranking.

Source: https://huggingface.co/papers/2602.17481

### VLM / Node-Graph Material Synthesis

VLMaterial is the most relevant 2025 proof that the "image -> procedural
program" direction is real. It fine-tunes a VLM to generate Python programs for
procedural material node graphs, then verifies and renders candidates. The
repository is MIT for code and weights, but the Blender procedural material
dataset is CC BY-NC 4.0, the recommended training hardware is far beyond a
single laptop for full fine-tuning, and the repo is explicitly an archival paper
reference rather than an actively maintained product. It is a serious research
reference, not a turnkey asset-factory dependency.

Source: https://github.com/mit-gfx/VLMaterial

MultiMat is the April 2026 follow-up signal from Adobe Research: material node
graphs should be treated as visual and textual programs, and constrained search
is used to keep generated graphs statically correct. This supports our local
architecture strongly: constrained DSL/templates, renderer-in-loop validation,
and search over valid graph/program space. As of this pass, it is a paper page,
not a ready CLI tool to install.

Source: https://research.adobe.com/publication/multimat/

MaterialX is the practical interchange standard to watch for the material side.
MaterialX ShaderGen can generate GLSL, OSL, MDL, and MSL from node graphs; the
project's September 2025 1.39.4 release added WGSL support and more procedural
nodes. That makes MaterialX a good long-term export/interchange target for
ground/world/UI materials, but it does not replace Godot-first spell templates.

Sources: https://materialx.org/Tools.html and https://materialx.org/index.html

### Datasets And Evaluation

Vipitis/Shadereval-inputs on Hugging Face provides 467 Shadertoy-derived
function completion inputs with parsed GLSL functions and license fields. It is
useful for evaluation and mining idioms, but too small and too licensing-sensitive
to use blindly as a production generation base.

Source: https://huggingface.co/datasets/Vipitis/Shadereval-inputs

`shaders21k` is the larger upstream Shadertoy/TwiGL corpus: roughly 21,000
OpenGL fragment shader programs with rendered outputs, originally introduced for
procedural-image representation learning. It is valuable for retrieval and idiom
mining, but it should be treated as a research/reference corpus until licensing
and direct-code reuse rules are explicit.

Source: https://mbaradad.github.io/shaders21k/

Vipitis `shadermatch` is a Hugging Face/evaluate metric that renders
Shadertoy-style code through WGPU and compares the visual output. It is useful as
an optional critic for Shadertoy-format experiments. It should not replace the
Godot role gate because it measures code/image similarity, not gameplay fitness,
performance, or Godot compatibility.

Source: https://huggingface.co/spaces/Vipitis/shadermatch

ArtifactsBench is not shader-specific, but its design is relevant: render the
artifact, evaluate visual and interactive results, and preserve intermediate
judge outputs for reproducibility. The lesson for this project is not "use a
multimodal judge for everything"; it is "never evaluate generated visual code
only from source text."

Source: https://artifactsbenchmark.github.io/

### Renderer And Conversion Tools

Godot's own docs say Godot shading language is GLSL-based and provide direct
guidance for converting GLSL, Shadertoy, and Book of Shaders code. Shadertoy's
`mainImage` maps into Godot's `fragment`, with `fragColor`/`fragCoord`
represented by Godot built-ins like `COLOR` and `FRAGCOORD`.

Source: https://docs.godotengine.org/en/stable/tutorials/shaders/converting_glsl_to_godot_shaders.html

Godot's command line supports `--script`, `--path`, and `--headless`. The docs
describe headless mode as `--display-driver headless --audio-driver Dummy` and
useful with scripts. That is enough to justify a CLI render wrapper, though in
practice shader screenshot capture may need `--no-headless` if the GPU backend
does not render correctly headless on Windows.

Source: https://docs.godotengine.org/en/latest/tutorials/editor/command_line_tutorial.html

`pygfx/shadertoy` is a practical Python path for ShaderToy-style GLSL rendering:
it supports `Shadertoy.from_id`, `from_json`, offscreen snapshots, frame capture,
and a CLI. It is not Godot-native, but it is useful for mining/adapting
Shadertoy-compatible GLSL and building a render-and-score path before Godot
conversion.

Source: https://github.com/pygfx/shadertoy

ShaderToy-MCP is a read/search MCP server for Shadertoy. It is interesting
because it gives an LLM structured access to real shader examples, but it should
be used only in a reference lane with license tracking. It is not a replacement
for first-party templates.

Source: https://mcpservers.org/servers/wilsonchenghy/ShaderToy-MCP

AI Co-Artist is the most directly relevant research pattern for animated GLSL
effects: LLM-assisted evolutionary mutation and crossover of shader animations.
The local `shader_evolve.py` intentionally implements the safer first step:
evolution over valid Godot template parameters rather than arbitrary GLSL.

Source: https://huggingface.co/papers/2512.08951

SHADERed has a Godot shader plugin with canvas shader support, syntax
highlighting, autocomplete, error reporting, debugging, and custom uniforms. It
is valuable as a manual technical-artist debugger, but it is not the primary
batch automation layer.

Source: https://shadered.org/plugin?id=godotshaders

Material Maker remains important for procedural materials, ground/world detail,
and node-based texture authoring. Its repository is MIT, Godot-based, and at
release 1.6 as of April 18, 2026. It is a texture/material graph tool, not a
spell shader generator, but its graph/source format and GLSL node ideas are
worth borrowing.

Source: https://github.com/RodZill4/material-maker

Godot AI 0.4.3 is a recent Godot asset-library MCP bridge with tools for scenes,
nodes, materials, particles, UI/themes, project settings, and tests. This is
worth watching for editor integration once CLI rendering is validated, but the
current shader bottleneck is quality/ranking rather than editor automation.

Source: https://godotengine.org/asset-library/asset/5050

### PBR Material Generators Adjacent To Shader Work

StableMaterials and Chord are not live VFX shader generators, but they are good
Path B candidates for ground/world/UI material inputs.

StableMaterials has public Hugging Face weights and pipeline code for tileable
PBR material maps: basecolor, normal, height, roughness, and metallic.

Source: https://huggingface.co/gvecchio/StableMaterials

Chord / Generative Base Material is Ubisoft La Forge's SIGGRAPH Asia 2025
open-source prototype for PBR material estimation from generated texture images.
Ubisoft's own writeup says the output is promising but not yet AAA-production
quality, especially around strong specular/metal cases. That makes it a test
candidate, not a replacement for the current texture QA pipeline.

Sources: https://ubisoft-laforge.github.io/world/chord/ and https://www.ubisoft.com/en-us/studio/laforge/news/1i3YOvQX2iArLlScBPqBZs/generative-base-material-an-open-source-prototype-for-pbr-material-estimation-debuting-at-siggraph-asia-2025

MaterialPicker is a SIGGRAPH 2025 Adobe Research system that uses a Diffusion
Transformer for multimodal material generation from text and/or image crops. It
is most relevant to photo-to-PBR and distorted/off-angle material capture. It is
not a live animated shader generator.

Source: https://research.adobe.com/publication/materialpicker-multi-modal-dit-based-material-generation/

Generative Neural Materials is a SIGGRAPH 2025 Adobe Research system for
image-conditioned neural material generation with a universal 16-channel
feature-texture basis and reported real-time decoding at 1024x1024. This is a
watch item for learned runtime materials, not a near-term Godot effect-shader
dependency.

Source: https://research.adobe.com/publication/generative-neural-materials/

OpenPBR and MaterialX support the "standard material / graph IR" lane.
MaterialX's current specification is v1.39, and OpenPBR is best understood as an
uber-shader parameterization for surface materials. This is useful for
interchange and PBR surface libraries; it should not block Godot-first spell VFX
templates.

Sources: https://materialx.org/Specification.html and https://developer.nvidia.com/blog/unlock-seamless-material-interchange-for-virtual-worlds-with-openusd-materialx-and-openpbr/

Slang/Slang.D matter if the project later needs cross-backend shader generation
or differentiable shader optimization. For the current Godot 4.5 `canvas_item`
lab, Slang is a watch item rather than a first integration target.

Sources: https://github.com/shader-slang/slang and https://research.nvidia.com/labs/rtr/publication/bangaru2023slangd/

## Old Project Findings

The closest match to the user's older shader app is:

`C:\Users\josep\Downloads\shader-cauldron-v6.html`

A copy is preserved at:

`D:\assets\art_lab\legacy\shader-cauldron-v6.html`

It is a single-file WebGL procedural shader generator dated 2026-02-11. It has
style pools, pattern generators, randomization retries, mutation/tweak logic,
auto-cycling, sliders, history thumbnails, favorites, screenshots, GLSL editing,
and Godot 2D/3D export. It should be treated as a design reference and source of
pattern ideas, not as the new production system.

Related older assets:

- `C:\Users\josep\Documents\Newest\shader-training-pipeline`
- `C:\Users\josep\moom\lenovo build\ShaderViewer`
- `C:\Users\josep\Downloads\spell-effect-library*.html`
- `C:\Users\josep\jk engine\archived\spells\...`

The November 2025 shader-training pipeline is interesting because it already
scraped Shadertoy data and screenshots for Qwen2.5-VL LoRA training. The risk is
that a fine-tuned visual-language model may learn style/code associations but
still not produce production-grade, license-clean, Godot-ready shaders. It is a
research branch, not the mainline.

## Proposed System

The pipeline should have five layers.

1. Template/kernel library:
   Godot `.gdshader` templates with explicit uniforms and roles. Examples:
   aura, beam, projectile, portal, shield, dissolve, ground overlay, UI glow,
   world water/heat haze, force field, decal, impact ring, and particle process
   shaders.

2. Generator:
   Seeded parameter sampling, local mutation around winners, and later a
   Cauldron-style procedural expression grammar for new code sections. LLMs can
   propose new templates, but accepted templates should be checked into the
   library and exercised by the batch harness.

3. Render:
   CPU proxy renderers for fast exploration where practical; Godot CLI rendering
   for final acceptance. ShaderToy/WGPU rendering can be a separate importer path
   for raw GLSL experiments.

4. Review:
   Objective metrics first: coverage, center, edge energy, colorfulness,
   contrast, motion, flicker, clipping, silhouette aspect. Then optional
   reference-set scoring against curated examples. LLMs read metrics and
   JSON packets; they should not be asked to OCR screenshots.

5. Promotion:
   Copy only high-scoring, diverse candidates into a review queue. The queue
   should include preview/flipbook, request JSON, shader source, mutation command,
   and source batch.

## Review Of The Pasted Chat Notes

Most of the notes are directionally right, but they need to be scoped.

- Text-to-shader tools exist, but they are best treated as ideation/debug helpers.
  They can produce GLSL snippets and Shadertoy-style sketches; they do not solve
  taste, Godot integration, performance, or asset-library consistency.
- VLMaterial validates constrained program synthesis. The takeaway is not "clone
  it and depend on it tomorrow"; it is "use a narrow DSL or template system and
  render every candidate."
- MultiMat validates multimodal node-graph search. The local equivalent is
  template families plus reference-driven evolution until a real open tool lands.
- Evolutionary search is worth adding now, but only over valid shader templates
  and parameters. Evolving arbitrary GLSL expressions too early will waste time
  on compile failures and noisy novelty.
- Path A / Path B is still the right long-term split for materials: Path A is
  editable procedural shader/template code; Path B is texture-map extraction or
  generated PBR maps used as reference targets. The current shader lab implements
  the render/score/search side first. Texture-map extraction already lives mostly
  in the AAA texture workflow.
- LPIPS or CLIP/DINO image embeddings would improve reference scoring, but the
  first implementation intentionally uses cheap deterministic features so it can
  run locally without downloading another model.

## Review Of `research/shades.md`

`shades.md` is aligned with the current architecture but adds useful candidates
to the backlog. Its strongest contribution is naming the external-reference
lane: ShaderToy-MCP, `shaders21k`, and `shadermatch`. Those should be tested
behind license/provenance rules and used to improve first-party templates, not
to paste community shader code into production.

The second useful contribution is separating live VFX shaders from static PBR
material generation. StableMaterials and Chord should be evaluated by the texture
pipeline, while the shader lab stays focused on live Godot templates, DSL blocks,
rendered flipbooks, and promotion queues.

Detailed intake review: `D:\assets\research\shades_intake_review.md`

## Review Of `research/deep_research_report_5_image_to_shader.md`

This report reframes "image to shader" as a representation ladder:

- parameter sets for existing shaders,
- PBR/SVBRDF maps,
- bounded procedural graphs or DSL programs,
- raw shader source code,
- neural material representations.

This maps well to the local architecture. The current shader lab already owns
the first lane through Godot templates and `request.json`. The texture pipeline
owns the PBR-map lane. The next shader-lab engineering step is not MaterialX or
neural materials; it is richer template metadata and a bounded Cauldron-style DSL
that can be compiled, rendered, scored, and promoted.

Detailed intake review: `D:\assets\research\deep_report_5_intake_review.md`

## Implemented In This Pass

Added:

- `art_lab/tools/shader_promote.py`
  Creates small human review queues from one or more batches, with diversity
  filtering and mutation commands.

- `art_lab/tools/shader_evolve.py`
  Evolves valid template parameters toward curated reference images using the
  normal non-OCR role gate plus reference similarity as selection pressure.

- `art_lab/tools/shader_reference_score.py`
  Scores candidates against curated reference image folders.

- `art_lab/tools/shader_godot_render.py`
  Godot CLI wrapper for engine-rendered frames and flipbooks when a Godot binary
  is available.

- `art_lab/shaders/prompts/llm_shader_operator.md`
  A concrete operating loop for LLM-driven generation without OCR dependence.

- `art_lab/tools/shader_lab_index.py`
  Builds a static dashboard over recent batches, review queues, references,
  templates, operator prompt, and recovered Cauldron.

- `art_lab/legacy/FOUND_OLD_SHADER_WORKFLOW.md`
  Local inventory of the older Cauldron and related shader assets.

## Near-Term Adoption Sequence

This week:

1. Run a broad 80-candidate batch using the current five templates.
2. Promote a 12-24 item review queue with `shader_promote.py`.
3. Pick 2-5 winners and run local mutation batches at `0.10-0.16` strength.
4. Add a small curated reference set for one target, such as storm projectile or
   occult portal, then run `shader_evolve.py` for 3-5 generations.
5. Run `shader_reference_score.py` on broad and evolved batches to compare style
   proximity without changing the base quality gate.
6. Provide or install a Godot 4.5 executable path and run `shader_godot_render.py`
   against the promoted queue.

Next:

- Add ground/world/UI template families.
- Port useful expression families from Shader Cauldron into the Python batch
  generator.
- Add a clean HTML dashboard over review queues.
- Audit the old Shadertoy training pipeline for license/data quality before any
  fine-tuning work.
