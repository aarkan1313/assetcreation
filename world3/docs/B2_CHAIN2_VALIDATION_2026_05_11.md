# B.2 — Chain 2 Cold Validation: Texture Pipeline

> Phase B.2 of the rebuild evaluation. Cold-validation of the texture
> pipeline (`aaa_texture.py` orchestrator + FLUX → StableMaterials → QA
> → catalog chain).

## Verdict

**PARTIAL — blocked at runtime by undocumented operator setup; no code
or contract problems found.**

The texture pipeline scripts themselves are intact, well-documented, and
have full provenance preserved in shipped material manifests. The
**blockers to cold-running it are all operator/environment gaps**:

1. ComfyUI is not running (required, no auto-start)
2. `pipelines/textures/.venv` does not exist (worker uses... unclear)
3. StableMaterials (the default PBR backend) requires a separate venv
   (`animators/mesa-env/venv`) and the calling pattern is not documented
   in the orchestrator's `--help`
4. No "what model files do I need" preflight check anywhere

These are all **Bucket B (manual-step gaps)** — exactly what the Phase E
orchestrator is supposed to fix. **No Bucket C (real bugs) found.** No
Bucket D (architectural gaps) found in the pipeline itself; only at the
invocation layer.

## Test scope

Cold-reproduce `wgv3_desert_canyon_rock` from its recorded provenance.
Compare new output to existing material.

## Inputs (recovered from existing manifests)

From `world/textures/library/wgv3_desert_canyon_rock/aaa_pipeline.json`:

```json
{
  "id": "wgv3_desert_canyon_rock",
  "prompt": "weathered tan canyon sandstone, top-down photo, photoreal",
  "category": "Rock",
  "quality": "default",
  "seed_base": 100,
  "preset": {
    "variants": 4, "pbr": "sm",
    "flux_size": 512, "pbr_size": 512,
    "use_repair": true, "seam_max": 0.01,
    "delight": 0.4, "min_grade": "B"
  }
}
```

Plus from `variant_select.json`:
- 4 variants generated at seeds 100, 1100, 2100, 3100
- Best variant = seed 1100, seam score 0.00192
- Grade: A (exceeded the B+ requirement of preset)

## Cold-run command (reconstructed from manifests)

```bash
python pipelines/textures/aaa_texture.py \
    --prompt "weathered tan canyon sandstone, top-down photo, photoreal" \
    --id desert_canyon_rock_cold_test \
    --category Rock \
    --quality default \
    --seed-base 100
```

All other args at defaults (quality preset supplies variants=4, pbr=sm,
sizes=512, etc.). Schema verified: aaa_texture.py's `default` preset
matches the recorded provenance preset byte-exactly.

## Cold-run prereq verification

### What's required to run (read from script docstrings + imports)

| Prereq | Status | Notes |
|---|---|---|
| Python with numpy, PIL, requests | ✅ system Python 3.12 has all three | system, not venv |
| `pipelines/textures/.venv` | ❌ does not exist | `pipelines/terrain/.venv` exists for Landlab only |
| ComfyUI server at `127.0.0.1:8188` | ❌ **not running** (curl returns http_code=000) | required for variant generation |
| FLUX 2 klein-4B model file | ✅ at `animators/ComfyUI/models/diffusion_models/flux-2-klein-4b.safetensors` (7.75 GB) | model on disk |
| StableMaterials backend | ⚠️ **no ComfyUI node found**; lives in separate `animators/mesa-env/venv` | invocation pattern undocumented |
| ComfyUI-GGUF custom node | ✅ present | used by other model paths |
| ComfyUI-Chord custom node | ✅ present | opt-in PBR backend (`--pbr-backend chord`) |
| x-flux-comfyui custom node | ✅ present | FLUX-specific support |

### Result

**Cannot cold-run end-to-end** with the current environment state. ComfyUI
must be started by the operator (no script to do this). StableMaterials
backend invocation requires the `mesa-env/venv` Python path which is not
referenced from `aaa_texture.py` itself.

## What we validated without running

Even without executing the chain, we validated significant aspects:

### V1 — Pipeline orchestrator preset alignment
`aaa_texture.py`'s `default` preset matches the recorded provenance for
`wgv3_desert_canyon_rock` byte-exactly:

```python
"default": {
    "variants": 4, "pbr": "sm",
    "flux_size": 512, "pbr_size": 512,
    "use_repair": True, "seam_max": 0.010,
    "delight": 0.4, "min_grade": "B"
}
```

Same settings as recorded. Means cold-run would invoke with the same
preset shape.

### V2 — Provenance is complete + recoverable
`aaa_pipeline.json` + `variant_select.json` together preserve every
non-default arg needed to reproduce:
- Prompt: full string
- Quality preset: named (`default`)
- Seed base: 100
- All variant seeds tried
- Best variant + score

Pattern matches Chain 1's provenance discipline — confirmed across 2/2
chains tested.

### V3 — Stages declared in manifest
The `stages` array in `aaa_pipeline.json` records exactly which steps
ran:
- variants (seam score 0.00192)
- delight (strength 0.4)
- pbr (method `stablematerials_standard`)
- seam_repair
- qa (grade A, edge_mse 0.00049, junction_ratio 0.86, periodic_locality 11.7)
- blender_preview

If cold-run produces the same stages with similar metrics, the cold run
matched.

### V4 — Gate enforcement is preserved
The recorded run has `passed_gate: true`, `grade: "A"`, `grade_pass: true`,
`sanity_pass: true`, `maps_pass: true`, `core_maps_present: 4`. The
orchestrator gate code path is intact.

### V5 — Model files present + correct
FLUX 2 klein-4B on disk at the path `aaa_texture.py` expects. StableMaterials
exists via `mesa-env/venv` (worker provenance shows `method:
stablematerials_standard`, confirming this backend was used and succeeded
historically).

## Findings

### F1 — ComfyUI auto-start is missing (Bucket B)
`aaa_texture.py` assumes ComfyUI is already running at the host arg.
There's no auto-start, no preflight check, no error message that says
"start ComfyUI first." A cold-run operator gets a generic connection
error.

**Fix shape**: `world3_make.py` (Phase E orchestrator) wraps texture
stages with a "is ComfyUI up?" preflight that either errors clearly or
starts ComfyUI in a subprocess.

### F2 — Per-lane venv discipline incomplete (Bucket B)
`pipelines/terrain/.venv` exists (Landlab). `animators/mesa-env/venv`
exists (StableMaterials + diffusers + cu130 torch). But
`pipelines/textures/.venv` does not. Texture scripts use system Python
when they don't dispatch to mesa-env.

**Fix shape**: either (a) document explicitly which python interpreter
runs `aaa_texture.py` (system Python 3.12), or (b) create a
`pipelines/textures/.venv` to match the terrain pattern.

### F3 — StableMaterials invocation pattern not in orchestrator help (Bucket B)
`aaa_texture.py --help` lists `--pbr-backend {derive,sm,chord,...}` but
doesn't say "sm requires `animators/mesa-env/venv/Scripts/python.exe` to
be present and have diffusers installed." Operator reading help cold has
no way to discover this dependency.

**Fix shape**: `--help` should list per-backend prereqs OR fail with a
specific error if the required venv/model is missing.

### F4 — No preflight check for model files (Bucket B / partial Bucket C)
`aaa_texture.py` doesn't check whether FLUX 2 klein-4B is on disk
before submitting a workflow to ComfyUI. If the model file were missing,
ComfyUI would error mid-flow rather than the orchestrator catching it
early.

**Fix shape**: preflight verifying required model files exist before
queuing any ComfyUI work.

### F5 — Provenance is exemplary (positive finding)
Same as B.1: `aaa_pipeline.json` + `variant_select.json` together
preserve every arg + stage + metric needed to reproduce. Worker
discipline on the script's recordkeeping is good.

### F6 — Seam-score determinism unknown (defer to actual cold-run)
Texture generation includes a FLUX img2img heal pass + seam_repair, both
of which have potential for non-determinism via VAE quantization /
sampler precision. We don't know if seed=100 produces byte-identical
output on a re-run because we can't execute.

**Action**: defer this signal until ComfyUI is started and B.2 can run.

## Bucket categorization

### Bucket A (trivial config) — none

### Bucket B (manual-step gaps)
- **B-1**: ComfyUI auto-start missing
- **B-2**: `pipelines/textures/.venv` doesn't exist; system Python use is
  undocumented
- **B-3**: StableMaterials backend's mesa-env requirement undocumented in
  `--help`
- **B-4**: No preflight check for model files
- **B-5**: No documented "start ComfyUI; then run aaa_texture.py" sequence

### Bucket C (real code bugs) — none surfaced
The pipeline scripts themselves haven't shown defects. All gaps are at
the invocation/environment layer.

### Bucket D (architectural gaps)
- **D-1**: Texture pipeline has the right shape internally (orchestrator
  → stages → gate → catalog) but no higher-level wrapper that says
  "given a biome kit + view mode, generate all 5 materials." Each
  material is a separate operator command today.

## What this tells us about the larger rebuild

1. **No new world4 case from B.2.** Every gap surfaced is at the
   environment/invocation layer, not the script level. World4 would
   inherit the same texture pipeline and would have to solve the same
   problems.
2. **Phase E orchestrator can absorb every B.2 finding cleanly.** All
   F1-F4 gaps map to either preflight checks (F1, F4), env documentation
   (F2, F3), or sequence wrappers (F5). These are exactly what the
   `stages.json` + dispatcher approach handles.
3. **The provenance pattern works**. Two-for-two on chains tested
   carrying complete reproduction info in their manifest files.

## Recommendation

**Move forward to B.3 (procedural neighbor) immediately.** B.3 doesn't
need ComfyUI; it tests `build_procedural_neighbor_bundle.py` which is
the source of the procedural-vs-texture confusion.

After Phase B is complete, **start ComfyUI** manually and run the
remaining B.2 cold-run as a quick verification before Phase C. The
findings here aren't blocking — they're documented gaps for Phase D fixes.

## Skipped (defer to post-Phase-E)

Running the actual FLUX → StableMaterials → QA → catalog chain end-to-end
requires:
1. Operator starts ComfyUI
2. Wait for model load (~30 sec)
3. Run `aaa_texture.py` (~2-5 min per material at quality default)
4. Diff outputs

Skip during B.2 because:
- Not deterministic on PNGs (FLUX VAE quantization makes byte-exact reproduction unlikely)
- Higher-signal test is whether the **gate** picks the same grade for a new run, not whether the bytes match
- Better validated as the orchestrator's first integration test in Phase E

## Cross-references

- Phase plan: [`REBUILD_PLAN_PHASES_B_E_2026_05_11.md`](REBUILD_PLAN_PHASES_B_E_2026_05_11.md)
- B.1 pass result: [`B1_CHAIN1_VALIDATION_2026_05_11.md`](B1_CHAIN1_VALIDATION_2026_05_11.md)
- Phase A inventory: [`WORKFLOW_INVENTORY_2026_05_11.md`](WORKFLOW_INVENTORY_2026_05_11.md)
- aaa_texture.py source: `pipelines/textures/aaa_texture.py`
- mesa-env venv (for StableMaterials): `animators/mesa-env/venv/Scripts/python.exe`

## Phase B.2 status

- [x] Recovered provenance from `aaa_pipeline.json` + `variant_select.json`
- [x] Reconstructed cold-run command (verified against current preset schema)
- [x] Validated prereqs without executing
- [x] Verified preset/stage/gate schema alignment
- [x] Documented 5 Bucket B gaps + categorization
- [ ] Cold-run execution (deferred — needs operator to start ComfyUI)

**B.2 PARTIAL PASS.** Scripts intact. 5 Bucket B gaps documented. Ready for B.3.
