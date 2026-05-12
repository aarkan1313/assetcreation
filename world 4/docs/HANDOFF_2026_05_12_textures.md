# Handoff prompt — texture generation session (Axis 2 + 6 setup)

> Paste this into a fresh chat to start the next session. It's a
> self-contained takeover prompt; the agent should be able to start
> work from this alone.

---

I'm continuing a project called World 4 (W4). It's a Godot 4.5 + Python
world-generation system. Working directory: `D:\assets\world 4\`.

**This session's job: generate 48 texture maps for 4 new biomes.**

## Read these docs in order before doing anything

1. `D:\assets\world 4\docs\ROADMAP.md` — current top-level "what's next."
2. `D:\assets\world 4\docs\strategy\BIOMES.md` — the 5 chosen biomes
   with palette and slot-source method per slot.
3. `D:\assets\world 4\docs\plans\AXIS6_TEXTURE_VARIETY_2026_05_11.md` —
   the per-texture plan: 48 maps, prompt sketches, source method
   (real-ortho vs ComfyUI), execution order, validation pass.
4. `D:\assets\world 4\docs\reference\PITFALLS.md` — the 4 known terrain
   artifact classes. **Pitfall #1 (texture-driven speckle) is the
   relevant one for this session** — every new texture should be
   validated against the near-black-texel scan before binding.
5. `D:\assets\world 4\docs\reference\ORCHESTRATOR_GUIDE.md` — pipeline
   command cheat sheet.

## Where we are right now (2026-05-11)

**Two axes shipped in the previous session:**
- **Axis 1 (Scale) closed.** 1024 m × 1024 m world, 16 tiles,
  radius-paging with async WorkerThreadPool builds, persistent
  unloaded-tile cache. Per-tile build cost 77 ms wall-clock (~4 ms
  main-thread). 2 hitches per 200 s of walking — effectively
  hitch-free.
- **Axis 4 (View) first expansion.** Three view shaders (walk / iso /
  topdown), each with its own material and per-view loaded-tile
  radius. WASD pans iso + topdown; scroll-wheel zooms topdown ortho.

**Plan-stage artifacts now exist** for Axis 2 (Biome) and Axis 6
(Textures), which is what this session executes against.

## The 5 biomes (pinned in `strategy/BIOMES.md`)

1. **Temperate forest** — already exists as `materials/anchor_v2/`.
   No generation needed.
2. **Alpine / snowy** — cold whites, cool greys, dark slate rock.
3. **Arid / desert** — warm sandy tans, dry oranges, weathered brown rock.
4. **Rocky highlands / scree** — mid-greys, sparse moss, weathered bedrock.
5. **Coastal wetland / marsh** — dark wet browns, muted greens, faded blue-greys.

Each new biome needs 3 slots (ground / mid / rock) × 4 PBR maps
(albedo / normal / roughness / ao) = 12 textures. 4 new biomes ×
12 = **48 new texture maps**.

## What to do this session

Per `plans/AXIS6_TEXTURE_VARIETY_2026_05_11.md`, execution order:

1. **Alpine ground (snow) FIRST.** Most visually distinct from
   everything in the catalog. ComfyUI FLUX2-klein 9B. Validate that
   the stack works end-to-end before committing to the full batch.
2. **Stop after step 1 and screenshot in scale_demo.** Drop the new
   `materials/biome_alpine/ground/*.png` files into a copy of an
   existing material `.tres`, point `scale_demo.tscn`'s
   `material_override_path` at it temporarily, and look at the editor.
   If alpine ground reads as alpine, the rest of the plan is on track.
   If not, re-prompt before committing to the full batch.
3. **Generate the other 8 ComfyUI ground/mid slots** in a batch.
4. **Run real-ortho `_soft_composite` for the rock slots** that need
   DEM input (alpine rock, desert rock).
5. **Validation pass per slot** — near-black texel scan, tileability
   check, palette match, normal map sanity. Per PITFALLS.md #1, any
   albedo or AO map with `p5` luminance below ~0.05 will speckle
   without the shader's luma floor. Note any that need to be
   regenerated.
6. **Write `pipeline/write_material_tres_biomes.py`** — a small
   emitter that produces one `.tres` per biome, mirroring the existing
   `write_material_tres_scale_v1.py` pattern.
7. **Update the SCALE_BUILD_NOTES.md** with what shipped.
8. **Don't wire per-tile biome assignment yet** — that's Axis 2 proper
   and gets its own session.

## Critical context

- **The FLUX2-klein 9B stack is staged and validated.** See memory entry
  `flux2_klein_9b_setup.md` — it needs Qwen3-8B text encoder
  (Comfy-Org fp8mixed), NOT the qwen_3_4b used by klein-4B.
- **"tileable seamless texture" prompt wording is safe for FLUX2-klein**
  but mis-read by Chroma/SD3.5/Qwen as the building-material noun
  "tile." See memory `tile_prompt_poison_pill.md`.
- **The anchor demo is the locked regression baseline.** Don't change
  `materials/anchor_v2/`, `terrain_anchor_v2.gdshader`, or
  `AnchorTerrain.gd`. Anything we generate goes in `materials/biome_<name>/`.
- **Run `--headless --import` after dropping new PNGs into the
  project** so Godot picks them up. Or right-click in editor
  FileSystem → Reimport.

## What success looks like

- 48 new texture maps on disk, organized under
  `materials/biome_<alpine|desert|rocky|wetland>/`.
- Each slot validated against Pitfall #1 (near-black scan) and tileable.
- 4 new `.tres` biome material files under
  `worlds/scale_demo/biomes/material_<biome>.tres`.
- A screenshot of at least the alpine ground rendered in scale_demo
  (swap material_override_path temporarily, walk to a tile, capture).
- SCALE_BUILD_NOTES.md or a new build-note doc captures what shipped.

## What NOT to do

- Don't wire per-tile biome assignment into ScaleWorld yet — that's
  the Axis 2 step, separate session.
- Don't start the soft-transition workflow (Axis 6 proper). Hard
  borders ship first.
- Don't generate tropical / volcanic / lunar / badlands biomes. Those
  are wishlist parking, not in this 5.
- Don't change anchor or scale_demo's existing material bindings —
  the new biomes don't replace existing materials, they sit alongside.

## How to drive the user

The user expects:
- Plan-first execution (the plan is already written, just execute
  against it)
- Strict one-change-per-iteration when debugging
- Editor screenshots as ground truth, not headless captures
- Methodological discipline from `docs/handoffs/COMPACTION_HANDOFF.md`
  (operator mode rules: drive tactics, ask only on destructive /
  anchor-breaking / W3-touching changes)
- Update docs as state changes; don't let them go stale

The user is on a 5090 laptop. FLUX2-klein 9B should fit fine.

---

If you've got context space, also read `docs/build-notes/SCALE_BUILD_NOTES.md`
for the full picture of how Axis 1 + Axis 4 landed. Otherwise just
trust the plan doc and execute.

Good luck.
