# Handoff: M1 OpenTopo material catalog migration -> OpenTopo worker (2026-05-08)

## Status

`DROPPED`

Superseded 2026-05-08 by user direction to keep worker and orchestrator work
consolidated in this chat for now. The orchestrator executed this migration
directly; see `world3/materials/catalog.json`.

## Task

Migrate the six finished OpenTopo Guadalupe Cypress material classes into the
new world3 material catalog. This is M1 prep work: the catalog must contain
real-source material ids before M2 transition pairs can reference them and
before M4 can unify `terrain_blend` with `terrain_hex_detail`.

## Inputs

- Catalog rules: `world3/materials/CATALOG.md`
- Machine-readable catalog to edit: `world3/materials/catalog.json`
- State doc context: `world3/docs/WORLD3_STATE_2026_05_08.md`, sections 2B,
  2C, and 4/M1
- Finished material index:
  `world3/opentopo/processed/textures/Guadalupe_Cypress_finished_materials_index.json`
- Your workflow docs:
  `world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md`
  `world3/docs/OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md`
  `world3/docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md`

Material ids to migrate exactly:

```text
bare_soil
bright_rock
dry_wash
rocky_slope
scrub_dense
scrub_sparse
```

## Deliverables

- [ ] Append one catalog entry for each of the six ids above under
      `materials` in `world3/materials/catalog.json`.
- [ ] Set `source` to `real` for all six.
- [ ] Set `shader_binding` to `terrain_hex_detail` for all six. This records
      current reality; M4 will unify shaders later.
- [ ] Set `scale_m_per_repeat` to the real material repeat. Use `64.0` unless
      the class manifest contradicts that.
- [ ] Fill `provenance` with enough data to audit the asset:
      Guadalupe Cypress source, source manifest path, material class, source
      policy, operations, edge metrics, and key shader/image settings from the
      finished-material index.
- [ ] Fill `pbr_maps` using repo-relative paths from the index outputs:
      albedo, normal, roughness, height, ao, and the detail maps if useful as
      additional fields.
- [ ] Fill `color_family` with a practical transition-planning family for each
      class.
- [ ] Fill `validated_views` from your current review evidence. Use
      `needs_review` where the evidence is incomplete.
- [ ] Remove the six migrated ids from `pending_worker_materials`.
- [ ] Reply with the committed paths and any uncertainties.

## Accept Criteria

- `world3/materials/catalog.json` parses as JSON.
- Each of the six ids appears exactly once under `materials`.
- All non-null `pbr_maps` paths exist.
- The six entries use `source=real` and `shader_binding=terrain_hex_detail`.
- Provenance makes clear these are source-real soft composites with derived
  detail, not procedural repaint products and not geography-preserved place
  textures.
- No runtime, shader, or transition-tool changes are included in this handoff.

## Out of Scope

- Do not build transition strips yet. That is M2 after this migration lands.
- Do not modify `terrain_blend.gdshader`, `terrain_hex_detail.gdshader`, or
  scene wiring.
- Do not rename the six material ids.
- Do not redesign the catalog schema. Add fields only when needed to preserve
  OpenTopo provenance without breaking the existing procedural entries.
- Do not move or regenerate texture assets.

## Deadline

No hard deadline. This is the next worker task; start when you pick this up.

## Pointers for the worker

The catalog is intentionally tracking workflow/QA quality, not just final
shipping content. Use `asset_status = pipeline_validation` unless you have a
better status already established in your docs.

`scale_m_per_repeat` should line up with the current finished material shader
setting. The index reports `world_uv_scale = 0.015625`, which implies a 64m
repeat.

Keep paths repo-relative where possible, matching the procedural entries.

---

## Worker reply

[Worker fills in when responding]

### What landed

- (commit hash) - short description

### Surprises / deviations

What did not go to plan, or things the orchestrator should know.

### Things I could not do

If any deliverables are not met, list why.

### Next-step suggestions

Optional. If you saw an obvious follow-up, name it.

---

## Orchestrator review (after worker reply)

[Orchestrator fills in]

### Verdict

`ACCEPTED` | `REVISIONS REQUESTED` | `DONE`

### Notes

What was integrated, what was deferred, what surprised the orchestrator.

### Integration commit

(orchestrator integration commit hash)
