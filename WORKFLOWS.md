# Master Workflow List

For each asset type: **what you're creating → which tools you have → the order to run them**. Updated 2026-05-07. Concise on purpose; details in [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md), tool inventory in [TOOLS_INDEX.md](TOOLS_INDEX.md), per-tool docs at [docs/tools/](docs/tools/README.md).

Each section follows the same shape:

```
ASSET → first decision → tool branches → run order
```

If you only need the run order, read the bold line at the bottom of each section.

## Index

1. [Character (3D rigged)](#1-character-3d-rigged)
2. [Prop (3D mesh)](#2-prop-3d-mesh)
3. [PBR Texturing](#3-pbr-texturing) — both tileable and mesh-driven paths
4. [Audio — Ambience / SFX / Music / TTS](#4-audio)
5. [Icon / UI element](#5-icon--ui-element)
6. [VFX — 3D bake (particles / fracture / smoke / fog)](#6-vfx-3d-bake)
7. [VFX — Shader (.gdshader)](#7-vfx-shader)
8. [Game Data record](#8-game-data-record)
9. [DEM (real-world heightmap)](#9-dem-real-world-heightmap)
10. [Scene composition](#10-scene-composition--open)

VFX has two lanes (6 and 7). They are not the same thing — see `pipelines/vfx/` vs `art_lab/`.

---

## 1. Character (3D rigged)

> **Canonical chain decided 2026-05-07** per [research brief #01](docs/research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md): rig-first → skeletal animation by topology → Blender retarget. Shape-keys (AnimateAnyMesh) only for ambient/secondary motion. The earlier procedural chain (Meshy → preprocess → AnimateAnyMesh → sprite) produced bad outputs because **AnimateAnyMesh is not a substitute for skeletal animation** — it's a 4D mesh-deformation foundation model trained on short, low-displacement deformations.

### Path A — Humanoid character (~10 of 33 in current roster)

```
Concept image
   ↓
meshy/batch_pipeline.py
   ├── meshy_image_to_3d.py     (Meshy API → 350-740k tri GLB)
   └── preprocess_mesh.py       (Blender decimate to 30k tris, UVs preserved)
   ↓
SkinTokens demo.py  (default rigger for humanoids; ~30s)
   → FBX with skeleton + skin weights
   ↓
hy-motion-fbx-exporter (Hunyuan-Motion text→motion; ~10s)
   → BVH/FBX in SMPL-H or Mixamo skeleton
   ↓
Blender bpy retarget  (or Mixamo Auto-Rigger / Make-It-Animatable)
   → animated FBX on character skeleton
   ↓
(Optional) foot-locking pass + Blender CI linter
   ↓
Blender headless EEVEE-Next sprite-sheet bake (8 angles × 16 frames)
   ↓
Final FBX + sheet.png → Godot import
```

Total: ~1-2 min per humanoid per clip + parallelizable sprite bake.

### Path B — Non-humanoid character (~23 of 33)

```
Concept image
   ↓
meshy/batch_pipeline.py (same as Path A)
   ↓
[Rig — pick ONE based on topology]
   ├── RigAnything                 unusual topology (sandworms, tentacles, segmented)
   └── SkinTokens                  clean quadrupeds with bilateral symmetry
   ↓
[Animate — pick ONE based on text-conditioning need]
   ├── AniMo ⏳ (planned)          text-conditioned, 114 species, best for biological creatures
   ├── AnyTop                      unconditional sampling, best for OOD topologies
   │                               (sandworm, tentacle, six-legs)
   └── Puppeteer ⏳ (planned, WSL2)  video-guided, hardest cases, end-to-end rig+animate
   ↓
Blender retarget (when rigger ≠ animator skeleton)
   ↓
(Optional) contact-pose cleanup + CI linter
   ↓
Blender sprite bake → Godot
```

Total: ~2-5 min per non-humanoid per clip plus AnyTop curation overhead.

### Hybrid (skeletal + shape-key) — for production polish

After Path A or B, layer shape-key animation **additively** for secondary detail:
- Face expressions
- Gill flutter / mantle pulse / tentacle ripple
- Idle breathing

**This is the only valid use of AnimateAnyMesh** — bake mesh deformation as shape keys via Blender script, layer on top of the skeletal track.

### Animation review (CI gate before fanout)

Build a ~100-line Blender linter to catch the "barely moves their head" failure mode before scaling up:

```python
# 1. Static-frame detection (~10 lines)
#    sum of per-bone rotation deltas across clip < threshold = fail
# 2. Foot-skating per Kovar/Schreiner '02 (~50 lines)
#    sample foot-bone xy each frame; flag frames where delta > epsilon while in-contact
#    > 5% skate-frames = fail
# 3. FVMD aggregate (pip-installable)
#    over-smoothing / jitter detection
#    NOTE: lit warns FMD-family does NOT reliably catch foot-skate
```

### Sprite-sheet bake (final stage, both paths)

Blender headless EEVEE-Next is the right tool — no 2026 alternative beats it. Pattern:

```powershell
# One blender --background --python script.py per character
# Orthographic camera on parented Empty; rotate 8× per frame; 16 frames
# Composite via Pillow (faster than Blender's compositor)
# Parallelize:
ForEach-Object -Parallel { ... } -ThrottleLimit 4
```

Budget: ~14 min/character at 200 ms/frame for 8 angles × 16 frames.

### Fallback chain

```
Path A SkinTokens fails on humanoid?
   → RigAnything → Hunyuan-Motion → retarget
   → Mesh2Motion app (manual UI) → Mixamo retarget

Path B AniMo doesn't have the species?
   → AnyTop (closest specialized model) → curate samples
   → Puppeteer video-guided (you provide reference clip)
   → Manual Blender keyframing (last resort)
```

### Run order (humanoid):

1. `python meshy\batch_pipeline.py --input <concept>.png --id <name>`
2. `cd D:\assets\animators\SkinTokens && .venv\Scripts\python.exe demo.py --input D:\assets\meshy\preprocessed\<name>_p.glb --output D:\assets\meshy\rigged\<name>.glb`
3. `D:\assets\animators\hy-motion-fbx-exporter\.venv\Scripts\Activate.ps1 && hy-motion-export "<motion prompt>" -c D:\assets\meshy\rigged\<name>.glb -o D:\assets\meshy\animated\<name>_<action>.fbx`
4. Run Blender CI linter on the FBX
5. Run Blender sprite-sheet baker

### Run order (non-humanoid):

1. `python meshy\batch_pipeline.py --input <concept>.png --id <name>`
2. `cd D:\assets\animators\RigAnything && .venv\Scripts\python.exe inference.py -c config.yaml --load ckpt/riganything_ckpt.pt -s inference true --mesh_path D:\assets\meshy\preprocessed\<name>_p.glb`
3. **AniMo (when installed):** `python animo/inference.py --prompt "<motion>" --skeleton <rigged_skeleton>.bvh`
   **OR AnyTop (already installed):** `python -m sample.generate --model_path save/<topology>_model_*/model*.pt --object_type <closest_match> --num_repetitions 3` (curate from 3)
4. Blender retarget (rigger skeleton ≠ animator skeleton)
5. CI linter + sprite bake

**Quality reference:** [docs/audits/REVIEW.md](docs/audits/REVIEW.md) (the depth standard for character work).
**Latest review:** [docs/pipeline_reviews/06_characters.md](docs/pipeline_reviews/06_characters.md) — research-calibrated 2026-05-07 PM.

---

## 2. Prop (3D mesh)

Decision: do you have a concept image, or just a recipe?

```
                    ┌── HAVE concept image ──┐
                    │                        │
            ai_route_dispatch.py picks:      │
              ├── Trellis2 (default)         │
              │     pipelines/props/         │
              │     trellis2_batch.py        │
              │     (model-load-once)        │
              │                              │
              └── HY3D-2.1 (fallback)        │
                    pipelines/props/         │
                    hunyuan3d_route.py       │
                    (ComfyUI workflow)       │
                                             │
            ┌── HAVE recipe (no image) ──────┘
            │
       pipelines/props/proc_generate.py
            │
            └── (procedural geometry from PROC_RECIPES.md)
   ↓
postprocess_ai_route.py  (7-stage orchestrator)
   1. stage_into_library
   2. preprocess              (Blender geometry cleanup)
   3. lod_chain               (4-tier DECIMATE COLLAPSE: 100/65/35/15%)
   4. collision_decompose     (CoACD convex hulls)
   5. billboard_bake          (far-LOD billboard atlas)
   6. pbr_material_bind       (bind to texture sets)
   7. validate_props + export_godot
   ↓
Output: world/props/library/<prop_id>/  (prop.json, thumbnail.png, mesh, qa.json)
        world/props/godot/<prop_id>/    (Godot scene + LOD nodes)
```

**Run order:**
1. (Concept route) `python pipelines\props\trellis2_batch.py --concept <img>.png --id <prop_id> --preset balanced`
2. **OR** (Procedural) `python pipelines\props\proc_generate.py --recipe <recipe_id>`
3. `python pipelines\props\postprocess_ai_route.py --id <prop_id> --render-class hero`
4. `python pipelines\props\validate_props.py --library world\props\library`

`--render-class`: `scatter` (50k tris, 1024² tex) / `balanced` (200k, 2048²) / `hero` (500k, 2048²) / `hi_tex` (200k, 4096²).

For variation: `python pipelines\props\variation_sweep.py --id <prop_id> --variations 4`.

---

## 3. PBR Texturing

**First decision: tileable texture set, or per-mesh UV-baked PBR?** These are two separate workflows that solve different problems.

| Workflow | Input | Output | When to use |
|---|---|---|---|
| **3a. Tileable PBR set** | text prompt | seamless 1024² PBR set, UV-tiled via shader across any surface | big surfaces, biome ground, walls, repeated material |
| **3b. Mesh-driven PBR** | mesh GLB/OBJ + text prompt | per-mesh UV-baked PBR (one set per mesh) | hero rocks, unique cliff faces, set-piece terrain, meshes where the *shape itself* is part of the texture story |

Most production work uses both. Tileable for the 90% case, mesh-driven for hero/unique pieces.

### 3a. Tileable PBR set

Sub-decision: full PBR set or just an albedo?

```
        ┌── FULL PBR (canonical) ───┐
        │                           │
   pipelines/textures/aaa_texture.py
        │
        ├── stablematerials_image2pbr.py  (StableMaterials backend)
        │
        ├── seam_repair.py                (if seams visible)
        ├── derive_pbr_v2.py              (fill missing maps)
        ├── texture_qa.py                 (writes qa/seam_score.json + grade)
        └── blender_preview.py            (visual A/B)
        ↓
        Output: world/textures/library/<id>/
                  <id>_albedo.png + _normal.png + _roughness.png
                  + _metallic.png + _ao.png + _height.png
                  aaa_pipeline.json + qa/seam_score.json + previews

        ┌── ALBEDO ONLY (fast) ────┐
        │                          │
   pipelines/textures/flux_seamless.py
        │
        4-pass FLUX 2 + offset+heal:
        Pass 1: text2img full-res
        Pass 2: circular shift by half (exposes seams)
        Pass 3: img2img heal (low-denoise)
        Pass 4: reverse shift → tileable
        ↓
        Output: world/textures/library/<id>/<id>_albedo.png
        (no PBR maps; pair with derive_pbr_v2.py if needed)

        ┌── INGEST third-party ────┐
        │                          │
   pipelines/textures/polyhaven_fetch.py     (PolyHaven CC0)
   pipelines/textures/ambientcg_fetch.py     (AmbientCG)
        ↓
        ALWAYS run texture_qa.py after ingest (quality varies upstream)
```

**Run order (canonical, full PBR):**
1. `python pipelines\textures\aaa_texture.py --prompt "<desc>" --id <set_id> --category <Bricks|Rock|...>`
2. `python pipelines\textures\texture_qa.py --id <set_id>` (auto-runs as part of step 1, but useful to re-grade after edits)
3. If grade is C: `python pipelines\textures\seam_repair.py --id <set_id>` then re-QA

**Run order (albedo only):**
1. `python pipelines\textures\flux_seamless.py --prompt "<desc>" --id <set_id> --size 1024 --seed 7 --heal-strength 0.35`
2. `python pipelines\textures\derive_pbr_v2.py --id <set_id>` (if PBR needed)
3. `python pipelines\textures\texture_qa.py --id <set_id>`

**Grades target:** A is `<0.0015` edge MSE; B is `<0.008`; C is anything worse. 7 sets in the library are currently un-graded (run `texture_qa.py --all` to fix that).

### 3b. Mesh-driven PBR (MaterialAnything)

Iterative multi-view diffusion that bakes PBR maps onto a specific mesh's UV layout. **Mesh-only** — flat 2D textures don't work (architectural constraint, not a bug — see `pipelines/textures/derive_pbr_v2.py` for 2D albedo→PBR instead).

```
   Input: GLB/OBJ mesh + text prompt + starting albedo (texture_kd.png)
        ↓
   animators/MaterialAnything/scripts/generate_texture_pbr_3d.py
        │
        Iterative loop per viewpoint:
        ├── render depth + normal from camera N
        ├── ControlNet-Depth inpaint (text2img + RePaint)
        ├── material_estimator (predict albedo+bump+roughness+metallic from inpainted view)
        ├── uvrefine_model (refine maps using cross-view consensus)
        └── update UV-space material textures
        ↓
   Output: outputs/<run_id>/generate/
          ├── material/    per-view albedo/bump/metallic/roughness PNGs
          ├── mesh/        per-view OBJ snapshots
          ├── rendering/   how the mesh looks with materials applied
          └── (depth/normal/inpainted/mask = process artifacts)
```

**Run order:**
1. **Convert input mesh to OBJ + provide starting texture:**
   ```powershell
   python -c "import trimesh; trimesh.load('input.glb', force='mesh').export('demo/test/mesh.obj')"
   copy demo\test\Material_0.png demo\test\texture_kd.png  # rename for the script
   ```
2. **Run the generator** (smoke test settings — 6 viewpoints, 20 ddim steps; production = 36 viewpoints, 50 steps):
   ```powershell
   cd D:\assets\animators\MaterialAnything
   .\venv\Scripts\python.exe scripts\generate_texture_pbr_3d.py `
     --image2materials_model ./pretrained_models/material_estimator `
     --uvrefine_model ./pretrained_models/material_refiner `
     --input_dir ./demo/test --obj_name mymesh --obj_file mesh.obj `
     --prompt "<text describing desired material>" --add_view_to_prompt `
     --num_viewpoints 6 --viewpoint_mode predefined `
     --ddim_steps 20 --seed 42 --device 2080 `
     --output_dir ./outputs/<run_id>
   ```
3. **Output to inspect:** `outputs/<run_id>/generate/rendering/0.png` (textured mesh preview), then `material/<view>_albedo.png` for raw maps.

**Notes:**
- `--num_viewpoints` valid values: 1, 2, 4, 6, 12, 20, 36 (or "objaverse", "shapenet", "objaverse22").
- `--ddim_steps 20` is smoke-test fast; production uses 50.
- Smoke test on goblin: ~10 min wall-clock, 56 MB output.

Full install recipe in [`animators/INSTALL_MATRIX.md § MaterialAnything`](animators/INSTALL_MATRIX.md).

### 3c. Mesh-driven hero terrain (experimental — not yet validated)

> **Status: documented but never run on a real terrain mesh.** Treat as a path to try when worldgen scene-composition is back on the table or when a specific hero terrain piece is needed. SOTA survey #02 (textures research brief) is investigating better alternatives.

The same MaterialAnything pipeline (#3b) can in principle texture a **terrain mesh** rather than a prop. The output is **bespoke per-mesh** — *not tileable* — so it's the wrong tool for biome ground (kilometer-scale repeating tiles) but the *right* tool for unique terrain hero pieces:

| Use case | Right tool |
|---|---|
| Biome ground tiled across a kilometer of terrain | **3a tileable** |
| Unique boss-arena floor, set-piece cliff face, volcano caldera, dragon's lair, hero canyon wall | **3c mesh-driven** |

**Hypothetical pipeline:**

```
   DEM heightmap PNG (e.g. from dems/<region>.tif)
        ↓
   Convert to subdivided plane mesh (256×256 verts, displaced by heightmap)
        ↓
   UV-unwrap (planar projection top-down for ground; auto-unwrap for cliffs)
        ↓
   Export as OBJ + starting albedo (texture_kd.png)
        ↓
   MaterialAnything generate_texture_pbr_3d.py
   --prompt "cracked desert ground with scattered pebbles, top-down satellite view"
   --num_viewpoints 12 --viewpoint_mode predefined
        ↓
   Per-mesh UV-baked PBR (one tile, one bespoke texture, mesh-aware)
```

**Open questions** (in research brief #02):
- What viewpoint configuration works best for flat horizontal terrain? (Default cameras are object-centered.)
- Does the iterative multi-view consensus actually help for ground-on-a-flat-mesh, or does it just produce smudgy results?
- How does this compare to tileable PBR + good shader-driven height-blending for the same visual budget?
- Are there 2026 alternatives that explicitly handle "tileable + mesh-aware" (e.g., DreamMat-style)?

**Don't run this without first dispatching brief #02** — answer informs whether to spend the time on this path or use a 2026 alternative.

---

## 4. Audio

Decision: what kind of audio?

### 4a. Biome ambience

```
pipelines/audio/biome_ambience.py
   ├── pipelines/audio/local_audio_open.py   Stable Audio Open 1.0 (1.21B), GPU bake
   ├── pipelines/audio/recipes/biome_ambience.json   (10 biomes × 4 layers)
   └── 4-layer model: bed_drone + bed_air + wildlife_sparse + distant_event
   ↓
LUFS-normalized per LUFS_AUTHORING_GUIDE.md
   ↓
Output: audio/ambience/<biome>/<layer>__<seed>.wav
```

**Run:** `python pipelines\audio\biome_ambience.py --recipe pipelines\audio\recipes\biome_ambience.json`

LUFS targets: -28 dBFS bed_drone, -30 dBFS bed_air, -22 dBFS wildlife peak, -20 dBFS distant_event peak.

### 4b. SFX

```
pipelines/audio/synth_sfx.py            procedural baseline (always available)
pipelines/audio/eleven_sfx.py           ElevenLabs cloud route (env-gated)
pipelines/audio/cc0_ingest.py           freesound CC0 ingestion
   ↓
Output: audio/sfx/<category>/<id>.wav
```

**Run:**
- Procedural: `python pipelines\audio\synth_sfx.py --catalog <recipe>.json`
- Cloud: `python pipelines\audio\eleven_sfx.py --prompt "wood crack, sharp" --id wood_crack_a01`

### 4c. Music

```
pipelines/audio/local_music_yue.py      YuE local (parked, weights pending)
pipelines/audio/adaptive_music.py       adaptive stems
   ↓
Output: audio/music/<id>/{ogg, wav, stems/}
```

### 4d. Speech (TTS)

```
pipelines/audio/local_tts_f5.py         F5-TTS local (GPU)
pipelines/audio/openai_tts.py           OpenAI cloud (env-gated)
   ↓
Output: audio/tts/<id>.wav
```

### 4e. Pack and validate

```
pipelines/audio/audio_qa.py             LUFS / loudness QA
pipelines/audio/lint_audio.py           catalog linter
pipelines/audio/loop_detect.py          loop-point detection
pipelines/audio/ambience_pack.py        ambience pack for Godot
pipelines/audio/export_godot.py         Godot import resources
```

**Run order (typical):**
1. Bake (one of 4a/4b/4c/4d)
2. `python pipelines\audio\audio_qa.py`
3. `python pipelines\audio\lint_audio.py`
4. `python pipelines\audio\export_godot.py --library audio`

---

## 5. Icon / UI element

Decision: which generation route?

```
                      ┌── PROCEDURAL (always) ──┐
                      │ pipelines/ui/synth_icons.py
                      │                          │
                      ├── CLOUD (env-gated) ─────┤
                      │ ├── openai_icons.py        gpt-image-1
                      │ ├── recraft_icons.py       Recraft V3 (supports --svg, set-style)
                      │ └── pixellab_icons.py      PixelLab
                      │                          │
                      └── LOCAL (GPU) ──────────┘
                        local_diffusion_icons.py  FLUX-schnell via ComfyUI
   ↓
pipelines/ui/lint_icons.py  + icon_validator.py
   ↓
pipelines/ui/pack_atlas.py    → ui/atlas.png + ui/atlas.json
   ↓
pipelines/ui/nine_slice.py    → ui/9slice/<frame_id>/
   ↓
pipelines/ui/hud_mockup.py    → ui/hud_preview_<faction>_<state>.png
   ↓
pipelines/ui/export_godot.py
```

**Run order:**
1. Pick generation route (procedural for baseline; cloud or local for hero icons)
2. `python pipelines\ui\<route>.py --catalog <schema>.json --out ui\<route>\`
3. `python pipelines\ui\lint_icons.py`
4. `python pipelines\ui\pack_atlas.py --in ui\<route> --out ui\atlas.png --json ui\atlas.json`
5. (Frames) `python pipelines\ui\nine_slice.py --in <frame>.png --id <name>`
6. (HUD mockup) `python pipelines\ui\hud_mockup.py --faction <name> --state <state>`
7. `python pipelines\ui\export_godot.py`

Cloud routes fall back to `synth_icons.py` automatically if env keys missing.

---

## 6. VFX (3D bake)

Decision: which physics backend?

```
authoring artifact: effect.json     (canonical)
   ↓
pipelines/vfx/bake.py routes by effect kind:
   ├── particle_cpu     numpy SoA particles + emitter + gravity + drag
   ├── fracture2d       Voronoi shards + analytical motion
   ├── smoke_field      semi-Lagrangian advection 2D smoke field
   ├── volumetric_fog   numpy 3D noise → Texture3D-via-slice-atlas (3D)
   └── external         already-baked artifacts (e.g. spell-lab migration)
   ↓
manifest.json + frames/ + flipbook.png + extras (particles.json | field.json | fragments.json)
   ↓
Godot export (pick target):
   ├── pipelines/vfx/export_godot.py        2D flipbook
   └── pipelines/vfx/export_godot_3d.py     4 targets:
                                              ├── 3d_billboard
                                              ├── decal
                                              ├── mesh_trail   (uses MeshTrail3D.gd runtime)
                                              └── fog_volume   (uses fog Texture3D)
   ↓
Output: vfx/catalog/<kind>/<id>/
        Runtime helpers: vfx/runtime/MeshTrail3D.gd + AudioCueBus.gd
```

**Authoring helpers:**
- `python pipelines\vfx\author_grid.py` → 24-cell element × archetype catalogue
- `python pipelines\vfx\author_damage.py` → 12-effect damage / impact catalogue
- `python pipelines\vfx\import_spell_lab.py` → migrate legacy spell-lab artifacts

**Run order:**
1. Author or migrate effect.json
2. `python pipelines\vfx\bake.py --effect <path>/effect.json`
3. `python pipelines\vfx\export_godot.py` or `export_godot_3d.py --target <…>`
4. (Optional) `python pipelines\vfx\gallery.py` → `vfx/index.html`

GPU plan: [pipelines/vfx/GPU_BACKENDS_PLAN.md](pipelines/vfx/GPU_BACKENDS_PLAN.md) (deferred Phase 13).

---

## 7. VFX (shader workflow)

**Different from #6.** Use this when iterating on a Godot `.gdshader` file (visual look) rather than baking content (frames + manifest).

```
art_lab/shaders/templates/  (6 first-party templates)
   ├── beam_lightning_2d.gdshader
   ├── dissolve_fire_2d.gdshader
   ├── portal_swirl_2d.gdshader
   ├── ring_field_2d.gdshader
   ├── shield_ripple_2d.gdshader
   └── macro_detail_v1.gdshader   (terrain shader)
   ↓
art_lab/tools/shader_evolve.py        generate N candidates from template (LLM)
   ↓
art_lab/tools/shader_compile_preview.py + shader_godot_render.py
   render previews via Godot headless
   ↓
art_lab/tools/shader_reference_score.py
   score against curated reference set
   ↓
art_lab/tools/shader_promote.py
   shortlist top candidates
   ↓
art_lab/tools/shader_batch_review.py
   build review pages
   ↓
art_lab/tools/shader_lab_index.py
   static dashboard at art_lab/shaders/index.html
   ↓
Output: art_lab/shaders/batches/<batch>/
        art_lab/shaders/review_queues/<batch>/
```

**Run order:**
1. `python art_lab\tools\shader_evolve.py --template <template>.gdshader --batch <name> --n 12`
2. `python art_lab\tools\shader_godot_render.py --batch <name>`
3. `python art_lab\tools\shader_reference_score.py --batch <name> --reference <ref>.png`
4. `python art_lab\tools\shader_promote.py --batch <name> --top 4`
5. `python art_lab\tools\shader_batch_review.py --batch <name>`

**Decision: when to use #6 vs #7?** Full disambiguation in [docs/VFX_LANES.md](docs/VFX_LANES.md). One-liner: **simulation-driven → #6. Formula-driven → #7.**

| Goal | Use lane |
|---|---|
| "Bake a fireball: particles + impact frames + manifest for Godot." | #6 — `pipelines/vfx/` |
| "Iterate on portal_swirl until it looks like reference image." | #7 — `art_lab/shaders/` |
| "Make a dissolve effect for a sprite." | #7 (shader) |
| "Make a fire AOE that does damage on hit." | #6 (bake content) |
| "Tune a shield-ripple visual." | #7 |
| "3D fog volume / ambient haze" | #6 (`volumetric_fog` backend) |

Don't merge them — they solve different problems.

---

## 8. Game Data record

Decision: which generation backend?

```
schemas (pipelines/game_data/schemas.py)
   ↓
pipelines/game_data/generate_records.py
   backend cascade (--backend auto):
   ├── openai            gpt-image-1 sibling for text + JSON schema
   ├── anthropic         Claude tool-schema
   ├── synthetic         deterministic baseline (always available)
   └── vLLM (local)      pipelines/game_data/local_llm_backend.py
                          --device cuda --run-model
                          guided_json + xgrammar
   ↓
pipelines/game_data/validate_records.py
   ↓
pipelines/game_data/roundtrip_test.py    (.tres ↔ JSON)
   ↓
pipelines/game_data/balance/duckdb_reports.py
   item value-vs-rarity, ability cost-vs-effect, faction crosstab
   ↓
pipelines/game_data/yarn_link.py         (when dialogue exists)
   ↓
pipelines/game_data/export_godot.py
   ↓
Output: game_data/{generated, validated, godot, reports, schemas, source}/
```

**Run order:**
1. `python pipelines\game_data\generate_records.py --schema <name> --count <n>`
2. `python pipelines\game_data\validate_records.py`
3. `python pipelines\game_data\roundtrip_test.py`
4. `python pipelines\game_data\balance\duckdb_reports.py`
5. (When dialogue exists) `python pipelines\game_data\yarn_link.py`
6. `python pipelines\game_data\export_godot.py`

Schema migration: `python pipelines\game_data\migrate_records.py --from <vX> --to <vY>`.

---

## 9. DEM (real-world heightmap)

Decision: where does the data come from?

```
                 ┌── BBOX known ──────┐
                 │ pipelines/terrain/ │
                 │ import_dem.py      │
                 │ --dataset <NAME>   │
                 │                    │
   ┌── catalog search first ──────────┤
   │ pipelines/terrain/               │
   │ catalog_search.py                │
   │ (no quota cost)                  │
   │                                  │
   ├── BULK from wishlist ────────────┤
   │ pipelines/terrain/bulk_pull.py   │
   │ walks data_wishlist.json         │
   │ resumable + rate-limit-aware     │
   │                                  │
   ├── REGIONAL (Arctic/REMA/LINZ) ───┤
   │ pipelines/terrain/               │
   │ fetch_regional_stac.py           │
   │ direct provider S3 (bypasses OT) │
   │                                  │
   ├── BIG (multi-tile composite) ────┤
   │ pipelines/terrain/tile_stitch.py │
   │ e.g. full Yosemite at 1m, 9-tile │
   │                                  │
   └── MYSTERY (random worldwide) ────┘
     pipelines/terrain/mystery_sampler.py
     300 procedural bboxes
   ↓
Output: dems/<DATASET>_<W>_<S>_<E>_<N>.tif       (raw cache)
        pipelines/terrain/output/<id>/height_16.png  (bundle)
```

**23 verified datasets:** COP30, AW3D30, GEBCOIceTopo, USGS10m, USGS1m (OT+ tier), SRTM15Plus, CA_MRDEM_DTM, ArcticDEM10m, REMA10m, LINZ1m_DTM, …

**Run order (typical):**
1. `python pipelines\terrain\catalog_search.py --bbox <W> <S> <E> <N>` (find what's available)
2. `python pipelines\terrain\import_dem.py --id <name> --dataset <NAME> --bbox <W> <S> <E> <N> --size 1024`

**Bulk:**
- `python pipelines\terrain\bulk_pull.py --tier premium --dry-run` (plan)
- `python pipelines\terrain\bulk_pull.py --tier premium` (do)

**Big region:**
- `python pipelines\terrain\tile_stitch.py --id <name> --rows 3 --cols 3 --size 4096 --bbox <W> <S> <E> <N> --dataset USGS1m`

**Where DEMs go from here:** they are the seed for whatever new worldgen / scene-composition pipeline replaces v1/v2 (see [#10](#10-scene-composition--open)).

---

## 10. Scene composition — OPEN

```
8 working pipelines emit canonical assets:
   characters/  props/  textures/  audio/  ui/  vfx/  game_data/  dems/
   ↓
   ↓   ❌ NOTHING ASSEMBLES THESE INTO A GODOT SCENE
   ↓   (worldgen v1 + v2 archived 2026-05-07)
   ↓
world3/  ←  user's fresh Godot project (clean target)
```

The single biggest open question post-nuke. Two architectural options:

| Option | Lives at | Pro | Con |
|---|---|---|---|
| **Factory style** | `pipelines/scene_compose/` (new) | Re-usable across projects; matches existing pipeline shape; emits to `world/` + `godot_pack/` | More glue between pipeline and game project |
| **Game-project style** | `world3/pipeline/` | Owned by one game; faster iteration; emits in-place | Doesn't re-use across projects |

Until decided, the 8 working pipelines emit orphan assets that don't combine. **This is the highest-leverage decision in the project.**

Once decided, the pipeline will need to compose at minimum:
- Heightmap from `dems/` (or synthetic)
- Per-pixel biome label
- Per-biome texture set from `world/textures/library/`
- Scattered props from `world/props/library/` (with biome rules)
- Ambience from `audio/ambience/<biome>/`
- VFX hooks from `vfx/catalog/`
- HUD overlay from `ui/atlas.png`
- Game data records from `game_data/godot/`

See [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md) for the full gap analysis.

---

## Cross-cutting

### Validation
```powershell
python pipelines\_meta\link_validator.py     # cross-pipeline references (effect → audio → icon → record)
```

### Godot export
```powershell
python pipelines\godot_export\export_godot.py --pipeline <name> --in <library> --project <godot_project>
python pipelines\godot_export\screenshot_scenes.py --project <godot_project>
```

### HuggingFace surveillance
```powershell
python pipelines\_meta\hf_surveyor.py
```

### Image utilities
```powershell
python pipelines\_meta\depth_normal.py --in <img>.png
python pipelines\_meta\matting.py --in <img>.png
python pipelines\_meta\upscale.py --in <img>.png --scale 4   # Real-ESRGAN x4plus / SwinIR
```
