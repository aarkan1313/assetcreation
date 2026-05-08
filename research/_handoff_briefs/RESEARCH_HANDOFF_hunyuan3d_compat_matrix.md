# Research handoff — Hunyuan3D-2.1 / cu128 / sm_120 compatibility matrix

**Status:** active brief. Spawn this as a research agent in the background while the install proceeds. The agent's job is to stay one step ahead of the build — when the build hits a wall, the agent should already have the matrix entry that explains the wall.

## Goal

Maintain a **living compatibility matrix** of every "X works with Y on RTX 5090 / cu128 / sm_120" data point relevant to getting Hunyuan3D-2.1 + `custom_rasterizer` + `mesh_inpaint_processor` + PBR texture baking running on Windows 11 / Python 3.12. The matrix is the artifact — not a narrative report.

## Why this brief exists

The user has tried Hunyuan3D-2.1 multiple times and failed, almost certainly at the `custom_rasterizer` build step (the only `custom_rasterizer` wheel published is for `torch260.cuda126`; on cu128 / sm_120 it must be source-built with MSVC + CUDA Toolkit 12.x + `TORCH_CUDA_ARCH_LIST="12.0"`). The dependency chain is brittle and version-sensitive across torch / CUDA / nvcc / Python / kijai-wrapper-commit / VS-Build-Tools. Without a compatibility matrix we will burn hours on a rebuild for every version drift.

## Output format

Write findings to `D:/assets/research/hunyuan3d_compat_matrix.md` as a **table-first document**. Sections:

1. **Working configurations** — every confirmed "this combination builds + runs PBR baking end-to-end on a 5090."
2. **Known-broken configurations** — version pairs reported broken with the specific error signature and where it surfaced (kijai issue, comfy thread, reddit, blog).
3. **Fix recipes** — for known-broken combos, the patch / pin / env-var that resolves it.
4. **Open questions** — things you couldn't resolve in this pass.

For each row: source URL, date observed, GPU model, OS, Python, torch (version + cuXXX), CUDA toolkit, MSVC version, kijai commit (or `main@<sha>`), visualbruno commit, custom_rasterizer build result, mesh_inpaint_processor build result, end-to-end PBR bake result, single-line note.

## Specific questions to answer

1. **What `torch` version range is currently producing working `custom_rasterizer` builds on cu128?** Nightly? A specific stable? Pin to `torch==2.7.0+cu128` or similar?
2. **What CUDA toolkit version is the practical sweet spot?** The user's machine has nvcc 13.0 (`cuda_13.0.r13.0/compiler.36424714_0`, build Aug 20 2025). The kijai docs and ethanstoner guide reference 12.8. Does cu13 toolkit work to build extensions for cu128 torch? (PyTorch + CUDA toolkit minor-version mismatch tolerance.)
3. **Is `custom_rasterizer` actually required for PBR baking, or only for the rasterized normal map step?** If we can run the kijai workflow with a `custom_rasterizer = None` fallback and still get usable diffuse/metallic/roughness via multiview baking, the build risk drops dramatically.
4. **Has anyone published a prebuilt `custom_rasterizer` wheel for cu128 / sm_120 / cp312** — github releases, comfy-deps repos, civitai mirrors, anywhere? Check kijai's releases page, recent issues, the visualbruno fork releases, and comfy-deploy / comfy-org wheels.
5. **What are the exact `requirements.txt` entries to STRIP** before `pip install -r` to prevent torch downgrade? The agent's prior pass identified `torch` itself; check for `torch>=`, `torchvision`, `torchaudio`, `xformers`, `flash-attn`, `triton`. List every line that needs to go in both `ComfyUI-Hunyuan3DWrapper/requirements.txt` and `ComfyUI-Hunyuan3d-2-1/requirements.txt`.
6. **What's the `mesh_inpaint_processor` fallback behavior when not built?** Is the wrapper graceful (worse infill, still produces texture) or does the workflow fail outright?
7. **MSVC version pinning** — does `cl.exe` from VS 2022 17.10 work, or do we need 17.6 / 17.8? Some torch C++ extensions are picky about MSVC ABI changes.
8. **VS Build Tools standalone vs full Visual Studio** — does the rasterizer build need the IDE or are Build Tools 2022 sufficient? (Affects how heavy the install is if MSVC isn't already present.)
9. **`hy3dpaint/` model layout** — kijai expects a specific folder structure under `models/checkpoints/Hunyuan3D-2.1/`. Confirm exact layout (whether `hunyuan3d-paintpbr-v2-1/` is at the top of the checkpoint dir or nested deeper).
10. **`Hunyuan3D-Omni` and `Hunyuan3D-Part`** — same kijai wrapper or different node packs? (Lower priority; we're targeting plain 2.1 first.)
11. **`HunyuanWorld-Mirror`** (Oct 2025 release) — what is it, when would we use it for prop work, does it ride the same custom_rasterizer? (Lower priority.)

## Stay-current loop

Re-run this research roughly every 1-2 weeks while we're depending on Hunyuan3D, OR when the build hits a wall the matrix doesn't cover. The kijai repo gets PRs frequently; new wheels and fixes appear in issues comments. Keep the matrix file's `last_updated` date current.

## Sources to mine

Primary:
- https://github.com/kijai/ComfyUI-Hunyuan3DWrapper — issues, releases, recent commits
- https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1 — same
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1 — Tencent's own issues for ground truth
- https://github.com/ethanstoner/Hunyuan3D-2.1-Complete-Install-Guide — the only step-by-step we know of
- https://github.com/comfyanonymous/ComfyUI/discussions/6643 — Blackwell / cu128 thread

Secondary:
- HuggingFace `tencent/Hunyuan3D-2.1`, `tencent/Hunyuan3D-Omni`, `tencent/Hunyuan3D-Part`, `tencent/HunyuanWorld-Mirror`
- r/StableDiffusion, r/comfyui — search for "custom_rasterizer 5090" / "custom_rasterizer cu128" / "Hunyuan3D 5090"
- civitai articles tagged Hunyuan3D
- ComfyUI-Manager's deps repo for any wheel mirrors

## Working notes

When you find a new working configuration, append it to the matrix even if it conflicts with our current install — we may want to roll back to it. When you find a fix recipe, copy the exact shell incantation, not a paraphrase.

## Owner / lifecycle

Owned by whoever's actively building Hunyuan3D on the factory. Archive the file to `_archive/research/hunyuan3d_compat_matrix.md` once we have a stable working install for ≥30 days.
