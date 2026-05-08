# Hunyuan3D-2.1 / cu128 / sm_120 compatibility matrix

`last_updated: 2026-05-06`
`target_machine: RTX 5090 (sm_120) / Win11 / Python 3.12.10 / nvcc 13.0 (CUDA Toolkit 13.0, Aug 20 2025 build)`
`scope: kijai ComfyUI-Hunyuan3DWrapper + visualbruno ComfyUI-Hunyuan3d-2-1 + Tencent Hunyuan3D-2.1 source — custom_rasterizer + mesh_inpaint_processor + PBR baking pipeline`

---

## TL;DR — read this first before building anything

**HOT FINDING (2026-03-10).** Kijai now ships a prebuilt `custom_rasterizer` wheel in the wrapper repo at:
`hy3dgen/texgen/custom_rasterizer/dist/custom_rasterizer-0.1.0+torch2100.cuda130-cp312-cp312-win_amd64.whl`
Source: kijai commit [`7fbc376`](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/commit/7fbc376) titled "Add torch 2.10+cu130 wheel for custom rasterizer".
**This wheel is for torch 2.10 + cu130 / cp312 / win_amd64 — it is NOT a cu128 wheel.** It will refuse to install on torch 2.7.x / 2.8.x / cu128 (`is not a supported wheel on this platform`, see issue [#181](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/181)). It WILL install if you upgrade to torch 2.10 + cu130 nightly.

**The other prebuilt wheel** (still shipped alongside): `custom_rasterizer-0.1.0+torch260.cuda126-cp312-cp312-win_amd64.whl` for torch 2.6 + cu126. Useless on cu128 unless you downgrade.

**No cu128-tagged wheel exists anywhere as of 2026-05-06** — not in kijai releases (releases page is empty), not in visualbruno's `dist/` folder (only generic torch-version-untagged wheels there for cp310/cp311/cp312 win_amd64), not in YanWenKun WinPortable releases, not in wildminder's AI-windows-whl mirror.

**Three viable install paths** ranked by build-pain:
1. **Easiest path — switch to torch 2.10 + cu130 nightly.** Use kijai's prebuilt cu130 wheel directly. Your installed nvcc 13.0 matches. No source build needed. Risk: torch 2.10 stable may not exist yet; nightly cu130 is the lane. Verify with `pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu130`.
2. **Compromise path — torch 2.7 / 2.8 + cu128 + source build.** The user is on this path. Requires MSVC + CUDA Toolkit 12.8 (sidecar — your nvcc 13.0 alone is probably fine for cu130 but iffy for cu128 extensions; install CUDA 12.8 toolkit alongside) + `set TORCH_CUDA_ARCH_LIST=12.0` + `set DISTUTILS_USE_SDK=1`. See row WB-01 below.
3. **Fallback path — Tencent Docker image with CUDA 12.8.0-devel.** Source build inside the container with `TORCH_CUDA_ARCH_LIST="...;12.0"` and `CUDA_NVCC_FLAGS="-allow-unsupported-compiler"`. Confirmed-working recipe from Tencent issue [#122](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/issues/122).

**Critical pip hygiene before `pip install -r requirements.txt`:**
- STRIP `torch`, `torchvision`, `torchaudio` from BOTH `ComfyUI-Hunyuan3DWrapper/requirements.txt` AND `ComfyUI-Hunyuan3d-2-1/requirements.txt`. Pip will silently downgrade your nightly cu128/cu130 build to stable cu126 otherwise (confirmed in comfy [#6643](https://github.com/comfyanonymous/ComfyUI/discussions/6643)).
- Do NOT install `xformers` from PyPI in this env — it pins torch <= stable and will undo your nightly install. Use a Windows-cu128-prebuilt xformers (e.g. `czmahi/xformers-windows-torch2.8-cu128-py312`) only if a node hard-requires it.
- `flash-attn` and `triton` likewise need cu128/cu130-matched wheels — not from PyPI.

---

## 1. Working configurations

| ID | Date | Source | GPU | OS | Python | torch | CUDA tk | nvcc | MSVC | kijai sha | visualbruno sha | custom_rasterizer | mesh_inpaint | PBR bake | Note |
|----|------|--------|-----|----|--------|-------|---------|------|------|-----------|-----------------|-------------------|--------------|----------|------|
| WK-01 | 2026-03-10 | [kijai 7fbc376](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/commit/7fbc376) | unspecified | Win11 | 3.12 | 2.10.0+cu130 | 13.0 | 13.0 | VS2022 v143 | 7fbc376+ | n/a | prebuilt wheel | n/a | n/a | Wheel ships in repo: `custom_rasterizer-0.1.0+torch2100.cuda130-cp312-cp312-win_amd64.whl`. Maintainer-published, no end-to-end PBR confirmation in commit msg. |
| WK-02 | 2025-08-25 | [YanWenKun WinPortable v4-cu129](https://github.com/YanWenKun/Hunyuan3D-2-WinPortable/releases) | RTX 5090 | Win11 | 3.12.11 | 2.8.0 | 12.9 | 12.9 | n/a (portable) | bundled | n/a | bundled (cu129) | bundled | end-to-end works (per release notes) | Portable bundle — explicit Blackwell support claim. CUDA 12.9 binaries, not cu128. |
| WK-03 | 2025-06-15 | [kijai cbe2837 + ethanstoner guide](https://github.com/ethanstoner/Hunyuan3D-2.1-Complete-Install-Guide) | RTX 30/40 | Win11 | 3.12 | 2.6.0+cu126 | 12.6 | 12.6 | VS2022 v143 | cbe2837 | n/a | prebuilt `custom_rasterizer-0.1.0+torch260.cuda126-cp312-cp312-win_amd64.whl` | prebuilt | confirmed working | Pre-Blackwell era reference. KJNodes pinned to 37a0973. opencv-contrib-python required (ximgproc). |
| WK-04 | 2025-08-07 | [visualbruno fork main](https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1) | unspecified Ampere+ | Win11 | 3.12 | >=2.6.0+cu126 | 12.6 | 12.6 | VS2022 | n/a | 9d7ef32 | prebuilt `custom_rasterizer-0.1-cp312-cp312-win_amd64.whl` (no torch tag) | prebuilt | works on cu126 | Generic-tagged wheel — installs on any torch but kernel must match runtime; do NOT use on cu128/cu130 (silent ABI break possible). |
| WK-05 | 2026-02-27 | [visualbruno 9d52415](https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1) | unspecified | Linux/Win | 3.12 | unspecified | 12.x | n/a | n/a | n/a | 9d52415 | source build with C++20 flags | source build | n/a | "Added compile options for C++20" — needed for newer torch headers. |
| WK-06 | 2026-03-16 | [kijai 2609efa](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/commit/2609efa) | unspecified | Linux | 3.12 | 2.10+cu130 | 13.0 | 13.0 | gcc | 2609efa | n/a | source build (Linux nvcc args fixed) | n/a | n/a | Setup.py now gates `/Zc:preprocessor` on `os.name=='nt'`. Linux build works without that flag. |
| WK-07 | unknown | Tencent issue [#122](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/issues/122) | RTX 5090 | Linux Docker (`nvidia/cuda:12.8.0-devel-ubuntu22.04`) | 3.10/3.12 | cu128 (pip index) | 12.8 | 12.8 | gcc | n/a | upstream | source build with `TORCH_CUDA_ARCH_LIST="6.0;6.1;7.0;7.5;8.0;8.6;8.9;9.0;12.0"` + `CUDA_NVCC_FLAGS="-allow-unsupported-compiler"` | source build | confirmed PBR | The only confirmed-running 5090 + cu128 + custom_rasterizer recipe. Containerized — port to Win11 by reproducing env vars. |

## 2. Known-broken configurations

| ID | Date | Source | GPU | OS | Python | torch | CUDA tk | nvcc | MSVC | Failure | Error signature |
|----|------|--------|-----|----|--------|-------|---------|------|------|---------|-----------------|
| BK-01 | 2026-03-10 | [kijai #204](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/204) | RTX 4060 | Win10/11 | 3.10 | 2.9.1+cu130 | 13.0 | 13.0 | MSVC 2022 | source build of custom_rasterizer | `error C2872: 'std': ambiguous symbol` in `torch/include/torch/csrc/dynamo/compiled_autograd.h:1134` |
| BK-02 | 2026-03-03 | [kijai #203](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/203) | RTX Pro Blackwell 5000 | Win11 | 3.13 | 2.1.x | 13.0 | 13.0 | MSVC 2022 | source build | C++ namespace conflict, `error C2872: 'std': ambiguous symbol` (same root cause as BK-01) |
| BK-03 | 2026-02-20 | [kijai #201](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/201) | RX 9060XT (RDNA4 gfx1200) | Win11 ROCm | unspec | ROCm torch | n/a | n/a | n/a | runtime import | `No module named 'custom_rasterizer'` — wheel is CUDA-only, no ROCm path |
| BK-04 | 2026-02 | [kijai #181](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/181) | unspec | Win11 | 3.13.6 | 2.8.0+cu129 | 12.9 | n/a | n/a | wheel install | `ERROR: custom_rasterizer-0.1.0+torch260.cuda126-cp312-cp312-win_amd64.whl is not a supported wheel on this platform` — cp312 wheel rejected on Python 3.13 |
| BK-05 | 2026 | [kijai #206](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/206) | unspec | Win11 | 3.12 | unspec | unspec | n/a | possibly missing VC++ runtime | runtime import | `ImportError: DLL load failed while importing custom_rasterizer_kernel: The specified module could not be found` |
| BK-06 | 2026 | [kijai #207](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/207) | unspec | unspec | unspec | unspec | n/a | n/a | n/a | runtime AttributeError | `module 'utils3d.torch' has no attribute 'intrinsics_from_fov_xy'` — utils3d API drift |
| BK-07 | 2025-03 | [HF tencent/Hunyuan3D-2 disc 38](https://huggingface.co/tencent/Hunyuan3D-2/discussions/38) | RTX 5070/5080 | Win | 3.13.2 | 2.8.0.dev cu128 | 12.8 | n/a | n/a | wheel install | `custom_rasterizer-0.1-cp312-cp312-win_amd64.whl is not a supported wheel on this platform` — Python 3.13 trying to load cp312 wheel |
| BK-08 | 2025+ | comfy [#6643](https://github.com/comfyanonymous/ComfyUI/discussions/6643) | RTX 50-series | any | any | any | any | n/a | n/a | xformers install | xformers from PyPI force-downgrades torch nightly → stable cu126; your cu128 install vanishes silently |
| BK-09 | 2025-04 | YanWenKun WinPortable [#11](https://github.com/YanWenKun/Hunyuan3D-2-WinPortable/issues/11) | unspec | Win | unspec | unspec | n/a | not installed | not installed | source build | `Compilation of custom_rasterizer failed with [WinError 2]` — missing nvcc / MSVC on PATH |
| BK-10 | 2025+ | comfy [#3793](https://github.com/comfyanonymous/ComfyUI/issues/3793) | any | any | 3.12 | nightly cu128 | n/a | n/a | n/a | requirements.txt clobber | bulk `pip install -r` overwrites torch nightly with PyPI stable; `xformers`, `flash-attn`, `triton` all guilty |
| BK-11 | 2025-08 | Dao-AILab flash-attention [#1885](https://github.com/Dao-AILab/flash-attention/issues/1885) | any | Win | 3.12 | 2.7.0+cu128 | 12.8 | n/a | MSVC | `flash-attn` 2.8.3 source build | wheel build fails — use prebuilt from `lldacing/flash-attention-windows-wheel` instead |
| BK-12 | 2025-09 | pytorch [#166120](https://github.com/pytorch/pytorch/issues/166120) | any | Win | any | 2.9.0+cu128 | 12.8 | 12.8 | n/a | C++ extension build | `Unknown CUDA arch 10.1` when arch flag autodetect tries `sm_101` (now sm_110 in CUDA 13). Set `TORCH_CUDA_ARCH_LIST` explicitly. |
| BK-13 | 2025+ | pytorch [#172807](https://github.com/pytorch/pytorch/issues/172807) | RTX 5090 | any | any | any | any | n/a | n/a | NVFP4 / block-scaled MMA | Auto-detected arch flag drops `a` suffix: `sm_120a → sm_120`. Breaks Blackwell NVFP4 / CUTLASS block-scale. Set `TORCH_CUDA_ARCH_LIST="12.0a"` if you need NVFP4 (rasterizer doesn't). |
| BK-14 | 2025+ | facebookresearch detectron2 [#5503](https://github.com/facebookresearch/Detectron2/issues/5503) | any | any | any | 2.9.1 | 13.0 | 13.0 | n/a | C++ extension build with system CUDA 13 + torch cu128 | toolkit/torch CUDA-minor mismatch breaks build. Same class of failure custom_rasterizer hits on the user's machine. |
| BK-15 | 2025+ | comfy [#10143](https://github.com/comfyanonymous/ComfyUI/issues/10143) | any | Linux | 3.12 | nightly cu130 | 13.0 | n/a | n/a | xformers install | xformers wheel pins torch <=2.8 — incompatible with cu130 nightly |

## 3. Fix recipes

| ID | Symptom | Fix |
|----|---------|-----|
| FR-01 | `error C2872: 'std': ambiguous symbol` (BK-01, BK-02) building custom_rasterizer with torch 2.9+ on Windows | Edit `<env>/Lib/site-packages/torch/include/torch/csrc/dynamo/compiled_autograd.h` — comment out the `::std::string` type-handling block around line 1134-1136. Ugly but unblocks the build. (Reported in [#204](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/204).) |
| FR-02 | Wheel rejected — wrong Python tag (BK-04, BK-07) | Use Python 3.12 (cp312) — do NOT use 3.13. The wrapper's cp312 wheel will not load on cp313 even if torch matches. |
| FR-03 | `DLL load failed while importing custom_rasterizer_kernel` (BK-05) | Install Microsoft Visual C++ Redistributable 2015-2022 (latest x64). Verify by running the wheel's `.pyd` through Dependencies.exe — usually missing `MSVCP140.dll` or `VCRUNTIME140_1.dll`. Also ensure `import torch` runs before `import custom_rasterizer_kernel` (the wrapper does this in [977213](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/commit/977213)). |
| FR-04 | utils3d API drift `intrinsics_from_fov_xy` missing (BK-06) | Pin `utils3d` to a known-good version, or edit `ComfyUI-Hunyuan3DWrapper/utils.py` line 116 to call `intrinsics_from_fov` with adjusted params. Track upstream fix. |
| FR-05 | Source build of custom_rasterizer on Win + cu128 + sm_120 | Open "x64 Native Tools Command Prompt for VS 2022", then: `set DISTUTILS_USE_SDK=1` + `set TORCH_CUDA_ARCH_LIST=12.0` + `set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8` + `cd hy3dgen\texgen\custom_rasterizer` + `python setup.py bdist_wheel`. If toolkit version mismatches torch's expected cu128, add `set NVCC_FLAGS=-allow-unsupported-compiler`. |
| FR-06 | nvcc 13.0 vs torch cu128 mismatch (the user's machine) | Install CUDA Toolkit 12.8 sidecar to `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8`. Don't uninstall 13.0. Set `CUDA_HOME` and `CUDA_PATH` to the v12.8 path for the build shell only. PyTorch's cu128 extension build expects a 12.x-series nvcc; 13.0 will cause `Unknown CUDA arch` (BK-12) and ABI tag mismatches. nvcc 13.0 is fine ONLY if you switch torch to 2.10+cu130 (FR-09). |
| FR-07 | requirements.txt clobbers nightly torch (BK-08, BK-10) | Strip these lines from BOTH `ComfyUI-Hunyuan3DWrapper/requirements.txt` and `ComfyUI-Hunyuan3d-2-1/requirements.txt` before `pip install -r`: any line starting with `torch`, `torchvision`, `torchaudio`, `xformers`, `flash-attn`, `triton`, `bitsandbytes`. Currently kijai's requirements.txt does NOT list torch (good) but contains `pybind11`, `trimesh`, `diffusers>=0.31.0`, `accelerate`, `huggingface_hub`, `einops`, `opencv-python`, `transformers`, `xatlas`, `pymeshlab`, `pygltflib`, `scikit-learn`, `scikit-image`. Replace `opencv-python` with `opencv-contrib-python` for ximgproc support (per ethanstoner). |
| FR-08 | xformers force-downgrade trap (BK-08, BK-15) | Never `pip install xformers` in this env. If a node demands it, use a prebuilt cu128 Windows wheel: `pip install -U https://huggingface.co/czmahi/xformers-windows-torch2.8-cu128-py312/resolve/main/xformers-...whl` (replace with current). Or skip xformers entirely; Hunyuan3D doesn't strictly need it. |
| FR-09 | Switch to torch 2.10 + cu130 path | `pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu130` — then directly `pip install hy3dgen/texgen/custom_rasterizer/dist/custom_rasterizer-0.1.0+torch2100.cuda130-cp312-cp312-win_amd64.whl`. nvcc 13.0 already matches. Skips the source build entirely. Caveat: cu130 nightly may break other ComfyUI nodes — test the rest of your stack first. |
| FR-10 | mesh_inpaint_processor build needed | Wheels in `hy3dpaint/DifferentiableRenderer/dist/mesh_inpaint_processor-0.0.0-cp312-cp312-win_amd64.whl` (visualbruno fork). This is a pure-CPython extension (no CUDA), so the torch/CUDA tag does not matter — same wheel works on cu126/cu128/cu130. Confirmed pure-Python pybind11 build. If install fails the fix is `pip install pybind11 setuptools` then `cd hy3dpaint/DifferentiableRenderer && python setup.py bdist_wheel`. |
| FR-11 | "Build with VS 2022 17.10" question (Q7) | VS Build Tools 2022 (workload "Desktop development with C++") IS sufficient — full Visual Studio IDE not required. Confirmed by ethanstoner guide using only "Visual C++ Build Tools v143". Pin: any 17.x works in practice (17.6 / 17.8 / 17.10 / 17.12 all reported OK). The C++20 flag added in [9d52415](https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1) requires MSVC 17.0+, trivially satisfied. |
| FR-12 | Tencent Docker reference recipe | `FROM nvidia/cuda:12.8.0-devel-ubuntu22.04` + `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128` + `ENV TORCH_CUDA_ARCH_LIST="6.0;6.1;7.0;7.5;8.0;8.6;8.9;9.0;12.0"` + `ENV CUDA_NVCC_FLAGS="-allow-unsupported-compiler"` + `cd custom_rasterizer && python setup.py install`. End-to-end PBR confirmed on RTX 5090 (Tencent issue [#122](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/issues/122)). |
| FR-13 | sm_120a vs sm_120 (BK-13) | If a future code path needs Blackwell NVFP4: `set TORCH_CUDA_ARCH_LIST=12.0a` (with the `a` suffix). For custom_rasterizer this is unnecessary — the kernel does not use block-scale MMA. `12.0` (no suffix) is fine for rasterization. |

## 4. Folder layout for models (Q9)

Per [HF tencent/Hunyuan3D-2.1 tree](https://huggingface.co/tencent/Hunyuan3D-2.1/tree/main/hunyuan3d-paintpbr-v2-1) and ethanstoner guide:

```
ComfyUI/models/
  diffusion_models/
    hunyuan3d-dit-v2-1.ckpt
  vae/
    hunyuan3d-vae-v2-1.ckpt
  checkpoints/                      <- kijai wrapper expects this for paint
    Hunyuan3D-2.1/
      hunyuan3d-paintpbr-v2-1/      <- nested under Hunyuan3D-2.1/
        feature_extractor/
        image_encoder/
        scheduler/
        text_encoder/
        tokenizer/
        unet/
          modules.py
        vae/
        model_index.json
        README.md
```

The `hunyuan3d-paintpbr-v2-1/` directory is **nested** under `Hunyuan3D-2.1/`, not at the top of `models/checkpoints/`. The HF repo `tencent/Hunyuan3D-2.1` already has it under that name — clone into `models/checkpoints/Hunyuan3D-2.1/` and it lays out correctly.

## 5. Answers to the 11 brief questions

| Q | Answer |
|---|--------|
| 1. torch range producing working `custom_rasterizer` builds on cu128? | None published as wheel. Source-build only — Tencent confirms cu128 + `TORCH_CUDA_ARCH_LIST=12.0` + `-allow-unsupported-compiler` works (issue #122). On Windows, torch 2.7.x or 2.8.x + cu128 nightly, paired with CUDA Toolkit 12.8 sidecar, is the practical sweet spot. Avoid torch 2.9+ on Win until the C2872 namespace bug (BK-01) clears. **Cleaner alternative: torch 2.10 + cu130 + kijai's prebuilt wheel.** |
| 2. CUDA toolkit sweet spot — does nvcc 13.0 work for cu128? | **No, not cleanly.** nvcc 13.0 building extensions for cu128 torch produces `Unknown CUDA arch` warnings (BK-12) and renamed-arch (`sm_101→sm_110`) issues; ABI mismatches between torch's bundled cu128 stubs and nvcc 13's host headers reported (BK-14). Recommended: install CUDA Toolkit 12.8 sidecar (don't uninstall 13.0) and point `CUDA_HOME` at v12.8 for the build shell. **OR** switch torch to 2.10+cu130 and use nvcc 13.0 natively — the kijai prebuilt wheel matches that lane exactly. |
| 3. Is custom_rasterizer required for PBR baking, or only normal-map step? | Required for the rasterized-multiview-render step (`HY3DRenderMultiview`). Without it, the kijai workflow's primary PBR-bake path fails at that node — `No module named 'custom_rasterizer'` import at workflow load (BK-03). There is no `custom_rasterizer = None` graceful fallback in the wrapper as of kijai main today. The mesh_inpaint_processor is separately required for the texture-infill step but is pure-Python and easy to build. |
| 4. Prebuilt cu128 / sm_120 / cp312 wheel anywhere? | **No cu128-tagged wheel exists publicly.** Closest matches: (a) kijai's `+torch2100.cuda130-cp312` (cu130 not cu128, since 2026-03-10); (b) kijai/visualbruno `+torch260.cuda126-cp312` (cu126 — too old for sm_120 kernels); (c) YanWenKun WinPortable v4-cu129 bundles cu129 wheels embedded in the portable archive (extractable). **No civitai mirror, no comfy-deploy mirror, no kijai release attachments** (releases page empty). |
| 5. requirements.txt lines to STRIP | Strip from BOTH wrappers: `torch`, `torch>=...`, `torchvision`, `torchaudio`, `xformers`, `flash-attn`, `triton`, `bitsandbytes`, plus any `--index-url` lines. Current kijai `requirements.txt` does NOT list torch/xformers (good) — it lists: `trimesh, diffusers>=0.31.0, accelerate, huggingface_hub, einops, opencv-python, transformers, xatlas, pymeshlab, pygltflib, scikit-learn, scikit-image, pybind11`. Swap `opencv-python` → `opencv-contrib-python` for `ximgproc` support. |
| 6. mesh_inpaint_processor fallback if not built? | Texture-infill step fails at runtime — workflow does NOT gracefully degrade. You get a Python `ModuleNotFoundError` mid-execution (per kijai issues comments). Build is trivial (pure pybind11, no CUDA), so just install the prebuilt wheel from `hy3dpaint/DifferentiableRenderer/dist/`. |
| 7. MSVC version pinning? | Not strictly pinned. VS 2022 v143 (any minor 17.6 / 17.8 / 17.10 / 17.12) reported working. C++20 compile flag added 2026-02-27 (visualbruno [9d52415](https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1)) requires MSVC 17.0+, trivially met. The reported C2872 ambiguity (BK-01/02) is NOT an MSVC version issue — it's a torch 2.9+ header issue. |
| 8. VS Build Tools standalone vs full Visual Studio? | **Build Tools 2022 sufficient.** Workload required: "Desktop development with C++" (gives you `cl.exe`, Windows 10 SDK, MSVC v143 toolchain). Full IDE not needed. Confirmed by ethanstoner guide. |
| 9. hy3dpaint/ model layout | See section 4 above. `hunyuan3d-paintpbr-v2-1/` lives nested **inside** `models/checkpoints/Hunyuan3D-2.1/`, not at the top of checkpoints. |
| 10. Hunyuan3D-Omni / Hunyuan3D-Part — same wrapper? | **Not in kijai's wrapper** as of 2026-05-06. Kijai's wrapper supports Hunyuan3D 2.0 / 2.0-mini / 2.0-mv / 2.1 (DiT + Paint). Omni and Part are separate Tencent repos requiring their own integration. No community ComfyUI wrapper for either yet. |
| 11. HunyuanWorld-Mirror (Oct 2025)? | Released 2025-10-22 ([HF tencent/HunyuanWorld-Mirror](https://huggingface.co/tencent/HunyuanWorld-Mirror)). It's "HunyuanWorld 1.1" — a feed-forward 3D scene reconstruction model (NOT mesh generation): video / multi-view → dense point cloud + multi-view depth + camera params + surface normals + 3D Gaussians, single forward pass. **Use case for prop work: probably none.** It outputs Gaussian-splat scenes, not retopologized meshes. Different code path entirely; does NOT use `custom_rasterizer`. |

## 6. Open questions

- **Q1.** Does kijai's torch2100.cuda130 wheel actually run end-to-end PBR on RTX 5090, or only install? (Commit message claims it builds; nobody has posted a render.)
- **Q2.** Will torch 2.10 stable land before the user's window? Currently only nightly cu130 ships sm_120 kernels in stable form; switching to nightly is a soft destabilizer for unrelated nodes.
- **Q3.** Is there a way to make kijai's setup.py emit a `+torch270.cuda128` wheel cleanly on Windows, or does the nightly torch-2.7-cu128 ABI break the build path that worked for torch 2.10? Worth a single-shot attempt with `TORCH_CUDA_ARCH_LIST=12.0` + CUDA Toolkit 12.8 + MSVC 17.10 before falling back to FR-09.
- **Q4.** YanWenKun WinPortable v4-cu129 — is the embedded `custom_rasterizer` wheel literally extractable and reusable in a non-portable ComfyUI? (Likely yes; worth grabbing the .7z and inspecting `wheels/`.)
- **Q5.** Does `triton-windows` (pre) build cleanly on cu128 in the same env? Required for sageattention but not for Hunyuan3D itself.

---

## Sources index (canonical URLs)

- kijai wrapper: https://github.com/kijai/ComfyUI-Hunyuan3DWrapper
- kijai issue #181 (incompatible versions): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/181
- kijai issue #201 (ROCm): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/201
- kijai issue #203 (Blackwell 5000): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/203
- kijai issue #204 (cu130 C2872): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/204
- kijai issue #206 (DLL load failed): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/206
- kijai issue #207 (utils3d): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/issues/207
- kijai commit 7fbc376 (torch 2.10+cu130 wheel): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/commit/7fbc376
- kijai commit 2609efa (Linux setup.py): https://github.com/kijai/ComfyUI-Hunyuan3DWrapper/commit/2609efa
- visualbruno fork: https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1
- visualbruno commit 9d52415 (C++20): https://github.com/visualbruno/ComfyUI-Hunyuan3d-2-1/commit/9d52415
- Tencent Hunyuan3D-2.1: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Tencent issue #122 (Docker 5090): https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/issues/122
- ethanstoner install guide: https://github.com/ethanstoner/Hunyuan3D-2.1-Complete-Install-Guide
- comfy 5090/Blackwell thread: https://github.com/comfyanonymous/ComfyUI/discussions/6643
- comfy 5090 sageattention thread: https://github.com/Comfy-Org/ComfyUI/discussions/6980
- pytorch sm_120 official tracker: https://github.com/pytorch/pytorch/issues/159207
- pytorch sm_120a auto-detect bug: https://github.com/pytorch/pytorch/issues/172807
- pytorch CUDA arch unknown: https://github.com/pytorch/pytorch/issues/166120
- pytorch cu130 binaries: https://github.com/pytorch/pytorch/issues/159779
- detectron2 cu13 build break: https://github.com/facebookresearch/Detectron2/issues/5503
- HF tencent/Hunyuan3D-2.1: https://huggingface.co/tencent/Hunyuan3D-2.1
- HF tencent/Hunyuan3D-2 disc 38 (cu128 5070/5080): https://huggingface.co/tencent/Hunyuan3D-2/discussions/38
- HF tencent/HunyuanWorld-Mirror: https://huggingface.co/tencent/HunyuanWorld-Mirror
- HF czmahi xformers cu128 cp312: https://huggingface.co/czmahi/xformers-windows-torch2.8-cu128-py312
- HF lldacing flash-attention windows wheels: https://huggingface.co/lldacing/flash-attention-windows-wheel
- HF ldilov torch 2.7.0 cu128 cp312: https://huggingface.co/ldilov/torch-2.7.0-cu128-cp312
- YanWenKun WinPortable releases: https://github.com/YanWenKun/Hunyuan3D-2-WinPortable/releases
- wildminder AI-windows-whl: https://github.com/wildminder/AI-windows-whl
- comfyui-wiki Hunyuan3D guide: https://comfyui-wiki.com/en/tutorial/advanced/3d/huanyuan3d-2
- codersera Win11 install 2026: https://codersera.com/blog/set-up-hunyuan3d-2-on-windows-a-step-by-step-guide/
- Tencent Hy3D paintpbr v2.1 setup.py (HF mirror): https://huggingface.co/spaces/tencent/Hunyuan3D-2.1/blob/main/hy3dpaint/packages/custom_rasterizer/setup.py
