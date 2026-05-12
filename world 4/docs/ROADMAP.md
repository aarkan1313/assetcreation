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

**Axis 6 transitions** — soft biome blending, texture-array
infrastructure, slot-pool indirection (streaming-ready). Shipped
2026-05-12 on branch `axis6-transitions`. Captures
`axis6_5{a,b,c,d}_*_2026_05_12.png`. Full writeup
`build-notes/AXIS6_BUILD_NOTES_2026_05_12.md`. Portability guide
`plans/AXIS6_PORTABILITY_README.md`. Ready to merge to main.

### Parallel strands (medium-term, after Axis 6)

Two strands that can run in any order. Pick whichever is more
game-blocking when its turn comes.

- **Strand A — 3D depth.** Real-game scale (Axis 1 follow-up: 4-8 km
  worlds, LOD rings, DEM stitching). Procedural biome assignment from
  heightmap (Axis 2 follow-up). Per-view × per-biome shading (Axis 4 ↔
  Axis 2 follow-up). Real-ortho rock backfill (Axis 2 follow-up).
  *Makes the 3D pipeline more capable.*

- **Strand B — Output models.** Offline bake renderer (render world to
  static image at build time). 2D-game integration recipe (Godot 2D
  scene consuming a W4 bake). Per-game packaging as a Godot
  addon/plugin. *Unlocks 2D/2.5D game output models without giving up
  the W4 terrain pipeline.*

The Strand B story matters for the 2.5D wizard game specifically: a
baked image consumed by a 2D scene runs at sprite-game framerates
while reusing all of W4's terrain authoring.

### Long-term

- **Decoration (Axis 5).** Vegetation, rocks, scatter. Density maps
  per biome. Needed in both strands (3D scatter + 2D sprite scatter).
- **LLM-drivability cross-cut.** LLM authors biome catalog + tile
  layout + DEM source. Becomes interesting once core engine stable.
- **Per-game packaging.** Final form of "drop into any project" — the
  W4 system as a Godot plugin shipped per game.

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

## What's next, ranked

Order reflects current judgement. Reranking happens any time the
calculus changes (new info, new constraints, new user priorities).

### 1. Pick a strand (Strand A vs Strand B)
**What:** Axis 6 shipped. The next session's first decision is which
strand of the parallel-path plan to push:

- **Strand A — 3D depth.** Real-game scale (Axis 1 follow-up: 4-8 km
  worlds, LOD rings, multi-DEM stitching). Procedural biome assignment
  (Axis 2 follow-up). Per-view × per-biome shading (Axis 4 ↔ Axis 2
  follow-up). Real-ortho rock backfill (Axis 2 follow-up). Makes the
  3D pipeline more capable.
- **Strand B — Output models.** Offline bake renderer (render world to
  static image at build time). 2D-game integration recipe (Godot 2D
  scene consuming a bake). Per-game packaging as a Godot
  addon/plugin. Unlocks 2.5D / topdown / 2D game output models
  without giving up the W4 terrain pipeline.

The 2.5D wizard game leans Strand B. Real-game scale + decoration
leans Strand A. Either path is unblocked; the choice is about what
game ships first.

### 2. Parked follow-ups (any time, low priority)

These don't block either strand and can run independently when an
afternoon opens up:

- **Biome streaming** — LRU eviction + async layer-load. Slot-pool
  indirection is already in place; just needs the policy + loader.
  Plan for it when biome count exceeds ~30 (current scale_demo has
  5 biomes, ~250 MB compressed in VRAM).
- **Per-pair feather widths** — author per-biome-pair widths so
  alpine↔desert can be wider than alpine↔forest.
- **4-way junction handling** — currently drops the 4th distinct
  neighbor at a 4-way tile junction. Rare; v1 limitation.
- **Iso/topdown per-biome shading** (also listed under Strand A) —
  currently single-material in iso/topdown views. Cross-cut Axis 4 ↔ 2.
- **Real-ortho rock textures** for alpine + desert (also listed under
  Strand A). Currently ComfyUI placeholders. Authenticity-only.
- **Procedural biome assignment** (also listed under Strand A). 4×4
  layout is hand-coded in `assign_biomes_scale_demo.py`. Becomes
  meaningful at larger world sizes.
- **Hand-painted / procedural splats** — splats are produced by
  `build_tile_splats.py`'s hard + feather modes. Other splat sources
  (noise masks, painted boundaries) plug in via the same on-disk
  contract.

## What's not next-this-session (and why)

These are real concerns; they're parked behind Axis 6 + the strands
above, not abandoned. See "Strategic shape" for where they live in the
multi-month picture.

- **Source axis (Axis 3) — procedural amplification.** Real DEMs work
  fine and we have hundreds cached. Procedural makes sense once we
  want non-Earth or specifically-shaped terrain. Not urgent.
- **Decoration (Axis 5).** Listed in the long-term section of
  Strategic shape. Needs both strands (3D scatter + 2D sprite scatter)
  so it makes sense as a follow-on after either strand A or B has
  matured.
- **LLM-drivability cross-cut.** Long-term per Strategic shape.
  Becomes interesting once core engine is stable across both strands.

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
