# Proceduralizing real DEMs — research brief

**Goal:** Use the cached library of 50+ GB of real-world DEMs as a *learning corpus* for a procedural terrain generator that produces "physically plausible but never-seen-before" landscapes. Anywhere we can get geographic plausibility for free, we should — synthetic FBM-noise terrain looks fake the moment a player notices ridges that don't channel water like real ridges do, or valleys that meet rivers at impossible angles.

This is a **stretch / research goal**, not an immediate build target. The catalogue we're filling up by ingesting OpenTopography is the *prerequisite data* for this work. Until the catalogue has hundreds of regions cached, nothing here is testable.

## Why this is worth pursuing

What real terrain has that synthetic-noise terrain doesn't:
- **Hydrologically consistent rivers** — water always flows downhill, joins tributaries at characteristic angles, carves valleys with predictable cross-sections.
- **Erosion-budget consistency** — high places are sharp because they erode toward steepness; low places are smooth because they fill with sediment. This isn't just a one-pass post-process; it's a self-consistent feedback over geological time.
- **Plate-tectonic macro structure** — continental shelves, fold mountains, rift valleys, oceanic trenches. Multi-scale, not just "noise in 5 frequency bands."
- **Climate × geology coupling** — glaciated terrain looks different from desert terrain at the *same scale*. Glaciers carve U-shaped valleys; rivers carve V-shaped ones; wind sculpts entirely differently.
- **Plausible scale relationships** — a real mountain range covers 100s of km, with foothills covering more area than peaks. Synthetic noise doesn't naturally reproduce these power-law scale distributions.

What synthetic FBM/ridged-Perlin gets you:
- ✅ Cheap
- ✅ Infinite seeds
- ❌ Hydrology is wrong (water doesn't flow correctly)
- ❌ Macro shape is wrong (continents look like blobs)
- ❌ No terrain history (everything looks the same age)
- ❌ Doesn't transfer between scales (same noise at 1km and at 10cm)

A "procedural-from-real" approach blends them: keep procedural's freshness and infinity, get real's physical plausibility.

## Approaches, ranked by tractability and ambition

### Approach 1 — Statistical fingerprinting (low effort, decent payoff)

**Concept:** Compute statistical fingerprints of real-DEM regions (height histograms, slope distributions, curvature spectra, flow-accumulation power laws), then *bias* synthetic FBM to match a target fingerprint.

**Implementation sketch:**
1. For each cached DEM, compute:
   - Height histogram (32 bins, normalized)
   - Slope histogram (32 bins)
   - Curvature distribution (positive/negative ridges/valleys)
   - Power spectrum of heights (FFT magnitudes vs frequency)
   - Flow-accumulation power law exponent
   - Roughness vs scale (Hausdorff-like fractal dimension at multiple scales)
2. Cluster real DEMs by fingerprint → "fjord cluster," "alpine cluster," "dune-sea cluster," etc.
3. Build synthetic generator that produces FBM noise + transformations until its output's fingerprint matches a target cluster's distribution.

**Pros:** Cheap to compute. Statistically grounded. No ML required.

**Cons:** Doesn't capture *spatial* structure — two regions with same fingerprints can still look very different. Won't reproduce hydrology specifically.

**Effort:** ~1 week. Could ship as `dem_fingerprint.py` + `synth_terrain.py --target-fingerprint <cluster_id>`.

### Approach 2 — Patch-based texture synthesis (medium effort, high payoff)

**Concept:** Treat the DEM library as a corpus of "valid" terrain patches. To generate new terrain, **stitch and blend patches** from real DEMs using texture-synthesis algorithms (graphcut, image quilting, PatchMatch). Output looks novel but every pixel is locally consistent with something real.

**Implementation sketch:**
1. Tile every cached DEM into 256×256 overlapping patches; index them.
2. Generate new terrain by laying down patches with seam-minimizing graph-cut, much like image quilting.
3. Constraint mode: "fill this 1024×1024 area with patches matching tag 'fjord'" or "blend fjord macro with hoodoo micro."

**Pros:** Output has hydrological + erosion structure for free, since every patch came from real terrain. Gives a strong "physically plausible" feel without explicit physics.

**Cons:** Seam artifacts unless the matching is good. Constrains output to the convex hull of the corpus. Memory-heavy on a big patch index.

**Effort:** ~1-2 weeks. Could ship as `dem_quilt.py --corpus <cache_dir> --target <tags> --size 2048`. Fits between `import_dem.py` and the biome engine in the existing pipeline.

**Adjacent reference:** Image-quilting (Efros & Freeman 2001) is the academic foundation. There are good Python implementations of graph-cut quilting.

### Approach 3 — Diffusion model fine-tuned on DEMs (high effort, high payoff)

**Concept:** Fine-tune a small image diffusion model (or train a small one from scratch) on heightmap tiles labeled by tags ("fjord," "alpine," "desert"). Sample from it for novel terrain.

**Implementation sketch:**
1. Tile every cached DEM into 256×256 patches with metadata tags.
2. Fine-tune SD or a tiny custom diffusion on `(tag-vector → 16-bit grayscale heightmap)` mapping.
3. Sample with classifier-free guidance: "generate a 512×512 heightmap that's 40% fjord, 30% glacial, 30% volcanic."
4. Optionally, condition on a sketched macro layout (ControlNet-style) so user can paint where mountains go.

**Pros:** Very flexible, supports interpolation between styles. Output quality depends on data scale — with 50 GB of patches, very plausible.

**Cons:** Training infra. Needs the 5090. Diffusion samples don't *guarantee* physical plausibility (can produce impossible terrain), so a post-pass hydraulic erosion is needed.

**Effort:** ~3-4 weeks for a competent first version. Lots of unknowns. Highest payoff if it works.

**Adjacent references:** "Terrain GANs" (~2018-2021 literature has half a dozen papers). MESA AI in our pipeline is similar in spirit but trained on a tiny dataset; with 50 GB our domain-specific corpus is much better.

### Approach 4 — Physical simulation seeded by real macro (medium effort, very high payoff)

**Concept:** Use real DEM as the *initial condition* for a long physical simulation (tectonic uplift + hydraulic erosion + glacial carving). Result is "what would this region look like after 100 million more years of erosion under these climate conditions?"

**Implementation sketch:**
1. Pick a real DEM as starting heightmap.
2. Run multi-stage simulation:
   - Tectonic uplift (linear gradient toward "still-active" zones)
   - Hydraulic erosion (Landlab — we already have this)
   - Glacial carving (where altitude > snowline, U-shaped valley smoothing)
   - Aeolian deposition (downwind dune formation in dry zones)
3. Each pass produces a new heightmap that's a fantasy variant of the real region with consistent physics history.

**Pros:** Outputs are *guaranteed physically plausible* by construction. Combinatorial space is huge (4 different climates × any DEM × any uplift profile = thousands of variants).

**Cons:** Slow. Each pass might take minutes. Tuning the simulation parameters to get nice-looking results is nontrivial.

**Effort:** ~2 weeks. Builds on the Landlab integration we already have.

## Recommended ordering

If we ever pursue this:

1. **Approach 1 (fingerprinting)** first — cheap, immediately useful for tagging the catalogue and discovering "what kinds of terrain we actually have."
2. **Approach 2 (patch quilting)** second — if (1)'s clustering gives clean groups, quilting from each cluster produces good blends with little risk.
3. **Approach 4 (physics simulation)** third — high payoff but slow. Best as a separate `--style physics_evolved` option in `dem_fantasy_edit.py`.
4. **Approach 3 (diffusion)** last — biggest commitment. Worth it if we want to scale to "infinite worlds, all geologically plausible."

## Why this is worth waiting on

We need the data first. The cached corpus is the prerequisite. With ~50 GB of real DEMs covering the world's diverse geomorphology, all four approaches become feasible. **Without** the data, none of them work.

So: keep ingesting (Phase B), keep adding biomes (Phase C), and revisit this when the catalogue is ~600 regions deep. At that point the question shifts from "can we?" to "which of the four approaches do we pick?"

## Adjacent references

- Procedural Worlds, Galloway et al. (good survey of state-of-the-art)
- World Machine (commercial — does erosion + hydraulic + climate sim, expensive)
- Gaea (commercial — similar)
- Terragen (commercial — atmospherics + terrain)
- Watershed-based DEM analysis: Tarboton 1997 (still the basis of `flow_accumulation_d8` we use)
- "Authoring of self-similar terrain by example" (Argudo et al., academic)

## Filing this away

This is parked until either:
- The catalogue hits ~600 regions cached (we have a useful corpus), OR
- Someone asks "what's the long-term plan beyond just pulling more presets?" (this is the answer)
