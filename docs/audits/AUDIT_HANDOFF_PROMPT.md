# Audit chat — prompt

Copy everything below the `---` line into a fresh Claude Code session at `D:\assets\`.

---

You are auditing the `D:\assets` asset-factory project after a long, busy session. Your job is to produce **one definitive state-of-the-project document** that can be trusted as the ground truth going forward. Many docs in this tree were written during in-flight work and may now be stale, contradictory, or aspirational. Your output is what we'll cite next time anyone asks "where is X" or "what's done."

This is a read-and-write audit, not an implementation chat. Don't run pipelines. Don't generate assets. Don't deep-dive any single subsystem. Read, cross-check, summarize, flag drift, file an honest report.

## The factory in 90 seconds

Self-generated AAA-grade asset pipelines for a Godot 4.5 / TLTE game. Pipelines for terrain, textures, props (3D), VFX, audio, UI/icons, world maps, characters, game-data. Most pipelines are at v2/v3 SOTA. Phase 11 (props deep-dive) and Phase 12 (audio deep-dive) just landed on 2026-05-06. Recent reframe (also 2026-05-06): assets are mostly throwaway proofs — the goal is figuring out which pipelines work, not building a content library. Quality bar high; volume bar low.

## Where to start reading (in this order)

1. `../../README.md` — entry-point summary, ~1 page
2. `../../DOCS_INDEX.md` — canonical doc-ownership map. **Read this first to know what every doc owns.**
3. `../../PIPELINE_DIRECTORY.md` — live status table; the at-a-glance section + tables-by-pipeline
4. `../plans/ROADMAP.md` — current focus + parity scorecard + after-Phase-11 section + tier 0/1/2/3 priorities
5. `../plans/EXPANSION_PLAN.md` — phased checklist + decision log (decision log is at the bottom; oldest at top, newest at bottom)
6. `REVIEW.md` — bug post-mortems with REVIEW-discipline format. Phase 11 has 8 patches documented; Phase 12 in flight.
7. `../plans/LONG_TERM_VISION.md` — multi-month directional intent
8. `HANDOFF_<pipeline>_<v>_<date>.md` — per-pipeline build snapshots (one per pipeline, latest version only). The current set:
   - `../handoffs/HANDOFF_phase11_props_2026_05_06.md` (props v3 deep-dive)
   - `../handoffs/HANDOFF_phase12_audio_2026_05_06.md` (audio Stable Audio Open bake)
   - `HANDOFF_audio_v3_2026_05_06.md`
   - `../handoffs/HANDOFF_ui_v3_2026_05_06.md`
   - `../handoffs/HANDOFF_vfx_v2_2026_05_06.md`
   - `HANDOFF_props_v2_2026_05_06.md`
   - `../handoffs/HANDOFF_game_data_v2_2026_05_06.md`
   - `../handoffs/HANDOFF_phase9_2026_05_06.md` (open-weights / ComfyUI)
   - `../handoffs/HANDOFF_audit_expand_2026_05_06.md` (cross-cutting AB1)
9. `../../world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md` — the deep A/B for AI-route picker
10. `_archive/` — superseded handoffs + old audits. Treat as historical; never re-promote without a reason.

## What to actually verify

For each major doc above, you need to:

### 1. Cross-check claims against disk

Many claims are like "57 vfx effects in catalog" or "39 sfx / 112 variants" or "135 icons" or "10 biomes wired with full ambience." Pick **5-10 of these claims at random** and verify by listing the relevant directory. Common verification commands:

- `ls D:/assets/world/props/library/ | wc -l` — should match prop count
- `ls D:/assets/audio/ambience/ | wc -l` — should match biome count
- `ls D:/assets/vfx/catalog/**/effect.json` — should match VFX count
- `ls D:/assets/ui/icons/*.png | wc -l` — should match icon count
- `python pipelines/_meta/link_validator.py` — should report MISSING: 0 if cross-pipeline refs are clean

If a claim is wrong, **flag it specifically**: "PIPELINE_DIRECTORY.md line 12 says 57 vfx effects but disk has 73."

### 2. Cross-doc consistency

The same fact often shows up in multiple docs. Find disagreements. Examples that have been issues before:
- ROADMAP scorecard grades vs PIPELINE_DIRECTORY status markers
- Number of biomes in world.json files vs scatter rules vs ambience recipes
- Phase 11/12 status across DOCS_INDEX, ROADMAP, PIPELINE_DIRECTORY, EXPANSION_PLAN
- "v3 sweet spot" claims about specific sweep configs (HY3D `hi_geo`, Trellis2 `mid`, etc) — check the AB doc + handoffs for consistency

### 3. Stale "current focus" claims

ROADMAP and PIPELINE_DIRECTORY both say things about current focus and what's next. After Phase 11 + Phase 12, the focus has shifted. Check that:
- Phase 11 (props deep-dive) is closed-out (not in_progress)
- Phase 12 (audio deep-dive, Stable Audio Open bake) reflects either "shipped" or "in flight, all 10 biomes baking" depending on disk state at time of audit
- "Current focus" line in PIPELINE_DIRECTORY at-a-glance matches what's actually being worked on

### 4. Deferred items that should still be on the books

These were explicitly deferred but **NOT dropped**. Confirm each is still tracked somewhere:
- Phase 11C scene integration (drop hero prop into Godot biome scene; gated on world-gen recovery)
- Multi-prop generalization test (N=1 obelisk → N≥3 different prop types)
- Hunyuan3D-Omni pilot (gated on bbox-envelope adherence pass criteria)
- World-gen "totally broke" — user's words, 2026-05-06. Some active state may have been lost. Check whether ROADMAP / PIPELINE_DIRECTORY mention this.
- LM Studio + EpicGamesLauncher + the stale ComfyUI on port 8188 were killed during Phase 11 to free GPU. None of these get auto-restarted.

### 5. Files that exist but shouldn't, or that should but don't

Things to look for:
- `_archive/` should contain only superseded handoffs + old audits + orphan research; nothing live
- `D:\tmp\` is user scratch; `../../pipelines/props/_phase11_forensics/` mirrors the Phase 11 stuff that was promoted from D:\tmp\. Check whether Phase 12 has a parallel `_phase12_forensics/`. Probably not yet — flag if so.
- `../../pipelines/props/postprocess_ai_route.py` should exist and be the orchestrator for AI-route GLBs. If missing, that's a regression.
- `../../pipelines/audio/STABLE_AUDIO_SETUP.md` should exist with HF token + license + 6-step install instructions.
- `../../pipelines/props/TRELLIS2_PATCHES.md` should exist with Trellis2 venv patch forensics.

### 6. The big-picture honest read

What's the project actually doing? What's working? What's broken? What's pretending to work?

Specific things to assess:
- **Cross-pipeline integration**: per the reframe, this is the highest-leverage work. Has any of it landed? `stage_biome_scatter.py` v3 prop_pool pickup, walkable spawn-on-terrain, link_validator UNUSED sweep, "prove the seams" demo. Check ROADMAP Tier 0.
- **Pipelines NOT yet built**: cinematics, quest schema, save/load, localization, performance budgets, cross-pipeline gallery, factory.jsonl manifest. These are Tier 1. Are any of them started?
- **GPU-window flips queued**: per ROADMAP Tier 3, ~9 items including Stable Audio Open bake (Phase 12 just completed this!), FLUX schnell + LoRA train, Trellis2 (Phase 11 completed), Hunyuan3D-2.5 (Phase 11 completed for 2.1; 2.5 weights aren't open per compat-matrix research), Taichi VFX bakers, F5-TTS, vLLM, Wan, YuE. Update which are still queued vs completed.
- **Real production content gated on user intent**: TLTE seed records, hero-prop concept PNGs, real Yarn dialogue files. None of these are unblocked yet — confirm.

## What your output should look like

Write a single new doc at `D:\assets\AUDIT_2026_05_<DAY>.md` (use today's date). Structure:

### Section 1: Executive summary (~10 lines)
What state is the project in, in plain language. Not a marketing summary; an honest one. If something's broken, say so. If two docs disagree, name the contradiction.

### Section 2: Per-pipeline status table

Columns: `pipeline | claim_in_PIPELINE_DIRECTORY | claim_on_disk | drift | confidence`. One row per pipeline (terrain, textures, props, vfx, audio, ui, world_maps, characters, game_data). For each, do a quick spot-check (3-5 commands max) against what the directory claims. `drift` is a one-line summary: "matches" / "underclaims" / "overclaims, says X but disk has Y" / etc.

### Section 3: Doc-by-doc audit (~10 docs)

For each major doc (README / DOCS_INDEX / PIPELINE_DIRECTORY / ROADMAP / EXPANSION_PLAN / REVIEW / LONG_TERM_VISION / each pipeline's HANDOFF), note:
- Whether it's still accurate
- Specific lines or claims that drifted
- Whether it should be updated, deprecated, or archived

### Section 4: Things-on-the-books that nobody is actively working on

A flat list, with each item's status, why it's deferred, what would unblock it. So nothing falls off the radar.

### Section 5: Recommended next moves

3-5 concrete options for what to do next, ordered by leverage. Each with a one-line tradeoff. Examples:
- "Land Phase 12 closing docs (REVIEW + ROADMAP scorecard moved Audio to A) — 30 min"
- "Pivot to Phase 13: VFX GPU baker deep-dive (Taichi MPM) — parallel install-pain shape to Phase 11/12, ~half day"
- "Pivot to Path B cross-pipeline composition demo — gated on world-gen recovery, unknown effort"
- "Doc-cleanup pass: archive any handoffs older than the latest per-pipeline version" — etc.

### Section 6: Drift / inconsistency flags

Specific pairs of "doc A line N says X" / "doc B line M says Y, contradicts." Don't fix them in this audit — just flag them so the user can decide.

## Tone

Be direct. Skip all "great work so far!" phrasing. Numbers > adjectives. If a section says "all 10 biomes wired" but only 5 directories exist on disk, write "claim says 10, disk has 5" — not "minor discrepancy noted."

## Time budget

This audit should take ~20-40 min of agent work. If you find yourself going deeper than that on any one section, log a "this needs its own follow-up audit" note and move on.

## Constraints

- Read-only. Don't modify any docs in this audit pass — your output is the new audit doc, not edits to the others.
- Don't spawn sub-agents. Read with Glob/Grep/Read directly.
- Don't run any of the AI pipelines (Trellis2, HY3D, Stable Audio Open) — those need GPU and are out of scope.
- Do run `python pipelines/_meta/link_validator.py` — it's CPU-only and gives the canonical cross-pipeline reference signal.
- Do run small `ls`/`wc -l`/`du -sh` spot-checks against the file tree.
- The user asked you specifically to "make me a prompt for a chat to do that" — your chat is that audit chat. Do the audit; don't write a prompt for another one.

Begin.
