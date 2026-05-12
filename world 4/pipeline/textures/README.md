# W4 texture pipeline (code-side reference)

For the user-facing feature doc see [docs/features/textures.md](../../docs/features/textures.md).
For why-the-architecture see [docs/plans/TEXTURE_PIPELINE_FINDINGS_2026_05_12.md](../../docs/plans/TEXTURE_PIPELINE_FINDINGS_2026_05_12.md).

This file is the quick-reference for someone editing the `tx_*` modules.

## Modules

| Module | Role | Hot path? |
|---|---|---|
| `tx_pipeline.py`        | Orchestrator. Holds `PipelineSettings` + `run_pipeline()`. | yes |
| `tx_seamless.py`        | FLUX 4-pass tileable generation. ComfyUI subprocess. | yes |
| `tx_variant_select.py`  | Generate N variants, score by composite, keep all. | yes |
| `tx_pbr_hybrid.py`      | **DEFAULT** PBR backend. SM tileable + derive PBR. | yes |
| `tx_pbr_derive.py`      | Alt backend: heuristic-only. Fast. No seam fix. | opt-in |
| `tx_pbr_sm.py`          | Alt backend: pure StableMaterials. | opt-in |
| `tx_seam_repair.py`     | PatchMatch over offset cross. Fallback. | rarely |
| `tx_qa.py`              | 4 gating + 2 advisory metrics. | yes |
| `experiment_audit_matrix.py` | 16-combo audit. Run-history; reproducibility. | no |

## Conventions

- **Output map filenames** are canonical: `albedo.png / normal.png /
  roughness.png / ao.png / height.png / metallic.png` (no `<id>_`
  prefix). All `tx_*` backends write this layout.
- **`out_dir` is owned by the caller.** The pipeline writes into it
  but doesn't clean up siblings. Caller is responsible for the
  biome/slot/idx layout if they want one.
- **Backends are interchangeable** behind a single signature:
  `derive_pbr(input_albedo: Path, out_dir: Path, *, category: str, ...) -> dict`
- **All settings live in `PipelineSettings`.** Don't sneak hidden
  defaults into helper functions; if it's a knob, surface it.

## Adding a new PBR backend

1. New file `tx_pbr_<name>.py` exposing `derive_pbr(input_albedo, out_dir, *, category, **opts) -> dict`.
2. Write `albedo.png + normal.png + roughness.png + ao.png + height.png + metallic.png` into `out_dir`.
3. Return a log dict including at minimum `{"backend": "tx_pbr_<name>", "maps": [...]}`.
4. Wire it into `tx_pipeline.py`'s Stage 3 dispatcher.
5. Add `<name>` to the `--pbr-backend` choices in the CLI.

## Adding a new QA check

1. Write a pure function in `tx_qa.py`: `def <name>(im: np.ndarray, threshold: float) -> dict`.
2. Decide: gating or advisory? Gating contributes to A-D grade.
3. If gating, add to `grade_checks` tuple inside `qa_albedo()` and update the grade thresholds.
4. If advisory, return it in the `advisory:` block of the report.
5. Add a per-category override in `W4_CATEGORY_OVERRIDES` if the check
   needs different thresholds per material class.

## Adding a new biome

1. Create `pipeline/biomes/<biome>.yaml` (copy alpine.yaml).
2. Per slot, set `category` to one of {Snow, Sand, Mixed, Rock, Concrete,
   Foliage, Ground, ...}. Drives QA thresholds in `tx_qa`.
3. Write candidate prompts under each slot's `candidates:` list.
4. Run `python pipeline/diversity_run.py --biome <biome>`.

## Common pitfalls

- **Image array dtype mismatches.** Upstream QA helpers expect float32
  normalized to 0..1. `tx_qa.qa_albedo` does the conversion once at
  entry; helpers that take uint8 (e.g. PIL operations in `tile_4x4`)
  convert as needed. Don't pass raw 0..255 floats to upstream's
  `edge_continuity` etc — you'll get MSE values 65000× too large.
- **`Flux2Scheduler` silently ignores `denoise`.** It's not "running
  at denoise=1.0" — it runs klein's distilled schedule, which is a
  different computation entirely. If you want to actually vary
  denoise, use `BasicScheduler` (but be aware that hammers the
  offset cross at denoise=1.0 — see findings doc).
- **SM is the seam closer.** Don't remove SM from the hybrid backend
  thinking derive_pbr_v2 alone is enough. We have the data showing
  it isn't. (`old_drift` audit run: midline ratio 22 without SM, 1.3
  with it.)

## Running the audit experiment again

```bash
python pipeline/textures/experiment_audit_matrix.py
```

Generates 16 combos × `windpack` prompt. Already-completed combos
detected and skipped. Outputs to
`the world 4/candidates/_pipeline_review/audit/`. Builds a comparison
sheet. Kept for reproducibility — historical record of how the audit's
predictions diverged from reality.
