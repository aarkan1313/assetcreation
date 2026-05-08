# Research Brief — Per-Instance Mesh Albedo Inpaint Workflow (2026 SOTA)

## Goal

Identify 2026-current SOTA for **per-instance variation on rigged 3D character meshes via texture-level inpainting** — specifically how to take one base mesh + a reference insignia/decal/marking and produce N variants with that marking baked into the albedo at asset-prep time.

This is the workflow gap that lets a faction system actually feel different in-game (Ashen Pact goblin with red flame brand vs Verdant Compact goblin with green leaf sigil), generalized to:
- **Faction insignia** — same goblin, different per-faction body marking
- **Damage states** — scorch marks, cracks, blood
- **Tier markings** — gold trim on elites, scars on veterans
- **Variant variety** — different war paint per pack within the same faction
- **Set-piece encounters** — boss with custom branding

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, CUDA 12.8+ / torch >=2.7)
- Windows 11 native preferred; Python 3.11 venvs (current pattern)
- WSL2 acceptable for Linux-only deps

## Context

The 8 SOTA briefs we ran on 2026-05-07 covered every existing pipeline lane (characters, textures, props, VFX, audio, UI/icons, game data). **None covered per-instance mesh surface variation as a workflow.** Adjacent findings:

- **Brief #02 (textures)** identified Hunyuan3D-Paint 2.1 (Tencent) as 2026 mesh-PBR SOTA with multi-view diffusion + 3D-aware RoPE + illumination-invariant albedo. Designed for *initial* texturing, not per-instance variation.
- **Brief #03 (props)** noted Trellis2 multi-image conditioning is "closest 2026 analog to ControlNet for 3D" — for variation in *generation*, not in *texturing existing meshes*.
- **Brief #07 (UI/Icons)** recommended LoRA training for icon faction differentiation. User flagged this as hand-waving — slightly different palette doesn't make a faction "feel different" gameplay-wise. **Real gameplay-meaningful signal is per-instance surface variation on enemy meshes**, which is a mesh-texturing workflow problem, not an icon styling problem.

## Current state

- **Base mesh generation:** ✅ Trellis2 (props), Meshy (characters)
- **Rigging + skinning:** ✅ Puppeteer (validated 2026-05-07 native Win cu128), SkinTokens, RigAnything
- **Animation:** ✅ Hunyuan-Motion (humanoid), AnyTop (OOD topology), per brief #01 canonical chain
- **Initial texturing:** 🟡 MaterialAnything (validated, but reclassified as no-longer-SOTA per brief #02), Hunyuan3D-Paint 2.1 (queued for hero_mesh sibling lane), Trellis2 ships PBR-textured GLBs end-to-end
- **Per-instance surface variation:** ❌ **does not exist as a workflow**

## Three core architectural questions

### Q1 — UV-space inpainting vs. camera-projection inpainting

Two candidate architectures for mesh albedo inpainting:

**(a) UV-space inpaint.** Flatten the mesh's albedo to its UV layout, run a 2D diffusion inpaint with mask in UV space, repack. Clean pixel boundaries; deterministic per-instance. **Risk:** UV seams cut up the insignia; islands break logical placement; works only if UVs are coherent.

**(b) Camera-projection inpaint.** Render the mesh from N angles, run 2D diffusion inpaint on each render with a placement mask, project back to UV via multi-view consensus. AAA standard pattern. **Risk:** smudging at view boundaries; requires multi-view diffusion model (Hunyuan3D-Paint shape) or aggressive consensus logic.

**Question:** Which architecture is current 2026 SOTA for **per-instance mesh marking baking** specifically? Is there a published pattern that handles both UV coherence and visual placement intuitively?

### Q2 — Reference-conditioned inpainting that preserves identity

Generating "a red flame logo" as a text prompt produces a different flame each call. We need **the SAME insignia** (authored or generated once) applied to N goblins.

The 2026 toolkit pieces that exist:
- **IP-Adapter** for FLUX.1 / FLUX.2 — reference image conditioning
- **InstantID-style identity preservation** — face-locked but maybe extends?
- **ControlNet-Inpaint + ControlNet-Mask** — geometric/structural control
- **FLUX.2 Redux** — multi-reference image conditioning (per brief #07)
- **Hunyuan3D-Paint 2.1** — multi-view PBR diffusion with reference conditioning

**Question:** What's the canonical 2026 workflow for "given a single reference insignia PNG + a base mesh + a placement region, bake that exact insignia onto the mesh's albedo with N variants of placement noise but identity preservation"? Is this a single tool, or is it stitched from IP-Adapter + ControlNet + a 3D-aware inpainter?

### Q3 — Placement mask authoring

Per-faction placement is fine (chest center, every faction has a chest brand). Per-instance variation (this orc has the brand on his shoulder; that one on his back) is harder. Three approaches:

**(a) Hand-authored mask atlas.** One UV mask per "brand region" per character family. Designer authors once, pipeline applies to N instances.

**(b) Procedural mask generation.** Use a 3D-aware feature like part-segmentation (BANG / PartGen) to identify body parts, randomize placement within constraints (always upper torso, never face).

**(c) ControlNet-Pose-driven.** If the rig is known, use bone positions to anchor regions ("on the right pectoral").

**Question:** Which approaches have shipped tooling in 2026? Is there a "part-aware mask placement" tool that solves this without per-character hand-authoring?

## Specific tools to investigate

### Mesh-PBR inpaint candidates
- **Hunyuan3D-Paint 2.1 / 2.5** (Tencent, brief #02 surfaced for hero terrain) — does it support inpaint mode with reference images?
- **DreamMat** — 2024-era, mesh PBR. Inpaint capability?
- **Make-A-Texture** (arXiv 2412.07766) — fast multi-view inpaint, brief #02 mentioned.
- **TEXGen** — UV-space diffusion, architecturally suited for UV-space inpaint approach.
- **Paint3D** — multi-view, possibly has inpaint mode.

### 2D inpainters that could project to UV
- **FLUX.2 Inpaint** — official inpaint variant of FLUX.2 (verify availability)
- **SDXL-Inpaint + IP-Adapter + ControlNet-Inpaint** — well-trodden 2D path
- **Stable Diffusion 3 inpaint** — if it exists as a published path

### Reference-identity preservation
- **IP-Adapter Plus / Style-only weight types** — for reference image conditioning
- **InstantID / InstantStyle** — face-locked identity preservation
- **ControlNet-Tile / ControlNet-Reference** — though Reference-only is largely deprecated for FLUX per brief #02

### Part / mask awareness
- **BANG** (Hyper3D) — part decomposition, brief #03 mentioned
- **PartField** (already installed in Puppeteer venv) — part feature extraction
- **SAM 2 / SAM 3** — segmentation for mask authoring
- **SAMURAI / Grounded-SAM** — text-prompted segmentation for "the chest area"

## Research questions

### Q1 — Is there a 2026 SOTA tool for per-instance mesh albedo inpaint?

What's the most-cited recent paper or shipped tool for "given a textured 3D mesh + a reference image + a placement region, produce a new textured mesh with the reference applied"? Has anyone published a clean workflow specifically for game-asset variation pipelines?

### Q2 — UV-space vs camera-projection — which is winning in production AAA in 2026?

GDC 2025 / SIGGRAPH 2025 talks on "tribal markings on enemies" / "damage states" / "elite variants" — what's the actual production pattern? Substance Painter still dominates for hand-authoring; what's the *automation* pattern when you need 50 variants?

### Q3 — Identity preservation for non-face references

Most identity-preservation literature is face-locked (InstantID, Photomaker). For arbitrary reference like "this exact red flame logo" — what works? Is it just IP-Adapter at high weight + ControlNet-Inpaint, or is there a dedicated tool?

### Q4 — Multi-instance batch workflow

We don't want one-off interactive ComfyUI sessions. We want a CLI-driven batch: "given `goblin_base.glb` + `ashen_pact_brand.png` + `chest_mask.png`, produce 20 variant GLBs." What's the canonical automation shape in 2026? ComfyUI API? A Python wrapper? A dedicated tool?

### Q5 — Damage-state / weathering pattern

Adjacent: "scorch marks, cracks, blood spatter on a mesh" is the same architecture but with procedural references rather than authored ones. Is there a 2026 SOTA "weathering pass" tool that could share infrastructure with insignia inpaint?

### Q6 — Free vs cloud tradeoff

Cloud is parked per user direction (2026-05-07). What's the local-only 2026 path on RTX 5090 sm_120 / cu128? Hunyuan3D-Paint 2.1 needs 21 GB VRAM and Blackwell port (1-2 days, similar shape to Puppeteer). Is there a lighter-weight option that fits this exact use case without the full mesh-PBR stack?

### Q7 — Integration with existing rig + animation chain

If we bake the insignia into the GLB's albedo, the rigged version (post-Puppeteer) needs to inherit it. Does Puppeteer's skinning preserve the texture coordinates? Or do we have to re-rig after texturing? **Workflow ordering question — texture first then rig, or rig first then texture?**

## Honest comparison ask

For each candidate tool, please report:
- **Does it actually do per-instance inpaint?** (Or is it a one-shot texturing tool that we'd be misusing?)
- **Hardware fit on RTX 5090 sm_120 / cu128?**
- **License** (commercial-safe vs research-only).
- **Maturity** (production-grade vs research code).
- **Honest comparison vs hand-authoring in Substance Painter** at the volume we'd need (5-50 variants per character family). Cloud diffusion isn't competing with high-end manual authoring on quality; it's competing with the *labor cost* of authoring N variants.

## Output format

Produce `09_mesh_inpaint_per_instance.response.md` as a sibling to this brief. Same shape as the existing 8 responses: TL;DR + per-Q sections + watch-list + cross-cutting recommendations. **Bias toward "what should we install / build / dispatch next"** — we have validated 2026 patterns now (Puppeteer install, dedicated venv, A/B-comparable wiring) and want concrete next-step recommendations, not abstract surveys.

## Background workers

- **Worldgen worker** in `world3/` — leave alone.
- **Texture worker** in `pipelines/textures/` + `world/textures/library/` — adjacent lane, but mesh inpaint is a *characters* lane concern. No overlap expected.

## What we already decided (don't relitigate)

- **Cloud parked** — Rodin Gen-2, Stable Audio 2.5, Recraft V4 cloud spend all queued not done. Local-only for now.
- **AniMo skipped** — training-only research repo. Don't recommend.
- **Native Win cu128 venvs** — established pattern; one venv per pipeline lane.
- **Additive tooling, not replacements** — every tool we add wires alongside existing tools with A/B-comparable flags.
- **Don't fan out 33 characters** — content authoring, not pipeline work.

## Pointers

- Latest cross-cutting state: [docs/plans/NEXT_STEPS_2026_05_07.md](../../plans/NEXT_STEPS_2026_05_07.md)
- Latest handoff: [docs/handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md](../../handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md)
- 8 prior briefs + responses: this same directory.
