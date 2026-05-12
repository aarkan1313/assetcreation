# Handoff prompt — fresh roadmap, post-rebuilds

> Paste into a new chat to pick up W4 work after the 2026-05-12 long
> session. The session reset priorities, rebuilt the texture pipeline
> from scratch, added a walking player controller, and ran two full
> biome diversity batches. This handoff sets the next chat up to work
> on the new tiered roadmap.

---PROMPT START---

I'm continuing a project called World 4 (W4). It's a Godot 4.5 + Python
world-generation system. Working directory: `D:\assets\world 4\`.

## Read these docs in order before doing anything

The roadmap was rewritten this session. The new tier order is the source
of truth for "what to work on next."

1. **`docs/README.md`** — index of everything in docs/.
2. **`docs/ROADMAP.md`** — **rewritten 2026-05-12 with user-priority
   tiers.** Replaces the prior "Strand A vs B" framing. Read this
   carefully; it's what shapes the rest of the session.
3. **`docs/STATE.md`** — current state snapshot.
4. **`docs/strategy/WISHLIST.md`** — has two major new entries added
   2026-05-12: **stochastic ground texturing** (3-tier MVP-to-AAA
   architecture) and **vegetation + organic-asset system**.
5. **`docs/features/textures.md`** — canonical W4 texture pipeline
   doc. The pipeline was rebuilt this session — don't reach for
   old `aaa_texture.py` references.
6. **`docs/reference/PITFALLS.md`** — terrain artifact debugging.
7. **`docs/reference/TOOLS.md`** — one-line-per-item tool index.

## What just shipped in the last session (so you don't redo it)

This was a long session — multiple bigger pieces landed. Pulling them
out so you don't trip over them:

### Texture pipeline — fully rebuilt
- W4-owned `pipeline/textures/` package (the `tx_*` modules) replaces
  the shared infra at `D:/assets/pipelines/textures/` for W4 use. The
  shared infra is read-only for W4 now — reuse its pure functions but
  don't modify it.
- Hybrid PBR backend (`tx_pbr_hybrid.py`): StableMaterials runs the
  tileable diffusion (we keep ONLY its albedo, which closes the
  midline-cross seam), then `derive_pbr_v2` builds the rest of the
  PBR maps from that cleaned albedo. This was an unexpected finding —
  see `docs/plans/TEXTURE_PIPELINE_FINDINGS_2026_05_12.md` for the
  full diagnostic chain. Audit was wrong on 3/4 predictions; the
  empirical answer was different. Don't reflexively swap stages
  without re-running validation.
- New `mip32_stdev` QA metric catches the "vanishes at terrain
  distance" failure that the prior 3-check metric missed.
- Per-category thresholds calibrated against actual outputs: Snow=6,
  Sand=6, Rock=8 for mip32_stdev (in `tx_qa.W4_CATEGORY_OVERRIDES`).
- New nested candidate layout at `the world 4/candidates/<biome>/
  <slot>/_review/<NN>_<tag>/` (post-cull) with `_to_delete/` siblings
  consolidated to `world 4/_to_delete/<biome>/<slot>/` for bulk removal.

### Two diversity batches shipped end-to-end
- **Alpine** (51 prompts, 16/21/14): 32 A / 15 B / 4 C / 0 fail.
  Culled by user to 5 ground / 13 mid / 11 rock = 29 keeps. Rest
  moved to `world 4/_to_delete/alpine/`.
- **Desert** (51 prompts, 16/21/14): 21 A / 21 B / 9 C / 0 fail.
  Final summary written but **NOT YET CULLED** — user review pending.
  Contact sheets at `the world 4/candidates/desert/{ground,mid,rock}/
  _contact_sheet.png` (also `_contact_sheet_b_c_d.png` for rejects).

### Walking player controller (test harness)
- New `scripts/test_harness/PlayerBody.gd` — CharacterBody3D capsule
  with gravity + collision + own camera + G fly-toggle + own HUD.
  Sits BESIDE AnchorCameraRig — does NOT replace it. Anchor +
  scale_demo + every existing capture scene are bit-identical by
  construction.
- Opt-in test scenes at `scenes/test_harness/clipmap_walk_test.tscn`
  and `capture_clipmap_walk_test.tscn` (with `ForceWalkPhysics.gd`
  helper for landing tests).
- Mouse capture auto-toggles on activate/deactivate; click-to-recapture.
- Full build-note at `docs/build-notes/PLAYER_CONTROLLER_BUILD_NOTES_2026_05_12.md`.

### Axis 1 Path 2 — Stage 4.1 (single-biome rendering proof)
- `ClipmapWorld.gd` refactored: async heightmap regen now uses a
  `HeightmapRefreshJob` RefCounted class with its own composer ref;
  worker never writes scene-owned state. Sets up Stage 4.2 multi-
  biome biome-culler work.
- `terrain_world_v3.gdshader`: splat `sampler2DArray` + global PBR
  ground `sampler2DArray` uniforms + fragment-loop fallback to
  `base_albedo` when uniforms aren't bound. Single-biome proof
  shipped with A/B captures.
- Build-note: `docs/build-notes/STAGE4_1_BUILD_NOTES_2026_05_12.md`.
- **Editor verification still pending user** for stages 2-3.6 + 4.1.

### Documentation refresh
- `docs/features/textures.md` — new canonical W4 texture pipeline doc.
- `pipeline/textures/README.md` — code-side quick reference.
- Audit + findings docs (`TEXTURE_PIPELINE_AUDIT_2026_05_12.md` and
  `TEXTURE_PIPELINE_FINDINGS_2026_05_12.md`) marked HISTORICAL with
  pointers to the canonical doc.
- `docs/STATE.md`, `docs/ROADMAP.md`, `docs/reference/TOOLS.md`,
  `docs/README.md`: all updated to reference the rebuilt pipeline,
  not the old `aaa_texture.py` path.
- `docs/strategy/WISHLIST.md`: two new sections (stochastic texturing,
  vegetation).
- ROADMAP rewritten with user-priority tiers (see below).

### Other miscellany
- Shared `pipelines/textures/texture_qa.py` Snow/Sand/Water/Liquid
  periodic threshold tightened 18 → 13 (calibrated against the
  alpine batch — that's the only shared-infra change made this
  session).
- `.gitignore` rule added to skip `world 4/_to_delete/` trash root.

## The new tiered roadmap (2026-05-12)

The previous "Strand A vs Strand B" framing is gone. User reset
priorities. New tier order:

**Tier 0 — Cross-cutting (always apply)**
- Performance floor: RTX 3060/4060. Every new feature benchmarks or
  is gated behind a quality tier (use `config/quality_tiers.json` +
  `pipeline/quality_tiers.py` + `scripts/QualityTiers.gd`).
- LLM-drivability — schema + validator + deterministic outputs.

**Tier 1 — World scope (active next)**
1. Finish Axis 1 Path 2 — Stage 4.2 (multi-biome culler) + editor
   verification of stages 1-3.6 + 4.1.
2. Remove world-bound for infinite world. `ClipmapWorld` currently
   has a soft 4 km bound; remove the assumption so distant tiles
   generate from kernels on demand. True procedural infinite via
   `NoiseStackKernel` (and future kernels).
3. Skybox + atmosphere. Procedural sky, fog, distance haze, minimal
   time-of-day. NEW shader + scene setup.
4. Intra-biome regional variation v0 — tile scale (MVP-floor from
   wishlist "Stochastic ground texturing").

**Tier 2 — Inhabiting the world**
5. Procedural decoration v0 (Axis 5). Rocks, plants, debris. Designed
   so individual instances can be hand-authored-overridden later
   (replace-seam pattern). Long-arc plan in wishlist "Vegetation +
   organic-asset system".

**Tier 3 — Texture / biome workflow polish**
6. Stochastic per-tile texturing MVP-good (adds stochastic UV
   sampling on top of Tier 1's MVP-floor).
7. Easier biome-author loop. `promote_candidate.py` script,
   palette-lock authoring, batch UX, workflow docs.
8. Intra-biome variation cluster-scale and sub-biome scale.
9. AAA-target compositor — only if Tier 1+3 stochastic doesn't
   close the visible-tile-repeat gap empirically.

**Tier 4 — Output models (deferred)**
10. Offline bake renderer.
11. 2D-game integration recipe.
12. Per-game packaging.

The wizard game's 2.5D framing leans on Tier 4 eventually. Path to
"real game" still goes through Tier 1-2 first.

## Where to start

Read ROADMAP.md, then pick from Tier 1. The natural next pieces:

- **If Axis 1 Path 2 editor verification is the blocker**: ask the user
  whether they've verified stages 2-3.6 + 4.1 in the editor yet. If
  not, that's a prerequisite to Stage 4.2.
- **If Stage 4.2 (multi-biome culler) is ready to start**: the design
  is in `superpowers/specs/2026-05-12-clipmap-splat-biomes-design.md`.
- **If the user wants the "true infinite" item first**: it's smaller
  scope (remove the 4 km bound from `ClipmapWorld`) and probably 1-2
  sessions.

## Methodological rules to remember

- W4 owns `pipeline/textures/`. Don't modify `D:/assets/pipelines/
  textures/` — that's shared infra, read-only for W4.
- For W4 work, the project ethos is **Quality ≥ Performance > anything
  else > time-to-ship**. No deadlines; always pick architecturally
  correct even if more sessions.
- LLM-drivability is a cross-cut: every layer should be schema +
  validator + deterministic so a future LLM agent can drive it.
- Performance gates everything past Tier 0; route new tunables
  through `quality_tiers.json`.
- Texture pipeline defaults are LOCKED based on the diagnostic chain
  in `TEXTURE_PIPELINE_FINDINGS_2026_05_12.md`. Don't change defaults
  without re-running the validation set.
- Editor verification is mandatory for visual changes (headless
  captures hide bugs editor shows — see PITFALLS #6b).
- Don't launch the Godot editor from within agent shells (auto-fires
  "completed" before the window opens). Print the launch command
  for the user to run manually.

## Current desert batch state — needs user attention

The desert diversity batch JUST finished. Outputs at `the world 4/
candidates/desert/{ground,mid,rock}/`. Contact sheets ready.

**Pending action**: user reviews + culls (same flow as alpine — keeps
go to `_review/`, discards to `_to_delete/desert/<slot>/`). See the
alpine reorg commit `935a286` for the pattern.

If the user wants to skip the cull and move to roadmap work, that's
fine — the candidates can sit. But mention the pending review.

## Useful state

- Recent commits: `git log --oneline -25` from this session shows the
  whole arc.
- Memory file `w4_texture_pipeline_2026_05_12.md` summarizes the
  texture pipeline rebuild for future sessions.
- Background task `bsfgcwz98` (Monitor) was the desert batch progress
  watcher; it has timed out by now, just informational.

---PROMPT END---
