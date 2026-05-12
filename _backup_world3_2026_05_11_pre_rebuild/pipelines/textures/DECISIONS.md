# Texture Pipeline — Decisions Log

Architectural decisions that shaped the pipeline. Each entry explains what was
decided, what alternatives were considered, and why. "See also" links point to
the experiment evidence.

---

## Bake PBR maps at SR resolution before mipping (Phase B.2, 2026-05-07)

**Decision:** After super-resolving to the working resolution (2K/4K), re-derive
normal, AO, and roughness from the SR'd height+albedo rather than using the
SR'd versions of those maps.

**Alternatives considered:**
1. Use SR'd normal/AO/roughness directly (just stretch the 512-derived maps to 2K)
2. Re-generate all maps via SM/CHORD at 2K natively (much more expensive)
3. Bake only normal; SR AO and roughness (mixed approach)

**Why bake all three:**
- SR'd normal is geometrically wrong: ESRGAN misinterprets normal map RGB as
  photographic content and produces color interference artifacts (cyan/green
  smearing on rock edges). Re-baking from the 2048 height gives clean,
  geometrically-correct normals with sub-texel Sobel gradient accuracy.
- AO is a hemisphere integral — smoother and more physically accurate at higher
  resolution. Re-baking at 2048 gives tighter concavity detection with smoother
  falloff vs the stretched 512-derived version.
- SR'd roughness is hallucinated by Real-ESRGAN (it doesn't understand what
  roughness means). A blend with freshly-derived roughness from the 2048 albedo
  micro-luminance is more physically meaningful.

**Why not option 2 (native high-res generation):**
- SM/CHORD at 2K would require 8-10× the compute per material.
- For ground textures in a terrain renderer, SR+bake produces visually
  equivalent or better results at a fraction of the cost.

**Why not option 3 (bake only normal):**
- AO and roughness benefits are real and cheap to bake. No reason to skip them.
- All three maps take <1s combined to bake at 2048.

**See also:** `TEXTURE_RND.md` B.2 entry for measured A/B results.
`world3/docs/captures/phase_b/B2_bake_ab/` for visual evidence.
