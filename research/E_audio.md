# Assignment E - Audio Pipeline / SFX, Music, Voice

Date: 2026-05-06  
Scope: SFX, combat Foley, spell sounds, ambience, music loops, voice one-shots, trim/normalize/loop tooling, and Godot 4.5 import/export strategy.

## Executive Recommendation

The best 2026 audio stack is not one AI music model. It is a small asset factory:

1. **Primary AI SFX API:** [ElevenLabs Sound Effects](https://elevenlabs.io/docs/capabilities/sound-effects). It has a clean API, game/interactive use cases in the docs, controllable duration, prompt influence, and a loop option. It is the fastest path from natural language to usable combat/spell/UI/ambience sounds.
2. **Primary local/open audio generator:** [Stable Audio Open 1.0](https://huggingface.co/stabilityai/stable-audio-open-1.0) for local experiments and no-cloud prototyping. It can generate up to 47 seconds of stereo 44.1 kHz audio from text. Use it carefully: Stability's current community license allows free limited commercial use below the revenue threshold, but license terms must be checked before shipping.
3. **Primary free library source:** [Kenney audio packs](https://kenney.nl/assets?q=audio) for CC0 game-ready UI/RPG/impact/digital sounds, plus [Sonniss GameAudioGDC](https://gdc.sonniss.com/) for large royalty-free professional SFX bundles. Sonniss is commercially usable for media projects but explicitly disallows AI/ML training, so treat it as source assets only.
4. **Primary voice:** [ElevenLabs TTS / Voice Design](https://elevenlabs.io/text-to-speech-api) for expressive character voice and multi-speaker dialogue; [OpenAI `gpt-4o-mini-tts`](https://platform.openai.com/docs/guides/text-to-speech) for simple API-driven narration/one-shots when consistency and cost matter more than extreme character acting.
5. **Processing spine:** `ffmpeg` + `ffmpeg-normalize`/`pyloudnorm` + `librosa` + `soundfile`. This trims, fades, normalizes, detects onsets, checks loops, converts formats, writes metadata, and generates waveform/spectrogram previews.

For music, use AI as a sketch tool, not the first shipping dependency. [Suno v5.5](https://suno.com/blog/v5-5), [Google Lyria 3 Pro](https://blog.google/innovation-and-ai/technology/ai/lyria-3-pro/), Udio, and Stable Audio 2.5 are impressive, but legal/licensing/terms risks are higher for full tracks than for short SFX. For a solo Godot game, start with short ambient loops, stingers, and stems, then replace important tracks with commissioned, licensed, or clearly cleared music later.

## Current Local State

`D:\assets\audio\` currently contains only:

```text
audio\
  music\
  sfx\
```

There is no manifest, normalization pass, loop validator, Godot import preset, cue metadata, or audio preview page. That is acceptable; audio should be built as a new pipeline rather than patched onto an old one.

The recommended canonical asset shape:

```text
audio\sfx\spell\acid_splash_small\
  source.wav
  processed.wav
  preview.png
  spectrogram.png
  cue.json
  godot\acid_splash_small.tres

audio\music\forest_day_loop\
  source.wav
  loop.ogg
  stems\
  cue.json
```

`cue.json` should store `id`, `kind`, `source`, `license`, `prompt`, `model`, `seed/request_id`, `duration`, `loop`, `lufs`, `true_peak_db`, `format`, `bus`, `godot_node`, and any warnings.

## Tool Survey

| Tool/source | Role | License / interface | Differentiator | Caveat |
|---|---|---|---|---|
| [ElevenLabs Sound Effects](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert) | Text-to-SFX | Commercial API; `POST /v1/sound-generation` | Best practical cloud API for game SFX; supports duration, looping, prompt influence | Paid/cloud; generated output still needs auditioning |
| [Adobe Firefly Sound Effects](https://www.adobe.com/products/firefly/features/sound-effect-generator.html) | Text/voice-to-SFX | Commercially safe Adobe web tool | Strong UX and "act it out" timing workflow | Web/GUI first; weak LLM automation unless API access appears |
| [Stable Audio Open](https://huggingface.co/stabilityai/stable-audio-open-1.0) | Local text-to-audio | Stability community license; local PyTorch/diffusers | Local generation, 47s stereo output, good for ambiences and experimental SFX | Model is 2024, slower than API, license must be watched |
| [Stable Audio 2.5](https://stability.ai/stable-audio) / [fal API](https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/api) | Cloud music/SFX | Commercial API through providers | Higher-quality current Stability model; text-to-audio and audio-to-audio | Cloud cost and provider terms |
| [Meta AudioBox](https://ai.meta.com/blog/audiobox-generating-audio-voice-natural-language-prompts/) | Research reference | Research; demo discontinued as of Feb 2026 | Important paper/model concept for unified speech+sound prompting | Not a practical production tool now |
| [AudioCraft / MusicGen / AudioGen](https://ai.meta.com/resources/models-and-libraries/audiocraft/) | Local research generator | Open research code/models; model licenses vary | Useful baseline for older local text-to-music/SFX | Behind 2026 cloud quality; not first choice |
| [Suno v5.5](https://suno.com/blog/v5-5) | AI music sketching | Web product; API access mostly third-party/unofficial | Fast full songs, vocals, structure, personalized models | Copyright/legal uncertainty and weak headless official workflow |
| [Google Lyria 3 Pro](https://blog.google/innovation-and-ai/technology/ai/lyria-3-pro/) | AI music | Gemini/Vertex/AI Studio/Gemini API rollout; SynthID watermarking | 2026 current music model, up to 3-minute structured tracks | Still new; terms and access limits matter |
| [Udio](https://www.udio.com/) | AI music | Web product; no clean official pipeline found | Strong genre/mix quality reputation | Legal/terms and headless automation risk |
| [ElevenLabs TTS](https://elevenlabs.io/docs/overview/capabilities/text-to-speech) | Character voice | Commercial API | Very expressive; Eleven v3 supports audio tags and multi-speaker dialogue | Voice cloning requires consent discipline |
| [OpenAI TTS](https://platform.openai.com/docs/guides/text-to-speech) | Narration/voice one-shots | Commercial API | Simple, steerable `gpt-4o-mini-tts`, multiple formats, streaming | Built-in voices are less character-specific than cloned/designed voices |
| [Coqui XTTS-v2](https://huggingface.co/coqui/XTTS-v2) | Local voice fallback | Coqui Public Model License | Local voice cloning from short reference clips | License is non-commercial; not a shipping default |
| [Kenney audio](https://kenney.nl/assets?q=audio) | CC0 source library | CC0 | Game-ready, small, clean packs for UI/RPG/impact/digital sounds | Stylized/simple, not cinematic |
| [Sonniss GDC bundles](https://sonniss.com/gameaudiogdc/) | Pro source library | Royalty-free media production license | Huge professional SFX archive, commercial use, no attribution | No AI training; large downloads; not all assets are organized for instant use |
| [Freesound API](https://freesound.org/docs/api/) | Searchable SFX library | API; mixed CC licenses | Search/download metadata, packs, descriptors, similar sounds | Must filter license, attribution, quality, noise |
| [jsfxr/Jfxr/Bfxr](https://github.com/chr15m/jsfxr), [Jfxr](https://github.com/ttencate/jfxr) | Procedural retro SFX | Unlicense/BSD/Apache variants | Deterministic UI/coin/laser/jump sounds; perfect for LLM parameter generation | Retro/chiptune style only |
| [FFmpeg loudnorm](https://ffmpeg.org/ffmpeg-filters.html#loudnorm), [ffmpeg-normalize](https://github.com/slhck/ffmpeg-normalize) | Batch processing | Open source CLI/Python | Reliable conversion and EBU R128 loudness normalization | Needs careful target choices for game categories |
| [pyloudnorm](https://pypi.org/project/pyloudnorm/), [librosa](https://librosa.org/doc/latest/index.html) | QA/analysis | Python libraries | LUFS, peak, silence/onset detection, tempo/loop analysis | More code to write, but very controllable |

## What Is Actually SOTA In 2026

For **short SFX**, ElevenLabs is the practical winner because the API is built for exactly this job. The docs expose game/interactive use cases, optional exact duration, looping, prompt influence, and output formats including MP3 and WAV/PCM depending tier/model. It is not "perfect", but it is directly automatable and much easier to wire into an LLM-driven asset factory than a web-only tool.

For **commercially safe guided SFX**, Adobe Firefly is strong because it lets a human record mouth sounds/timing and turn that into a designed effect. That is excellent for video-aligned Foley, footsteps, and impacts. The weakness is automation: a GUI tool is not the backbone for this project unless Adobe exposes the needed API access.

For **local SFX/music**, Stable Audio Open is the best practical install target. It is not the newest model, but it runs locally through `stable-audio-tools` or Diffusers, and the outputs are long enough for ambiences and loops. AudioBox is not recommended because Meta states its demo is no longer available as of February 2026; it remains research context, not a production path.

For **music**, the SOTA is moving quickly. Suno v5.5 is current as of March 26, 2026, with stronger personalization, custom models, and voices. Google Lyria 3 Pro is also current, creates up to 3-minute structured tracks, and is rolling out through Vertex AI, Google AI Studio, Gemini API, Gemini, and Google Vids. These are credible for prototypes, menu loops, trailers, and mood boards. For shipping game music, use caution: generated full songs create higher rights, platform, and style-consistency risk than short generated SFX.

For **voice**, ElevenLabs is still the highest-control character voice platform. OpenAI TTS is the cleanest general-purpose API fallback: `gpt-4o-mini-tts` supports steerable instructions, several voices, streaming, and output formats like MP3, Opus, AAC, FLAC, WAV, and PCM. Coqui XTTS-v2 is useful because it may already be cached locally, but the model license is non-commercial, so it should be a research/offline placeholder only.

## Recommended Pipeline

### Stage 1: Ingest and Generate

Support four source modes:

- `library`: Kenney, Sonniss, Freesound filtered to CC0/compatible licenses.
- `ai_sfx`: ElevenLabs first; Stable Audio Open local fallback.
- `ai_voice`: ElevenLabs or OpenAI TTS; XTTS-v2 only for non-commercial scratch work.
- `procedural`: jsfxr/Jfxr-style parameter generation for UI, pickups, retro beeps, simple hits.

The LLM should produce a structured request, not just a prompt:

```json
{
  "id": "fireball_cast_small",
  "kind": "sfx",
  "source_mode": "ai_sfx",
  "prompt": "short magical fireball cast, dry ignition, airy whoosh, no explosion tail",
  "duration": 0.8,
  "loop": false,
  "variants": 6,
  "category": "spell",
  "bus": "SFX"
}
```

### Stage 2: Process

Every source should pass through:

- trim leading/trailing silence,
- optional de-noise/high-pass for bad library recordings,
- fade in/out of 5-30 ms for one-shots,
- loop crossfade for ambience/music,
- loudness normalization,
- true-peak limiting,
- sample-rate/channel conversion,
- waveform and spectrogram preview.

Use FFmpeg for conversion and loudnorm, `pyloudnorm` for analysis/validation, and `librosa` for silence/onset/tempo checks.

Suggested initial loudness targets:

- UI: around -22 to -20 LUFS, true peak <= -1 dBTP.
- Combat/spell one-shots: around -18 to -16 LUFS, true peak <= -1 dBTP.
- Voice one-shots/dialogue: around -18 LUFS, true peak <= -1 dBTP.
- Ambience: around -28 to -24 LUFS, true peak <= -2 dBTP.
- Music loops: around -23 to -18 LUFS depending density, true peak <= -1 dBTP.

These are starting targets. The game bus mix should decide final perceived balance.

### Stage 3: Package for Godot

Godot 4.5 supports WAV, Ogg Vorbis, and MP3. The docs state WAV is lightweight to play on CPU but large, while Ogg is smaller but heavier to decode; MP3 sits between them. Use:

- **WAV** for short, frequent SFX and UI sounds.
- **Ogg Vorbis** for music, ambience, and long voice.
- **MP3** only when compatibility/distribution size matters and loop precision is less important.

Export a `.tres` or `.import` companion plus a cue table. For playback:

- non-positional UI/menu audio: `AudioStreamPlayer`;
- in-world 2D sounds: `AudioStreamPlayer2D`;
- randomized repeated one-shots: `AudioStreamRandomizer`;
- music layers/playlists: `AudioStreamPlaylist`, `AudioStreamSynchronized`, or a small custom music manager.

Create Godot buses early: `Master`, `Music`, `Ambience`, `SFX`, `UI`, `Voice`, `ReverbSend`, `DuckSidechain`.

## Test Plan

Test five asset classes:

1. **UI click pack:** generate 20 variants with jsfxr/Jfxr and compare to Kenney Interface Sounds.
2. **Combat impacts:** Kenney/Sonniss source + ElevenLabs generated variants; success is clear transient, no clipped tail, consistent loudness.
3. **Spell cast:** ElevenLabs prompt variants + Stable Audio Open local variant; success is 0.5-1.2s readable sound with no mush.
4. **Ambient loop:** ElevenLabs loop mode or Stable Audio Open 20-30s ambience; success is no audible loop seam after 10 repeats.
5. **NPC bark:** ElevenLabs v3 and OpenAI TTS; success is intelligible, emotionally directed, and licensed/consented voice.

Concrete pass criteria:

- waveform/spectrogram preview exists,
- no clipped samples,
- loudness within target band,
- true peak under target,
- loop seam RMS delta below threshold for loops,
- exported Godot resource loads,
- `cue.json` includes source/license/model/prompt.

## Integration Effort

- Manifest + folder contract: 2-4 hours.
- FFmpeg/pyloudnorm processing script: 4-8 hours.
- Waveform/spectrogram preview: 2-4 hours.
- Kenney/Sonniss/Freesound ingesters: 4-10 hours, depending API/auth/download choices.
- ElevenLabs SFX adapter: 2-4 hours once API key handling is available.
- OpenAI/ElevenLabs TTS adapter: 2-5 hours.
- Stable Audio Open local runner: 4-12 hours depending CUDA/PyTorch friction.
- Godot exporter/cue table: 4-8 hours.

## Starter Kit

Start with four pieces:

1. **ElevenLabs Sound Effects** for custom SFX and loops.
2. **Kenney CC0 audio + Sonniss GDC** for immediate source libraries.
3. **FFmpeg + pyloudnorm + librosa** for trim, normalize, loop QA, previews, and conversion.
4. **OpenAI TTS or ElevenLabs TTS** for voice one-shots; use ElevenLabs for character acting and OpenAI for simple reliable API speech.

Add Stable Audio Open after the processing/export spine is working. Add Suno/Lyria/Udio only as music sketching tools until the licensing and export terms are clear enough for shipping.

## Sources

- ElevenLabs Sound Effects and TTS: https://elevenlabs.io/docs/capabilities/sound-effects, https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert, https://elevenlabs.io/text-to-speech-api, https://elevenlabs.io/docs/overview/capabilities/text-to-speech
- OpenAI TTS/audio docs: https://platform.openai.com/docs/guides/text-to-speech, https://platform.openai.com/docs/guides/audio
- Stable Audio: https://huggingface.co/stabilityai/stable-audio-open-1.0, https://stability.ai/stable-audio, https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/api
- Google Lyria and SynthID: https://blog.google/innovation-and-ai/technology/ai/lyria-3-pro/, https://gemini.google/overview/music-generation/, https://deepmind.google/en/models/synthid/
- Suno: https://suno.com/blog/v5-5, https://help.suno.com/en/articles/11362305
- Meta AudioBox / AudioCraft: https://ai.meta.com/blog/audiobox-generating-audio-voice-natural-language-prompts/, https://ai.meta.com/research/publications/audiobox-unified-audio-generation-with-natural-language-prompts/, https://ai.meta.com/resources/models-and-libraries/audiocraft/
- Coqui XTTS-v2: https://huggingface.co/coqui/XTTS-v2, https://docs.coqui.ai/en/latest/models/xtts.html
- Source libraries: https://kenney.nl/assets?q=audio, https://gdc.sonniss.com/, https://sonniss.com/gameaudiogdc/, https://freesound.org/docs/api/
- Processing tools: https://ffmpeg.org/ffmpeg-filters.html#loudnorm, https://github.com/slhck/ffmpeg-normalize, https://pypi.org/project/pyloudnorm/, https://librosa.org/doc/latest/index.html
- Procedural SFX: https://github.com/chr15m/jsfxr, https://github.com/ttencate/jfxr, https://github.com/increpare/bfxr
- Godot audio docs: https://docs.godotengine.org/en/4.5/classes/class_audiostream.html, https://docs.godotengine.org/en/4.5/classes/class_audiostreamplayer2d.html, https://docs.godotengine.org/en/4.5/classes/class_audiostreamplaylist.html
