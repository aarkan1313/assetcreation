# W4 Roadmap

> The single source for **what to work on next** + the multi-month
> strategic shape. AXES.md owns "what each axis is"; this doc owns
> "which axis to expand next, and why" plus "where the parallel paths
> go long-term."
>
> Read this when you start a session and don't already have a chosen
> task. If the candidates here feel stale, rerank — the doc evolves.

## Strategic shape

W4 is **a portable world-generation engine**, not a single game's
generator. Architectural decisions preserve "drop into any project"
generic-ness. The first game on the W4 engine will likely be a 2.5D
wizard game, but the engine itself stays game-agnostic.

### Near-term (just shipped)

**Texture pipeline rebuild** — W4-owned `tx_*` modules at
`pipeline/textures/`, hybrid PBR backend (SM tileable + derive maps),
canonical doc `features/textures.md`. Shipped 2026-05-12.

**Axis 6 transitions** — soft biome blending, texture-array
infrastructure, slot-pool indirection (streaming-ready). Shipped
2026-05-12. Full writeup `build-notes/AXIS6_BUILD_NOTES_2026_05_12.md`.

**Axis 1 Path 2 stages 1-4.1** — kernel system + clipmap geometry +
heightmap stack + morph zones + single-biome rendering proof.
Still pending: editor verification + Stage 4.2 multi-biome culler.

### Priority-ranked goals (2026-05-12 revision)

User priority order. Each tier builds on the previous; can branch
out within a tier when an item bites.

**Tier 0 — Cross-cutting concerns (always apply).**

- **Performance / mid-tier hardware floor.** RTX 3060 / 4060 target.
  Every shipped feature must benchmark on that floor or be gated
  behind a quality tier. Quality-tier system already in place
  (`config/quality_tiers.json`); route new tunables through it.
- **LLM-drivability** — every layer is schema + validator + deterministic.

**Tier 1 — World scope (the foundation for "real game").**

- **Infinite world via kernels.** Axis 1 Path 2 already lays the
  groundwork (kernel system + clipmap rings + procedural heightmaps).
  Remove the soft world-bound assumption from `ClipmapWorld` so the
  player can walk past 4 km indefinitely. Distant tiles generate
  on-demand from kernels.
- **Biome-to-biome transitions** — Axis 6 shipped. Polish items
  parked (per-pair feather widths, 4-way junction).
- **Intra-biome regional variation** — same biome reads differently
  across regions. NEW work. Three scales, build in order: tile-scale
  → cluster-scale → sub-biome-scale. See wishlist
  "Stochastic ground texturing" for the architecture. Tier 7 below
  also picks at this from the texture-pipeline side.
- **Skybox + atmosphere** — procedural sky, fog, distance haze,
  time-of-day. NEW work; net new shader + scene setup.

**Tier 2 — Inhabiting the world.**

- **Procedural decoration v0 (Axis 5)** — rocks, plants, debris.
  Designed with a hand-authored-per-instance hook so it's easy to
  replace procedural with handcrafted later. See wishlist
  "Vegetation + organic-asset system" for the long-arc plan.

**Tier 3 — Texture / biome workflow polish.**

- **Stochastic per-tile texturing** — sibling system + stochastic UV
  sampling. Wishlist "Stochastic ground texturing" MVP-floor and
  MVP-good tiers. Also addresses Tier 1's tile-scale intra-biome
  variation goal.
- **Easier biome-author loop** — `promote_candidate.py` script,
  palette-lock authoring, diversity batch UX.
- **AAA-target compositor** — building-block composition per the
  wishlist's AAA section. Heavy investment; only worth it once
  Tier 1-2 ship and the visible-tile-repeat problem is empirical.

**Tier 4 — Output models (deferred).**

- **Offline bake renderer** — render world to static image at build
  time. Unlocks 2D/2.5D consumer recipes for the wizard game.
- **2D-game integration recipe** — Godot 2D scene consuming a bake.
- **Per-game packaging** — W4 as a Godot plugin shipped per game.

The wizard game's 2.5D framing leans on Tier 4 eventually. The path
to "real game" still goes through Tier 1-2 first; output-model work
is post-foundation polish.

## What's done

| Shipped | Date | Notes |
|---|---|---|
| Anchor demo | 2026-05-11 | 256m × 256m, locked as regression baseline. See `strategy/ANCHOR.md`. |
| Axis 1 (Scale) — first expansion | 2026-05-11 | 1024m × 1024m, 16 tiles. Radius-paging mechanism shipped; the cross-tile sampling, ghost-border, normal-stencil widening, and 4 documented pitfalls. See `build-notes/SCALE_BUILD_NOTES.md`. |
| Axis 1 chunk-loading perf pass | 2026-05-11 | 4× faster tile build (325 ms → 77 ms): cached-neighbor normals + skipped tangents on unshaded shader. Persistent unloaded-tile cache for free re-entry. Radius mode default. See `features/world-pipeline.md`. |
| Axis 1 async tile build | 2026-05-11 | `WorkerThreadPool.add_task` runs vertex/normal math off the main thread; only ~4ms finalize on main. Peak frame ms 96 → 17 (5×). FPS min 90 → 90, hitch count 7 → 2 over 200s autowalker. Axis 1 closed for current scope. |
| Axis 4 (View) — first expansion | 2026-05-11 | Three view shaders for scale_demo: walk (existing scale_v1), iso (flatter lambertian + form light), topdown (cartographic hillshade + sepia). Per-view radius bumps iso/topdown to whole-world automatically. Same albedo/slot-blend pipeline across all three. |
| Axis 4 iso/topdown movement | 2026-05-11 | WASD pans the iso + topdown cameras. Scroll wheel zooms topdown ortho size. HUD updated. |
| Doc consolidation + per-HUD layout | 2026-05-11 | Perf HUD moved top-right so it doesn't overlap gameplay HUD. ROADMAP + AXES kept current as each axis closed. |
| Axis 2 (Biome) — texture kits | 2026-05-12 | 48 texture maps for 4 new biomes (alpine, desert, rocky highlands, wetland) via ComfyUI FLUX2-klein 9B + aaa_texture.py at 1024². 4 new `material_<biome>.tres` files. All 12 slots passed near-black + normal sanity validation. Per-biome walk captures saved. See `build-notes/BIOME_KITS_BUILD_NOTES_2026_05_12.md`. |
| Axis 2 (Biome) — per-tile wiring | 2026-05-12 | ScaleWorld reads each tile's biome label from meta.json and routes to the matching `material_<biome>.tres` at spawn. 4×4 layout from BIOMES.md realized — hard borders visible at every biome adjacency. Walk + topdown captures saved. See `build-notes/AXIS2_WIRING_BUILD_NOTES_2026_05_12.md`. |
| Doc audit + TOOLS.md index | 2026-05-12 | Refreshed stale `AXES.md` Axis 1+2 state, rewrote `HANDOFF.md` as stable "how to take over" prompt (now points at ROADMAP), wrote `reference/TOOLS.md` as a one-line-per-item index of every pipeline script, shader, GDScript, scene. |
| Axis 6 (Textures) — Stage 5a foundation | 2026-05-12 | Texture-array + per-tile splat architecture landed end-to-end. Catalog → manifest builder (auto-upsample + L→RGB convert) → splat builder (hard mode + per-slot tier/layer meta) → `terrain_world_v2.gdshader` → global material → ScaleWorld runtime (builds 8 Texture2DArrays at init + per-tile uniform binding). 3 Godot pitfalls documented as PITFALLS #5/#5b. See `build-notes/AXIS6_5A_BUILD_NOTES_2026_05_12.md`. |
| Axis 6 (Textures) — soft transitions shipped | 2026-05-12 | Stages 5b (feather splats) + 5c (slot-pool indirection refactor) + 5d (two-tier verification, hero-tier 4K confirmed on forest closeup) + 5e (portability README) + 5f (this row + final build-note). Soft transitions visible at every biome boundary on scale_demo walk + topdown. 22 pytest cases total. Architecture is streaming-ready (slot-pool indirection in place, identity v1). Portability doc at `plans/AXIS6_PORTABILITY_README.md`. Full session writeup at `build-notes/AXIS6_BUILD_NOTES_2026_05_12.md`. Branch `axis6-transitions` ready to merge to main. |
| Axis 6 — world-splat pivot + mesh-density perf | 2026-05-12 | Hard-line bug in per-tile splats (visible only in editor Vulkan path, headless hid it) traced to bilinear-interpolation discontinuity at tile boundaries. Pivoted to a **world-spanning `Texture2DArray` splat (one layer per biome, sampled at world XZ)** — adjacent tiles share splat texels by construction, no hard line possible. N biomes (not 4) via per-layer storage; MAX_BIOMES=16 cap in shader, bumpable. Every tile uses the same global material — no per-tile duplication. Documented as PITFALLS #6. New `build_world_splat.py` + 5 tests including the boundary-continuity regression test. **Bonus:** `resolution_m` default 1m→2m. Tri count 656k→164k (-75%) with no visible quality loss (heightmap downsample analysis: 2.5cm mean error, 1.3m max). Async finalize 5ms→1ms per tile. |
| W4 texture pipeline rebuild | 2026-05-12 | Inherited shared-infra `aaa_texture.py` pipeline replaced by W4-owned `pipeline/textures/tx_*` modules. After a wrong-prediction audit + 16-combo experiment + diagnosis chain, found that StableMaterials' `tileable=True` diffusion is the actual midline-seam closer (not delight, not seam_repair). Built `tx_pbr_hybrid` (SM for albedo tileability + `derive_pbr_v2` for PBR maps). Validated on 5 diverse prompts: all midline ratios <2.72 vs broken pipeline's 16-22 (matches shipped 1.30). New nested candidate layout under `the world 4/candidates/<biome>/<slot>/`. New `mip32_stdev` QA metric catches "vanishes at terrain distance" failure mode. Canonical doc at `features/textures.md`. Full diagnostic record in `plans/TEXTURE_PIPELINE_FINDINGS_2026_05_12.md`. |

## What's next, ranked

User priority order (2026-05-12 revision). Tiered — finish a tier
before fully moving on, but you can branch between items within
a tier as scope demands.

### Tier 0 — Cross-cutting (always)

- **Performance on RTX 3060 / 4060.** New features must benchmark
  or be gated behind a quality tier. Use `config/quality_tiers.json`
  + `pipeline/quality_tiers.py` + `scripts/QualityTiers.gd`. Default
  tier is `high` (3060-class target).

### Tier 1 — World scope

1. **Finish Axis 1 Path 2 — Stage 4.2 + editor verification.**
   Multi-biome rendering in the clipmap. Validate all stages 1-3.5
   visually in the editor.
2. **Remove world-bound for infinite world.** Currently `ClipmapWorld`
   has a soft 4 km bound. Remove that assumption so distant tiles
   generate from kernels on-demand. True procedural infinite via
   `NoiseStackKernel` (and future kernels).
3. **Skybox + atmosphere.** Procedural sky, fog, distance haze,
   minimal time-of-day. NEW shader + scene setup.
4. **Intra-biome regional variation v0 — tile scale.** Wishlist
   "Stochastic ground texturing" MVP-floor: pick from N siblings
   per tile. Cheapest first slice. Sets up infrastructure for
   later cluster-scale and sub-biome-scale variation.

### Tier 2 — Inhabiting the world

5. **Procedural decoration v0 (Axis 5).** Rocks + plants + debris
   scatter. Density maps per biome. Designed so individual
   instances can be hand-authored-overridden later (replace-seam).
   See wishlist "Vegetation + organic-asset system" for the
   long-arc plan.

### Tier 3 — Texture / biome workflow polish

6. **Stochastic per-tile texturing — MVP-good.** Add stochastic UV
   sampling on top of Tier 1's MVP-floor.
7. **Easier biome-author loop.** `promote_candidate.py` script,
   palette-lock authoring, diversity batch UX, per-biome workflow
   docs.
8. **Intra-biome regional variation — cluster-scale and beyond.**
   Wishlist "Stochastic ground texturing" mid tiers. Continues the
   Tier 1 work at coarser scales.
9. **AAA-target compositor.** Wishlist "Stochastic ground texturing"
   AAA-target section. Building-block composition. Heavy investment;
   only worth promoting if the Tier-1 + Tier-3 stochastic work
   doesn't visually close the gap.

### Tier 4 — Output models (deferred)

10. **Offline bake renderer.** Render world to static image at
    build time. Unlocks 2D/2.5D consumer recipes.
11. **2D-game integration recipe.** Godot 2D scene consuming a bake.
    Wizard-game integration path.
12. **Per-game packaging.** W4 as a Godot plugin.

### Parked follow-ups (small, no specific tier — pick up when convenient)

- **Biome streaming** — LRU eviction + async layer-load. Slot-pool
  indirection already in place. Plan for when biome count > ~30.
- **Per-pair feather widths** — wider feather for alpine↔desert
  vs alpine↔forest.
- **4-way junction handling** — currently drops 4th distinct
  neighbor at 4-way tile junctions. Rare; v1 limitation.
- **Iso/topdown per-biome shading** — currently single-material in
  iso/topdown views.
- **Real-ortho rock textures** for alpine + desert — current
  ComfyUI rocks are placeholders. Authenticity-only follow-up.
- **Procedural biome assignment from DEM features** — rules infer
  biome from elevation + slope + climate. Replaces hand-painted
  splats at larger world sizes.
- **Hand-painted / procedural splats** — alternative splat sources
  plug in via the on-disk contract.

## What's not next (and why)

- **Source axis (Axis 3) — procedural amplification.** Real DEMs
  work fine. Kernel-based generation is being built as part of
  Tier 1 anyway. Axis 3 in its W3-era sense (DEM-to-procedural
  hybrid kernels) is parked.
- **LLM-drivability cross-cut.** Long-term. Layered into the design
  via schema + validator + deterministic outputs at every layer,
  but not active feature work yet.

## How to use this doc

- **Starting a session?** Read this top to bottom. Pick a candidate.
  If none feel right, talk it through — the rank might be stale.
- **Just shipped an axis?** Move it from "next" to "what's done." Update
  AXES.md "current state" for that axis. Re-rank the remaining
  candidates based on what's unblocked now.
- **New idea?** Goes in `strategy/WISHLIST.md` first. Promotes to a
  ranked candidate here when it has a concrete next-experiment and
  cost estimate.

## Update protocol

- This doc is the authoritative "what next." If it disagrees with prose
  in any other doc, this one wins for ordering.
- AXES.md still owns "what each axis is" (descriptions, exit criteria,
  notes).
- WISHLIST.md still owns parked-ideas backlog.
- Don't duplicate content. Cross-link instead.
