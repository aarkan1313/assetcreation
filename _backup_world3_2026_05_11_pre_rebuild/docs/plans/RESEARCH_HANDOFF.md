# Research Handoff — Asset Pipeline Deep Exploration

This is a self-contained briefing for an LLM/researcher to deeply explore the SOTA tooling landscape across our asset categories and return actionable recommendations. Read this whole file first, then pursue your assigned section.

---

## Project context

We're building a **complete asset factory** for a 2D-leaning game (Godot 4.5 / C# / "JK Engine / TLTE"). Right now, characters are mature: Meshy (cloud) + Trellis2 (local) for image→3D, multiple SOTA neural riggers (SkinTokens 2026, RigAnything, MagicArticulate), AnimateAnyMesh for text-to-mesh-animation, plus a Blender-based bake-to-sprite-atlas pipeline. ~33 characters baked end-to-end.

Other categories are infants: terrain is procedural FBM noise; textures take an input PNG and run a Sobel-derived normal; props chains existing tools; spells/VFX is a wide-but-shallow physics lab (17 engines installed at `D:\spell lab\`, never tested in depth). UI/audio/game-data don't exist yet.

The user wants **same depth of investigation** for every category as we did for characters: survey multiple options, test them, document tradeoffs, pick winners. We don't need identical tool counts everywhere — we need identical decision quality.

The user is **not technical at the JSON/CLI level**. The user works through an LLM (me, or a successor). Outputs need to be:
- Visually inspectable (renderable previews, video, image atlases)
- Invokable from natural-language prompts (the LLM runs the tools, the user describes intent)
- Documented well enough that a future LLM can pick it up cold

The user is genuinely considering rebooting their game using the lessons from building the factory. So **the factory is the project** for now — not a means to a specific game.

## Hardware

- RTX 5090 Laptop (sm_120 Blackwell, 24 GB VRAM)
- D: drive: 90+ GB free, the working volume (most pipelines live here)
- C: drive: 55 GB free, hosts the HF cache
- WSL2 Ubuntu 24.04 fully working with conda envs for Python AI tooling
- Native Windows Python 3.12, Blender 5.1, Node.js 24

## Existing pipelines (skim quickly)

| Category | Status | Notes |
|---|---|---|
| Characters | Mature | Meshy + Trellis2 image→3D, SkinTokens/RigAnything/MagicArticulate riggers, AnimateAnyMesh, Blender sprite bake |
| Terrain | Toy procedural | `../../pipelines/terrain/generate_heightmap.py` — FBM noise + 4 biomes + thermal erosion + 16-bit PNG. No image input, no hydraulic erosion, no splatmaps, no engine integration |
| Textures | Toy postprocessing | `../../pipelines/textures/process_texture.py` — input PNG → albedo + Sobel normal + heuristic roughness + Godot tres. No generation, weak seamless |
| Props | Untested wrapper | `../../pipelines/props/generate_props.py` — chains Meshy + preprocess. No scattering, no LoD, no Godot scene export |
| VFX (spells) | 17 engines installed, none exercised in depth | At `D:\spell lab\` — Taichi, Warp, LiquidFun, SPlisHSPlasH, PhiFlow, MuJoCo, Brax, JAX-MD, Genesis, Mantaflow, PhysX, GPU-Falling-Sand-CA, Sandspiel, Powder Toy, DiffTaichi, sailfish, voronoishatter |
| UI/icons | None | Blank slate |
| Audio | None | Blank slate |
| Game data | None | Blank slate |
| Scenes (composite) | None | Future |

## Project docs to read

- `D:\assets\TOOLS_INDEX.md` — full directory + every script
- `D:\assets\PIPELINE_GUIDE.md` — character pipeline walkthroughs
- `D:\assets\../audits/REVIEW.md` — bugs found and tool comparison
- `D:\assets\ROADMAP.md` — current plan (what you're contributing to)
- `D:\assets\animators\PIPELINE_RESEARCH.md` — research that produced the character rigger choices (good template for what we want from you)

---

## What I need from you (the researcher)

For your assigned category (see sections below), produce a **research report** with:

### 1. Tool/method survey (breadth)
List every viable approach. Don't filter early. Include:
- Open-source local tools
- Proprietary cloud APIs
- ChatGPT-driven workflows (where the human/LLM generates inputs and the local pipeline processes them)
- Procedural / hand-coded approaches
- Hybrid combinations

For each, include: project link (GitHub/website), license, last-meaningful-update date, install requirements (especially: does it need a specific torch/CUDA combo? Will sm_120 work?), and a one-sentence "what makes it different."

### 2. SOTA depth (what's actually best in 2026)
Identify which methods are genuinely state-of-the-art vs. which are old papers people still cite. Mention:
- Recent (2025-2026) papers/releases
- Benchmark numbers if any
- Where it's been adopted in production (game studios, big AI labs, popular tools)

### 3. Test plan
For the top 3-5 candidates, propose how we'd test them:
- One representative input
- Concrete success criteria (what does "works" look like?)
- Estimated install time + first-run time
- Specific failure modes to watch for
- Whether ChatGPT-driven inputs would work (since the user can provide ChatGPT-generated images/sketches/text)

### 4. Combinations / layering
The user said it correctly: "there are layers." For asset categories, we usually compose multiple tools:
- e.g. terrain = elevation source + erosion + biome shaping + splatmap generation + texture pairing + vegetation placement
- e.g. textures = generation + de-lighting + tiling fix + variant generation + PBR map derivation

Suggest **end-to-end recipes** that combine 3-5 tools. Examples:
- "Local terrain workflow: Worley + Diamond-Square + Lague hydraulic erosion (Python port) + auto-splatmap from height/slope + Polyhaven CC0 textures pulled from API"
- "Cloud-first terrain: Mapbox DEM API for real geography + filtering + custom biome paint over top"

### 5. LLM/UX considerations
This is the unusual constraint. The user works through me (an LLM). I drive the tools. So:
- Are there tools with **good Python/CLI interfaces** I can drive directly?
- Are there tools that **only work via GUI** (like Substance Designer)? Those are a problem unless they have headless modes.
- Does the tool produce **inspectable artifacts** (PNG/JSON I can show in chat)?
- Is the install path clean enough that I won't burn 4 hours on it?

### 6. Honest tradeoffs
Don't recommend something just because it's the most-starred. The user is a solo dev. I'm an LLM driving tools through chat. We need:
- Things that work today, not "promised in a paper"
- Things with clear install instructions, not "tested only on the author's H100 cluster"
- Things that produce outputs we can use in Godot 4.5, not "proprietary engine plugin"

### 7. A concrete recommendation
Once you've done the survey: pick a **starting kit** — 2-4 tools that, together, would let us build the category to "B+ depth" matching characters. Justify the picks. Order them by recommended adoption sequence.

---

## Research assignments (pick one or more)

### Assignment A — Terrain & worldgen (highest priority)
**Scope:** elevation/heightmap generation, biome maps, splatmaps, vegetation density, prop placement, scene assembly. Both **local-scale** (a single playable chunk) and **world-scale** (continent or region map shown in-game).

**Specific questions:**
- What's the SOTA for **AI-generated terrain heightmaps** in 2026? Diffusion models? Transformer-based? GANs?
- What's the best **open-source hydraulic erosion** library? Sebastian Lague's code is famous but is there something better?
- For **world maps** (the kind shown on a UI map screen), what generates them best? Wave Function Collapse? Voronoi-based? Tectonic plates simulators (Worldengine, etc.)?
- For **biome maps from a heightmap**, what's the cleanest auto-pairing of climate models (temp + moisture → biome)?
- Are there **terrain repositories** like Polyhaven for free CC0 heightmaps?
- Is **Mapbox or USGS DEM** still the best source for real-world elevation data? Free tiers?
- Tools like **Gaea**, **World Machine**, **Wonderland** — do they have CLI/headless modes?
- For **Godot 4.5 specifically**, what's the recommended workflow? `Terrain3D` plugin? Custom shader?
- **AI tools generating game worlds** that emerged 2025-2026 — what's real vs hype?

**Required deliverable:** terrain SOTA report following the structure above. Specifically include a "starter kit" recommendation: 3-5 tools that together give us local + world generation, biomes, erosion, and Godot integration.

---

### Assignment B — Tileable textures (high priority)
**Scope:** PBR materials (albedo, normal, roughness, metallic, AO, height) for environment surfaces — stone, dirt, grass, wood, fabric, metal. Tileable, game-ready, multiple style/age variants.

**Specific questions:**
- **Polyhaven, AmbientCG, ShareTextures, FreePBR, CGBookcase** — which has the best programmatic API/download? Free tier?
- **AI texture generation** — best 2026 tools? FLUX, SD 3.5, ControlNet for tiling, **MaterialGAN**, **Diffusion Material**, **Hyper3D**, Substance 3D Stager API. Local install vs cloud?
- **Seamless tiling** — what's the SOTA algorithm? Histogram matching? Patch-based (PatchMatch)? Diffusion-based reroll? Compare to our current cross-blend.
- **De-lighting** photo references — DELIGHTING-NET? Substance's de-light? Anything open-source that works?
- **PBR map derivation** from albedo — what's the SOTA for "give me a normal/rough/AO from this color image"? Is it still Sobel + heuristics, or are there ML-based estimators that work well?
- **Texture variation** (clean → mossy → wet → cracked) — best workflow?
- **Triplanar / decal / atlas** strategies for terrain blending in Godot 4.5?

**Required deliverable:** textures SOTA report. Include a "starter kit" of: one CC0 source for free assets, one AI generator for custom textures, one PBR-map estimator, one seamless-fix algorithm.

---

### Assignment C — VFX baking lab (medium priority, big scope)
**Scope:** the SpellLab v2 / VFX Lab rewrite. We have 17 physics engines installed at `D:\spell lab\repo-lab\` — most are untested at depth. Need to: (a) characterize what each is actually good at, (b) recommend the 2-4 we should use as primary tools, (c) propose an authoring + baking + Godot-export workflow.

**Engines installed:** Taichi, Warp (NVIDIA), LiquidFun, SPlisHSPlasH, PhiFlow, MuJoCo, Brax, JAX-MD, Genesis, Mantaflow, PhysX, GPU-Falling-Sand-CA, sandspiel, The Powder Toy, DiffTaichi, sailfish, voronoishatter, Newton (Warp-based).

**Specific questions:**
- For each engine, **what makes it unique?** Where does it shine, where does it fail?
- For **2D Godot gameplay** specifically, which 2-3 engines should be primaries?
- For **baked VFX flipbooks** (most spell visuals), what's the best workflow per phenomenon class? (fire/smoke/water/sand/destruction/swirl/lightning)
- Are there any engines we should **drop** (deprecated, abandoned, redundant)?
- Are there **new engines from 2025-2026** we should add? (e.g. Genesis was recent — what came after?)
- For **real-time 2D effects** (the rare cases that need live simulation), what's the right runtime engine integration with Godot 4.5? Any Godot-native plugins?
- The user mentioned "physics could be used outside spells too" — how would we use these engines for **environmental VFX** (waterfalls, smoke, fire) and **destruction** (breakable rocks, glass) baking?

**Required deliverable:** per-engine report (1-2 paragraphs each) + "starter kit" of 3-4 engines for 2026 + recommended VFX Lab v2 architecture (authoring tool + baker + viewer + Godot exporter).

---

### Assignment D — UI / Icons / Theme (medium priority)
**Scope:** game UI assets — spell icons, item icons, HUD frames, menu backgrounds, pixel-style fonts, button states. Plus maybe RPG-style portraits.

**Specific questions:**
- **AI icon generation** in 2026 — best tools? Local (FLUX with icon LoRAs?) vs cloud (Midjourney, Ideogram, Recraft)?
- **9-slice / 9-patch** generators? Manual workflow vs automated?
- **Pixel-style icons** specifically — best AI generators? PixelLab, Stable Diffusion with retro LoRAs, etc.?
- **Icon atlas packing** — what's better than what we have for character sprites? Are there tools like TexturePacker that have free CLI?
- **Godot Theme** resources — what's the cleanest workflow to wire icons into a `Theme.tres`?
- **Free icon libraries** — game-icons.net (CC-BY), Open Game Art, etc. — recommended sources?

**Required deliverable:** UI SOTA report + starter kit of: one icon generator, one atlas tool, one source of free icons, one Godot Theme template.

---

### Assignment E — Audio (low priority, deferrable)
**Scope:** SFX (combat hits, footsteps, spell casts, ambient), music (background loops, combat themes), voice (one-shot grunts/lines, NPC dialog if any).

**Specific questions:**
- **AI SFX generation** in 2026 — best tools? AudioBox, Stable Audio Open, ElevenLabs Sound Effects, Suno?
- **Local install** vs cloud APIs?
- **AI music generation** — Suno, Udio, MusicGen? Quality good enough for game backgrounds?
- **Voice generation** — Coqui XTTS-v2 (we have it cached), ElevenLabs, OpenAI TTS?
- **Trim/normalize/loop** workflow — sox, ffmpeg, audacity-headless?
- **Godot audio import** — best practices for compressed vs uncompressed, looping, 3D positional?

**Required deliverable:** audio SOTA report + starter kit.

---

### Assignment F — Game data / Lore (low priority)
**Scope:** structured game data (items, abilities, NPCs, factions, lore documents) and the pipelines to generate, validate, and import them.

**Specific questions:**
- **AI structured-data generation** — what's good in 2026 for "generate 50 items with stats matching this design doc"?
- **Schema validation** — JSON Schema? Pydantic? Godot Resource validators?
- **Lore document → structured fields** — best LLM workflows for parsing?
- **Generation seed lists** — do good repos exist for "names of medieval weapons" / "fantasy NPC name lists" we can sample from?

**Required deliverable:** game data SOTA report + starter kit.

---

## How to deliver your report

Write your report as a Markdown file at `D:\assets\research\<assignment_letter>_<topic>.md`. Example: `D:\assets\research\A_terrain.md`.

Length: target 1500-3000 words. Density over verbosity.

Include:
- All survey data with links
- Honest tradeoffs
- Concrete starter-kit recommendation
- Test plan for the kit
- Estimated effort to integrate (hours of work)
- Risks and known issues

After delivery, I'll integrate your recommendation into `ROADMAP.md` and start building.

---

## A few principles

1. **Use real data.** Where you can, fetch a tool's actual GitHub stats, latest release date, recent issues. Don't trust your training cutoff for what's SOTA.
2. **Be honest about hype.** Many "AI generates a game!" announcements are vaporware. Distinguish working tools from press releases.
3. **Test plans should be runnable in 1-2 hours each.** No "spend a weekend training a model from scratch."
4. **Prefer open-source.** The user can fall back to cloud if local isn't viable, but local-first is the default.
5. **Windows + WSL2 + RTX 5090 sm_120** is the deployment target. Anything that requires Linux-only or older GPUs needs a workaround documented.
6. **The LLM (me) drives the tools.** Don't recommend GUI-only workflows unless they have headless modes. Don't recommend tools requiring constant manual web-UI clicking unless that's literally the only path.

---

## Round 2 — SOTA followups (added 2026-05-06 after v1 builds landed)

The first wave (A-J) returned and got built. v1 pipelines are working but each has SOTA gaps the build chats explicitly flagged. These four briefs target those gaps. Same shape and depth as Round 1 reports.

### Assignment C2 — VFX 3D / volumetric / mesh-trail extension (medium priority)

**Scope:** research/C_vfx.md was bake-flipbook focused, correct for our 2D-leaning Godot scenes. Once we ship 2.5D iso scenes (already prototyped) we'll need 3D camera-aware billboards, volumetric smoke that respects depth, mesh-trail decals for projectiles, and GPU-particle integration with our existing Effect schema. This brief covers what's SOTA in 2026 for 3D / volumetric VFX in Godot 4.5 specifically.

**Specific questions:**
- Godot 4.5 `GPUParticles3D` ecosystem in 2026 — is it production-ready? Plugin marketplace?
- **Volumetric fog** in Godot 4.5 — the new vol-fog system. How well does it composite with our biome terrain? How to bake fog presets per biome?
- **Mesh-trail decals** — for projectile trails, vehicle tracks, blood drips. Best approach in Godot 4.5? Custom VertexBuffer? CSG?
- **Audio-reactive VFX** — we have an Audio pipeline that emits cue points; how do AAA games sync flipbook timing to audio cues at runtime?
- **VAT (Vertex Animation Textures)** — for crowd simulations or destruction. Godot 4.5 support?
- **Ribbon trails / line renderers** — Godot 4.5's TrailMeshGenerator vs custom shaders.
- **Decal flipbooks** — projecting a flipbook onto terrain (e.g. magic circle that fades in then dissipates).

**Required deliverable:** SOTA report + extension plan for `../../pipelines/vfx/`. Specifically: which new bakers belong (Taichi MPM is already planned; what else?), how to wire `Effect.kind` to support 3d_billboard / volumetric_fog / mesh_trail / decal_flipbook variants, recommended Godot 4.5 plugins.

---

### Assignment E2 — Audio: local Stable Audio + biome-aware ambience (medium priority)

**Scope:** research/E_audio.md covered cloud (ElevenLabs, Suno) + ffmpeg processing. v1 ships SFX. Two gaps:
1. **Local AI audio** — Stable Audio Open is open-weights, runs on the 5090 (~5GB). The build chat flagged it as the recommended local backend but didn't run it (GPU was busy). We need a clear "install + integrate" plan.
2. **Biome-aware ambience** — our biome system (lava_field, ice_cavern, mana_crystal, grassland) has zero ambient audio. AAA games layer 2-4 stems per biome (wind / wildlife / element / distant) at runtime. Procedural-ambience research has good 2024-2026 prior art (StableAudio + LoopGen models, Game Audio Conf talks).

**Specific questions:**
- **Stable Audio Open local install** in 2026 — install path, RTX 5090 sm_120 quirks, latency for 5-10 sec SFX vs 30-sec ambience.
- **Other open-weights audio models** — AudioCraft (Meta), MusicGen, AudioLDM2. Compare quality, license, latency.
- **Biome-ambience layering pattern** — what AAA games do (Skyrim, Elden Ring, BotW). 4-layer model (wind / wildlife / element / distant) vs adaptive.
- **Spatial audio in Godot 4.5** — HRTF support, AudioStreamPolyphonic best practices, AudioListener3D.
- **Adaptive music in Godot 4.5** — AudioStreamSynchronized, transition graphs. Authoring tools (FMOD/Wwise alternatives free for indie).
- **Foley libraries** — Sonniss GameAudio (CC0 yearly drops), Freesound CC-BY, BBC Sound Effects (commercial).

**Required deliverable:** SOTA report + a **biome ambience starter kit**: install plan for Stable Audio Open, design of `../../pipelines/audio/biome_ambience.py` (biome_id → 4-layer mix), recommended free libraries to ingest, Godot 4.5 spatial-audio integration recipe.

---

### Assignment F2 — Game Data: balance-constrained generation + playtest sim (low-medium priority)

**Scope:** research/F covered Pydantic schemas + LLM structured outputs + cross-reference validation. v1 ships everything reported. Two SOTA gaps:
1. **Balance-constrained generation** — current generator produces records, then a balance report shows "rarity histogram skewed". SOTA generators *constrain* the LLM during generation to hit balance targets. Has prior art in card games (Hearthstone autobalancer), roguelikes (PoE / Last Epoch), procgen-content tournaments.
2. **Test-driven generation** — LLM proposes a record, a mini-sim instantiates it in a tiny gameplay loop, rejects degenerate ones (e.g. ability that's strictly dominant). Slay the Spire's balance bot is a public example.

**Specific questions:**
- **Constrained generation** — current state of structured outputs (OpenAI strict mode, Anthropic, local llama-3 + outlines library). How to express "rarity must follow a 0.5/0.3/0.15/0.04/0.01 distribution"?
- **Multi-pass generators** — first pass draft, second pass critique, third pass revise. Worth the cost?
- **Test-driven content gen** — what game studios actually do. Slay the Spire dev blog. PoE design docs. Roguelike Celebration talks.
- **Balance metrics for ARPG-like systems** — DPS-per-rarity curves, TTK distributions, item-power-vs-level. What's worth measuring?
- **Sim-as-validator** — how to build a 100-line "kill-a-dummy" loop that catches degenerate abilities without becoming a full game.
- **Provenance / audit trail** — version control for generated records (git? CRDT? signed manifests?). What stays sane at 10000 records?

**Required deliverable:** SOTA report + design for `../../pipelines/game_data/balance/` and `../../pipelines/game_data/sim/`. Specifically: how to wire constrained generation into the existing `generate_records.py`, a 100-line playtest sim spec, balance-target file format (yaml/toml), reject-and-retry loop pattern.

---

### Assignment J2 — Props: variation parametrics + LOD chain authoring (medium priority)

**Scope:** research/J_props_3d_decoration_pipeline covered procedural recipes + Blender automation + AI image-to-3D. v1 ships 3 demo props. Two gaps:
1. **Variation parametrics** — research J recommended seed-driven family variants. Currently we make ONE rock per recipe. SOTA pattern: one recipe + seed sweep → 20 sibling rocks that share style but each looks unique. Already proven in our texture pipeline (4 variants per AAA texture); just needs porting to props.
2. **LOD chain authoring** — current ships `model_lod0.glb` only. Best practice: 3-4 LOD levels via Blender decimate ladder, with screen-space-error thresholds. Godot 4.5 supports automatic LOD swap with `mesh_lod_threshold` per MeshInstance3D.

**Specific questions:**
- **Procedural prop families** — best authoring pattern for "one recipe, N variants". Houdini HDA approach? Blender Geometry Nodes? Pure Python recipes with seed?
- **LOD generation in Blender 5.x** — decimate modifier vs `bpy.ops.mesh.decimate`, error metrics, normal preservation. ~70% / 40% / 15% poly tier defaults?
- **Godot 4.5 LOD integration** — `mesh_lod_threshold`, automatic swap, billboard fallback at extreme distance.
- **Material LOD** — reduce texture resolution for distant props? Atlas-pack distant-LOD UVs?
- **Procedural "kitbashing"** — combining base shapes (cube + cylinder + sphere) into varied props. Library of base meshes + Boolean ops?
- **Convex collision auto-gen** — vhacd, Blender RigidBody, Godot's built-in CollisionShape3D.create_trimesh_shape. What's actually best in 2026?
- **Scatter integration** — Godot 4.5 MultiMeshInstance3D vs new Foliage / GPU-instanced systems. Performance vs 100k props.

**Required deliverable:** SOTA report + extension plan for `../../pipelines/props/`. Specifically: design of `../../pipelines/props/variation_sweep.py` (recipe + seed range → N sibling GLBs), design of `../../pipelines/props/lod_chain.py` (single GLB → 4-LOD .tscn), recommended convex-collision generator, scatter integration notes for our `biome_scatter_rules.json`.

---

## How a Round 2 brief gets handed off

Per `EXPANSION_PLAN.md`:
1. Spawn a research subagent (general-purpose, run_in_background=true) with the brief above quoted in the prompt.
2. Agent writes `../../research/<assignment_id>_<topic>.md` matching the Round 1 report shape.
3. EXPANSION_PLAN.md item moves from `[ ]` to `[~]` to `[x]` as research lands and dependent build items proceed.
