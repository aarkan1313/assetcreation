"""W4 texture pipeline.

A from-scratch rebuild of the texture generation pipeline, owned by W4.
The shared infra at D:/assets/pipelines/textures/ stays untouched; this
package is a clean reimplementation that fixes the bugs and design
issues found in the 2026-05-12 audit (see
docs/plans/TEXTURE_PIPELINE_AUDIT_2026_05_12.md).

Modules (build order):
  tx_seamless.py        FLUX 4-pass generation, honor-denoise fixed
  tx_variant_select.py  Composite-score variant ranking, keeps all
  tx_pbr_derive.py      Default heuristic PBR (consistent with albedo)
  tx_pbr_sm.py          Opt-in StableMaterials backend
  tx_qa.py              QA + 3 new W4-specific checks
  tx_pipeline.py        Orchestrator (replaces aaa_texture.py for W4)

Driver:
  pipeline/diversity_run.py invokes tx_pipeline.py.
"""
