# HANDOFF — Phase 11 Props Deep-Dive (2026-05-06)

**Status:** ✅ landed. 11A + 11B + workflow infra complete. 11C scene integration deferred.

**Authoritative A/B doc:** `../../world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md`

## What shipped

### Two AI routes proven end-to-end on RTX 5090 / cu130 / Win11

- **Hunyuan3D-2.1 (visualbruno fork)** — concept image → DiT geometry → multi-view paint → bake → inpaint → PBR-textured GLB. **87 seconds on real Egyptian obelisk** (1.6 MB GLB, 40k faces, 1024² PBR).
- **Trellis2 4B (microsoft/TRELLIS.2-4B)** — concept image → 4B DiT mesh gen → o_voxel postprocess (UV unwrap + texture bake + GLB pack) → PBR-textured GLB. **86 seconds on real Egyptian obelisk** (13.9 MB GLB, 194k faces, 2048² PBR).

### 4×4 quality sweep on same concept

| Route | Configs | Best wall-clock | Sweet spot |
|---|---|---:|---|
| HY3D-2.1 | baseline / hi_geo / hi_paint / hero_max | 74s (`hi_geo`) | `hi_geo`: octree=512, max_facenum=100k, 1024² tex |
| Trellis2 | low / mid / hi / hi_tex | 4s postprocess (after 23s one-time mesh gen) | `mid`: decimation_target=200k, 2048² tex |

**Verdict: Trellis2 picked as default.** Even Trellis2 `low` (49k/1024²/4s postprocess) beats HY3D `hero_max` (100k/2048²/677s) visually. HY3D kept as ComfyUI-integration fallback for biome scatter authoring.

### Workflow infrastructure landed

| File | Purpose |
|---|---|
| `../../pipelines/props/ai_route_dispatch.py` | Trellis2-default dispatcher. `pick_route(render_class, has_fine_relief=, hero_polycount_budget_ok=, ...)` returns `RouteDecision(route, settings, reason)`. |
| `../../pipelines/props/trellis2_batch.py` | `BatchRunner` class. Loads 4B model + envmap ONCE, runs N concepts. Saves ~50s × N over per-concept python invocation. |
| `../../pipelines/props/trellis2_route.py` | Wired to BatchRunner via Trellis2 venv subprocess. Auto-resolves preset via dispatcher. `--legacy-cmd` keeps old `TRELLIS2_PROP_CMD` shell-out path. |
| `../../pipelines/props/TRELLIS2_PATCHES.md` | Forensics + reapply notes for the 3 venv patches our Trellis2 install needs (DLL search dirs, missing triton submodule pure-torch fallback, sentinel + dtype safety in fallback). |

### One-line smoke command for any future prop

```powershell
python D:\assets\pipelines\props\trellis2_route.py `
  D:\assets\world\props\concepts\<id>\source.png `
  --id <id> `
  --render-class hero_prop --has-fine-relief `
  --device cuda --run-model
```

## What was deferred

### Phase 11C — postprocess orchestrator ✅ DONE; scene integration deferred

**Postprocess orchestrator landed** at `../../pipelines/props/postprocess_ai_route.py`. Takes a fresh AI-route GLB and walks it through 7 stages to produce a Godot-importable prop in one command:

```powershell
python D:\assets\pipelines\props\postprocess_ai_route.py `
  --source-glb <path/to/ai_route_output.glb> `
  --id <prop_id> `
  --family <family> `
  --render-class hero_prop `
  --texture-set biome_grassland
```

**Stages** (per render_class defaults):
1. `stage_into_library` — copy GLB into `../../world/props/library/<id>/` + bootstrap `prop.json`
2. `preprocess` — Blender clean / merge verts / normalize-scale / target-tris (Stage 1 ~5s)
3. `lod_chain` — 4-tier DECIMATE chain via Blender (~3s)
4. `collision_decompose` — CoACD convex hulls (~30s on 100k mesh)
5. `billboard_bake` — 8-angle horizontal strip atlas (skipped for hero_prop)
6. `pbr_material_bind` — bind to texture-library set (<1s)
7. `validate_props` — full-library contract check (<1s)
8. `export_godot` — multi-LOD .tscn + multimesh template (<1s)

**End-to-end smoke verified on the Trellis2 obelisk:** `obelisk_egyptian_a04` shipped at `../../world/props/library/obelisk_egyptian_a04/` + `../../godot_pack/props/obelisk_egyptian_a04/`. 4 LODs at 194k / 126k / 68k / 29k tris, distances 25/60/120/200 m, CoACD convex hulls, biome_grassland PBR bound, `.tscn` ready to drop into a Godot scene.

**Two bugs found-and-fixed in the orchestrator:**
- `validate_props.py` only takes `--library`, not `--id` (full-library validator). Orchestrator now invokes it without per-id flag and lets the validator's pass/fail signal cover the full library; that's fine for our purposes since broken neighbors would be pre-existing factory bugs, not orchestrator-caused.
- Bootstrap `prop.json` initially wrote `triangles: 0` for LOD0 → `lod_chain.update_prop_json()` multiplied that by ratios → every LOD reported `tris=8` (the floor). Fix: orchestrator inspects the source GLB with trimesh and writes the real face count into the bootstrap, so the ratio math produces real triangle counts (194k / 126k / 68k / 29k for `hero_prop` ladder).

**Scene integration (drop into a real Godot scene)** still deferred — gated on world-gen recovering from current breakage (user noted "we started over on world gen, it totally broke" 2026-05-06). The prop is fully Godot-importable; the only missing step is opening a working biome `.tscn` and instancing the obelisk's `.tscn` as a child.

### Multi-prop generalization test

Current sample size is N=1 (Egyptian obelisk). Drop 3-5 different concept types (mushroom / crate / weapon / fountain / statue) through `trellis2_batch.py` to confirm Trellis2 generalizes. Gated on:
- Either user-provided concept PNGs (saves to `../../world/props/concepts/<id>/source.png`)
- Or `OPENAI_API_KEY` for `../../pipelines/props/concept_gen.py`

### Hunyuan3D-Omni pilot

Per Phase 11D-bis EXPANSION_PLAN entry. Pass criteria: bbox-conditioned envelope ±10% on long axis. Run only if envelope-fit becomes an issue. Geometry-only — no PBR — so always paired with our existing visualbruno paint chain for textures.

## Patches discovered + applied

See `../audits/REVIEW.md` "Phase 11 Props Deep-Dive — 6 patches found and fixed" section for full forensics. Quick list:

**HY3D-2.1 (visualbruno fork):**
1. `multiview_utils.py:45` — added `trust_remote_code=True`
2. `convert_utils.py:138` — replaced Chinese-character print with ASCII (Windows cp1252)
3. NVIDIA driver upgrade 592.01 → 596.36 (cu130 PTX runtime)

**Trellis2 4B venv:**
4. `flex_gemm/kernels/__init__.py` — added CUDA + torch DLL search dirs
5. `flex_gemm/kernels/triton/__init__.py` (new file) — pure-torch fallback for missing `indice_weighed_sum_fwd/bwd_input`
6. Same fallback: sentinel handling (-1 indices) + dtype preservation (fp16)

## Findings worth remembering

1. **AI-route quality is concept-quality-bottlenecked, not model-bottlenecked.** Same HY3D model on a flat-polygon placeholder vs a real photographic obelisk: identical mesh stats, dramatically different output. Both AI routes faithfully reproduce what the input shows; neither hallucinates detail.

2. **Geometry knobs >> texture knobs on HY3D for cost-of-quality.** `hi_geo` (74s, 100k faces) is faster than baseline (90s, 40k faces) AND gives more detail. Bumping texture 1024² → 2048² alone shoots wall-clock 90s → 387s for marginal visual gain.

3. **Trellis2 mesh gen is amortizable.** 23s one-time per concept + 4-20s postprocess per preset config. Batch runner saves 50s × N over per-concept python invocation.

4. **Both AI routes had "hidden" install pain on Blackwell / cu130.** The wheels exist (good!) but driver + DLL search path + Unicode console + missing-submodule patches were all needed. Documented for repeat installs.

## Where to look for what

```
world/props/ai_routes/
├── AB_hy3d_vs_trellis2_2026_05_06.md     ← authoritative A/B + sweep + dispatch matrix
├── hunyuan3d/
│   ├── ruined_obelisk_a_gate1/            ← geometry-only first run (placeholder concept)
│   ├── ruined_obelisk_a_gate2/            ← PBR first run (placeholder concept)
│   ├── ruined_obelisk_a_gate2_real/       ← PBR on real Egyptian concept (87s)
│   └── sweep/{baseline,hi_geo,hi_paint,hero_max}/   ← 4-config quality sweep
├── trellis2/
│   ├── ruined_obelisk_a_gate/             ← Trellis2 first run on real concept (86s)
│   ├── batch_smoke_ruined_obelisk_a/      ← batch runner smoke test (30s)
│   └── sweep/{low,mid,hi,hi_tex}/         ← 4-config quality sweep

pipelines/props/
├── ai_route_dispatch.py                   ← Trellis2-default dispatcher
├── trellis2_batch.py                      ← BatchRunner class
├── trellis2_route.py                      ← wired route adapter
├── hunyuan3d_route.py                     ← HY3D route adapter (still uses CLI workflow)
└── TRELLIS2_PATCHES.md                    ← Trellis2 venv patches forensics

D:\tmp\
├── sweep_compare_sheet.png                ← 4×2 grid of all 8 sweep configs (visual)
├── glb_compare/<run>/{front,back,left,right,iso}.png  ← per-config Blender renders
├── hy3d_sweep.py                          ← HY3D sweep runner (one-shot)
├── trellis2_sweep.py                      ← Trellis2 sweep runner (one-shot)
└── hy3d_resume_after_restart.md           ← restart-recovery notes (kept as forensics)
```

## Next focus (Phase 12 candidate)

Phase 11 closes the props lane. Per the original "treat each pipeline like the character pipeline" framing, the next pipeline to deep-dive is one of: **audio (real Stable Audio bake), VFX (Taichi GPU baker), game-data (real TLTE seed content), UI (real LoRA train run)**. Pick by user direction or by which has the most blockers preventing factory-wide cross-pipeline composition (the "biome + props + ambience + VFX + HUD" demo).
