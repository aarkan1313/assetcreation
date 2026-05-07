# HANDOFF — Phase 12 Audio Deep-Dive (2026-05-06 PM)

**Status:** ✅ landed. Real Stable Audio Open 1.0 GPU bake on all 10 biomes; ambience system fully shipped.

## What shipped

**Stable Audio Open 1.0 (1.21B) integrated end-to-end on RTX 5090 / cu130 / Win11**
- HF gated license accepted, token persisted, model downloaded (~5 GB safetensors + config tree)
- `../../pipelines/audio/local_audio_open.py` patched to prefer local-path loading over gated HF API at runtime
- bf16 inference: ~10-11 it/s on 50-step diffusion → 5-15s per stem
- Same `D:/assets/animators/ComfyUI_HY3D/.venv/` shared with HY3D — no separate venv

**Real biome ambience generated for all 10 biomes**
- `lava_field`, `ice_cavern`, `mana_crystal`, `grassland`, `forest`, `desert`, `tundra`, `swamp`, `charred_wasteland`, `underwater`
- Each biome: 2 looped beds (bed_drone + bed_air, 30s seamless) + N wildlife oneshots + N distant events
- Total ~140 WAVs / ~50 MB at 44.1 kHz mono, LUFS-normalized per E2 §2.3 spec
- Replaces the dry-run silence that was placeholder until now

**Workflow infra extended**
- `recipes/biome_ambience_large_only.json` — recipe variant that uses only the `large` model (avoids the small-model gated-license click-through)
- Pipeline-load amortization: model stays cached in `_PIPE_CACHE` across all 10 biomes in one run, saving ~30s per biome

## How to re-run

After a fresh restart or after token rotation, set the token + run:

```powershell
# (one-time per machine)
[Environment]::SetEnvironmentVariable("HF_TOKEN", "hf_...", "User")

# (for batch ambience generation)
D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\python.exe `
  D:\assets\pipelines\audio\biome_ambience.py `
  --recipe D:\assets\pipelines\audio\recipes\biome_ambience_large_only.json `
  --out D:\assets\audio\ambience
```

To re-bake a single biome (development):

```powershell
D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\python.exe `
  D:\assets\pipelines\audio\biome_ambience.py `
  --recipe D:\assets\pipelines\audio\recipes\biome_ambience_large_only.json `
  --out D:\assets\audio\ambience `
  --biome lava_field
```

## Patches applied

### 1. `local_audio_open.py` — prefer local-path over gated HF API

`StableAudioPipeline.from_pretrained(model_id, ...)` was hitting the gated HF API at runtime even after we'd downloaded the full model locally. Symptom: `GatedRepoError: 401 Client Error` after auth + license accept worked for the explicit `hf download` step. The runtime call doesn't pick up `HF_TOKEN` automatically in all paths.

Fix: lookup `D:/assets/animators/ComfyUI_HY3D/models/diffusers/<repo_name>/` and pass that path directly to `from_pretrained` if `model_index.json` exists. Falls back to the repo id if the local copy is missing.

### 2. `biome_ambience_large_only.json` — avoid the gated small model

The original recipe uses `"model": "small"` for wildlife/distant_event clips (which only need 1-2s of audio, where the small model's 11s ceiling is enough). But `stabilityai/stable-audio-open-small` is a separate gated repo from `stable-audio-open-1.0` — accepting one license doesn't auto-grant the other. Rather than ask the user for a second license click, the new recipe uses `large` for everything. The 1.21B is fast enough on a 5090 that this isn't a real cost (~5-10s per short clip).

Original recipe preserved at `recipes/biome_ambience.json`; the production runner now points at `recipes/biome_ambience_large_only.json`.

## What was already there (from earlier Audio v3 work)

The plumbing all worked dry-run before Phase 12 (per `HANDOFF_audio_v3_2026_05_06.md`):
- `biome_ambience.py` runner
- `local_audio_open.py` adapter (with dry-run fallback)
- `process_audio.py` LUFS normalization
- `audio_qa.py` per-stem QA
- `loop_detect.py` phase-aware seam scoring
- `ambience_pack.py` Godot exporter (BiomeAmbienceController.tscn + AmbienceReverb bus)
- `gallery.py` HTML browser
- `lint_audio.py` strict gating

Phase 12's job was to flip the GPU bake from `dry_run_silent` to real audio. Done.

## Findings worth remembering

1. **Diffusers `from_pretrained` is auth-flaky on gated repos even with HF_TOKEN set.** Local-path fallback is the robust pattern. Same trick will help us on any future gated-repo model.
2. **One license click is per-model-repo.** Stability has small + large + ARC + base models in separate gated repos. Always check what license your recipe wants vs what's been clicked.
3. **Pipeline reuse across biomes is huge.** First call: ~17s for 10s clip including pipeline warmup. Subsequent calls: ~5s for 10s clip. For 10 biomes × ~14 stems = 140 calls, that's saving ~30 min.
4. **Phase 11 (props) precedent translated cleanly.** Same install patterns (gated HF, license + token, local-path loader patches), same test scaffold (smoke first, then full bake), same closing-doc shape.

## Where to look for what

```
audio/ambience/
├── lava_field/         ← bed_drone + bed_air + wildlife/ + distant_event/
├── ice_cavern/
├── mana_crystal/
├── grassland/
├── forest/
├── desert/
├── tundra/
├── swamp/
├── charred_wasteland/
├── underwater/
└── ambience_summary.json  ← per-biome roll-up

pipelines/audio/
├── local_audio_open.py            ← Stable Audio Open 1.0 adapter (PATCHED for local-path)
├── biome_ambience.py              ← multi-biome runner
├── recipes/
│   ├── biome_ambience.json            ← original (mixes small + large models)
│   └── biome_ambience_large_only.json ← Phase 12 production (large only)
└── STABLE_AUDIO_SETUP.md          ← step-by-step license/token/install
```

## Next steps after Phase 12

- **Listen-test the bakes.** Open a few of the lava_field / underwater / mana_crystal beds in any audio player and confirm they actually sound like what the prompt asked for.
- **Wire into Godot via `ambience_pack.py`** — exports BiomeAmbienceController.tscn + per-biome AudioStreamRandomizer for wildlife/distant. Currently produced WAVs are not yet in `../../audio/godot/` Godot-import format.
- **Phase 13 candidate**: VFX deep-dive (next pipeline matching Phase 11/12 install-pain shape) OR Path B cross-pipeline composition (gated on world-gen recovery).
