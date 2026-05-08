# Audio — Manual Review (2026-05-07)

`pipelines/audio/` lane. **This one needs you to actually listen** — file sizes only tell you so much.

## Inventory (truth from disk)

### Ambience (post-Phase-12 Stable Audio Open bake)

10 biomes × 4-layer authoring model = **140 WAVs total** (a few have extra wildlife):

| Biome | bed_drone | bed_air | wildlife_sparse | distant_event | Total |
|---|---|---|---|---|---|
| charred_wasteland | 2 | 2 | 8 | 4 | 14 |
| desert | 2 | 2 | 8 | 4 | 14 |
| forest | 2 | 2 | **10** | 4 | **16** |
| grassland | 2 | 2 | 8 | 4 | 14 |
| ice_cavern | 2 | 2 | 6 | 4 | 12 |
| lava_field | 2 | 2 | 8 | 4 | 14 |
| mana_crystal | 2 | 2 | 6 | 4 | 12 |
| swamp | 2 | 2 | **12** | 4 | **18** |
| tundra | 2 | 2 | 8 | 4 | 14 |
| underwater | 2 | 2 | 8 | 4 | 14 |

- **bed_drone:** ~20s loops at 44.1 kHz mono (Stable Audio Open generates at 30s seamless, padded/cropped to 19.6s). LUFS-targeted to **-28 dBFS**.
- **bed_air:** similar, slightly different timbre. Target **-30 dBFS** (quieter than drone).
- **wildlife_sparse:** short ~1.5s impulses (birds, owls, creaks). Target **-22 dBFS peak**. Triggered Poisson-randomly at runtime.
- **distant_event:** medium-length ambient events (creak, howl, distant boom). Target **-20 dBFS peak**, very rare Poisson trigger.

Each WAV has a sibling `.cue.json` (timing metadata for runtime trigger).

### SFX (procedural / synth-baked)

**112 WAVs flat at `audio/sfx/<id>.wav`** across 39 unique SFX IDs (each with 2-4 variants). Categories:

| Category | IDs |
|---|---|
| Ambience sweeteners | `amb_air_sweetener`, `amb_distant_boom`, `amb_distant_thunder`, `amb_drone_grass/ice/lava/mana` |
| Combat | `fireball_cast`, `sword_swing`, `impact_flesh/metal/shield_block/stone/wood`, `spell_arcane/fire/ice/lightning_cast/impact` |
| Footsteps | `footstep`, `step_grass/metal/snow/stone/water/wood` |
| UI | `ui_back/click/close_menu/confirm/error/open_menu/pickup/purchase/quest_complete/select` |

**Durations:** UI clicks ~30 ms, footsteps ~50 ms, sword swing 370 ms, fireball cast 700 ms. Reasonable spread.

Each `<id>_vN.wav` has a sibling `<id>_vN_qa/` dir with `qa.json + spectrogram.png + waveform.png` (verified yesterday — these are the QA artifacts I miscounted as "empty scratch dirs," which they aren't).

### Music

**4 adaptive multi-stem tracks** authored by `adaptive_music.py` (procedural, not generative-model):

| Track | BPM | Bars | Stems | Use |
|---|---|---|---|---|
| `bossfight_a` | 140 | 16 | drums, low_brass, choir, lead_strings, perc_taiko | 5-stem boss intensity ramp |
| `combat_a` | 120 | 16 | drums, bass, lead, perc_hi | 4-stem calm→combat ramp |
| `exploration_a` | 90 | 32 | pad, harp, low_strings | 3-stem ambient loop |
| `town_a` | 100 | 24 | guitar, flute, tambourine | 3-stem morning→evening→festival |

Each track has `intent.json` (states + intensity + bus_layout amendments) + `manifest.json` + per-stem WAVs (27-85s mono at 44.1 kHz).

**This is real adaptive game music infrastructure** — the `intent.json` defines `states: {intro, phase_1, phase_2, phase_3, defeated}` for bossfight, with `intensity` weighting per stem. Drop into Godot with the per-stem AudioStreamPlayer setup and you get state-driven adaptive playback.

**Generative music status:** `phase9_yue_smoke.wav` is a 4-second stereo YuE smoke test. Not real production output — proves the pipeline runs, nothing more.

### TTS

`pipelines/audio/local_tts_f5.py` and `openai_tts.py` exist as tools. **Zero TTS output on disk.** No NPC dialogue authored yet to speak.

### Godot export (refreshed 2026-05-07)

- `audio/godot/ambience/<biome>/{bed_drone.wav, bed_air.wav, distant/, wildlife/, preset.tres}` — 10 biomes
- `audio/godot/sfx/<category>/<id>_vN.wav` — 39 categories
- `audio/godot/ui/<id>/` — 10 UI sound dirs
- `audio/godot/music/<track>/` — 4 tracks
- `audio/godot/bus_layout.tres` — pre-configured Audio bus tree
- **640 files total**, all timestamped today after the re-export

## What works

- ✅ **Ambience is the strongest output in the project.** Real Stable Audio Open 1.0 GPU bake on all 10 biomes. 140 WAVs. LUFS-targeted per-layer. Each biome has a 4-layer authoring model (constant bed + sparse wildlife + rare distant events) which is the *correct* way to build game ambience.
- ✅ **Cue metadata per WAV** (`.cue.json`) — frame-synced trigger plumbing for runtime.
- ✅ **Adaptive music is genuinely well-designed.** 4 tracks with intent-driven intensity ramps + Godot bus layout. Drop-in production-quality structure (the *audio* may or may not be — you tell me).
- ✅ **SFX coverage hits the basics** — 39 unique IDs across combat/footsteps/UI/spells. 2-4 variants each (so randomized playback won't sound identical).
- ✅ **QA pipeline is real** — every SFX wav has a paired QA dir with spectrogram + waveform + LUFS metrics.
- ✅ **Godot export is fresh** — all 640 files match disk state, bus_layout.tres pre-wired.
- ✅ **Procedural music vs. generative music separation is honest** — adaptive_music.py is procedural (always works); YuE is parked at smoke-test stage (gated on weights + GPU time).

## What's open / weak

1. **Stable Audio Open is generating *short* bed_drones.** 19.6s. Designed for 30-second seamless loops, but post-processing trims/pads. **You'll hear if there's an audible loop seam every 19.6s** — the pipeline reports `seam_rms: 0.005` for forest's bed_drone, which is small but not zero.
2. **Wildlife layer count varies a lot per biome** (forest 10, swamp 12, but ice_cavern 6, mana_crystal 6). Inconsistent — either swamps deserve more variety than crystal caves, or the prompt set was uneven.
3. **No music has been auditioned**, by anyone. `adaptive_music.py` is procedural — the stems exist, but I have no read on whether the *music itself* sounds good. Could be elevator-tier, could be solid. **You'd know in 30 seconds.**
4. **YuE generative music is parked.** Single 4-second smoke test. Not a real attempt yet — gated on GPU window + license click for the YuE model weights.
5. **TTS lane is paper.** Tools exist (`local_tts_f5.py`, `openai_tts.py`), no output. Gated on game_data dialogue authoring.
6. **SFX is procedural-only.** Synth_sfx.py / synth_sfx_extended.py — no ElevenLabs cloud bakes (ELEVEN_API_KEY would activate that), no Freesound CC0 ingests in `audio/sfx/`. The 112 SFX wavs are all algorithmic.

## User verdict (2026-05-07) — content quality

After auditioning the samples: **"some are ok, but mostly they sound like noise/static."**

Verdict: **trash the current bakes, keep the workflows and pipelines.** Move forward with focused review/creation rather than continuing to ship procedural defaults.

This matches the pattern we saw in UI and VFX:
- **Pipeline plumbing is correct** — LUFS targets, 4-layer ambience model, adaptive music intent system, QA artifacts, Godot bus layout.
- **Procedural / unprompted-cloud output is placeholder-tier** — the audio version of UI's "color-swap factions" or VFX's "palette-swap spell grid."
- **The pipeline can produce real audio** when given real content authoring intent, just like VFX's blood/dust/spark cluster shows real physics tuning when an author cares.

**Action:** archive the current Phase 12 bake to `_archive/audio_phase12_bake_2026_05_07/`. Re-bake later with curated prompts + real reference recordings for SFX. Pipeline tooling stays.

## Pipeline-level read

- **State after audition:** **infrastructure is real, output is throwaway noise.** Same pattern as UI and VFX — pipeline plumbing solid, content placeholder.
- **Strongest part:** the LUFS authoring model, 4-layer ambience design, adaptive music intent system, QA artifacts per WAV. These are correct game-audio architecture and should not be touched.
- **Weakest part:** **everything currently in `audio/`.** Procedural SFX synth is generic-noise tier, Stable Audio Open ambience is unrefined-prompt tier, adaptive music stems are procedural-not-musical.
- **What "shipping quality" requires (the path forward):**
  - **SFX:** swap procedural synth for either curated CC0 recordings (Freesound via `cc0_ingest.py`) or ElevenLabs SFX (`eleven_sfx.py`). The cloud lane exists, we just never used it.
  - **Ambience:** carefully-prompted Stable Audio Open re-bakes per biome with reference audio conditioning, not the off-the-shelf prompts. Pipeline supports this; recipes never tuned.
  - **Music:** YuE generative model (gated on GPU + license) for the 4 tracks. Or commission real composed music. Adaptive_music.py procedural output isn't going to ship.
  - **TTS:** wait until dialogue exists.

## Concrete next moves

1. **Archive the current audio output** to `_archive/audio_phase12_bake_2026_05_07/`. Keep `audio/` as a structure but empty it of unusable content. Pipeline tools in `pipelines/audio/` untouched.
2. **Document the workflow itself as the deliverable** — what `pipelines/audio/biome_ambience.py` *can* produce given good prompts, what the LUFS targets are, what the 4-layer model looks like. The pipeline review proves the pipeline; the content was never the point.
3. **Defer real audio authoring** until there's specific game-design intent (e.g. "we need a forest scene right now"), at which point: tune the prompt, run the pipeline, audition, iterate. Same as we did with the obelisk — focused single-asset push, not broad procedural fill.

This becomes the canonical model for the rest of the per-pipeline reviews: separate the pipeline (asset) from the content (throwaway).

---

## Research-calibrated update (2026-05-07)

Brief #06 ([response](../research_briefs/2026_05_07_sota_survey/06_audio.response.md)) returned. **Most consequential brief since #02** — directly addresses the noise/static archive failure mode and surfaces real model upgrades for two of the three sub-lanes.

### Headline: noise/static was workflow, not model

The "189 MB archived May 2026" failure was a **prompt-quality + reference-conditioning** failure, not a Stable Audio Open model failure. The brief is direct: Stable Audio Open 1.0 stays — still the leading open-weights audio diffusion model in 2026. Stability went *closed* on the 2.x line; Open 1.0 is the canonical self-host target.

**The fix is reference clips + better QA, not a model swap.** Specifically:
- Current QA measures LUFS/peak/RMS/click — none of which fail on noise. **CLAP audio-text similarity** would have caught the failure pre-archive (cosine distance between prompt embedding and audio embedding is wide for noise).
- Current generation is text-only. **Adding reference-audio conditioning** (Stable Audio 2.5 cloud, or LoRA fine-tune on Open 1.0) is the actual workflow upgrade.

### Real upgrades for the OTHER two sub-lanes

**TTS (`local_tts_f5.py`):** **Chatterbox-Multilingual** (Resemble AI, MIT) is a near-strict upgrade — built-in emotion exaggeration + paralinguistic tags (`[laugh]`, `[sigh]`, `[chuckle]`), 17 languages, voice cloning from 5s, ~63% A/B win rate vs ElevenLabs. **MIT license = commercial OK.** F5 stays as fallback per our additive pattern.

**Music (`local_music_yue.py`):** **ACE-Step v1.5** (Jan 2026, Apache 2.0) supersedes YuE on game-tone benchmarks. Native multi-stem export via ControlNet-LoRA. **Apache 2.0 = commercial OK, royalty-free outputs.** `adaptive_music.py` runtime layer doesn't change — only the source stems do.

### Six action items, additive, in priority order

Per user direction 2026-05-07 PM: tooling additions go in side-by-side, not as drop-in replacements.

| # | Action | Type | Cost |
|---|---|---|---|
| 1 | ✅ **Done 2026-05-07 PM** — added **CLAP score** (`--clap-prompt`) + **PyMusicLooper seam validator** (`--loop-check`) to `audio_qa.py`. Default sanity-only path unchanged. Built `pipelines/audio/.venv` (py3.11 + torch 2.7+cu128). Verified on archived `bed_air.wav`: matching prompt = +0.407 ("matches"), unrelated prompt = -0.117 ("does_not_match") — discrimination solid | Additive QA | Done |
| 2 | Run `cc0_ingest.py` for real + extend with **PANNs auto-tagging** + **CLAP semantic index** | Per-biome reference library | 1-2 days |
| 3 | Wire **Stable Audio 2.5 cloud** OR train per-biome **LoRA on Stable Audio Open** (cloud parked per user direction; **LoRA path is the local alternative**) | Reference-conditioned ambience | 2 days local LoRA |
| 4 | Wire **AudioGen / MAGNeT** alongside `synth_sfx.py` | Self-hosted SFX peer | 1 day |
| 5 | Wire **ACE-Step v1.5** alongside `local_music_yue.py` for adaptive stems | Apache 2.0 successor | 1-2 days install |
| 6 | Wire **Chatterbox-Multilingual** alongside `local_tts_f5.py` | MIT TTS upgrade | 1 day |

### What NOT to do

- **Don't pursue Stable Audio 2.5 cloud** for now (cloud parked). LoRA fine-tuning on Stable Audio Open is the local alternative.
- **Don't keep investing in YuE.**
- **Don't tear out F5-TTS** — keep as Chatterbox fallback (per additive pattern).
- **Don't replace `synth_sfx.py` outright** — wire CC0 + AudioGen alongside; pick best per use case.
- **MusicGen-Stem caveat:** CC-BY-NC weights — non-commercial. ACE-Step is the commercial-safe choice.

### Texture worker impact

**None.** Audio is its own lane.
