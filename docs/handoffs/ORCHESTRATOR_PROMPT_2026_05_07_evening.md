# Orchestrator Handoff Prompt (paste into new chat)

Copy the block below into a new Claude Code chat to bootstrap orchestrator duties for the next session.

---

```
You are picking up orchestrator duties on a multi-day asset-pipeline project at D:\assets. The previous session (2026-05-07 evening) integrated all 8 SOTA research briefs, stood up 4 isolated pipeline venvs, wired 8 additive code changes, dispatched brief #09, built the pymoo Pareto utility, and wrote a Path 2 inpainting design doc.

Read these in order before doing anything:

1. D:/assets/docs/handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md  (canonical handoff)
2. D:/assets/docs/plans/NEXT_STEPS_2026_05_07.md  (cross-cutting state, free-wins backlog, Path 2 phases)
3. D:/assets/docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md  (per-instance mesh inpaint design — the user's high-priority direction)
4. D:/assets/docs/plans/ROADMAP.md  ("Research-calibrated findings" section has all 8 briefs)
5. C:/Users/josep/.claude/projects/d--assets/memory/MEMORY.md  (auto-loaded; contains 9 memory notes from prior sessions)

Key user directions to honor (do NOT relitigate):

- CLOUD IS PARKED. Don't propose Rodin Gen-2, Stable Audio 2.5, Recraft V4 cloud spend, DeepSeek V4-Pro, Claude Opus passes. They're all queued, not done.
- DON'T FAN OUT TO 33 CHARACTERS. User reframed this as content authoring, not pipeline work. Puppeteer's deer.obj + spiderman.obj smoke test already validates the chain. Running on goblin/hellhound/sandworm = QA on those specific meshes, not pipeline improvement.
- ADDITIVE TOOLING ONLY. Every new tool wires in side-by-side via a --flag with explicit A/B comparison. Default behavior preserved. Pattern established across meshoptimizer (props lod_chain), dreamsim+lpips (art_lab shader scoring), CLAP+PyMusicLooper (audio_qa).
- ONE VENV PER PIPELINE LANE. Don't pollute existing venvs with new lane deps. Discovered the hard way when modern peft (a dreamsim transitive) needed accelerate>=1.0 while Puppeteer is pinned accelerate==0.28.0.
- PERSISTENCE FIRST. User's biggest worry is doing work then losing it. Every install/fix lands in docs the same session. Three layers: handoff doc, ROADMAP, memory file.

Today's open priorities (recommended order):

1. User dispatches brief #09 (per-instance mesh inpaint) at their convenience. The brief at D:/assets/docs/research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.md is dispatch-ready.
2. Phase 0 Path 2 proof-of-concept: one-shot ComfyUI inpaint on goblin chest with hand-authored insignia + mask. ~1 day, no installs needed. Tells us if Architecture A (UV-space) is viable before brief #09 returns.
3. Free-wins backlog items 2-12 in NEXT_STEPS table (item 1 ✅ done). Each is sub-day to 2-day, no cloud, no curation.
4. After brief #09 returns: refine Path 2 design, start Phase 1 batch CLI.

Things to NOT do (decided by 2026 SOTA, not us):

- Don't fine-tune game-content LoRAs (#08).
- Don't set up RL on combat balance before combat is built (#08).
- Don't migrate Yarn → Ink / Dialogic 2 (#08) — lateral; build static analyzer instead.
- Don't buy World Anvil / LegendKeeper / Kanka / Campfire (#08).
- Don't adopt Inworld / Convai for dialogue (#08) — runtime NPC, not authoring.
- Don't adopt Lokalise / Phrase / Smartling pre-launch (#08).
- Don't pursue Hunyuan3D-3.0 full open weights (#03).
- Don't try image-to-3D for foliage (#03) — separate lane.
- Don't pursue AI HUD generators (#07).
- Don't pursue diffusion VFX (Sora 2 / AnimateDiff) (#04).
- Don't keep AniMo on the install list (#01).
- Don't install MocapAnything from github.com/animotionlab26 — unofficial reimpl, no checkpoints, AniMo pattern.
- Don't deepen MaterialAnything investment for hero terrain (#02).
- Don't replace vtracer/resvg/PIL atlas packer (#07).
- Don't adopt Neo4j / KuzuDB at <20K records (#08).

Background workers (don't disturb):

- Worldgen worker in world3/ — rebuilding scene-composition pipeline.
- Texture worker in pipelines/textures/ + world/textures/library/ — improving tileable textures. Brief #02 handoff written for them at docs/handoffs/HANDOFF_textures_research_2026_05_07.md.

Hardware target (unchanged):

- RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120 — needs CUDA 12.8+ / torch ≥ 2.7
- Windows 11; native Windows venvs at Python 3.11 default
- Check df -h /d before bulk pulls (D: has filled to 100% before)

First action: read the 5 docs in the list above, then ask me what to start. Confirm direction before installing anything; the persistence-first principle means we capture intent in docs before code touches disk.
```

---

## Notes for the user (don't paste below)

The above prompt is **self-contained** — a fresh Claude Code session reading only that block + the 5 docs it points to should be able to pick up cleanly. The 5 docs are the canonical view; everything else is reachable from them.

**If you want to reduce the prompt further** (e.g. the new chat has limited context), the minimum-viable version is:

> "Read D:/assets/docs/handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md and confirm direction before doing anything. Don't dispatch brief #09 — that's user-driven. Don't fan out 33 characters. Cloud parked."

**Recommended new-chat opening message** (after pasting the prompt above):

> "Continue. Phase 0 Path 2 PoC OR free-wins backlog items 2-4 — your call which to start first."

That gives the new session permission to act on item 2 of the open priorities (Phase 0) or items 2-12 of the free-wins backlog (whichever it picks). The orchestrator role is doing the work, not asking permission for every step.
