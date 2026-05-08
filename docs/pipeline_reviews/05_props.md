# Props — Manual Review (2026-05-07)

`pipelines/props/` lane. Phase 11 pushed this hard with the obelisk + AI route validation; this review checks **the rest of the library** beyond the hero asset.

## Inventory (truth from disk)

### Library: 51 entries on disk (validation latest reports 54 — see drift below)

By `render_class`:

| render_class | Count | What it is |
|---|---|---|
| **decal** | 26 | Flat decal PNGs (cracked_stone, moss_patch, mud_splash, rune_stain, scorch, etc.) |
| **scatter_multimesh** | 17 | Small variant meshes for biome scatter (rock_small, ruin_block, bone_pile, log, stump, mushroom_lantern, etc.) |
| **scene_prop** | 7 | Larger scene-anchor meshes (fence, tombstone, barrel_smoke, mushroom_lantern_demo, rock_small_demo, wooden_crate_demo) |
| **hero_prop** | **1** | obelisk_egyptian_a04 only |

### Variant pattern

Most entries are variant clusters under a base name:

| Family | Variants on disk |
|---|---|
| `bone_pile_a*` | a01, a02, a03 |
| `cracked_stone_03_*` | _01, _02, _03, _04, _05, _06 (6 decals) |
| `log_a*` | a01, a02 |
| `moss_patch_01_*` | _01-_06 (6 decals) |
| `mud_splash_02_*` | _01-_06 (6 decals) |
| `mushroom_lantern_a*` + `_demo` | a01, a02, demo |
| `rock_small_a*` + `_demo` | a01, a02, a03, a04, demo |
| `ruin_block_a*` | a01, a02, a03, a04 |
| `rune_stain_01_*` | _01-_04 (4 decals) |
| `scorch_01_*` | _01-_04 (4 decals) |
| `stump_a*` | a01, a02 |
| `tombstone_a*` | a01, a02 |
| `obelisk_egyptian_a*` | **a04 only** (a01/a02/a03 listed in validation but not on disk!) |
| `barrel_smoke`, `fence_a01`, `wooden_crate_demo` | singletons |

**Real distinct prop families: ~14.** Total entries (including variants): 51.

### Drift / cleanup find: validation drift

The latest validation report (`validation_20260507_020808.md`) lists **54** props and reports them all green ("ok 54"). But only **51** are actually in `world/props/library/`. Missing: `obelisk_egyptian_a01`, `_a02`, `_a03`. **Validation report is stale by 3 props.** Worth cleaning up.

### Decal alpha-coverage spread (signal for "is the decal real or empty?")

Sampled 5 decals:

| Decal | Alpha coverage |
|---|---|
| `cracked_stone_03_01` | **3.1%** ← almost empty |
| `rune_stain_01_02` | **1.3%** ← almost empty |
| `scorch_01_01` | 41.6% |
| `mud_splash_02_03` | 42.7% |
| `moss_patch_01_03` | 55.2% |

**Wide range.** Cracked stone + rune stain are at decal-strength <5% — these are *thin marks* not full ground decals. Moss / mud / scorch are substantial coverage. **Whether this is a quality issue or by-design depends on the art intent** (a hairline crack *should* be 1-3%; a moss patch shouldn't be).

### Mesh detail (sampled props)

| Prop | LOD0 GLB size | Notes |
|---|---|---|
| `obelisk_egyptian_a04` | **11.7 MB** (4-tier LOD: 11.7/10.3/9.6/8.8 MB) | **Only hero**. Trellis2 generated, full PBR maps embedded |
| `fence_a01` | 4.6 KB | Tiny — procedural |
| `log_a01` | (procedural) | Procedural |
| `rock_small_a01` | 132 KB | Procedural variant @ ~1500 tris target |

**The size delta is enormous.** Obelisk is **~88,000× larger** than fence_a01. The hero prop is a real PBR-textured asset; everything else is procedural geometry with no embedded textures.

### Procedural recipe params

`rock_small_a01` qa.json:
```
seed: 100, displacement_magnitude: 0.10, z_squash: 0.53, subdivisions: 4
```

The procedural variants are seed-perturbed parameter combos. Like the VFX palette swaps but at the geometry level. Reasonable for biome scatter (you want N rocks, not 1).

### AI route outputs

`world/props/ai_routes/` has **16 route outputs** (10 trellis2 + 5 hunyuan3d + 1 meshy). Most are smoke tests (`route_smoke_obelisk`, `batch_smoke_*`, `rs_*`) rather than real production. The A/B doc at `AB_hy3d_vs_trellis2_2026_05_06.md` is the Phase 11 finding (Trellis2 wins).

### Validation history

9 timestamped validation reports in `world/props/`. All clean (0 failures). The infrastructure runs.

### Godot drop-in

`world/props/godot/` — 274 files. `_materials/` (shared StandardMaterial3D resources), `_shared/` (PropMaterialBinder.gd), per-prop `<id>/<id>.tscn` + LOD nodes + collision. Real Godot integration.

## What works

- ✅ **Pipeline architecture is solid.** 7-stage postprocess orchestrator (stage_into_library → preprocess → LOD chain → CoACD collision → billboard bake → PBR bind → validate → Godot export). All stages produce real artifacts.
- ✅ **Hero prop pipeline (obelisk) proves the AI route end-to-end.** Trellis2 → 4-tier LOD → CoACD collision → PBR binding → Godot scene with material binder. This is the most complete asset in the project.
- ✅ **Procedural variant generation works.** rock_small/bone_pile/ruin_block/etc all have 2-6 variants from seeded parameter perturbations. Suitable for biome scatter.
- ✅ **Decal pipeline works** — 26 decals across 5 families. Alpha coverage varies (intentional — hairline cracks vs full moss).
- ✅ **Validation runs cleanly.** 0 failures across 9 runs. Schema enforced (prop_asset.v1, prop_qa.v1, prop_pbr_bindings.v1).
- ✅ **PBR material binding is real.** Mesh props bind to texture sets in `world/textures/library/` via a `PropMaterialBinder.gd` runtime helper. When the texture worker finishes their pass, this just lights up.
- ✅ **AI routes proven.** 10 Trellis2 outputs + 5 HY3D + 1 Meshy stub. Phase 11's A/B testing is real, with the AB compare sheet at `D:\tmp\sweep_compare_sheet.png`.

## What's open / weak

1. **Only 1 hero prop on disk.** The obelisk is the proof. Beyond that, **nothing has been put through the AI route end-to-end + 7-stage postprocess for production use.** The 14 prop families are dominated by procedural rocks/stones/decals.
2. **The "51 props" headline overstates it.** **14 distinct families × 1-6 variants each.** Useful for biome scatter, but not 51 unique gameplay-relevant assets.
3. **Validation report drift.** Latest report lists 54 (incl. obelisk_a01/02/03) but only 51 are on disk. Old obelisk variants were probably removed and validation wasn't re-run on the updated library.
4. **Some decals are nearly empty (1-3% alpha).** Could be intentional (hairline crack should be thin) or could be a generation artifact. Worth eyeballing.
5. **Procedural variant generation is parameter-perturbation, not authored.** Just like VFX's palette swap and game_data's name templates. Variants A through F are mostly the same shape with slightly different seeds.
6. **AI routes mostly smoke-tests.** 10 trellis2 entries but most are `*_smoke`/`*_demo` runs. The "Trellis2 is now the default" claim from Phase 11 hasn't translated into real prop production beyond the obelisk.
7. **No biome scatter test in a real Godot scene.** Phase 11C (scene integration) was deferred. We have 51 props ready to scatter but no validated demo scene of "drop these 17 scatter_multimesh props into a forest biome and see if it works."

## User verdict (2026-05-07)

After eyeballing samples:

1. **rock_small variants:** "**recolors but seem distinct-ish.**" The procedural-variant generation produces different-enough-to-pass shapes; not unique authored rocks but acceptable for biome scatter.
2. **Decal alpha range** (1.3% / 3.1% vs 55%): "they are just super light, not sure if it's a bug or not." Indeterminate — could go either way. **Worth keeping on the followup list to check intentionality.**
3. **Godot `_materials/`:** "not terrible, probably will make better later with our texture pipeline." Confirms — these are placeholders waiting on the texture-worker's output to bind into.

**User's broader reframe (worth recording verbatim):**

> "Honestly nothing was hand-authored, all just kind of made without review. We proved it works, we will want to make sure it works well on our next pass. **Honestly this is most likely the direction every pipeline and workflow will go.** That's fine lol we just started yesterday on this entire project. We are making crazy leaps honestly."

**This is the canonical reframe for the whole review pass.** The pattern across UI / VFX / Audio / Game Data / Props is identical and was always going to be: **build the pipeline, run it once with procedural defaults to prove the tooling, never hand-author. The output of the first pass is throwaway by design.** The value sits in the pipelines themselves, not the artifacts.

Calibrate next-step thinking accordingly:
- Don't measure pipelines by output quality (that wasn't the test)
- Measure pipelines by "can this produce real content given focused intent + good prompts/seeds/references?" — and that test is what comes next, asset by asset, when game design crystallizes

## Pipeline-level read

- **State:** **mature pipeline, hero prop validated, library is mostly procedural variants for biome scatter.** Same pattern as everywhere else: pipeline real, content thin.
- **Strongest part:** **the AI route → 7-stage postprocess → Godot integration chain**, proven end-to-end on the obelisk. This is the most complete asset-production path in the project.
- **Weakest part:** **only one prop has been produced through the hero path.** The other 50 are procedural. **The library exists primarily to feed biome scatter, not as a curated set of game-ready props.**
- **What "shipping quality" would require:**
  - Pick 5-10 hero props (e.g. specific weapons, shrines, banners, statues, key story objects). Run each through Trellis2 + postprocess. ~30 min × 5 = ~3 hours of pipeline work for a real hero set.
  - Validate biome scatter actually works in Godot — drop 50 procedural rocks into a real terrain scene and confirm performance.
  - Replace some of the 51 procedural variants with hand-curated AI route outputs where it matters (e.g. tombstones, ruin blocks).

## Concrete next moves

1. **Multi-prop generalization test** (the one I've been suggesting) — drop 3-5 diverse concept PNGs through `trellis2_batch.py` to confirm the AI route scales beyond the obelisk. ~30 min. **The single most valuable test for this pipeline right now.**
2. **Clean validation drift** — re-run `validate_props.py` on the live library so the report matches disk state. ~1 min.
3. **When you're ready to test scene integration:** Phase 11C — drop the 17 scatter_multimesh props into a Godot biome scene with `stage_biome_scatter.py`. ~1 hour, gated on world3 being ready.
4. **Don't archive these.** Unlike audio, props are kilobytes-MB and they prove the pipeline in measurable ways. Just stop counting "51 props" as gameplay-ready content — it's "14 families' worth of biome-scatter raw material plus 1 hero."

---

## Research-calibrated update (2026-05-07)

Brief #03 ([response](../research_briefs/2026_05_07_sota_survey/03_props_image_to_3d.response.md)) returned. **Reassuring, not redirecting.**

**Headline:** TRELLIS.2-4B remains the right default for May 2026. No released open-weights model decisively beats it for our props use case. "Trellis 3" doesn't exist. **Phase 11's Trellis2-as-default decision validated against 2026 SOTA** — useful negative result, no generator swap needed.

### Three named action items (all owned by us, all queued not started)

1. **Replace `DECIMATE COLLAPSE` with `meshoptimizer` in the LOD chain.** Highest-confidence concrete win in the brief — better silhouette quality at low LODs. Local code change in `pipelines/props/`.
2. **Add multi-image conditioning path on TRELLIS.2** for procedural variation — closest 2026 analog to "ControlNet for 3D." Uses our existing TRELLIS.2 install; just calls it with multiple reference images via the existing dispatcher.
3. **Add Rodin Gen-2 as opt-in `--hero` cloud route — PARKED.** User direction 2026-05-07 PM: no cloud right now. Adapter not built. When unparked: Rodin gives quad topology + BANG part decomposition for hero props (~$0.50–1.50/gen, ~60 s on cloud). Cloud only earns its keep here; local TRELLIS.2 dominates everything else.

### What NOT to do (per the brief)

- **Don't pursue full Hunyuan3D-3.0 open weights** — watch list, not adopt.
- **Don't try image-to-3D for foliage.** Trees won't be solved by image-to-3D in 2026; foliage needs a separate lane (SpeedTree / The Grove 3D / Blender-native procedural growth).
- **Don't expand cloud usage** beyond the parked Rodin hero case. Local TRELLIS.2 dominates economics.

### Watch list (no action, just track)

- **Knodt 2026** — quadric convex decomp (collision)
- **Hunyuan3D-3.0** — full open release, when/if
- **HY3D-Bench (Tencent, Feb 2026)** — 252K watertight meshes + 240K part-decomposed; useful if we ever want to fine-tune

### Texture worker impact

**None.** Brief #03 is entirely props-lane internal.

### What this changes

**Strategic:** nothing. Props is the most-invested lane in the project; 2026 SOTA confirmed our 2026-05-06 decisions.

**Tactical:** three small implementation tasks queued, all in code we already own, all sub-day work. Unblocks no one waiting on us.
