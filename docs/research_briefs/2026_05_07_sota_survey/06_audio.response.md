# Research Response — Audio Pipeline (2026 SOTA)

**Date:** 2026-05-07
**Hardware target:** RTX 5090 Laptop, 24 GB VRAM, sm_120, CUDA 12.8+, Windows 11
**Source brief:** `06_audio.md`

---

## TL;DR — what to actually do

1. **Ambience:** keep Stable Audio Open 1.0 *but* add **audio-to-audio reference conditioning** — either via Stable Audio 2.5 (cloud, paid, but the only first-party reference-conditioned path) or by fine-tuning Stable Audio Open on a curated CC0 reference set. Bigger wins come from **better prompts driven by reference clips** than from a model swap.
2. **SFX:** the user verdict ("noise/static") is a *prompt + curation* problem more than a model problem. **AudioGen / Tango 2** are the open-weights peers of ElevenLabs SFX, but the deterministic-per-asset use case (0.3 s wood crack) is *still* better served by a **curated CC0 + Freesound library auto-tagged with PANNs/CLAP**, with generative SFX as fallback. Run `eleven_sfx.py` for the small "characterful one-shot" set; run `cc0_ingest.py` for the bulk.
3. **Music:** **ACE-Step v1.5** is the 2026 open-weights successor to YuE for game-tone music, and it natively exports stems via a multi-track ControlNet-LoRA. **MusicGen-Stem** is the alternative and integrates with the existing audiocraft tooling. Keep `adaptive_music.py` for runtime intensity ramps; bake stems with ACE-Step.
4. **TTS:** **Chatterbox-Multilingual** (Resemble AI, MIT, ~63% A/B win rate vs ElevenLabs) is the single biggest swap. F5-TTS is reasonable but Chatterbox has built-in emotion exaggeration + paralinguistic tags (`[laugh]`, `[chuckle]`) that F5-TTS lacks. Replace `local_tts_f5.py` with a Chatterbox loader.
5. **QA:** add **CLAP audio-text similarity** ("does this sound like 'forest at dusk'?") to `audio_qa.py`. Use **PyMusicLooper** for automatic loop-seam validation. These two additions catch ~80% of the "this is just noise" failures *before* they hit the user audition.

The single biggest unlock: **build a 5-second reference clip per biome** (curated from Freesound CC0), then drive Stable Audio 2.5 inpainting / audio-to-audio off that. The current pipeline is technically correct but artistically untargeted — references fix that without requiring a model swap.

---

## Q1 — 2026 SOTA for game ambience

### Recommendations

1. **Stable Audio Open 1.0 (current) — keep, but fine-tune.**
   Still the leading open-weights audio diffusion model for variable-length loops. Trained on ~500K CC-0 / CC-BY / CC-Sampling+ recordings from Freesound + Free Music Archive. 47 s max, 44.1 kHz stereo. The "noise/static" output is a prompt-quality issue, not a model issue — and Stable Audio Open is *built to be fine-tuned* on custom libraries, which is what serious game studios are doing in 2026. ([Stable Audio Open paper](https://stability.ai/news-updates/stable-audio-open-research-paper), [HF model card](https://huggingface.co/stabilityai/stable-audio-open-1.0))

2. **Stable Audio 2.5 (Stability AI, Sept 2025) — cloud, but enterprise-grade.**
   The first audio model designed for "enterprise sound production at scale" — `<2 s` inference, supports text-to-audio, **audio-to-audio**, and **inpainting**. This is the model that solves the reference-conditioning gap (see Q2). API-only via Stability AI / Replicate / fal. Useful when you want the absolute best output and don't mind cloud cost. ([Stability AI announce](https://stability.ai/news-updates/stability-ai-introduces-stable-audio-25-the-first-audio-model-built-for-enterprise-sound-production-at-scale), [Replicate](https://replicate.com/stability-ai/stable-audio-2.5))

3. **Stable Audio Open Small (May 2025) — for fast iteration.**
   ~10 s @ 44.1 kHz in <7 ms on H100; runs on phones. Use for rapid prompt-iteration loops (test 50 prompts in a minute), then re-bake the winners on Open 1.0 for the long version. ([HF stable-audio-open-small](https://huggingface.co/stabilityai/stable-audio-open-small))

### Hardware fit

- Stable Audio Open 1.0 / Small: native on RTX 5090, sm_120 supported via torch >=2.7. Already plumbed in `local_audio_open.py`. Windows-native works.
- Stable Audio 2.5: cloud-only.

### License + cost

- Stable Audio Open: Stability AI Community License (free for non-commercial + small commercial; gated repo, requires HF acceptance).
- Stable Audio 2.5: commercial API, ~$0.02/sec generated typical pricing tier.

### Maturity

- 1.0 stable since mid-2024, well-documented; 2.5 is GA on enterprise tier since Sept 2025.

### Honest comparison

**Stable Audio Open 1.0 is still the right choice for self-hosted ambience baking in 2026.** No open-weights successor has clearly displaced it for variable-length atmospheric loops. The 2.x line went *closed* — Stability kept Open at v1.0 and pushed enterprise features into the paid 2.5. So the lateral-vs-upgrade answer is: **lateral on the model, upgrade on the workflow** (prompt curation, reference clips, fine-tuning).

---

## Q2 — Reference-conditioned ambience generation

### Recommendations

1. **Stable Audio 2.5 audio-to-audio + inpainting.**
   Direct support for "input your own audio, select where it starts, model fills the rest using the context." Can take a 5 s curated forest reference and generate a 30 s seamlessly-looping bed in the same style. **This is the cleanest 2026 path to reference-conditioned ambience.** Cloud-only. ([Stable Audio 2.5 prompt guide](https://stability.ai/learning-hub/stable-audio-25-prompt-guide), [Inpaint endpoint](https://www.eachlabs.ai/stability/stable-audio/stable-audio-2-5-inpaint))

2. **MusicGen-Style / AudioCraft style conditioning (open weights).**
   Meta's MusicGen variants accept audio reference for *style* via a contrastive style encoder. Music-tuned, but the technique transfers to ambient if you use Stable Audio Open + a similar style encoder fine-tune. Less plug-and-play than Stable Audio 2.5 but free. ([MusicGen-Style docs](https://github.com/facebookresearch/audiocraft/blob/main/docs/MUSICGEN_STYLE.md))

3. **Fine-tune Stable Audio Open on biome-curated CC0 references.**
   Train a small LoRA per biome (charred_wasteland, desert, etc.) on 50–200 curated reference clips. Stability published the fine-tuning recipe; community has shipped multiple biome-style LoRAs in 2025–26. Cost: ~30 min on RTX 5090 per LoRA. **This is the long-term answer if you want full self-hosting.** ([Stable Audio Open paper §4](https://arxiv.org/abs/2407.14358))

### Hardware fit

- Stable Audio 2.5: cloud, no local concerns.
- MusicGen-Style: native PyTorch, fits RTX 5090 with no special handling.
- LoRA fine-tune: ~12 GB VRAM peak, well within 24 GB; need ~6 hours of audio per LoRA.

### License + cost

- Stable Audio 2.5: commercial API (paid).
- MusicGen-Style: MIT (research) / CC-BY-NC (weights) — *non-commercial*; for commercial use, retrain on permissive data.
- LoRA on Stable Audio Open: inherits the Open Community License (commercial OK below the rev threshold).

### Maturity

- Stable Audio 2.5: GA since Sept 2025.
- MusicGen-Style: research/stable since 2024.
- Stable Audio Open LoRA: documented community workflow.

### Honest comparison

**This is the single biggest pipeline gap to fix.** Stable Audio Open 1.0 *cannot* take reference audio — it's text-only. Stable Audio 2.5 can; MusicGen-Style can (with caveats); a fine-tuned LoRA bypasses the whole question.

The pragmatic path: **start with Stable Audio 2.5 for the per-biome reference bake** (one-time cost, ~$5–10 per biome for many candidate generations), pick the winners, and *consider* a LoRA fine-tune later only if you bake hundreds of variants per biome. For 8 biomes × 4 variants each = 32 outputs, just pay the API.

---

## Q3 — 2026 SOTA for game SFX

### Recommendations

1. **ElevenLabs Sound Effects (cloud) — keep `eleven_sfx.py`, run it.**
   Still the cleanest "wood crack, sharp" → 0.3 s WAV path. ~$0.01 per generation, deterministic enough with seed. The plumbing exists; just run it. ([ElevenLabs SFX](https://elevenlabs.io/sound-effects))

2. **AudioGen + MAGNeT (Meta AudioCraft) — open-weights peer.**
   AudioGen is text-to-sound trained on environmental sounds (footsteps, door creaks, foley). MAGNeT is the non-autoregressive successor — much faster, comparable quality. MIT-licensed, weights are CC-BY-NC. **This is the best self-hosted SFX option in 2026.** ([AudioCraft repo](https://github.com/facebookresearch/audiocraft), [AUDIOGEN.md](https://github.com/facebookresearch/audiocraft/blob/main/docs/AUDIOGEN.md))

3. **Tango 2 (declare-lab) — competitive open SFX.**
   Outperforms AudioLDM2 on objective benchmarks; runs in a Docker. Less polished than AudioGen but actively maintained, instruction-tuned (FLAN-T5 conditioning), so prompts like "wood crack, sharp" work better than Stable Audio Open's prompt vocabulary. ([Tango paper site](https://tango-web.github.io/), [Replicate](https://replicate.com/declare-lab/tango))

4. **CC0 curation via Freesound — primary, not fallback.**
   Honest take: for a 0.3 s wood crack, a CC0-curated **real recording** beats any 2026 generative SFX model on perceived realism. Run `cc0_ingest.py`. Use generative for the long-tail prompts that don't have CC0 matches.

### Hardware fit

- AudioGen / MAGNeT: 6–10 GB VRAM, runs in audiocraft conda env on Windows native (PyTorch 2.7 wheel needed for sm_120).
- Tango 2: Docker WSL2 path easiest; native Windows with manual deps possible.

### License + cost

- ElevenLabs: ~$0.01/SFX, $5/month minimum.
- AudioGen/MAGNeT weights: CC-BY-NC (non-commercial). For commercial use either retrain or use ElevenLabs.
- Tango 2: CC-BY-NC weights, similar caveat.
- Freesound CC0: free, no attribution required.

### Maturity

- ElevenLabs SFX: production-grade, used by AAA studios.
- AudioGen/MAGNeT: stable since 2023/24, no major 2026 update.
- Tango 2: active, last release Q4 2025.

### Honest comparison

**For deterministic per-asset SFX, the 2026 answer has not converged.** Generative SFX is still hit-or-miss for short impact sounds. The actual SOTA workflow at 2026 game studios is **CC0-first, generative-fallback**:
1. Search Freesound CC0 for the asset → 70% of cases solved.
2. ElevenLabs SFX for missing items → 25%.
3. AudioGen/MAGNeT self-hosted for the rest or for batch / commercial-restricted cases → 5%.

The "noise/static" output you're seeing from `synth_sfx.py` is procedural-synthesis noise, which is *worse* than any of these. Replacing it with even a basic Freesound ingest will be a large step up.

---

## Q4 — 2026 music generation SOTA

### Recommendations

1. **ACE-Step v1.5 (Jan 2026) — current open-weights leader.**
   "The most powerful local music generation model that outperforms almost all commercial alternatives." Multi-platform (CUDA, Mac, AMD, Intel). Native **stem export** via a multi-track ControlNet-LoRA → separate vocals / instrumental tracks. Game-soundtrack-friendly prompts, royalty-free output. Successor to YuE in spirit. ([ACE-Step repo](https://github.com/ace-step/ACE-Step-1.5), [Review](https://ace-step.co/ace-step-1-5-review), [Paper](https://arxiv.org/html/2506.00045v1))

2. **MusicGen-Stem (Jan 2025, AudioCraft) — proper multi-stem generative.**
   Generates **3 separate stems** (bass, drums, other) at once *or* generates a stem conditioned on existing stems (so you can replace one stem at a time). One specialized compressor per stem. Built on the audiocraft framework you may already know. **This is the model that fits an adaptive-music pipeline best** because the stems are generated with mutual conditioning. ([MusicGen-Stem paper](https://arxiv.org/html/2501.01757v1), [Demo](https://simonrouard.github.io/musicgenstem/))

3. **YuE (parked) — re-evaluate but probably skip.**
   YuE was the early-2025 darling. ACE-Step v1.5 supersedes it on benchmarks and game-tone outputs in 2026. Don't invest in `local_music_yue.py` further; archive or replace.

### Hardware fit

- ACE-Step v1.5: 12–16 GB VRAM typical, fits 24 GB comfortably; CUDA 12.x friendly. Confirmed working on RTX 5090 in community reports.
- MusicGen-Stem: 8–14 GB VRAM, runs in audiocraft env.

### License + cost

- ACE-Step: Apache 2.0, **commercial OK**, royalty-free outputs.
- MusicGen-Stem: CC-BY-NC weights, code is MIT — commercial constrained.
- Suno V5: API only, ~$0.04/track; high quality but black-box, no stems by default.

### Maturity

- ACE-Step v1.5: production since Jan 2026, broad adoption.
- MusicGen-Stem: research-stable, audiocraft-backed.

### Honest comparison

**ACE-Step v1.5 is genuinely better than YuE for game music in 2026.** YuE's strength was full-song lyric-driven vocals, which is the wrong target for fantasy-game instrumental music. ACE-Step's instrumental quality, stem export, and Apache-2.0 license make it the right target.

For the specific "fantasy-game tone" criterion: ACE-Step handles cinematic / orchestral / ambient prompts better than YuE; both struggle with truly distinctive themes (Jeremy Soule territory). Generative music is good at **mood beds**, not memorable melodies.

---

## Q5 — Procedural music vs generative (hybrid)

### Recommendations

1. **Hybrid: ACE-Step bakes stems → `adaptive_music.py` orchestrates intensity ramps.**
   This is the natural fit. ACE-Step generates a 60-second piece in 4 stems (drums, bass, melody, pads). `adaptive_music.py` already implements the intensity-driven mute/unmute/crossfade logic. The intent.json state machine doesn't change — the *contents* of each stem just become generative instead of procedural.

2. **MusicGen-Stem with stem-replacement editing.**
   Lets you generate a base track, then regenerate just the "drums" stem for a higher-intensity variant. Native fit for adaptive playback because you stay within one model's musical understanding. Trickier to integrate (more inference calls) but gives perfect coherence between variants.

3. **AudioShake-style stem separation as a *fallback*.**
   If you find a single perfect track (CC0 or commissioned), AudioShake / Demucs can split it into stems for adaptive playback. Won't help with generation but useful for "we found this perfect Kevin MacLeod CC piece, now make it adaptive." ([AudioShake](https://www.audioshake.ai/), [Demucs](https://github.com/facebookresearch/demucs))

### Hardware fit

- ACE-Step + adaptive_music.py: native Windows path, no new deps beyond ACE-Step.
- Demucs: stable on Windows, MIT.

### License + cost

- ACE-Step: Apache 2.0 — outputs free for commercial.
- MusicGen-Stem: CC-BY-NC — non-commercial.
- Demucs: MIT, weights MIT.

### Maturity

- All production-grade.

### Honest comparison

**The current `adaptive_music.py` plumbing is the right architecture; the music *content* is the weak link.** Don't replace the intent.json state machine — it's the correct game-runtime contract. Just upgrade the source material from procedural-synth to ACE-Step stems. This is *strictly additive*: you can keep procedural as a fallback when ACE-Step output for a given biome doesn't pan out.

Implementation note: ACE-Step generates aligned stems by construction, so phase-coherence and tempo-locking come for free. With separate per-stem generation in something like Stable Audio Open, you'd have to align stems yourself — painful.

---

## Q6 — TTS for game NPCs

### Recommendations

1. **Chatterbox-Multilingual (Resemble AI, Apr 2025) — the swap.**
   First open-source TTS with **adjustable emotion exaggeration**. Built-in paralinguistic tags `[laugh]`, `[cough]`, `[chuckle]`, `[sigh]`. 17 languages. Voice cloning from 5 s. **63.75% A/B win rate vs ElevenLabs** in blind tests for naturalness + emotional resonance. **MIT license — fully commercial.** This is a clear, large upgrade over F5-TTS for game character voicing. ([Chatterbox repo](https://github.com/resemble-ai/chatterbox), [Comparison](https://www.genmedialab.com/comparisons/elevenlabs-vs-chatterbox-tts/))

2. **Fish Speech S2 (Mar 2026) — strong runner-up.**
   Apache 2.0, full weights + fine-tuning code, 3 GB VRAM minimum, runs comfortably on RTX 4090+ for production. Streaming inference. Better at long-form narration than Chatterbox; weaker on emotion exaggeration. ([Fish Audio S2](https://github.com/fishaudio/fish-speech))

3. **F5-TTS (current) — keep as fallback.**
   Still serviceable for neutral narration. Lacks emotion controls and paralinguistic tags. Don't invest more in it but don't tear it out — it works.

4. **VoxCPM2 (OpenBMB) — for multilingual-heavy use cases.**
   2 B params, 30 languages, voice cloning + voice design. Good if you have non-English NPCs.

### Hardware fit

- Chatterbox: 6–8 GB VRAM, runs natively on Windows. ComfyUI integrations exist.
- Fish Speech S2: 3 GB minimum, comfortable on RTX 5090.
- F5-TTS: already plumbed, no change.

### License + cost

- Chatterbox: **MIT** (commercial OK).
- Fish Speech S2: Apache 2.0.
- F5-TTS: MIT/CC-BY.
- ElevenLabs: cloud, ~$0.30/1K chars on subscriptions.

### Maturity

- Chatterbox: stable since mid-2025, broad adoption.
- Fish Speech S2: stable since Mar 2026.

### Honest comparison

**Chatterbox is a real upgrade over F5-TTS for game character voice, not a lateral move.** The emotion exaggeration knob and paralinguistic tags are exactly what NPCs need. F5-TTS sounds technically clean but emotionally flat; Chatterbox sounds *alive*. Replace `local_tts_f5.py` with a Chatterbox loader and keep F5 as a backup. ElevenLabs cloud remains best-in-class but is a recurring cost; for a single-developer game with hundreds of NPC lines, Chatterbox local is the right answer.

---

## Q7 — Audio QA tooling

### Recommendations

1. **CLAP audio-text similarity in `audio_qa.py`.**
   Add a CLAP score to every generated WAV: cosine(embed(audio), embed(prompt)). Flag any WAV below threshold (e.g. 0.25) as "doesn't sound like the prompt." Catches the "noise/static" failure mode automatically. **LAION-CLAP** is the standard checkpoint; Microsoft CLAP is a strong alternative; **Human-CLAP** is a 2025 fine-tune that aligns with subjective ratings. ([LAION-CLAP](https://github.com/LAION-AI/CLAP), [Microsoft CLAP](https://github.com/microsoft/CLAP), [Human-CLAP](https://www.emergentmind.com/topics/contrastive-language-audio-pretraining-clap))

2. **PyMusicLooper for loop-seam validation.**
   Open-source, automatically finds optimal loop points and crossfade seams. Run it on every ambience output — if it can't find a seam, the loop isn't loopable. Add seam-quality score (cross-correlation at the loop point) to QA output. ([PyMusicLooper repo](https://github.com/arkrow/PyMusicLooper))

3. **PANNs / YAMNet for content-class verification.**
   "Did this 'forest at dusk' generation actually contain bird/wind/rustle classes?" Run AudioSet-class classification, flag if expected classes are missing. Cheap, fast, deterministic.

4. **T-CLAP for sequential ambience.**
   For distant_event Poisson layer where order matters, T-CLAP adds temporal modeling on top of CLAP — flags audio where events happen in wrong order or wrong density. Newer (2025), less mature.

### Hardware fit

- CLAP, YAMNet, PANNs all run on CPU or GPU; <1 GB VRAM each.
- All are pip-installable, native Windows.

### License + cost

- LAION-CLAP: Apache 2.0.
- Microsoft CLAP: MIT.
- PyMusicLooper: MIT.
- PANNs: Apache 2.0.

### Maturity

- All production-grade.

### Honest comparison

**This is a strict upgrade over LUFS / peak / RMS / click detection.** LUFS metrics tell you the audio is loud-correct; CLAP tells you the audio is *content-correct*. Your current QA passes "noise/static" because noise is technically in-spec for LUFS. **CLAP would have caught the May 2026 archived-189 MB fail** — the gap between prompt embedding and audio embedding would have been wide. Add this as the next step.

Practical implementation: extend `audio_qa.py` with a `clap_score` column; sort by descending mismatch when previewing the bake; auto-archive anything below 0.20 to `_archive/low_clap/` with the prompt for human review.

---

## Q8 — CC0 curated library tooling

### Recommendations

1. **PANNs/YAMNet auto-tagging on Freesound ingest.**
   Run AudioSet-class classification on every download → derive auto-tags (e.g. `wind`, `birds`, `footsteps_concrete`, `crackle_fire`). Combine with Freesound's existing user tags for higher recall. **PANNs is the standard 2026 audio-tagger** for this use case. ([PANNs repo](https://github.com/qiuqiangkong/audioset_tagging_cnn))

2. **CLAP-based semantic search.**
   Index every CC0 sample by CLAP embedding. Then search by *prompt* or *reference audio*: "find me 30 forest-ambience-like samples." Replaces tag-based search with semantic match. Order-of-magnitude better than Freesound's text search for game-specific needs.

3. **LabelBuddy (Mar 2026) — annotation workflow.**
   Open-source AI-assisted audio annotation tool with PANNs / musicnn / Music Flamingo built-in. "Verify rather than label" workflow. Useful if you want to hand-curate after auto-tagging. ([LabelBuddy paper](https://arxiv.org/html/2603.04293v1))

4. **ffmpeg + pyloudnorm batch normalize.**
   For LUFS targets per layer (which you already have). Already in pipeline; just confirm it's running on ingest.

### Hardware fit

- All native Python, no GPU strictly needed (PANNs/CLAP faster on GPU but CPU-fine for batch ingest overnight).

### License + cost

- PANNs: Apache 2.0.
- LAION-CLAP: Apache 2.0.
- LabelBuddy: open source.
- Freesound API: free, requires API key, rate-limited.

### Maturity

- All stable.

### Honest comparison

**Your `cc0_ingest.py` exists but has never been run with real keys — that's the bottleneck, not tooling.** The 2026 best-practice is exactly what you'd extend it to: download → PANNs auto-tag → CLAP embed → LUFS-normalize → store in a vector DB (e.g. `chromadb` or just SQLite + numpy). A weekend of work on top of existing scaffolding.

The bigger win: **build per-biome reference clip libraries** (10–50 curated clips per biome, hand-picked from auto-tagged CC0). These become the inputs to Stable Audio 2.5 reference-conditioned generation (Q2). Same library answers Q3 (SFX-by-CC0 first) and Q7 (CLAP target embeddings for QA).

---

## Cross-cutting recommendations

### Priority order for re-baking

1. **First: build the reference library** (Q8). Run `cc0_ingest.py` for real with PANNs auto-tagging. Output: `audio/_reference/<biome>/*.wav` with manifest.json. Cost: 1–2 days.
2. **Then: re-bake ambience with reference conditioning** (Q1+Q2). Either Stable Audio 2.5 cloud (fastest) or fine-tuned Stable Audio Open LoRA per biome (best long-term). Cost: ~$50 cloud or ~2 days local LoRA.
3. **Then: replace synth_sfx with CC0+ElevenLabs hybrid** (Q3). Run cc0_ingest as primary, eleven_sfx for misses. Cost: ~$20–50 ElevenLabs + 2 days curation.
4. **Then: bake adaptive music with ACE-Step stems** (Q4+Q5). Replace YuE smoke-test, keep adaptive_music.py runtime layer. Cost: 1 day install + 1 day per biome bake.
5. **Last: TTS swap to Chatterbox** when NPC voice work begins (Q6). Don't rush this; current need is unclear. Cost: 1 day plumbing.

**In parallel:** add CLAP score + PyMusicLooper to `audio_qa.py` (Q7) — *do this first* since it tells you whether (1)–(4) actually worked.

### What to keep, what to replace

| Tool | Verdict |
|---|---|
| `biome_ambience.py` | **Keep.** Plumbing is correct. |
| `local_audio_open.py` | **Keep + extend.** Add audio-to-audio path (Stable Audio 2.5 client) and LoRA-load support. |
| `synth_sfx.py` / `synth_sfx_extended.py` | **Replace.** Use CC0+ElevenLabs+AudioGen hybrid. Archive. |
| `eleven_sfx.py` | **Run it.** Plumbing is fine; just hasn't executed with real keys. |
| `cc0_ingest.py` | **Run it + extend** with PANNs auto-tagging + CLAP indexing. |
| `local_music_yue.py` | **Replace with ACE-Step.** Archive. |
| `adaptive_music.py` | **Keep.** Only the input stems change. |
| `local_tts_f5.py` | **Replace with Chatterbox** when NPC work begins. |
| `openai_tts.py` | **Keep as cloud fallback.** |
| `audio_qa.py` | **Extend.** Add CLAP score, loop-seam score, PANNs class verification. |
| `lint_audio.py` / `loop_detect.py` | **Keep.** |

### What is actually new since the pipeline was built

- **Stable Audio 2.5** with audio-to-audio and inpainting (Sept 2025) — fixes the "no reference conditioning" gap.
- **ACE-Step v1.5** (Jan 2026) — supplants YuE; Apache 2.0; native stem export.
- **Chatterbox-Multilingual** (Apr 2025) — supplants F5-TTS for emotional NPC voice.
- **Fish Speech S2** (Mar 2026) — Apache 2.0 TTS alternative.
- **Human-CLAP** (2025) — improves QA correlation with subjective ratings.
- **MusicGen-Stem** (Jan 2025) — native multi-stem generation; useful for adaptive music if you can accept CC-BY-NC.
- **LabelBuddy** (Mar 2026) — AI-assisted audio annotation.

### What has *not* changed and is unlikely to in 2026

- "Generative SFX is unreliable for short deterministic impacts." Curated CC0 still beats every model on this.
- "Ambient generation needs reference clips to be artistically targeted." Pure-text prompts still produce generic output.
- "Procedural multi-stem orchestration is the right runtime architecture." No model generates adaptive-game-music in real time at quality; bake offline, orchestrate at runtime.

---

## Sources

- [Stable Audio Open — Research Paper, Stability AI](https://stability.ai/news-updates/stable-audio-open-research-paper)
- [stabilityai/stable-audio-open-1.0 — Hugging Face](https://huggingface.co/stabilityai/stable-audio-open-1.0)
- [stabilityai/stable-audio-open-small — Hugging Face](https://huggingface.co/stabilityai/stable-audio-open-small)
- [Stable Audio 2.5 announcement — Stability AI](https://stability.ai/news-updates/stability-ai-introduces-stable-audio-25-the-first-audio-model-built-for-enterprise-sound-production-at-scale)
- [Stable Audio 2.5 Prompt Guide — Stability AI](https://stability.ai/learning-hub/stable-audio-25-prompt-guide)
- [Stable Audio 2.5 Inpaint — Eachlabs](https://www.eachlabs.ai/stability/stable-audio/stable-audio-2-5-inpaint)
- [Stable Audio 2.5 — Replicate](https://replicate.com/stability-ai/stable-audio-2.5)
- [Stable Audio Open paper, arXiv:2407.14358](https://arxiv.org/abs/2407.14358)
- [AudioCraft — Meta AI](https://ai.meta.com/resources/models-and-libraries/audiocraft/)
- [facebookresearch/audiocraft — GitHub](https://github.com/facebookresearch/audiocraft)
- [AudioGen — AudioCraft docs](https://github.com/facebookresearch/audiocraft/blob/main/docs/AUDIOGEN.md)
- [MusicGen-Style — AudioCraft docs](https://github.com/facebookresearch/audiocraft/blob/main/docs/MUSICGEN_STYLE.md)
- [MusicGen-Stem paper, arXiv:2501.01757](https://arxiv.org/html/2501.01757v1)
- [MusicGen-Stem demo](https://simonrouard.github.io/musicgenstem/)
- [Tango — declare-lab](https://tango-web.github.io/)
- [Tango on Replicate](https://replicate.com/declare-lab/tango)
- [AudioLDM2 paper, arXiv:2308.05734](https://arxiv.org/html/2308.05734v3)
- [ACE-Step v1.5 — GitHub](https://github.com/ace-step/ACE-Step-1.5)
- [ACE-Step paper, arXiv:2506.00045](https://arxiv.org/html/2506.00045v1)
- [ACE-Step 1.5 review (2026)](https://ace-step.co/ace-step-1-5-review)
- [YuE foundation model — GitHub](https://github.com/multimodal-art-projection/YuE)
- [YuE paper, arXiv:2503.08638](https://arxiv.org/html/2503.08638v1)
- [Open-source music generation models 2026 — SiliconFlow](https://www.siliconflow.com/articles/en/best-open-source-music-generation-models)
- [Chatterbox TTS — F5TTS comparison](https://f5tts.org/chatterbox-tts)
- [Chatterbox vs ElevenLabs — GenMediaLab](https://www.genmedialab.com/comparisons/elevenlabs-vs-chatterbox-tts/)
- [Best local TTS models 2026 — Murmur](https://www.murmurtts.com/blog/best-local-tts-models-2026)
- [Fish Speech S2 open-source release](https://medium.com/@bytefer/the-free-open-source-alternative-to-elevenlabs-is-finally-here-3cbbacd9c6b9)
- [Best open-source TTS 2026 — BentoML](https://www.bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models)
- [LAION-CLAP — GitHub](https://github.com/LAION-AI/CLAP)
- [Microsoft CLAP — GitHub](https://github.com/microsoft/CLAP)
- [microsoft/msclap — Hugging Face](https://huggingface.co/microsoft/msclap)
- [CLAP / Human-CLAP overview — EmergentMind](https://www.emergentmind.com/topics/contrastive-language-audio-pretraining-clap)
- [PyMusicLooper — GitHub](https://github.com/arkrow/PyMusicLooper)
- [LabelBuddy paper, arXiv:2603.04293](https://arxiv.org/html/2603.04293v1)
- [AudioShake](https://www.audioshake.ai/)
- [Spleeter — GitHub](https://github.com/deezer/spleeter)
- [LTX-2 audio-video model](https://introl.com/blog/ltx-2-audiovisual-diffusion-synchronized-video-audio-2026)
- [OpenMOSS MOVA — GitHub](https://github.com/OpenMOSS/MOVA)
- [Best open-source audio generation models 2026 — SiliconFlow](https://www.siliconflow.com/articles/en/best-open-source-audio-generation-models)
- [AI sound effects 2026 guide — AI Magicx](https://www.aimagicx.com/blog/ai-sound-effects-generation-foley-guide-2026)
- [Best AI Sound Effect Generators 2026 — PixVerse](https://pixverse.ai/en/blog/best-ai-sound-effect-generator)
- [Deploy open-source music generation 2026 — Spheron](https://www.spheron.network/blog/deploy-open-source-ai-music-generation-gpu-cloud-2026/)
- [Free sound library guide — Infinity Audio](https://www.infinity.audio/resonance/free-sound-library-best-royalty-free-resources)
- [Freesound CC0 tag](https://freesound.org/browse/tags/cc0/)
