# Trellis2 patches (Phase 11A)

The Trellis2 venv at `D:\assets\animators\Trellis2\venv\` was set up against
older torch/CUDA and doesn't run end-to-end on our cu128 / sm_120 machine
without three patches. Applied 2026-05-06; documented here so we can reapply
them after a Trellis2 venv rebuild or upstream update.

## Why patches are needed

1. The shipped `flex_gemm.kernels.cuda.pyd` was compiled against torch 2.5/cu124.
   On torch 2.8/cu128 it fails to load (DLL missing) unless CUDA + torch lib
   directories are explicitly added to the Windows DLL search path.
2. The upstream `flex_gemm.kernels.triton` Python submodule was never installed
   into the venv — the package's `__init__.py` does `try: from . import triton;
   except ImportError: pass` then the upstream code unconditionally calls
   `kernels.triton.indice_weighed_sum_fwd`. Result: AttributeError.
3. The shipped triton kernel calls into `feats[indices]` where `indices` may
   contain `-1` sentinels (Trellis2's neighbor-map "no neighbor" marker). Our
   pure-torch fallback has to clamp + mask them.
4. `o_voxel.postprocess.to_glb()` uses fp16 tensors but our fallback's index_add
   was returning fp32. Dtype mismatch → `RuntimeError: Index put requires the
   source and destination dtypes match`.

## Patch 1: DLL search dirs in flex_gemm/kernels/__init__.py

**File:** `D:\assets\animators\Trellis2\venv\Lib\site-packages\flex_gemm\kernels\__init__.py`

Original:
```python
try:
    from . import triton
except ImportError:
    pass
from . import cuda
```

Replaced with:
```python
import os as _os
import sys as _sys


def _ensure_cuda_dll_path():
    """Ensure CUDA Toolkit + torch DLL dirs are searchable before loading
    flex_gemm.kernels.cuda. The shipped cuda.pyd was built against an older
    torch/CUDA but loads fine on cu128 once the right DLL search dirs are
    added (Windows since 3.8 needs explicit os.add_dll_directory).
    """
    candidates = [
        r"C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin",
        r"C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.8/bin",
        r"C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.1/bin",
    ]
    try:
        import torch as _torch
        torch_lib = _os.path.join(_os.path.dirname(_torch.__file__), "lib")
        if _os.path.isdir(torch_lib):
            candidates.insert(0, torch_lib)
    except Exception:
        pass
    for d in candidates:
        if _os.path.isdir(d):
            try:
                _os.add_dll_directory(d)
            except (OSError, FileNotFoundError):
                pass


_ensure_cuda_dll_path()

try:
    from . import triton
except ImportError:
    pass

try:
    from . import cuda
except ImportError as _cuda_err:
    print(f"[flex_gemm.kernels] cuda backend unavailable ({_cuda_err})", file=_sys.stderr)
```

## Patch 2: pure-torch triton fallback

**File (new):** `D:\assets\animators\Trellis2\venv\Lib\site-packages\flex_gemm\kernels\triton\__init__.py`

```python
"""Pure-torch fallback for missing flex_gemm.kernels.triton submodule.

The Trellis2 venv ships flex_gemm with only the cuda.pyd backend; the upstream
package's triton-kernel submodule was never installed. The reference grid-sample
op in flex_gemm.ops.grid_sample.grid_sample calls these two functions:

    kernels.triton.indice_weighed_sum_fwd(feats, indices, weight)
    kernels.triton.indice_weighed_sum_bwd_input(grad_out, indices, weight, N)

Semantics (forward):
  feats:   [N, C] feature table
  indices: [M, K] int neighbor indices into feats (K usually 8 for trilinear)
  weight:  [M, K] float weights aligned with indices
  out:     [M, C] = sum_k weight[:, k:k+1] * feats[indices[:, k]]

Sentinel handling: indices may contain -1 (or any out-of-range value) to
signal "no neighbor." Mask + clamp before gather; zero out their contribution.

Dtype handling: feats may be fp16; gathered/weight cast accordingly so
downstream index_put doesn't reject the dtype.
"""
from __future__ import annotations
import torch


def indice_weighed_sum_fwd(feats: torch.Tensor, indices: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    if indices.dtype != torch.int64:
        indices = indices.long()
    N = feats.shape[0]
    valid = (indices >= 0) & (indices < N)
    safe_idx = torch.where(valid, indices, torch.zeros_like(indices))
    gathered = feats[safe_idx]  # [M, K, C]
    w = (weight * valid.to(weight.dtype)).unsqueeze(-1)  # [M, K, 1]
    out = (gathered * w.to(gathered.dtype)).sum(dim=1)
    return out.to(feats.dtype)


def indice_weighed_sum_bwd_input(grad_out: torch.Tensor, indices: torch.Tensor,
                                  weight: torch.Tensor, N: int) -> torch.Tensor:
    if indices.dtype != torch.int64:
        indices = indices.long()
    M, K = indices.shape
    C = grad_out.shape[-1]
    grad_feats = torch.zeros((N, C), device=grad_out.device, dtype=grad_out.dtype)
    valid = (indices >= 0) & (indices < N)
    safe_idx = torch.where(valid, indices, torch.zeros_like(indices))
    for k in range(K):
        v_k = valid[:, k].to(weight.dtype).unsqueeze(-1)
        wk = weight[:, k].unsqueeze(-1) * v_k
        contrib = grad_out * wk
        grad_feats.index_add_(0, safe_idx[:, k], contrib)
    return grad_feats
```

## Reapply checklist

After any Trellis2 venv rebuild / upstream update:

1. Verify both files above exist and match.
2. Smoke-test:
   ```powershell
   D:\assets\animators\Trellis2\venv\Scripts\python.exe -c "from flex_gemm import kernels; print('triton:', hasattr(kernels, 'triton'), 'cuda:', hasattr(kernels, 'cuda'))"
   ```
   Expected: `triton: True cuda: True`
3. Run the batch runner on a known-good concept:
   ```powershell
   D:\assets\animators\Trellis2\venv\Scripts\python.exe D:\assets\pipelines\props\trellis2_batch.py `
     --concepts D:\assets\world\props\concepts\ruined_obelisk_a\source.png `
     --preset balanced
   ```
   Expected: `BATCH SUMMARY` with 1 row and `OK: True`.

## Upstream tracking

If a future Trellis2 release ships a working `flex_gemm.kernels.triton` and a
cu128-built `cuda.pyd`, we can drop both patches.

- Trellis2 repo: https://github.com/microsoft/TRELLIS (or wherever Trellis2 source lives — check `D:\assets\animators\Trellis2\.git\config`)
- flex_gemm package: shipped vendored inside Trellis2's venv; no upstream URL captured
- HF model: `microsoft/TRELLIS.2-4B`
