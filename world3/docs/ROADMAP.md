# world3 — Roadmap (v2)

Reframed 2026-05-07 after stocktake. The v1 roadmap (DEM analyzer →
procedural generator → infinite world) is archived in
`ROADMAP_v1_archived.md`. v2 is grounded in the concrete quality gaps
we surfaced through Phase 1 and Phase 2 — not the ambition-end of the
project.

**Long-term direction unchanged**: continuous / potentially infinite
world, real-DEM grounded, optionally procedural for arbitrary
extension. v2 just changes what we work on *first* to get there.

---

## 2026-05-08 update — operating-model + sequence revision

Two changes since the original v2 reframe:

1. **Single-stream orchestrator/worker model.** The world3 main chat
   is the orchestrator (owns roadmap + most work + cross-cutting
   decisions). The OpenTopo chat is a worker that takes scoped
   handoffs. State + boundary + handoff protocol live in
   [`WORLD3_STATE_2026_05_08.md`](WORLD3_STATE_2026_05_08.md).
   Replaces the "two parallel pipelines" framing.

2. **Phase F absorbed into M1–M6.** Once we recognized that
   material taxonomy + transitions + splat shader + chunk size are
   interlocked, doing them as a sequential "Phase F → G → H → I"
   was wrong. M1–M6 in [`PLAN.md`](PLAN.md) is the current
   iteration:
   - M1 — material catalog (orchestrator-led, blocks rest)
   - M2 — transition prototype (worker handoff)
   - M3 — chunk-size sweep (orchestrator, was Phase F.4-sweep)
   - M4 — splat-shader prototype (orchestrator, after M1+M2)
   - M5 — wire streaming + splat into `walk.tscn` (orchestrator)
   - M6 — harden streamed runtime: cache, collision, transition hook, source QA

The phase-by-phase content below stays accurate as historical
record + design notes (especially Phase F's research findings + the
Recommended Transition Pipeline). Treat this section as the current
direction; treat the rest as where we've been.

**Current status after the 2026-05-08 pass**:

- M1 material catalog is done and committed.
- M3 chunk-size sweep is done and locks 256 m as the synchronous base
  chunk size.
- M2 transition prototype pass 3 is done: four catalog-driven strips
  exist, user review says the transition workflow is promising, the
  clean Godot review scene plus score hints are in place, and rule-level
  tuning has been applied.
- M2 transition asset contract is resolved: generated boundary assets are
  referenced by `world3/jobs/biome_transition_rules.json`; base materials stay
  in the material catalog.
- M4 unified splat shader prototype pass 2 is done: a fixed five-slot shader
  renders height/slope fallback, RGBA splat weights, and OpenTopo macro/detail
  material compatibility; `ChunkLoader.gd` can now bind the runtime splat
  weight texture through the chunk material/weight contract.
- M5 is complete at prototype final form: visible terrain streams through
  256 m `ChunkLoader.gd` chunks using `terrain_splat_alpine.tres`. Static,
  short-crossing, and long-form sampled walk evidence live in
  `world3/docs/M5_WALK_SPLAT_STREAMING.md`; budget evidence lives in
  `world3/docs/M5_STREAMING_BUDGET.md`; the M1-M5 closure audit is
  `world3/docs/M1_M5_FINAL_AUDIT_2026_05_08.md`.
- M6 hardening is complete for the primary walk/runtime path: generated
  height/splat inputs have export-safe runtime caches, `walk.tscn` uses
  streamed chunk collision, the unified splat shader has an opt-in runtime
  transition-strip sampler, and green/organic source material noise has a
  machine-readable audit. Evidence:
  `world3/docs/M6_RUNTIME_HARDENING.md` and
  `world3/docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.md`.
- M7 pass 1 is complete for workflow/runtime validation: streamed chunks can
  generate rule-driven transition masks, bind catalog material pairs, and sample
  transition manifests without manual shader-position knobs. Evidence:
  `world3/docs/M7_BOUNDARY_RUNTIME_INTEGRATION.md`.
- M1-M7 visual audit is complete and downgrades M7 to workflow pass / visual
  rework. Current M4/M5/M7 terrain captures are diagnostics, not visual
  milestone closure. Evidence:
  `world3/docs/M1_M7_VISUAL_AUDIT_2026_05_08.md`.
- Visual remediation plan is active before normal M8 progress. Evidence:
  `world3/docs/M1_M7_VISUAL_REMEDIATION_PLAN_2026_05_08.md`.
- First remediation bridge is complete enough for review: runtime terrain can
  use OpenTopo source macro albedo with low-strength tileable detail, and the
  worst organic materials now have quarantined repair candidates. Evidence:
  `world3/docs/SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md` and
  `world3/docs/M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md`.
- ComfyUI/`aaa_texture.py` is now explicitly tracked as the peer procedural
  material lane for M8: 25 generated materials are inventoried, five organic
  blockers have a regeneration queue, and full-PBR runtime staging is auditable.
  First grassland blocker regeneration produced a strict-gate-pass candidate
  that also passed the first terrain-context candidate review. It remains
  quarantined because detail stress still reads slightly pale/hazy; use it for
  M4/M7 rerender trials before canonical promotion.
  Evidence: `world3/docs/COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md`
  and `world3/docs/M8_COMFYUI_TEXTURE_REGEN_PASS_2026_05_08.md` and
  `world3/docs/M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md`.
- Visual target is now explicit: reach roughly 70 percent of the best stacked
  photo/topo OpenTopo reference quality before visual milestone closure.
  Evidence: `world3/docs/M1_M7_VISION_GAP_REVIEW_2026_05_08.md`.

Recommended next lane: finish the **M7-M12 near roadmap**. The six-step sequence is now
explicit in [`M7_M12_NEAR_ROADMAP.md`](M7_M12_NEAR_ROADMAP.md):

1. M7 biome-boundary runtime integration. Runtime pass complete; visual
   remediation required before visual closure.
2. M8 organic source-material cleanup. Start with the ComfyUI regeneration
   queue plus source-stack terrain review; deterministic repair candidates stay
   quarantined until promoted.
3. M9 runtime performance and interaction polish.
4. M10 cross-source blending.
5. M11 corner and junction transitions.
6. M12 walk/iso/topdown view-mode parity.

Deferred systems (scatter, props, buildings/POIs, fantasy biome expansion, full
procedural infinite-world generation) stay parked until that lane proves the
terrain foundation.

Workflow snapshot: [`WORKFLOW_SNAPSHOT_2026_05_08.md`](WORKFLOW_SNAPSHOT_2026_05_08.md).

---

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

## Phase A polish — pipeline foundation hardening (DONE 2026-05-07)

Bridge between Phase A's prompt R&D and Phase B's upscaling. The
deferred items from Phase A's exit notes turned out to have higher
leverage than expected once we sat with them. This iteration is
*workflow + tooling* improvements — not new outputs, but stronger
foundations that every future material benefits from.

Operating principle (per user 2026-05-07): "build tools and workflow
improvements that future work depends on. Order tasks so each one's
output feeds the next, not the other way around."

Checklist:
- [x] **A.7 — Richness QA metric (advisory)**. New `richness` check
      in `texture_qa.py` that defends against the "smooth-A" failure
      mode (LESSONS L16). Combined `0.5 * (entropy/5 + p99_norm/0.4)`,
      per-category thresholds. Calibrated across 122 textures: all
      11 wgv3_* shipping pass, all 5 known smooth-A cases fail.
      Currently advisory (computed + printed but not folded into the
      A/B/C/D grade) so existing texture grades don't shift. Promote
      to hard gate after a few sessions of watching.
      Commit: `b551203`. Details: TEXTURE_RND.md "A.7" entry.

- [x] **A.8 — CHORD opt-in PBR backend**. Per the 2026-05-07 research
      handoff. Added `aaa_texture.py --pbr-backend {derive,sm,chord}`
      flag. CHORD (Ubisoft La Forge, SIGGRAPH Asia 2025) wins normals
      + height on hard-edge geometry; loses on rock roughness. Kept
      opt-in (not default) — the rock-roughness regression is real.
      Required a transformers 5.x compat patch in the upstream nodes
      and a gated HF model download. Don't migrate the existing
      shipping set. Commit: `ee73ccd`. Details: TEXTURE_RND.md "A.8"
      + DECISIONS.md "CHORD as opt-in PBR backend".

- [x] **A.9 — variant_blend rescue tool**. New
      `pipelines/textures/variant_blend.py`: combines N tileable
      variants into one tileable tile via softmax-weighted blending
      of tileable noise masks. Real trade-space, not a magic bullet:
      `--sharpness 12` cuts periodic from 19.5 → 8.5 on stuck-lattice
      cases (leaf_litter seed-300) at the cost of slightly worse
      edges. Manual rescue; not folded into orchestrator default.
      Commit: `530db77`. Details: TEXTURE_RND.md "A.9" entry.

- [x] **A.10 — Reference-image anchor mode on flux_seamless.py**.
      Took 3 attempts to land — handoff's "IP-Adapter drop-in" framing
      was based on FLUX.1 D, not klein-4B. Working design uses klein-
      native img2img with `BasicScheduler` (Flux2Scheduler silently
      ignores `denoise`). `--reference-image` + `--reference-mode
      anchor` + `--reference-denoise 0.70-0.88` works; final output
      shows clean reference influence (snow + brown forest_floor
      reference at 0.70 = "fresh snow over leaf bed" composite look).
      Heal pass surgically opts into BasicScheduler in anchor mode;
      default behavior unchanged for non-reference runs. Commit:
      next. Details: TEXTURE_RND "A.10" entry. **Surfaced unrelated
      issue:** Flux2Scheduler drops `denoise` project-wide; logged
      as a future audit task below.

- [x] **A.11 — CHORD + SM-roughness hybrid**. New
      `--pbr-backend chord_sm_rough` runs CHORD for albedo/normal/
      height/metallic/ao + SM for roughness only. A/B on rock_dark
      verified: lifts gate from FAIL→PASS (rough std 0.011→0.029,
      range 0.58–0.71→0.44–1.00) while preserving CHORD's geometry.
      Default + existing backends unchanged; `chord_sm_rough` is
      opt-in for Rock-class materials. Commit pending. Details:
      TEXTURE_RND "A.11" + DECISIONS "CHORD + SM-roughness hybrid".

Exit criteria for this polish phase:
- IP-Adapter wired into `flux_seamless.py` with at least one A/B
  showing reference-conditioning lifts material accuracy on a
  representative case.
- CHORD+SM-roughness hybrid available as a backend option, with
  A/B confirming it's not worse than either alone on rock.
- All wins documented in TEXTURE_RND Part 1; cookbook updates if
  any defaults shift.

Open / parked candidates (not in this phase):
- Auto-rescue mode (orchestrator detects "all variants share lattice"
  and falls through to `variant_blend`) — depends on more lattice
  cases to calibrate.
- Promote `richness` from advisory to hard-gate — wait until A.10/A.11
  finish so we have more data on whether new generations score
  consistently.
- Hero-mesh lane via Hunyuan3D-Paint 2.1 (handoff decision #3) —
  user "we'll see"; deferred.
- **klein-9B Edit** (vs the klein-4B we use now) — purpose-built
  image-edit variant of FLUX 2. Stronger native reference handling
  than what we got out of klein-4B + img2img anchor in A.10. Larger
  model (~9B vs 4B), separate gated download, slower inference. Not
  needed if A.10's working anchor mode covers our use cases; revisit
  if/when we need stronger material accuracy from references than the
  anchor approach delivers.
- **Honest partial-denoise heal pass audit** (surfaced by A.10c) —
  `Flux2Scheduler` silently drops `denoise`, so our heal pass has
  been running at full denoise=1.0 the whole project. Empirically
  fine, but switching all heal runs to `BasicScheduler` at honest
  `denoise=0.5` could improve content preservation. Requires A/B
  against the entire wgv3_* shipping set to confirm no regression.
  Half-session of work + careful evaluation. Lower priority than
  A.11/Phase B; pick up if/when seam quality starts mattering.
- **Curated reference photo set** for A.10 anchor mode — small
  library under `world/textures/references/` with 5-10 high-quality
  real-world material photos (dirt, rock, snow on leaves, etc.)
  that Phase B + future kits can use as anchors for material
  accuracy. ~half session to source + organize.

## Phase B — Upscaling + multi-resolution pipeline (DONE 2026-05-07)

Currently 512 throughout. Some uses (close-walk, hero materials, large
iso-camera footprint) need more. Some uses (mid-range topdown, far
foreground in walk) don't.

Foundation it'll consume from Phase A polish:
- Richness QA gate (A.7) catches smooth-A failures at every
  resolution tier.
- CHORD backend (A.8) provides sharper normals/heights for hard-edge
  materials at 1024 native — pairs naturally with upscaling.
- IP-Adapter (A.10, when done) adds reference-photo accuracy to FLUX
  outputs that get upscaled.

Checklist:
- [x] B.1 — SR survey + first SR tool (Real-ESRGAN via ComfyUI) — `sr_upscale.py`
- [x] B.2 — `bake_pbr.py` — high-res re-derive of normal/AO/roughness
- [x] B.3 — `mip_ladder.py` — 2K master → 2K/1K/512 with per-map correct filtering
- [x] B.4 — Per-tier QA wiring — `texture_qa.py --ladder` + cross-tier contact sheet
- [x] B.5 — Orchestrator integration — `aaa_texture.py --ladder` + flagship ladder
- [ ] B.6 — Alternative SR backends (optional; only if survey supports a better default)

Exit criteria:
- [x] One command produces a full mip ladder per material (`aaa_texture.py --ladder`)
- [x] Cross-tier QA wired (`texture_qa.py --ladder-dir`) with contact sheet
- [x] Flagship rock_dark full ladder shipped + reviewed (B5_flagship captures)
- [x] Documented per-backend bake rules (`bake_pbr.py` ROUGHNESS_BLEND_ALPHA table)
- [ ] B.6: alt backends evaluated (deferred; pursue if material-class gap surfaces)

## Phase C — Iso/topdown scale review (DONE 2026-05-07)

Auto-frame works for "render whole tile" but not for "render the area
around a player" or "render at a fixed game-relevant zoom level."

Checklist:
- [x] Define the target zoom levels. Locked in `world3/scripts/CamFraming.gd`:
      - Iso ARPG: 40m diameter (Diablo, PoE)
      - Iso strategy: 300m diameter (Civ, RTS)
      - Topdown game-tile: 50m diameter (Stardew-ish)
      - Topdown minimap: 10km diameter (whole-region)
- [x] Add a "framing target" mode to IsoCam / TopDownCam. Both scripts
      now support `anchor_path` + `visible_diameter_m`. Falls through
      to legacy auto-AABB when anchor isn't set — non-breaking.
- [x] A "player anchor" concept — `world3/scripts/PlayerAnchor.gd`,
      a Node3D that snaps Y to the actual terrain surface by sampling
      the heightmap (matches Terrain.gd 1:1).
- [x] Capture the same region at each zoom level for visual review.
      4 captures under `world3/docs/captures/phase_c/` against Tetons
      (4km, alpine kit). Minimap shows whole region with all biome
      blends; iso/topdown close zooms show snow surface in alpine
      center. Re-shoots with mid-elevation anchors are a polish task.
- [ ] Walk/iso/topdown shared-anchor decision deferred until walk-mode
      wires into the same anchor system. Open follow-up.

Exit criteria — all met:
- [x] IsoCam/TopDownCam scripts support both auto-AABB and
      framed-around-anchor modes (non-breaking; existing scenes
      unaffected).
- [x] Each game mode has 1-2 example captures (4 captures shipped,
      handoff at `docs/handoffs/HANDOFF_phase_c_anchor_framing_2026_05_07.md`).

Renderer caveat: the SceneTree-script runner hangs in `--headless`
(process_frame awaits never resume). Run captures without `--headless`
— ~2s/scene with a real window. Documented in captures/README.

## Phase D — Biome generalization (DONE 2026-05-07)

5 biome kits defined; only 3 (alpine, desert, tundra) have purpose-built
textures. temperate_forest and grassland reuse alpine textures, which
makes some regions look wrong (California chaparral with alpine
materials, Serengeti with alpine grass).

Checklist:
- [x] Generate temperate_forest kit (5 textures, palette-locked).
      wgv3_tf_leaf_litter (anchor) / wgv3_tf_loamy_soil / wgv3_tf_mossy_rock /
      wgv3_tf_bark_rock / wgv3_tf_fern_ground. All at grade A or B.
- [x] Generate grassland kit (5 textures, palette-locked).
      wgv3_gl_tall_grass (anchor) / wgv3_gl_dry_thatch / wgv3_gl_hardpan_soil /
      wgv3_gl_grass_rock / wgv3_gl_weathered_stone. All at grade A or B.
- [x] Apply Phase A learnings (better prompts, better settings) so
      these kits ship at higher first-pass quality than desert/tundra.
- [x] Re-run biome_consistency on every kit. Document the verdict
      table.
- [x] Re-capture region gallery with all 5 kits visible (2026-05-07).
      Captures in `world3/docs/captures/phase_e_gallery/` (the gallery
      was extended in Phase E to swap iso vs topdown materials per shot,
      so the post-fix captures live with the Phase E set). Surfaced and
      fixed a kit-binding bug: `terrain_blend_temperate_forest.tres`
      and `terrain_blend_grassland.tres` still pointed at alpine
      defaults. New tool `pipelines/textures/deploy_kit_to_world3.py`
      reads biome_kits.json and rebuilds the .tres files. After fix,
      chaparral renders correctly without snow caps.
- [ ] Optional: generate alternate variants of a slot for visual
      variety (3 grass-types in the grassland kit, randomized per
      region). Deferred.

Exit criteria — met:
- [x] All 5 kits have purpose-built textures and bound .tres materials.
- [x] All sampled regions render through their assigned kit. alpine,
      desert, tundra, temperate_forest read correctly. grassland is
      bound correctly but slope/height tuning leaves Tibet+Serengeti as
      near-uniform tall_grass — open as a Phase E or polish task, not
      a Phase D blocker.

## Phase E — Per-game-mode material tuning (DONE 2026-05-07)

The decision-locked principle "walk/iso/topdown are different games"
hasn't been implemented yet. Same material is bound to all three
scenes, with the same UV scale and shader params. They should each
own their tuning.

Checklist:
- [x] Per-mode material variants: each kit emits
      `terrain_blend_<kit>_<mode>.tres` for walk/iso/topdown via
      `pipelines/textures/emit_per_mode_materials.py`. 15 .tres
      committed (5 kits x 3 modes).
- [x] Tuning targets per mode (locked in MODES table of the emit tool):
      - **walk**: world_uv_scale 0.4 (~2.5m repeat), normal_strength
        1.2, macro_value 0.05, blend_sharpness 12.0
      - **iso**: world_uv_scale 0.1 (~10m repeat), normal_strength
        1.0, macro_value 0.15, blend_sharpness 8.0 (current default)
      - **topdown**: world_uv_scale 0.02 (~50m repeat), normal_strength
        0.4, macro_value 0.35, blend_sharpness 4.0
- [x] Per-mode capture sweeps to validate. 3 alpine captures in
      `world3/docs/captures/phase_e/` show clear visual differences:
      walk = surface detail, iso = mid blend, topdown = color blocks.
- [x] Update `RegionGalleryCapture` and the per-mode capture scenes
      (`walk.tscn`/`iso.tscn`/`topdown.tscn`) to pick the right
      `_<mode>.tres`. Gallery derives per-mode material paths from
      `biome_kit_material` and swaps `material_override` between
      iso and topdown shots; re-pushes elev_min/range to each newly-
      bound ShaderMaterial. Game scenes now point at
      `terrain_blend_alpine_{walk,iso,topdown}.tres`.

Exit criteria — all met:
- [x] Each game mode has its own material variant per kit.
- [x] Same region rendered through the 3 modes shows clearly different
  treatments (close detail vs. mid detail vs. flat color blocks).

## Phase F — Multi-tile / continuous world (NEXT)

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

Updated target after tileable texture review:

- Do not keep polishing one repeated orthophoto tile. It can be seamless and
  still read wrong because real shrubs, rocks, drainage marks, and image noise
  repeat at the wrong scale.
- Split real-ground material work into `macro / meso / micro` layers:
  broad real map color, unlike real crop variants, and cleaned close detail.
- Build unlike tile-to-tile review first: several sibling real crops for one
  material class, mixed in a `16 x 16` Godot grid.
- Only after that review passes, move the variant set into a real shader path
  with texture arrays/atlases and soft per-cell blending.

Immediate OpenTopo texture sprint status:

1. Done: `dry_wash` unlike-variant atlas and hard-mixed QA scene.
2. Done: `4096` soft-composite output that blends unlike variants instead of
   hard-switching at tile borders.
3. Done: six material classes generated with the same soft-composite workflow:
   `bare_soil`, `bright_rock`, `dry_wash`, `rocky_slope`, `scrub_dense`, and
   `scrub_sparse`.
4. Done: finish pass writes balanced albedo, neutral source-derived detail maps,
   and `terrain_hex_detail` Godot materials for all six classes.
5. Current review: use `tileable_finished_material_review.tscn` and the real
   Godot captures to mark which classes work at close, mid, and far camera
   distances.
6. Next build step: promote viable classes into the normal world3 material
   library and use the full real map as macro color/reference instead of
   treating one orthophoto composite as every scale of ground detail.

Current HD audit:

```text
docs/OPENTOPO_PHASE2_HD_REVIEW.md
docs/OPENTOPO_PHASE2_MAX_REVIEW.md
docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md
docs/OPENTOPO_TILEABLE_TEXTURE_PILOT_AUDIT.md
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

Originally A → B → D → C → E → F. Actual order shipped:
A (done) → A polish (done) → B (done) → C (done) → D (done) → E
(done) → F (next).

C/D/E all landed in a single 2026-05-07 evening session. D's
kit-binding bug was surfaced by the C-D handoff capturing a regression
on chaparral/grassland regions; the fix mechanism (`deploy_kit_to_world3.py`)
ended up being the same plumbing E needed for per-mode emission, so
D and E share the texture-deploy / .tres-rewriting tooling.

Each phase's first action is a small written plan (PLAN.md rewrite)
that decomposes the phase's checklist into the next session's worth
of work.
