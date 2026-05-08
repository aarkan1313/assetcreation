# Next-Session Prompt

Copy/paste this as the opening message in a fresh session. It contains
the minimum context to pick up where the last session left off,
without re-reading everything. Past-session, you wrote it to yourself.

---

## Session opener (copy from here)

We just finished **Phases B/C/D/E** on world3. Texture pipeline,
camera framing, biome generalization, and per-game-mode material
tuning are all in place. **All work is committed.**

**Next up is Phase F: multi-tile / continuous world** — walk off the
edge of one region into another seamlessly. Current "regions" are
4-20km tiles loaded one at a time; we don't stream. This is a research
+ prototype phase, not a single-session item.

**Project state**: world3 is a real-DEM-driven terrain generator at
`D:/assets/world3/`. The phase ledger after this session arc:

- Phase 0-2.5: MVP loop, shader stack, biome kits, region gallery — DONE
- Phase A:    texture quality + prompt R&D — DONE
- Phase A polish: 4 PBR backends, richness gate, variant_blend, reference anchor — DONE
- Phase B:    SR + mip-ladder + per-tier QA via `aaa_texture.py --ladder` — DONE (`84ed00e`, `6e62b37`)
- Phase C:    anchor-mode framing + PlayerAnchor + zoom captures — DONE (`1dee0f8`, `eca28ba`, `8ca2ec0`)
- Phase D:    all 5 biome kits with bound .tres + region gallery — DONE (`ca171e9`, `4b53a0f`, `2d92cd1`)
- Phase E:    per-mode material variants wired into game scenes + gallery — DONE (`c4d68c0`, `75b15d1`, `2346acf`)

**Read these first, in order, ~15 min total**:

1. [`world3/docs/README.md`](world3/docs/README.md) — docs index. Get oriented.
2. [`world3/docs/PLAN.md`](world3/docs/PLAN.md) — current iteration: B/C/D/E recap and Phase F plan.
3. [`world3/docs/ROADMAP.md`](world3/docs/ROADMAP.md) — Phase F scope under "Phase F — Multi-tile / continuous world".
4. [`world3/docs/captures/phase_e_gallery/`](world3/docs/captures/phase_e_gallery/) — 7-region gallery showing all 5 kits through both iso and topdown modes. Visual review of the iteration's outputs.
5. [`world3/docs/captures/phase_c/`](world3/docs/captures/phase_c/) — anchor-framing zoom-level captures (40m / 300m / 50m / 10km).
6. [`world3/docs/captures/phase_e/`](world3/docs/captures/phase_e/) — alpine walk/iso/topdown sanity captures.

## Phase F scope (from ROADMAP.md)

The long-term goal is continuous / potentially infinite world. We don't
need to solve infinite-world today, but we should build a small
proof-of-concept.

Checklist:

1. **Research existing approaches**:
   - Godot 4 chunk streaming patterns (built-in or library).
   - Existing terrain plugins (Terrain3D, HTerrain) — feasibility of
     integrating with our heightmap + blend material approach.
   - Memory budget per chunk.
2. **Design**: what's a "chunk"? Current "region" is 4-20km — too
   big for walk-mode streaming. Chunks probably want to be 256-512m.
3. **Small test**: 2x2 grid of identical Tetons tiles at 4km each,
   stitched. Verify:
   - No visible seam between tiles.
   - No double-load of shared edge.
   - Mesh continuity at boundaries.
4. **Decide**: keep one heightmap per region, or split regions into
   multiple chunks at build time?

**Exit**:
- Walking off the edge of one tile and into another works without
  visible discontinuity.
- Documented streaming budget (how many tiles loadable at once before
  frame budget breaks).
- Decision-locked on chunk size + format.

## Open polish items (parked, can pick up before F)

None block Phase F, but each is small enough to fit before/within an
F session:

- **Grassland slope/height tuning.** Tibet + Serengeti currently read
  as near-uniform tall_grass. Kit binding is correct; `slope_threshold`
  / `h_grass_dirt` need lowering so rock/dirt show through on slopes.
  Half-session of param sweeping + recapture.
- **Non-alpine per-mode visual review.** Phase E's emit tool covers
  all 5 kits; only alpine got dedicated capture scenes. Other kits
  validated only via the gallery's per-mode swap. Could add
  kit-specific capture scenes for closer inspection.
- **Walk-mode shared-anchor decision.** Phase C deferred whether walk
  shares a `PlayerAnchor` with iso/topdown or each gets its own.
  Decide when walk-mode wires into the anchor system.
- **Region gallery: walk shot.** Gallery currently produces iso +
  topdown per region; could add a walk shot using the walk-tuned
  material. Walk needs an eye-level Camera3D pose.

## Operational reminders

- **Godot binary**: `C:/Godot/Godot_v4.5-stable_win64.exe`.
- **Always run captures WITHOUT `--headless`.** The SceneTree-script
  runner pattern hangs in headless (process_frame awaits never resume
  reliably). Real-window mode is fast (~2s/scene) and produces correct
  output. See `world3/docs/captures/phase_c/README.md` for the
  documented gotcha.
- **After deploying / regenerating any .tres**, run
  `Godot --headless --editor --import` once before capturing to register
  new texture .import metadata.
- **D: drive**: was 100% on 2026-05-06. Check `df -h /d` before bulk
  pulls / multi-tile runs.
- ComfyUI: test with `curl -fsS http://127.0.0.1:8188/system_stats`.
  If down: see `pipelines/textures/RECIPES.md` "Prerequisites".
- Always set `$env:PYTHONIOENCODING="utf-8"` in PowerShell.

## What I'd ask before doing anything

Phase F is the next ROADMAP item but it's a research + prototype
phase, not a single-session item. The user may prefer to:

> "Phase F is research-heavy and not a single-session task. Want me
> to start the research phase, or pick up one of the open polish items
> (grassland tuning, non-alpine per-mode review, region-gallery walk
> shot, walk-anchor wiring) first?"

If they say start Phase F, begin with the research bullet — survey
Godot chunk-streaming patterns and Terrain3D/HTerrain integration
feasibility. Don't install anything until research clarifies which
approach fits our heightmap + ShaderMaterial + meta.json pattern.

## Doc-system reminder (where to write new findings)

- Code/behavior change → relevant runbook (PIPELINE/TOOLS/RECIPES) +
  DECISIONS entry if architecturally meaningful
- "I expected X but got Y" surprise → LESSONS
- Sweep / experiment / prompt opinion → TEXTURE_RND
- New canonical command for a use case → RECIPES
- Phase wrap-up → handoff doc under `docs/handoffs/`
- Otherwise: DECISIONS.md is the safe default (append-only)
