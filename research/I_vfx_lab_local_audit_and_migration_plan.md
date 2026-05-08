# I - VFX Lab Local Audit And Migration Plan

Date: 2026-05-06  
Scope: `D:\spell lab` -> `D:\assets\vfx` migration, Godot 4.5 baked VFX pipeline  
Relation to prior research: builds on `research/C_vfx.md` and the local Spell Lab artifact inventory.

## Executive Recommendation

Do **not** do another broad physics-engine search first. The old Spell Lab is
already much deeper than the roadmap summary implies. `D:\spell lab\repo-lab`
contains working or artifact-producing demos for Newton, Taichi, Warp, PhiFlow,
JAX-MD, Genesis, MuJoCo, Brax, LiquidFun, PhysX, Mantaflow, SPlisHSPlasH, a
first-party sand lab, and first-party 2D fracture.

The next useful research/build project is a **migration from engine demo lab to
content VFX factory**:

```text
old: engine scenario -> backend artifact
new: effect.json -> bake -> normalize -> preview -> pack -> Godot export -> catalog
```

Keep the current engine disposition from `C_vfx.md`:

- Primary: **Taichi**, **LiquidFun**, **Newton/Warp**, **PhiFlow**.
- Secondary specialists: **SPlisHSPlasH**, **PhysX**, **Mantaflow/Blender**,
  first-party **2D Fracture**.
- Reference only: **Sandspiel**, **The Powder Toy**, **GPU-Falling-Sand-CA**,
  **DiffTaichi**, **Sailfish**, **Brax**, **MuJoCo**, **JAX-MD**, **Genesis** as
  narrow/experimental sources.

The key change is that engines are no longer the product. **Effects are the
product.**

## What Exists Locally

### Old Lab Root

`D:\spell lab`

Important subfolders:

- `repo-lab`: engine wrappers, demos, lab server, `labctl.py`.
- `spell-sandbox`: browser UI, artifact viewer, generated artifacts.
- `newton`: Newton install/output.
- `captures`: screenshots.

### Existing Engine Control Surface

`D:\spell lab\repo-lab\labctl.py`

Useful commands already documented in the old lab:

```powershell
python labctl.py list
python labctl.py context --format markdown
python labctl.py demo taichi warp phiflow jax-md mujoco
python labctl.py demo newton splishsplash liquidfun physx mantaflow sandspiel
python labctl.py index
python labctl.py audit
```

### Existing Artifact Index

`D:\spell lab\spell-sandbox\artifacts\index.json`

Current audit count: 23 artifact entries.

`D:\spell lab\spell-sandbox\artifacts\AUDIT.md` reports pass status for:

- `brax/force_curve_search`
- `fracture2d/shard_baker`
- `genesis/rubble_stack`
- `genesis/rune_shatter`
- `jax-md/swarm_field`
- `liquidfun/particle_splash`
- `mantaflow/wave_smoke_field`
- `mujoco/chain_impulse`
- `newton/mpm_granular`
- `phiflow/promoted_spell_fields`
- `phiflow/smoke_field`
- `physx/rubble_stack`
- `sand-lab/first_party_ca`
- six `spell_prototype/*` effects
- `splishsplash/dambreak`
- `taichi/sand_spell`
- `warp/blackhole_particles`
- `warp/spell_particle_forge`

This means the previous "engines untested" description is stale. The engines are
not production-ready, but many have real artifacts.

## Important Existing Artifact Families

### Particle / Flipbook Effects

Examples:

- `liquidfun/particle_splash`
- `splishsplash/dambreak`
- `warp/blackhole_particles`
- `warp/spell_particle_forge`
- `jax-md/swarm_field`
- `spell_prototype/arcane_shock_ring`
- `spell_prototype/blood_orbit`
- `spell_prototype/fireball_projectile`

Typical files:

- `manifest.json`
- `particles.json`
- `flipbook.png`
- `flipbook.json`
- `preview.svg`

Immediate Godot target:

- `AnimatedSprite2D` / sprite atlas for flipbook playback.
- `GPUParticles2D` or `MultiMeshInstance2D` for particle replay.
- CanvasItem shader overlay from Art Lab shader templates.

### Field / Flow Effects

Examples:

- `phiflow/smoke_field`
- `phiflow/promoted_spell_fields`
- `mantaflow/wave_smoke_field`
- `spell_prototype/gravity_lens_field`
- `spell_prototype/smoke_rift`

Typical files:

- `field.json`
- `velocity.json`
- `flipbook.png`
- `preview.svg`

Immediate Godot target:

- Flipbook if baked.
- Flowmap texture or sampled JSON-to-texture conversion.
- Shader-driven distortion, smoke advection, fog, magical field warping.

### Rigid / Fracture Effects

Examples:

- `fracture2d/shard_baker`
- `physx/rubble_stack`
- `genesis/rubble_stack`
- `genesis/rune_shatter`
- `spell_prototype/rune_shatter`
- `mujoco/chain_impulse`

Typical files:

- `bodies.json`
- `fragments.json`
- `preview.svg`

Immediate Godot target:

- `Polygon2D` shards from `fragments.json`.
- Transform timelines from `bodies.json`.
- Optional collision proxy generation.
- Replayed breakable props, shield shatters, ice plates, rubble bursts.

## Proposed New VFX Catalog Contract

Build under:

```text
D:\assets\vfx\
  catalog\
    spells\
    environment\
    projectiles\
    destruction\
    ambient\
  tools\
  bakers\
  godot\
  migrated_from_spell_lab\
```

Every VFX entry:

```text
vfx/catalog/<kind>/<effect_id>/
  effect.json
  manifest.json
  preview.png
  flipbook.png
  frames/
  particles.json
  field.json
  velocity.png
  fragments.json
  bodies.json
  godot/
    effect.tscn
    effect_material.tres
  notes.md
```

Canonical `effect.json`:

```json
{
  "id": "acid_splash_small",
  "kind": "spell",
  "phenomenon": "liquid",
  "school": "poison",
  "backend": "liquidfun",
  "duration_s": 1.2,
  "fps": 30,
  "bounds_px": [512, 512],
  "visual": {
    "palette": ["#b7ff4a", "#4ca51e", "#111b08"],
    "blend": "additive_or_alpha",
    "lighting": "unlit"
  },
  "outputs": ["flipbook", "particles", "godot_scene"],
  "gameplay_hooks": {
    "shape": "impact_splash",
    "damage_tags": ["poison"],
    "collision": "first_hit"
  }
}
```

`manifest.json` should be generated, not hand-authored. It records:

- source backend artifact path,
- command used,
- frame count/fps/bounds,
- exported files,
- QA metrics,
- Godot resource paths,
- warnings and limitations.

## Migration Tools To Build

### 1. `vfx_import_spell_lab.py`

Input:

```powershell
python vfx\tools\vfx_import_spell_lab.py `
  --artifact-root "D:\spell lab\spell-sandbox\artifacts" `
  --kind spells `
  --out D:\assets\vfx\catalog
```

Responsibilities:

- Read old `index.json`.
- Copy selected artifacts into new catalog shape.
- Normalize paths and names.
- Convert `preview.svg` to `preview.png` if needed.
- Preserve original `manifest.json` and `last_run.json`.
- Generate new `effect.json` stub.
- Write `migration_notes.md`.

Acceptance:

- Import at least 6 strong old prototype effects:
  - `fireball_projectile`
  - `smoke_rift`
  - `gravity_lens_field`
  - `rune_shatter`
  - `liquidfun/particle_splash`
  - `fracture2d/shard_baker`

### 2. `vfx_validate.py`

Responsibilities:

- Validate `effect.json`.
- Check required artifacts exist.
- Check flipbook dimensions and metadata match.
- Check JSON files are parseable and frame counts align.
- Warn on very large JSON payloads.
- Assign preliminary status: `usable`, `needs_godot_export`, `reference_only`,
  `broken`.

Acceptance:

- Runs over all migrated effects.
- Writes `vfx/catalog_index.json`.
- Produces a Markdown validation report.

### 3. `vfx_pack_flipbook.py`

If frames exist:

- Pack frames into atlas.
- Write atlas JSON.
- Generate preview contact sheet.

If only old `flipbook.png` exists:

- Validate metadata and copy.

Acceptance:

- Produces Godot-importable flipbook data for all particle/field effects.

### 4. `vfx_godot_export.py`

Targets:

- `AnimatedSprite2D` / `SpriteFrames` for flipbooks.
- `GPUParticles2D` presets for particle effects.
- `Polygon2D` shard scene for fracture effects.
- `ShaderMaterial` hook for field/flow effects.

Acceptance:

- One migrated flipbook effect can be opened in Godot.
- One fracture effect exports polygons/transforms.
- One field effect exports a texture/metadata usable by a shader.

### 5. `vfx_gallery.py`

Generate:

`D:\assets\vfx\index.html`

Needs:

- cards grouped by kind/phenomenon/backend/status,
- preview image or flipbook,
- links to JSON artifacts,
- warnings,
- "Godot export exists" badge.

Acceptance:

- User can visually browse migrated VFX without opening the old Spell Lab UI.

## Backend Disposition For The New Catalog

| Backend | New role | Keep? | Why |
|---|---|---:|---|
| First-party shader lab | live effect shader | yes | Mainline for cheap runtime spell visuals |
| LiquidFun | 2D fluid timing baker | yes | Best match for blood/goo/acid/water splashes |
| Taichi | custom material/grid baker | yes | Best path to owned sand/fire/heat/mask simulation |
| PhiFlow | smoke/field/flowmap baker | yes | Best for fields and velocity maps |
| Warp/Newton | high-end particle/material reference | yes | Strong GPU/offline reference lane |
| First-party 2D fracture | destruction/shards | yes | Already export-friendly |
| SPlisHSPlasH | water reference | secondary | High-quality water, heavy |
| PhysX/Genesis | rigid/debris reference | secondary | Useful body transforms, not daily driver |
| Mantaflow/Blender | smoke/fire reference | secondary | Strong if Blender batch route is stable |
| JAX-MD/Brax/MuJoCo | force/constraint reference | narrow | Useful ideas, not pipeline core |
| Sandspiel/Powder Toy/GPU CA | behavior reference | reference | Study rules, keep code license-safe |
| Sailfish/DiffTaichi/VoronoiShatter | historical/reference | mostly no | Learn from, do not build around |

## Phenomenon Routing Table

| Phenomenon | Preferred route | Output |
|---|---|---|
| Projectile trail | shader lab + Warp particles | flipbook + particle JSON + `.gdshader` |
| Fireball impact | shader lab + Taichi heat/sparks | flipbook + particles |
| Smoke rift | PhiFlow / Mantaflow | field/velocity + flipbook |
| Acid splash | LiquidFun | particles + flipbook |
| Water splash | LiquidFun first, SPlisHSPlasH for high-quality reference | particles + foam/mask |
| Sand/lava/oil | Taichi or first-party CA | field + flipbook |
| Shatter/ice/glass | first-party 2D fracture | fragments + transform timeline |
| Rubble/debris | PhysX/Genesis/Newton reference | bodies timeline |
| Aura/portal/shield | shader lab first | `.gdshader` + flipbook preview |
| Fog/wind/distortion | PhiFlow field + shader lab | velocity texture + shader |

## First Implementation Slice

Build the migration tooling before adding new simulation features.

1. Create `D:\assets\vfx\catalog`.
2. Implement `vfx_import_spell_lab.py`.
3. Import 6 representative effects.
4. Implement `vfx_validate.py`.
5. Implement `vfx_gallery.py`.
6. Export one flipbook effect and one fracture effect to Godot.

This gives immediate value from the old lab and prevents a third parallel VFX
system from forming.

## Test Plan

### Test A - Fireball Prototype Migration

Input:

`D:\spell lab\spell-sandbox\artifacts\spell_prototype\fireball_projectile`

Success:

- Catalog entry exists under `D:\assets\vfx\catalog\spells\fireball_projectile`.
- `effect.json`, `manifest.json`, `flipbook.png`, `particles.json`, and preview
  exist.
- Gallery plays or displays it.
- Godot export creates a simple scene.

### Test B - LiquidFun Splash Migration

Input:

`D:\spell lab\spell-sandbox\artifacts\liquidfun\particle_splash`

Success:

- Preserves particle metadata and material notes.
- Exports flipbook.
- Tags phenomenon as `liquid`.

### Test C - Fracture Shard Migration

Input:

`D:\spell lab\spell-sandbox\artifacts\fracture2d\shard_baker`

Success:

- Preserves `fragments.json` and `bodies.json`.
- Godot export creates `Polygon2D` or a documented import recipe.

### Test D - Smoke Field Migration

Input:

`D:\spell lab\spell-sandbox\artifacts\phiflow\smoke_field`

Success:

- Preserves `field.json` and `velocity.json`.
- Produces a preview and shader-use note.

## Risks

- Old artifact JSON files are large. The new catalog should avoid duplicating
  huge files unnecessarily if hardlinks or copy-on-demand are acceptable.
- Some previews are SVG, not PNG. HTML can display SVG, but Godot previews may
  need raster conversion.
- Old artifacts are engine-demo shaped, not gameplay-effect shaped. `effect.json`
  stubs need human/LLM cleanup.
- Godot export for particle timelines may need simplification; replaying millions
  of particle points directly is not practical.
- Commercial VFX tools like EmberGen/LiquiGen/IlluGen may produce higher quality,
  but they are GUI/subscription and should remain optional references until a
  clean automation path exists.

## Sources

- Local: `D:\spell lab\repo-lab\README.md`
- Local: `D:\spell lab\repo-lab\ENGINE_ROADMAP.md`
- Local: `D:\spell lab\spell-sandbox\artifacts\AUDIT.md`
- Local: `D:\spell lab\spell-sandbox\artifacts\index.json`
- Prior report: `D:\assets\research\C_vfx.md`
- Godot 4.5 particles: https://docs.godotengine.org/en/4.5/tutorials/2d/particle_systems_2d.html
- Godot 4.5 particle shaders: https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/particle_shader.html
- NVIDIA Warp: https://nvidia.github.io/warp/
- Newton physics: https://developer.nvidia.com/newton-physics
- Taichi: https://docs.taichi-lang.org/
- LiquidFun: https://google.github.io/liquidfun/index.html
- SPlisHSPlasH: https://splishsplash.physics-simulation.org/
- PhiFlow: https://github.com/tum-pbs/PhiFlow
