# audio/ — output directory (intentionally empty)

This is the output directory for the audio pipeline. **It was emptied 2026-05-07** after a manual review found the procedural / unprompted-cloud bake was placeholder-tier (mostly noise/static). See [`docs/pipeline_reviews/03_audio.md`](../docs/pipeline_reviews/03_audio.md) for the full review.

## Where the old content went

`_archive/audio_phase12_bake_2026_05_07/` — 189 MB, includes:
- `ambience/` — 140 Stable Audio Open WAVs across 10 biomes
- `sfx/` — 112 procedural SFX
- `music/` — 4 adaptive multi-stem tracks (procedural, not generative)
- `voice/` — TTS scratch
- `library/`, `godot/`, manifests, gallery.html

Don't restore unless you want them. They're kept for forensics.

## Why empty rather than delete?

The pipeline is the deliverable, not the content. `pipelines/audio/` retains:
- `biome_ambience.py` (Stable Audio Open ambience baker — the most useful tool)
- `local_audio_open.py` (gated-repo loader with local-path fallback)
- `synth_sfx.py` + `synth_sfx_extended.py` (procedural SFX synth)
- `eleven_sfx.py` (ElevenLabs cloud SFX — never run, env-gated)
- `cc0_ingest.py` (Freesound CC0 ingest — never run)
- `local_tts_f5.py` + `openai_tts.py` (TTS, never run on real content)
- `local_music_yue.py` (YuE generative music, parked)
- `adaptive_music.py` (procedural multi-stem authoring)
- `audio_qa.py` + `lint_audio.py` + `loop_detect.py` (QA tools)
- `ambience_pack.py` + `export_godot.py` (Godot export)
- LUFS targets per layer in `LUFS_AUTHORING_GUIDE.md`

## When to re-bake

When there's specific game-design intent ("I need forest ambience for scene X"), do a focused single-asset push:
1. Tune the Stable Audio prompt with reference audio conditioning
2. Run `biome_ambience.py` with the curated recipe
3. Audition the output
4. Iterate or accept

Don't run the broad procedural fill again. We have proof the pipeline works; we don't need 140 more placeholder WAVs.

## SFX path forward

Procedural synth (`synth_sfx.py`) produces noise-tier output. Real SFX needs either:
- ElevenLabs cloud (`eleven_sfx.py`) for synthesized hero sounds with prompt control
- Curated Freesound CC0 recordings via `cc0_ingest.py`

Both are env-gated and never been run.

## Music path forward

`adaptive_music.py` is procedural. Output is structurally correct (BPM, stems, intent JSON, Godot bus layout) but not musical. Real music needs YuE (`local_music_yue.py`, GPU-gated) or commissioned composition.
