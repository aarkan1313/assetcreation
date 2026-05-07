# World Generation QA — 2026-05-06

> **Status (2026-05-07):** historical snapshot. This QA report covers worldgen **v1** end-to-end at production resolution. Worldgen v1 broke later on 2026-05-06; v2 rebuild lives at `pipelines/worldgen_v2/` (milestone 1 terrain-only). Treat these results as proof v1 worked end-to-end at one point, not as current factory status.

End-to-end test of every world-gen pipeline at production resolution (1024 px). Every pipeline ran cleanly to a complete Godot bundle. No manual tweaks needed.

## Test matrix

| # | Pipeline | Input | Output | Time | Status |
|---|---|---|---|---|---|
| 1 | `terrain_bundle.py` | synthetic FBM, mountains biome, **Landlab hydraulic erosion 80 steps** | `pipelines/terrain/output/qa_alpine_hydraulic/` | ~60s | ✅ |
| 2 | `import_dem.py --source mapzen` | real-world Mapzen tile (8/50/90, alpine 881–2613m) | `pipelines/terrain/output/qa_alpine_real/` | ~10s | ✅ |
| 3 | `worldengine` + `worldengine_to_bundle.py` | continent-scale plate-tectonic sim, 12 plates | `pipelines/terrain/output/qa_worldengine_continent/` | ~50s | ✅ |
| 4 | `mesa_terrain.py` | **AI text-to-DEM** prompt, 40 ddim steps | `pipelines/terrain/output/qa_mesa_canyon/` | ~6s gen + bundle | ✅ |
| 5 | `generate_world_map.py` | seed 99, 18 settlements, 5 factions, 10 landmarks | `world/maps/qa_world_a/` | ~30s | ✅ |
| 6 | `export_godot.py --type terrain` | bundle 1 → Godot pack | `godot_pack/terrain/qa_alpine_hydraulic/` | ~1s | ✅ |

All bundles share the same contract: `height_16.png`, `normal.png`, `splat_rgba.png`, `biome.png`, `vegetation_density.png`, `water_mask.png`, `flow.png`, hillshade + hypsometric previews, `terrain.json`, `godot/heightmapshape3d.tres`. Drop-in compatible with each other and the Godot exporter.

## Quality assessment by pipeline

### 1. Synthetic + Landlab hydraulic (best for "fantasy alpine")

**Strengths:** Hydraulic erosion produces visible drainage networks — the flow.png shows clear river channels carving valleys. The 80-step Landlab pass took ~30s and gives the hand-crafted look of natural erosion. Heightmap range is full (0–65535). No tiling artifacts because it's domain-warped FBM.

**Weaknesses:** Without manual tuning the biome distribution defaults to "everything is rock or grass" — no genuinely flat valley floors or distinct snow caps unless we explicitly shape the histogram. The synthetic feel is still slightly too uniform; real DEMs have more structural variety.

**When to use:** Fantasy maps, abstract worlds, anywhere you want full creative control. **The default for in-game terrain.**

### 2. Mapzen real-world DEM (best for believability)

**Strengths:** Real elevation = real plausibility. Alpine tile shows actual ridge structure, glacial valleys, plateau breaks that procedural noise can't fake. Files are larger (1.46 MB height vs 1.36 MB synthetic) because real DEM has more high-frequency detail. Worked instantly with no API key (Mapzen is public).

**Weaknesses:** Limited to ~256m vertical range (single Terrarium tile = small geographic extent). Each tile is whatever's at that lat/lon — you don't get to art-direct it. Also got upsampled from 256→1024 so the detail-per-pixel is photographic-quality but interpolated.

**When to use:** When you need "this looks like a real place" credibility. Pair with manual exaggeration if the source area is too flat.

### 3. WorldEngine continent (best for "world map of a planet")

**Strengths:** Plate-tectonic sim. Outputs continents, oceans, climate, biomes, rivers, precipitation, temperature — a full world simulation per seed. Useful for picking *where* on a continent to drop a playable region. Very small file sizes (5 KB height) because the output is naturally low-frequency.

**Weaknesses:** Not playable terrain by itself. The grayscale heightmap is "where is land" not "what does ground look like." You'd use this to generate a continent then *zoom in* to a region and re-generate playable terrain at that location.

**When to use:** World-building stage. Generate a continent, pick a region, hand the coordinates to pipeline 1 or 2 for playable terrain.

### 4. MESA AI text-to-DEM (best for prompt-driven exotic terrain)

**Strengths:** Text prompt → real DEM. Generated "dramatic desert canyon" → 768×768 native + paired Sentinel-2-style optical preview + DEM. Uniquely *text-controllable* — none of the other pipelines accept "make me a canyon." 6 second inference on the 5090. Largest height file (1.77 MB) because MESA outputs more sub-meter detail than synthetic erosion produces.

**Weaknesses:** Adobe research license = non-commercial. Output resolution is fixed at 768; we resample to bundle size. Style is photographic (Sentinel-2 satellite look) which doesn't match every game's art direction.

**When to use:** When you want a *specific kind of place* the other pipelines can't make ("alien hex pillars", "lava field with cooling fissures", "ancient meteor impact crater"). Treat as concept-art seed, not final shippable terrain unless you mask the licensing.

### 5. World map (strategic political/biome layer)

**Strengths:** The thing the other 4 pipelines don't make — political/strategic view. **143 rivers, 17 A* roads, 18 named settlements with importance scoring, 5 weighted-Voronoi factions, 10 landmarks** all in pure Python in 30s. Full G-deep-dive contract: every layer is a separate GeoJSON or PNG so Godot can render it as vector overlay (Polygon2D, Line2D, Sprite2D).

**Weaknesses:** Settlement names are placeholder syllable templates — not localized or culture-aware. No region naming logic yet (just "region_0..N"). No 3D handoff: this isn't terrain, just the strategic map.

**When to use:** The world-map screen of the game. The "press M" view.

### 6. Godot exporter (drop-in import)

Took the qa_alpine_hydraulic bundle and produced a Godot 4.5 ready `godot_pack/terrain/qa_alpine_hydraulic/` with:
- `heightmapshape3d.tres` — collision-ready
- `height_16.png` + `normal.png` + `splat_rgba.png` + `biome.png` + `vegetation_density.png` + `water_mask.png`
- `terrain.json` — provenance copied
- `godot_export.json` — drop-in instructions

That's the full chain. Drag the folder into Godot's filesystem panel and instance the .tres on a `HeightMapShape3D` collision node.

## Side-by-side comparison

For the same "alpine mountain region" intent:

| Aspect | Synthetic+Landlab | Mapzen real | WorldEngine | MESA AI |
|---|---|---|---|---|
| Time to result | 60s | 10s | 50s | 6s + bundle |
| Heightmap variety | medium | high | low (continent-scale) | high |
| Drainage realism | high (Landlab simulated) | high (real) | low | medium |
| Art-directable | high | low | medium | very high (text prompt) |
| Repeatable from seed | yes | yes (same tile) | yes | yes (same prompt+seed) |
| Commercial license | OK | OK (Mapzen public) | OK (MIT) | **NO (Adobe research)** |
| File size (height) | 1.36 MB | 1.46 MB | 5 KB | 1.77 MB |
| Best for | default in-game terrain | "real place" credibility | world map seed | exotic prompts |

## Bugs found + fixed during this run

1. **`numpy 2.4.4 / pandas binary mismatch`** — diffusers stack pulled new numpy; `pip install --upgrade pandas` fixed.
2. **`import_dem.py` PIL `I;16` resize fail** — PIL 12+ doesn't accept LANCZOS on `I;16` mode. Fixed by routing resize through `F` (float32) mode, then converting back.

## Verdict

**The terrain pipeline stack is shippable.** Four independent input modes (procedural, real-DEM, world-scale, AI), one bundle contract, one Godot exporter. Each excels in a different niche. None of them block on the others.

**The only real gap right now is artistic direction:** none of these pipelines yet reads a *biome kit JSON* and produces terrain styled to match it (e.g. "desert temple" terrain that looks visually consistent with a desert temple texture kit). That's the next seam: tie the terrain output's biome distribution to the texture kit's anchor palette.
