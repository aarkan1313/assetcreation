# Worldgen Quality Knobs

> **Status (2026-05-07):** worldgen v1 era doc. Worldgen v1 broke late 2026-05-06; rebuild active at `pipelines/worldgen_v2/`. The knobs documented here are still **directionally right** for v2 — keep this as reference / lessons-learned. v2's milestone 1 is terrain-only (no scatter / no real PBR sets / no 2D-iso / no multi-DEM stitch), so several knobs below are out-of-scope until v2 grows them back.

Reference for the production quality toggles in our terrain → Godot pipeline,
with measured results from the 2026-05-06 A/B/C matrix on `death_valley_basin`.

These are the **proven** knobs. The pipeline is workflow-proof — these scenes
won't ship — but the recipe below is what to run when we DO need a
production-quality region.

See `D:\tmp\quality_matrix\comparison_grid.png` for the side-by-side that the
notes below summarize.

---

## TL;DR — recipe for max quality

```powershell
# 1. Re-bake the DEM at higher source resolution (knob A)
python pipelines\terrain\region_pipeline.py `
  --id <region> --bbox <W S E N> --dataset <dataset> `
  --style mythic --strength 1.3 `
  --biomes <comma-list> `
  --project C:\Users\josep\test\new-game-project `
  --size 2048    # 2x default

# 2. Upscale every biome texture set used by the region (knob B)
foreach ($s in @('biome_<a>','biome_<b>','biome_<c>','biome_<d>')) {
  python pipelines\textures\upscale_biome_set.py --set $s --factor 4
}

# 3. Re-bind + re-stage with denser mesh (knob C)
python pipelines\textures\biome_texture_bind.py `
  --world D:\assets\world\worlds\<region> --quality default --skip-missing
python pipelines\godot_export\stage_biome_terrain.py `
  --world D:\assets\world\worlds\<region> `
  --project C:\Users\josep\test\new-game-project `
  --walkable --cameras --cam character `
  --mesh-subdiv 512   # 2x default
```

That's the full quality stack. Each step is independently testable.

---

## A — DEM source resolution (`--size 2048`)

**What it does.** Re-samples the OpenTopography GeoTIFF + re-runs the biome
engine, splat compiler, biome_texture_bind, scatter generator, and stage at a
higher base resolution (default 1024 → 2048).

Knock-on effects observed in the matrix:
- Heightmap detail visibly sharper (more vertices → more displacement steps)
- Splat boundary cleaner; biome transitions less stair-stepped
- **Scatter density increases dramatically** — the biome engine finds more
  valid placement cells at higher resolution. In the death_valley case the
  iso shot went from sparse green pines + amethyst shards to a dense forest.
- Texture sampling is unchanged at the source — but the mesh that samples
  them has more verts so micro-features don't get lost.

**Cost.** ~1.5–2× pipeline time end-to-end. Output dirs roughly 4× larger
(height_16.png at 2048² vs 1024²). Disk-cheap on the small regions, can be
problematic on stitched 4096² recipes (4× the data again).

**When to use.** Marquee scenes, demo material, anything you'll zoom in on.
Skip for regions used as world-map satellite previews or thumbnails.

**Disk impact.** ~16 MB → ~64 MB per region's `output/<id>/` dir.

**Verdict.** **Highest single-knob impact.** Most of what makes a "production
quality" region look real lives here.

---

## B — Texture upscale (`upscale_biome_set.py --factor 4`)

**What it does.** Runs PIL Lanczos resize (4×) on every PBR map of a biome
texture set, in place. Backs up originals to `_original_<map>.png` so it's
revertable.

**Cost.** ~5–60s per set on the 5090 (CPU-bound, since Lanczos is PIL).
~50 MB extra per set on disk (original + upscaled). Six PBR maps per set:
albedo, normal, roughness, ao, metallic, height.

**When to use.** When you can SEE the original 1024² texel grid (typically
when iso character cam zooms in tight on a single biome). For
the marquee scenes that's almost always.

**Limitation.** **Lanczos doesn't invent detail.** It removes pixel-grid
artifacts but cannot add high-frequency content the source didn't have. The
matrix shows the difference is subtle — texture surface looks slightly
smoother but doesn't gain new features. **For real detail invention, swap
the resize call for Real-ESRGAN x4plus** (model goes in
`animators/ComfyUI/models/upscale_models/`). The CLI surface stays the same.

**Verdict.** Cheap, harmless, but the *least* impactful of the three knobs at
default Lanczos. Worth doing for production but don't expect drama.

---

## C — Mesh subdivision (`--mesh-subdiv 512`)

**What it does.** The terrain `PlaneMesh` defaults to 256 subdivisions per
side on a 512m plane = 2m per quad. Bumping to 512 = 1m per quad, which
matches USGS1m source DEM pixel density 1:1.

**Cost.** ~4× vertex count (262k → 1.05M). Negligible for modern GPUs;
fillrate is the bottleneck, not vertex count.

**Effect.** Visible improvement at iso character cam where ridge edges and
ravine walls are seen at grazing angles — the 2m steps in baseline read as
"chunky cliffs", at 1m they read as smooth contour. At topdown it's nearly
invisible (you're looking straight down so step size doesn't matter).

**When to use.** Any scene with iso or perspective camera angles. Not needed
for pure topdown.

**Verdict.** Free quality. Should probably be the new default.

---

## ABC combined

Run all three. The contributions stack mostly cleanly: A adds detail to the
heightmap and scatter, C lets the mesh actually display A's heightmap detail,
B smooths the texel grid on top. There's no interaction term where they
fight each other.

---

## D — Triplanar / projection strength (`--triplanar 0.0` recommended)

Discovered 2026-05-06 after the user flagged "super blended/mushy looking
stuff" in the iso/topdown shots of the A/B/C matrix. Investigated through
multiple shader rewrites; the current state is documented below.

**What was wrong (vanilla triplanar).** The original shader ran at
`triplanar_strength=1.0` with `pow(abs(N), sharpness)` weighting between 3
axis projections. On gentle slopes (most of death_valley), each pixel was
~80% top-down + 10% X-projected + 10% Z-projected. The side-projected
samples produced visible **horizontal/diagonal "rain stripes"** because the
texture was read at stretched scale along an oblique ray.

**Attempted fix #1 (Quilez biplanar).** Replaced 3-axis triplanar with
2-axis biplanar (max + median weight). Result: **swirl artifacts on flat
ground** because the median-axis tiebreaker between two near-zero
horizontal-normal components flips fragment-to-fragment. Reverted.

**Attempted fix #2 (slope-aware top-down + cliff blend).** Always sample
top-down, smoothly blend in a side-projected sample only when slope > 0.55.
Result: **swirl artifacts on cliff peaks** because heightmap peaks have
horizontal normals that rotate around the peak axis, causing the X-vs-Z
side-axis pick to swirl. Even smooth-blending the two side axes by their
weights didn't help — the texture pattern itself swirls when sampled in
side-projection on a peaky surface. Reverted.

**Settled answer.** Use `triplanar_strength=0.0` (pure top-down UV) for
character-cam scenes. This is **strictly the cleanest projection** for the
top-down/iso angle. Tradeoff: textures visibly stretch along near-vertical
cliff faces. For mana_crystal cliffs at iso this is moderately visible as
"vertical streaks of crystal pattern"; for other biomes (gentler heightmaps)
it's nearly invisible.

**Cost.** None visually for character cam at most biomes. Cliff-stretch is
the residual artifact. For first-person/perspective scenes with player
walking up to a cliff, leave `--triplanar 1.0` so the cliff doesn't smear,
and accept the slight slope blend stripes.

**Verdict.** `--triplanar 0.0` is the new default for character cam staging,
already wired. CLI:

```powershell
python pipelines\godot_export\stage_biome_terrain.py ... --triplanar 0.0
```

**Real fix to cliff stretch (open):** Mikkelsen 2022 hex-tiling. See knob E.

Side-by-side reference shots in `D:\tmp\diag_mushy\`:
- `E_originals_topdown.png` (vanilla triplanar — mushy stripes)
- `F_no_triplanar_topdown.png` (top-down, clean flat)
- `H_triplanar1_sharp16_iso.png` (high-sharpness triplanar — best of triplanar variants)
- `J_slopeaware_topdown.png` (slope-aware top+cliff — swirls on peaks)
- `M_pure_topdown_topdown.png` (final settled answer for topdown)

---

## E — Mikkelsen hex-tiling (NOT YET IMPLEMENTED — recommended next)

Per the 2026-05-06 research survey (Mikkelsen JCGT 2022), hex-tiling is the
production answer to **both** visible repeats AND cliff stretch in one
pass. Algorithm: sample the texture 3 times per fragment with random
per-virtual-hex-cell offset+rotation, blend via Mikkelsen's contrast ramp.

Why this fixes both problems we have:
- **Repeats**: each hex cell of the surface uses different texture
  offset+rotation, breaking the 6-8 visible repeats in our 50m frame
- **Cliff stretch**: the hex grid is in tangent space, not world space, so
  steep faces sample as cleanly as flat ones (no axis flipping)

**Cost.** ~30% slower than vanilla top-down (3 fetches + contrast ramp
math). At 1080p/60Hz on the 5090 this is invisible.

**Status.** Not implemented. Public Godot 4 GLSL port available at
godotshaders.com ("Stochastic Hex-Tiling (Mikkelsen's Adaptation)").
~1 day of integration work to swap our `triplanar_color` etc. functions for
hex-tile equivalents while keeping the splat blend.

**Ship target.** When mana_crystal cliffs at iso become a visible blocker
to demo quality.

---

## Knobs we DIDN'T test but are worth knowing about

| Knob | Where | Effect |
|---|---|---|
| `COLLISION_RES` (currently 128) | `stage_biome_terrain.py:37` | Heightmap collision grid. 128 = 4m cells, 256 = 2m, 512 = 1m. Higher = player capsule clips less on cliff edges. Tradeoff: bigger HeightMapShape3D resource (256² = 4× collision data). |
| Real-ESRGAN x4plus | drop in `animators/ComfyUI/models/upscale_models/` | True detail-inventing upscaler, replaces Lanczos in knob B. |
| `--res N` on import_dem | OT pull resolution | Pull the source TIFF at a higher resolution than `--size` so we have headroom to downsample. Defaults to `--size`. Useful for regions with lots of micro-features. |
| `tile_stitch.py` | new tool | For regions over OT's per-call km² limit, stitch N×M tiles. Marquee 4096² output. |
| `triplanar_strength` shader uniform | terrain material | 0 = pure top-down UV (cheap, stretches on cliffs), 1 = full triplanar (no stretch, ~3× sample cost). Defaults middle. |
| Texture `tiling_meters` | registry per-biome | We bumped 3-4m → 6-8m on 2026-05-06 to reduce visible repeats at character cam. Going higher reduces repeats further at the cost of macro-feature loss. |

---

## Iso/topdown elevation: when does climbable height matter?

Open question raised 2026-05-06 during scene review:

> "i think one problem with the iso/topdown is the height doesn't translate
>  well, theres some clipping issues. both these make it hard to navigate /
>  doesnt feel good. is climbable elevation even meaningful in iso/topdown?"

Honest answer: **mostly not, in the games people actually ship.**

What ARPG-style games do with elevation:
- **Diablo 2/3/4, Path of Exile, Last Epoch**: elevation is *visual flavor*.
  Players walk on a navmesh that's effectively flat from a gameplay standpoint
  — pathfinding doesn't care about Y. Cliffs are pathable obstacles, not
  steps the player physically climbs.
- **Hades, Wildermyth, Songs of Conquest**: same — elevation is set-dressing.
- **Disco Elysium**: pure 2D with painted shadow.
- **Outliers (XCOM, Into the Breach)**: do use elevation, but they discretize
  it to integer levels (1, 2, 3 high) — no smooth ramps.

What our pipeline currently does: **physically simulates a continuous
heightmap with a 1.8m capsule character.** That mismatch is the source of the
clipping you noticed. The capsule gets stuck on a 4m cliff face that any
ARPG would just have you walk around.

For production iso/topdown the right path is one of:
1. **Flatten the navmesh.** Keep visual heightmap, but generate a
   navmesh that simplifies cliffs into walls and gentle slopes into walkable
   surfaces. Player follows navmesh, not heightmap.
2. **Discretize elevation.** Snap player Y to terrain Y at sample points,
   drop the physics capsule entirely.
3. **Embrace it.** Some Soulslikes/Roguelites (e.g. Death's Door) DO have
   real-3D iso terrain with climbable elevation. Requires extensive collision
   tuning, not appropriate for our procedural scale.

We're prototyping the asset pipeline, not the gameplay. So what we have
(physics-based capsule on heightmap) is fine for proof-of-pipeline. **The
clipping issues are expected and don't need to be solved at this stage** —
they tell us "if this becomes a game, switch to navmesh-based locomotion."

---

## Workflow proof status (2026-05-06)

What's been verified end-to-end:
- ✅ A: 2048-DEM rebake (death_valley_basin)
- ✅ B: 4× Lanczos texture upscale (3 sets)
- ✅ C: mesh subdiv 512 (death_valley_basin)
- ✅ ABC stacked
- ✅ Reverting B is one-command (`upscale_biome_set.py --revert`)
- ✅ Comparison grid auto-composed at `D:\tmp\quality_matrix\comparison_grid.png`

**Reproduce the matrix:**
```powershell
# fresh baseline
python pipelines\godot_export\stage_biome_terrain.py `
  --world D:\assets\world\worlds\death_valley_basin `
  --project C:\Users\josep\test\new-game-project `
  --walkable --cameras --cam character

# render baseline + each knob to D:\tmp\quality_matrix\<config>\
# then python D:\tmp\compose_quality_grid.py
```
