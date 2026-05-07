# world3 — Roadmap (v2)

Reframed 2026-05-07 after stocktake. The v1 roadmap (DEM analyzer →
procedural generator → infinite world) is archived in
`ROADMAP_v1_archived.md`. v2 is grounded in the concrete quality gaps
we surfaced through Phase 1 and Phase 2 — not the ambition-end of the
project.

**Long-term direction unchanged**: continuous / potentially infinite
world, real-DEM grounded, optionally procedural for arbitrary
extension. v2 just changes what we work on *first* to get there.

## Operating principles

- **One thing at a time.** Each phase has a clear scope and an exit
  criterion. We don't move on until the current phase's checklist is
  done.
- **Improve what we have before extending.** Quality of existing
  outputs (textures, kits, materials) before more breadth (more
  regions, kernels, infinite world).
- **Research before building.** Texture quality and upscaling both
  benefit from looking at what other people are doing before we
  commit to a workflow. Both are R&D-flavored phases.
- **Defer LOD and kernels.** LOD is a decision we make when
  performance forces it. Kernels are a strong long-term direction but
  not a 2026 priority.
- **Document as we go.** New decisions land in DECISIONS.md, new
  surprises in LESSONS.md, runbooks updated.

## Phase A — Texture quality + prompt R&D (DONE 2026-05-07)

The texture pipeline is mature, but FLUX still misses prompts ~30% of
the time and we don't have a systematic understanding of what works.
This phase is mostly *experiments and observations*, not new code.

Checklist:
- [x] Reproducible experiment harness: `pipelines/textures/experiment.py`
      — supports `seeds`/`prompts`/`settings` modes; outputs contact
      sheets + JSONL manifests.
- [x] Same-prompt sweep on 5 representative materials (A.2): volcanic,
      snow, sand, grass, leaf_litter × 3 seeds. Surfaced two clear weak
      cases (snow stylization, leaf_litter lattice). Findings in
      TEXTURE_RND Part 1.
- [x] Prompt-permutation sweep on weak cases (A.3): snow + leaf_litter,
      4 variants × 3 seeds each. Both rewritten with decisive winners.
      Three new anti-patterns added to cookbook (aerial-photograph-of-
      field, rare-jargon names, mismatched-substrate descriptors).
- [x] Settings sweep (A.4): variants count 4/6/8 on sand + leaf_litter.
      Found 4 stays as default; 6 helps variance-sensitive materials;
      8 never wins. heal_strength sweep deferred — A.3 prompt fixes
      reached threshold without needing it.
- [x] External research (A.5): `pipelines/textures/EXTERNAL_TECHNIQUES.md`
      survey of state-of-the-art. Confirmed our offset+heal algorithm
      matches the open-source canon. Documented dead ends. Identified
      future candidates (variation-and-stitch, CHORD model).
- [x] Apply learnings to weak materials (A.6): tundra_ice +
      desert_canyon_rock prompt rewrites — both had directional cues
      flagged in Part 2. Same fix as A.3 snow worked. The directional-
      cue rule is now confirmed across 3 materials, promoted to a
      general anatomy rule in the cookbook.
- [x] Regenerate shipping textures: wgv3_snow, wgv3_forest_floor,
      wgv3_tundra_ice, wgv3_desert_canyon_rock all regenerated at
      grade A. Before/after captures archived.

Exit criteria — all met:
- ✅ Prompt-accuracy qualitatively higher (4 weak materials lifted to
  A grade; cookbook doubled in size).
- ✅ At least one new technique adopted (variants-count tuning rule
  from the EXTERNAL_TECHNIQUES survey).
- ✅ Cookbook doubled in size with concrete patterns + 3 new anti-
  pattern entries + the directional-cue anatomy rule.

Open / deferred items (candidates for a later phase):
- "Richness" minimum-energy QA metric — 3 confirmed "smooth-A"
  failure cases now (LESSONS L16 strengthened). Small enough for a
  single-session add.
- Flux Fill / controlnet-inpaint model swap for the heal step
  (EXTERNAL_TECHNIQUES technique #12) — speculative; defer.
- Variation-and-stitch tool (cprimozic-inspired) — could rescue
  lattice-prone materials more cleanly than prompt rewrites alone.

## Phase B — Upscaling + multi-resolution pipeline (NEXT)

Currently 512 throughout. Some uses (close-walk, hero materials, large
iso-camera footprint) need more. Some uses (mid-range topdown, far
foreground in walk) don't.

Checklist:
- [ ] Audit current `flux_upscale.py` — what works, what doesn't,
      what's PBR-aware vs. albedo-only.
- [ ] Research alternatives:
      - Real-ESRGAN, SwinIR, BSRGAN (general-purpose SR)
      - Tileable-aware super-resolution wrappers
      - ComfyUI's upscaler ecosystem (UltimateSDUpscale, ESRGAN,
        custom workflows)
      - 4× SR followed by tiling repair vs. integrated tile-aware SR
- [ ] Decide a target resolution ladder: e.g. 512 default, 1024 for
      "good" terrain materials, 2K/4K for hero materials.
- [ ] Build/extend an upscaler that handles all 5 PBR maps (not just
      albedo). Normal needs special handling (don't blur it; bicubic
      or normal-aware SR).
- [ ] Per-tier QA: tile_2x2 + Blender preview at every resolution
      tier so we can compare visually.
- [ ] Pick a flagship texture (probably wgv3_rock_dark) and produce
      the full ladder; document the difference visually.

Exit criteria:
- One pipeline command that takes a 512 PBR set → 1K or 2K with all
  maps preserved and tiling intact.
- Clear policy: which textures get which tier, and why.

## Phase C — Iso/topdown scale review

Auto-frame works for "render whole tile" but not for "render the area
around a player" or "render at a fixed game-relevant zoom level."

Checklist:
- [ ] Define the target zoom levels. Two reference points each:
      - Iso ARPG-style: ~30-50m visible diameter (Diablo, PoE)
      - Iso strategy: ~200-500m visible (Civ, RTS)
      - Topdown minimap: whole region or ~10km radius
      - Topdown game-tile: ~50m radius (Stardew-ish)
- [ ] Add a "framing target" mode to IsoCam / TopDownCam: instead of
      auto-AABB, frame around a world position with a configurable
      visible diameter.
- [ ] A "player anchor" concept (just a Vector3 for now) that the
      iso/topdown cameras can frame relative to.
- [ ] Decide: do iso/topdown share a player anchor with walk, or do
      they each get their own?
- [ ] Capture the same region at each zoom level for visual review.
      Helps lock in which game type each mode actually serves.

Exit criteria:
- Each game mode has 1-2 documented "good" framings with example
  captures.
- IsoCam/TopDownCam scripts support both auto-AABB and
  framed-around-anchor modes.

## Phase D — Biome generalization (fill out kits)

5 biome kits defined; only 3 (alpine, desert, tundra) have purpose-built
textures. temperate_forest and grassland reuse alpine textures, which
makes some regions look wrong (California chaparral with alpine
materials, Serengeti with alpine grass).

Checklist:
- [ ] Generate temperate_forest kit (5 textures, palette-locked).
      Likely: leaf-litter / loamy-soil / weathered-bark-rock / mossy-
      rock / understory-fern.
- [ ] Generate grassland kit. Probably: tall-grass / dry-thatch /
      hardpan-soil / grass-rooted-rock / weathered-stone.
- [ ] Apply Phase A learnings (better prompts, better settings) so
      these kits ship at higher first-pass quality than desert/tundra.
- [ ] Re-run biome_consistency on every kit. Document the verdict
      table.
- [ ] Re-capture region gallery with all 5 kits visible. Verify each
      region renders with appropriate biome.
- [ ] Optional: generate alternate variants of a slot for visual
      variety (3 grass-types in the grassland kit, randomized per
      region).

Exit criteria:
- All 5 kits have purpose-built textures.
- All 16 regions render through their assigned kit and look
  appropriate (not necessarily perfect, but not visibly wrong).

## Phase E — Per-game-mode material tuning

The decision-locked principle "walk/iso/topdown are different games"
hasn't been implemented yet. Same material is bound to all three
scenes, with the same UV scale and shader params. They should each
own their tuning.

Checklist:
- [ ] Per-mode material variants: each kit emits
      `terrain_blend_<kit>_<mode>.tres` for walk/iso/topdown.
- [ ] Tuning targets per mode:
      - **walk**: tile UV ~0.3-0.5 (1-3m repeat), sharp normals,
        macro_value low (close-up dominates), strong sun
      - **iso**: tile UV ~0.05-0.1 (10-20m repeat), softer normals,
        macro_value moderate, ssao on, slight stylization
      - **topdown**: tile UV ~0.01-0.02 (50-100m repeat), normals
        muted, macro_value high (color-blocking dominates), high sun
- [ ] Update `RegionGalleryCapture` and per-mode capture scenes to
      pick the right `_<mode>.tres`.
- [ ] Per-mode capture sweeps to validate.

Exit criteria:
- Each game mode has its own material variant per kit.
- Same region rendered through the 3 modes shows clearly different
  treatments (close detail vs. mid detail vs. flat color blocks).

## Phase F — Multi-tile / continuous world

Long-term goal: walk off the edge of one region and seamlessly enter
another. We don't need to solve infinite-world today, but we should
build a small proof-of-concept.

Checklist:
- [ ] Research existing approaches:
      - Godot 4 chunk streaming patterns
      - Existing terrain plugins (Terrain3D, HTerrain) — feasibility
        of integrating with our heightmap+blend material approach
      - Memory budget per chunk
- [ ] Design: what's a "chunk"? The current "region" is too big
      (4-20 km). Chunks probably want to be 256-512 m for walk-mode
      streaming.
- [ ] Small test: 2x2 grid of identical Tetons tiles at 4 km each,
      stitched. Verify: no visible seam between tiles, no double-load
      of shared edge, mesh continuity at boundaries.
- [ ] Decide: do we keep one heightmap per region, or split regions
      into multiple chunks at build time?

Exit criteria:
- Walking off the edge of one tile and into another works without
  visible discontinuity.
- Documented streaming budget (how many tiles loadable at once
  before frame budget breaks).
- Decision-locked on chunk size + format.

## Parallel OpenTopo Branch - Texture, scene, and HD zoom R&D

The OpenTopo pilots opened a parallel branch that can feed the main terrain
roadmap:

- Baked ground textures from real orthophoto/terrain evidence.
- Fused real-place scenes/maps from DTM, orthophoto, NIR, canopy, and LAZ.
- High-detail zoom/chunked delivery for close-range terrain fidelity.

This branch is tracked in:

```text
docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md
```

Near-term target: review the generated Guadalupe Cypress 4096 and 8192
single-tile scenes plus the 16K RGB stress scene, then decide whether the next
investment should be baked ground materials, procedural close-detail blending,
or chunked high-detail delivery.

Current HD audit:

```text
docs/OPENTOPO_PHASE2_HD_REVIEW.md
docs/OPENTOPO_PHASE2_MAX_REVIEW.md
```

## Deferred

- **LOD**: decide when performance forces it. Probably during Phase F
  when multi-tile loads stress the GPU. Not a planning priority now.
- **DEM analyzer / kernels**: long-term goal but no current pressure.
  Real DEMs from OpenTopo are sufficient for the foreseeable future.
- **Procedural generator**: dependent on kernels.
- **Real water / sea level / scatter / vegetation**: gameplay layer,
  out of scope for terrain phases.

## Phase order

Roughly sequential but Phase F can start in parallel with E if
desired. A → B → D → C → E → F is a sensible default. C might come
earlier if framing concerns block visible progress.

Each phase's first action is a small written plan (PLAN.md rewrite)
that decomposes the phase's checklist into the next session's worth
of work.
