# Stable Audio Open — install + auth setup

The Stable Audio Open models live behind a gated HF repo (free, click-through Stability Community License). The audio pipeline's `local_audio_open.py` adapter is built and `from diffusers import StableAudioPipeline` already works in our `ComfyUI_HY3D` venv — but the model download requires HF auth + license accept.

This doc is your step-by-step. Total time: ~3 minutes for steps 1-3, then ~5 GB download for step 4.

## Going for the BIG model (1.21B "stable-audio-open-1.0")

Per `local_audio_open.py:64-65`:
- `small`: `stabilityai/stable-audio-open-small` — 341M params, ≤11s clips, ~2 GB VRAM
- `large`: `stabilityai/stable-audio-open-1.0` — **1.21B params, ≤47s clips, ~5 GB VRAM** ← this one

The large model is the production target — it can do full 30-second biome ambience beds in one shot vs the small model's 11s ceiling (which would force us to loop short clips, defeating the "seamless 30s loop" intent in our recipes).

## Step 1 — Accept the license (open these in browser, click the big "Agree" button)

Both repos use the same Stability Community License. Accepting on one does NOT auto-grant the other; click each.

- **PRIMARY (do this one first)**: https://huggingface.co/stabilityai/stable-audio-open-1.0
- Optional fallback (smaller, faster, less capable): https://huggingface.co/stabilityai/stable-audio-open-small

The page shows "You need to agree to share your contact information to access this model." Fill in the gate form (just name + reason for use is fine, e.g. "personal game asset generation"). Approval is **automatic and instant**.

License is the **Stability AI Community License**: free for non-commercial AND commercial use under $1M revenue. Above $1M ARR, you need to talk to them.

## Step 2 — Create an HF access token

1. Go to https://huggingface.co/settings/tokens
2. Click "Create new token"
3. Type: **Read** (this is enough; we only download)
4. Name: `local_asset_factory` (or whatever)
5. Click "Generate"
6. **Copy the token** (`hf_...`) — you only see it once

## Step 3 — Drop the token into the env

PowerShell, persistent (User scope):

```powershell
[Environment]::SetEnvironmentVariable("HF_TOKEN", "hf_YOUR_TOKEN_HERE", "User")
```

Then close + reopen your shell (or just paste this into the current shell as well to use it now without restart):

```powershell
$env:HF_TOKEN = "hf_YOUR_TOKEN_HERE"
```

Verify:

```powershell
python -c "import os; print('HF_TOKEN set:', bool(os.environ.get('HF_TOKEN')), 'length:', len(os.environ.get('HF_TOKEN','')))"
```

## Step 4 — Download the weights (one-time, ~5 GB)

The adapter's `_load_pipeline()` will pull on first call automatically. We can also pre-download to make the first inference call faster:

```powershell
D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\hf.exe `
  download stabilityai/stable-audio-open-1.0 `
  --local-dir D:\assets\animators\ComfyUI_HY3D\models\diffusers\stable-audio-open-1.0
```

This takes ~3-5 min on a fast connection. The model lands in our local cache (and HF's, dedup'd). The `local_audio_open.py` adapter uses HF cache by default — the `--local-dir` is just for visibility.

## Step 5 — Smoke test (one short stem, ~10 seconds inference)

After step 4, test with a short single-stem run:

```powershell
D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\python.exe `
  D:\assets\pipelines\audio\local_audio_open.py `
  --prompt "deep continuous magma rumble, low sub-bass with distant fire crackle, no melody, no music" `
  --negative-prompt "music, melody, vocals, rhythm" `
  --duration 10 --steps 50 --seed 42 `
  --model large `
  --out D:\tmp\sao_smoke.wav
```

Expected output: `D:\tmp\sao_smoke.wav` (~860 KB, 10 seconds, 44.1 kHz mono). Wall-clock: ~30-60s for the first call (cold pipeline load + inference); subsequent calls are ~5-15s for a 30s clip on a 5090.

## Step 6 — Run the real biome ambience bake

Once smoke passes, batch all 10 biomes:

```powershell
D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\python.exe `
  D:\assets\pipelines\audio\biome_ambience.py `
  --recipe D:\assets\pipelines\audio\recipes\biome_ambience.json `
  --out D:\assets\audio\ambience
```

This generates real beds + wildlife + distant_event for all 10 biomes. Expected wall-clock: ~30 minutes total (4 stems × 10 biomes × ~10-30s each + variants).

## What's already wired and working without GPU

- `local_audio_open.py` adapter (CLI + python module) — built, dry-run-safe
- `biome_ambience.py` runner — built, currently producing dry-run silence for all 10 biomes
- `process_audio.py` — pyloudnorm normalization + loop-seam check
- `audio_qa.py` — per-stem QA report
- `loop_detect.py` — phase-aware seam scoring (closes E2 §6 monotonic-drone hole)
- `ambience_pack.py` — Godot exporter (BiomeAmbienceController.tscn + AmbienceReverb bus)
- `gallery.py` — static HTML browser (also works on dry-run silence)
- `lint_audio.py` — strict-audio gating wrapper

The only thing missing for real audio is the GPU bake. Once steps 1-5 are done above, step 6 fills in the silence with actual sound.

## Troubleshooting

### `OSError: You are trying to access a gated repo`

License not accepted yet, or token isn't being read. Verify with:
```powershell
D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\python.exe -c "from huggingface_hub import HfApi; print(HfApi().whoami())"
```
Should print your HF username, not `None`.

### `RuntimeError: CUDA out of memory`

The 1.0 model needs ~5 GB. If GPU is busy with another model (HY3D server still running, LM Studio, etc), free it first. Check with `nvidia-smi`.

### `RuntimeError: Stable Audio Open requires CUDA. CPU is unsupported.`

You're on the right machine; the adapter explicitly refuses CPU. If running over SSH or in a dev container without GPU, stop and run from a session that sees the 5090.
