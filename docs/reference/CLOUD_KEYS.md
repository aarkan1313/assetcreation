# Cloud Keys

Single index of every environment variable any tool in `D:\assets\` looks for, what it activates, and how the tool falls back when it's missing. Updated 2026-05-06.

**The principle:** every cloud-API tool is **gated** on an env var. If the var is missing, the tool either falls back to a local/synth path or exits cleanly with a clear message. No silent failures.

## Active env vars

| Env var | Tool | Activates | Fallback when missing |
|---|---|---|---|
| `OPENTOPOGRAPHY_API_KEY` | [`../../pipelines/terrain/import_dem.py`](../../pipelines/terrain/import_dem.py) | OpenTopography `/globaldem` and `/usgsdem` requests. **Required for terrain ingestion.** | Hard exit with message pointing to `https://opentopography.org/` for a free key. OT+ subscription unlocks USGS 1m + 400/24h. |
| `OPENAI_API_KEY` | [`../../pipelines/game_data/generate_records.py`](../../pipelines/game_data/generate_records.py) (`--backend openai`) | LLM-driven schema-constrained generation of items / abilities / NPCs / factions / lore | Synthetic generator (`--backend synthetic`); `--backend auto` (default) silently falls back. |
| `ANTHROPIC_API_KEY` | [`../../pipelines/game_data/generate_records.py`](../../pipelines/game_data/generate_records.py) (`--backend claude`) | Claude tool-schema generation of items / abilities / NPCs / factions / lore | Synthetic generator (`--backend synthetic`); `--backend auto` silently falls back through OpenAI, then Claude, then synthetic. |
| `OPENAI_API_KEY` | [`../../pipelines/ui/openai_icons.py`](../../pipelines/ui/openai_icons.py) | `gpt-image-1` icon generation | Tool returns exit code 2 with a clear message. The `synth_icons.py` procedural path is the always-available fallback. |
| `RECRAFT_API_KEY` | [`../../pipelines/ui/recraft_icons.py`](../../pipelines/ui/recraft_icons.py) | Recraft V3 cloud icon generation; supports `--style icon|vector_illustration|...`, `--style-id <UUID>` for set-style consistency, `--svg` for the vector lane. | Tool returns exit code 2 with a clear message. The `synth_icons.py` procedural path is the always-available fallback. |
| `ELEVENLABS_API_KEY` | [`../../pipelines/audio/eleven_sfx.py`](../../pipelines/audio/eleven_sfx.py) | ElevenLabs Sound Effects API (text-to-SFX) | Tool returns exit code 2 with clear message. The `synth_sfx.py` procedural path is the always-available fallback. |
| `FAL_KEY` | [`../../pipelines/textures/patina_adapter.py`](../../pipelines/textures/patina_adapter.py) | fal.ai cloud texture-patina application (decorative aging passes) | Tool exits with a clear message. Local pipeline runs without patina. |

## Runtime authorization gates

These are not long-lived API keys. They are explicit per-batch switches so GPU/cloud paths cannot run by accident.

| Env var | Tool | Activates | Fallback when missing |
|---|---|---|---|
| `MESHY_AUTH_FOR_THIS_BATCH=YES` | [`../../pipelines/props/meshy_route.py`](../../pipelines/props/meshy_route.py) | Allows the Meshy hero-prop adapter to spend credits for the current batch. | Dry-run only, or hard exit before paid API call. |
| `TRELLIS2_PROP_CMD` | [`../../pipelines/props/trellis2_route.py`](../../pipelines/props/trellis2_route.py) | Provides the local Trellis2 invocation template for `{image}`, `{out_glb}`, `{seed}`, `{target_tris}` once `--device cuda --run-model` is requested. | CPU dry-run writes a manifest only; no model import/load. |
| `KOKORO_TTS_CMD` | [`../../pipelines/audio/local_tts_f5.py`](../../pipelines/audio/local_tts_f5.py) (`--engine kokoro --device cuda --run-model`) | Optional local Kokoro-82M command template for `{text}`, `{out}`, `{voice}`, `{seed}`, `{speed}`. | Dry-run writes a placeholder WAV + cue; no model import/load. |
| `YUE_MUSIC_CMD` | [`../../pipelines/audio/local_music_yue.py`](../../pipelines/audio/local_music_yue.py) (`--device cuda --run-model`) | Optional local YuE command template for `{prompt}`, `{lyrics}`, `{out}`, `{seed}`, `{duration}`, `{title}`. | Dry-run writes a placeholder WAV + `.music.json`; no model import/load. |

## Phase 9 local-only replacements

These are not cloud keys. They are the local/open-weights paths that now replace or reduce dependence on the cloud adapters above. Real GPU/model execution still requires an explicit `--device cuda --run-model` or `--run` gate.

| Cloud path reduced | Local-only path | Runtime gate / blocker |
|---|---|---|
| OpenAI / Anthropic game-data generation | [`../../pipelines/game_data/local_llm_backend.py`](../../pipelines/game_data/local_llm_backend.py) with vLLM `guided_json` + `guided_decoding_backend=xgrammar` | Start local vLLM at `http://127.0.0.1:8000/v1`; command still requires `--device cuda --run-model`. |
| Recraft / OpenAI icon generation | [`../../pipelines/ui/local_diffusion_icons.py`](../../pipelines/ui/local_diffusion_icons.py) `--backend comfy` using FLUX-schnell + IP-Adapter workflow | ComfyUI custom nodes + free GPU; default plan mode writes no-cost JSON. |
| Meshy hero props | [`../../pipelines/props/hunyuan3d_route.py`](../../pipelines/props/hunyuan3d_route.py) using Hunyuan3D-2.5 Comfy workflow | Hunyuan3D Comfy nodes + free GPU; dry-run writes `prop_asset.v1`. |
| ElevenLabs voice/TTS spend | [`../../pipelines/audio/local_tts_f5.py`](../../pipelines/audio/local_tts_f5.py) F5-TTS / Kokoro | F5 Comfy nodes or `KOKORO_TTS_CMD` + free GPU; dry-run writes WAV+cues. |
| Cloud video/manual animation references | [`../../pipelines/video/comfy_video.py`](../../pipelines/video/comfy_video.py) Wan workflow | Wan Comfy nodes + free GPU; dry-run writes `video_plan.json`. |
| Manual HF landscape checks | [`../../pipelines/_meta/hf_surveyor.py`](../../pipelines/_meta/hf_surveyor.py) | Real mode uses public HF API; `--dry-run` verifies license filter without network. |

## Setting them in Windows

User-scope (persists across reboots and is what bash subprocess inheritance picks up most reliably):

```powershell
[Environment]::SetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "your-key-here", "User")
```

Per-shell only (lost when shell closes):

```powershell
$env:OPENTOPOGRAPHY_API_KEY = "your-key-here"
```

For PowerShell sessions where you want the User-scope value made available to subprocesses immediately:

```powershell
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")
```

This is the recommended pre-flight for every shell session that runs terrain pulls.

## Verifying what's set

```powershell
[Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")
[Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
[Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
[Environment]::GetEnvironmentVariable("ELEVENLABS_API_KEY", "User")
[Environment]::GetEnvironmentVariable("FAL_KEY", "User")
```

Each prints the key (or empty if not set).

## Stubbed / planned env vars

These tools will gate on these vars when implemented (see `../plans/EXPANSION_PLAN.md`):

| Env var | Future tool | Expansion phase |
|---|---|---|
| `MESHY_API_KEY` | already-existing `../../meshy/meshy_image_to_3d.py` (also `--api-key` CLI) | character pipeline |
| `STABILITY_API_KEY` | possible future Stable Audio cloud adapter | Phase 3 |
| `RUNWAY_API_KEY` | possible future video / motion adapter | not yet scoped |
| `SUNO_API_KEY` / `LYRIA_API_KEY` | music orchestrator if/when provider opens API | Phase 3 |

## Never required

These env vars are explicitly **not** used and never should be (false-positive grep hits):

- `*_TOKEN` pulled by HuggingFace's `transformers` library — local model loads only need this for gated repos. Set it if you need gated models, but no tool here requires gated weights as of 2026-05-06.

## Security notes

- **Don't share keys.** Per OT+ Terms, multi-seat is by request only.
- **Don't commit keys.** `D:\assets\` is not currently a git repo (audit confirmed). If git-init is added later, ensure `.env`-style files are gitignored.
- **Don't embed keys in shipped binaries.** All tools here read at runtime from env; nothing bakes a key into a build artifact.

## Related docs

- [OPENTOPO_API.md](OPENTOPO_API.md) — the OpenTopography API surface in detail (datasets, limits, tier matrix)
- [../plans/EXPANSION_PLAN.md](../plans/EXPANSION_PLAN.md) — when each stubbed var would be wired
- Per-tool handoffs: each `HANDOFF_<pipeline>_2026_05_06.md` has its own "Cloud-key contract" table
