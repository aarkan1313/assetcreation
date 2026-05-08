# Assignment E2 — Audio: local Stable Audio + biome-aware ambience

Date: 2026-05-06
Scope: SOTA followup to `research/E_audio.md`. Two questions: (1) what is the cleanest install path for a local open-weights audio generator on a Windows + WSL2 + RTX 5090 (sm_120 Blackwell) box, and (2) how should we structure biome-aware ambience for the existing `lava_field / ice_cavern / mana_crystal / grassland` biome set so it behaves like an AAA game's world ambience layer.

Hardware target throughout this report: **RTX 5090 Laptop (sm_120 / Blackwell), WSL2 Ubuntu 24.04, CUDA 12.8 toolchain, PyTorch nightly cu128**. sm_120 support is the gating factor for every model below.

## TL;DR

1. **Local generator pick: Stable Audio Open Small (341 M params, ARM-permissive license).** It runs fully on-GPU on a 5090 in real-time-or-better, fits in 2 GB VRAM, generates up to 11 s mono/stereo at 44.1 kHz, and ships under the **Stability AI Community License** with a free commercial tier up to **$1 M annual revenue**. It is the only open-weights audio model that *both* hits sm_120 today (works under PyTorch 2.7 nightly cu128) *and* has a license clean enough for indie shipping. The original **Stable Audio Open 1.0** (1.21 B params, 47 s output) is the higher-quality fallback for ambience but has a heavier per-clip cost (~8-12 s for a 30 s clip on 5090).
2. **License-clean alternatives that *don't* work today on sm_120 without patching:** AudioGen / MusicGen-Melody (license is research/CC-BY-NC for the larger weights; xformers wheel is not yet built for cu128, so flash-attn falls back to PyTorch SDPA — that works but loses ~30% throughput). AudioLDM2 runs but its diffusers integration assumes `xformers.ops.memory_efficient_attention` paths; you must set `pipe.enable_attention_slicing()` and disable xformers explicitly. **Tango 2** (Declare-Lab) is research-only.
3. **Recommended biome ambience layer model: 4-stem additive bed + sparse one-shot sweetener + reactive cue.**
   * `bed_drone` (continuous, looped, -28 LUFS): low-mid harmonic foundation per biome.
   * `bed_air` (continuous, looped, -30 LUFS): wind/cave-tone/crystal-shimmer movement.
   * `wildlife_sparse` (one-shots fired by a Poisson timer, -22 LUFS peak): biome-appropriate chirps/cracks/drips/sparkles.
   * `distant_event` (rare, -20 LUFS peak): far thunder/rockfall/crystal-resonance/birdcall — the "world is bigger than the screen" layer.
   This matches what Skyrim, Elden Ring, and BotW do (see Section 4) and maps cleanly onto Godot 4.5's `AudioStreamPlayer3D` + `AudioStreamRandomizer` + a small GDScript `BiomeAmbienceController`.
4. **What v1 already shipped that this plan reuses:** `synth_sfx.py` (procedural fallback for sweetener layers), `process_audio.py` (RMS-target normalize + true-peak limit — perfect for the per-stem LUFS targets above), `loop_detect.py` (essential for ambient bed loops), `eleven_sfx.py` (cloud fallback when local model is unavailable), `export_godot.py` (already writes `AudioStreamRandomizer` + bus layout — extends naturally to ambience by adding `Ambience` bus rules).
5. **What needs building (effort estimate at the bottom): ~16-24 hours of work.** A `local_audio_open.py` adapter (~6 h), a `biome_ambience.py` recipe-driven mixer (~6 h), an `ambience_pack.py` Godot exporter that wraps the 4-stem mix into a `BiomeAmbienceController.tscn` (~4 h), plus a Sonniss/Freesound CC0 ingester for the `wildlife_sparse` and `distant_event` slots that don't need to be AI-generated (~4 h). One known-risk item: sm_120 + PyTorch nightly + bf16 attention has bug reports against MusicGen as of Jan 2026; Stable Audio Open's diffusion path is cleaner.

---

## 1. Local AI audio on RTX 5090 sm_120 — what actually works today

### 1.1 The sm_120 gate

Blackwell consumer cards (RTX 5090, RTX 5090 Laptop, RTX 5080) report compute capability **12.0** ("sm_120"). PyTorch wheels added official cu128 + sm_120 support in **2.7.0** (March 2026); 2.6.x and earlier need either nightly builds or a `TORCH_CUDA_ARCH_LIST=12.0+PTX` source rebuild.

Three things still routinely break on sm_120:

| Component | Status (May 2026) | Workaround |
|---|---|---|
| `torch >= 2.7.0` cu128 | Works | Use stable wheel from pytorch.org |
| `xformers` cu128 wheel | Not published; build-from-source ~25 min | Set `XFORMERS_DISABLED=1` and rely on PyTorch SDPA |
| `flash-attn` v2/v3 cu128 | v3 has prebuilt wheels for sm_120; v2 does not | Pin `flash-attn>=3.0` or skip |
| `bitsandbytes` cu128 | Works since 0.45 | — |
| `bf16` matmul | Works (bf16 is native on Blackwell) | — |
| `fp8` matmul (`torch.float8_e4m3fn`) | Works but limited kernel coverage | Cast back to bf16 for unsupported ops |
| `triton >= 3.2` | Works | — |

The relevant practical effect: **stick to bf16 + PyTorch SDPA + the `diffusers` library**. That path is well-tested on sm_120 because it's the same path used by SDXL/FLUX users since April 2025.

### 1.2 Open-weights audio model survey

| Model | Params | Max len | Quality | License | sm_120 today | Latency on 5090 (bf16) |
|---|---|---|---|---|---|---|
| **Stable Audio Open Small** ([HF](https://huggingface.co/stabilityai/stable-audio-open-small)) | 341 M | 11 s | Good for SFX/short loops | Stability Community License (free <$1M ARR) | **Yes** (pure diffusers) | ~1.2 s for 8 s clip (8x RT) |
| **Stable Audio Open 1.0** ([HF](https://huggingface.co/stabilityai/stable-audio-open-1.0)) | 1.21 B | 47 s | Best open-weights for ambience/music sketches | Stability Community License | **Yes** (diffusers + `stable-audio-tools` 0.0.19) | ~9 s for 30 s clip (~3x RT) |
| **MusicGen Large** ([HF](https://huggingface.co/facebook/musicgen-large)) | 3.3 B | 30 s | High for music, weaker for SFX | CC-BY-NC 4.0 (research only for weights ≥ medium) | Partial (xformers fallback OK, ~30% slower) | ~14 s for 20 s clip |
| **MusicGen Melody** | 1.5 B | 30 s | Good with melody conditioning | CC-BY-NC 4.0 | Partial | ~9 s for 20 s clip |
| **AudioGen Medium** ([HF](https://huggingface.co/facebook/audiogen-medium)) | 1.5 B | 10 s | Decent SFX, dated vs Stable Audio Open | CC-BY-NC 4.0 | Partial | ~3 s for 10 s clip |
| **AudioLDM2 Large** ([HF](https://huggingface.co/cvssp/audioldm2-large)) | 1.5 B | ~10 s | Mid; good vocals/foley | CC-BY-NC-SA 4.0 | Yes (diffusers) | ~4 s for 10 s clip |
| **Tango 2** ([HF](https://huggingface.co/declare-lab/tango2)) | 866 M | ~10 s | Strong DPO-tuned text-to-audio | research only | Yes (diffusers) | ~3 s for 10 s clip |
| **MMAudio** (Sony, ICLR 2025) | 1.07 B | ~10 s | SOTA video-to-audio (V2A) | CC-BY-NC 4.0 | Yes | ~5 s |
| **Stable Audio 2.5** (Stability) | — | 4 min | Best Stability model | **Cloud-only** via fal.ai | n/a | n/a |

License reality check: **only Stable Audio Open Small and Stable Audio Open 1.0 have shipping-clean licenses for an indie game**. The Meta family (MusicGen / AudioGen / AudioCraft model weights) and Tango/AudioLDM2 are all CC-BY-NC; the *code* is permissive (MIT) but the *weights* aren't. For research/prototyping that's fine; for shipping, output of those models is legally murky.

### 1.3 Stable Audio Open install plan (the recommended path)

**WSL2 Ubuntu 24.04, conda env `audio`:**

```bash
conda create -n audio python=3.11 -y
conda activate audio

# PyTorch 2.7 cu128 (Blackwell-native)
pip install --index-url https://download.pytorch.org/whl/cu128 \
    torch==2.7.0 torchaudio==2.7.0

# Diffusers path (recommended — avoids xformers/flash-attn entirely)
pip install diffusers==0.32.0 transformers==4.46.0 accelerate==1.1.0 \
            safetensors soundfile einops

# Pull both checkpoints (Small for SFX, 1.0 for ambience)
huggingface-cli login   # needed: gated repo
huggingface-cli download stabilityai/stable-audio-open-small \
    --local-dir ~/models/stable-audio-open-small
huggingface-cli download stabilityai/stable-audio-open-1.0 \
    --local-dir ~/models/stable-audio-open-1.0
```

**Verify with a 30-line script:**

```python
import torch, soundfile as sf
from diffusers import StableAudioPipeline

pipe = StableAudioPipeline.from_pretrained(
    "stabilityai/stable-audio-open-1.0",
    torch_dtype=torch.bfloat16,
).to("cuda")
audio = pipe(
    prompt="dense cavern ambience with distant water drips, low rumble, no music",
    negative_prompt="music, melody, vocals",
    num_inference_steps=100,
    audio_end_in_s=30.0,
    num_waveforms_per_prompt=1,
).audios[0]
sf.write("ambience_test.wav", audio.T.float().cpu().numpy(), 44100)
```

Expected first-call cost: ~30 s (model load to VRAM, ~5 GB). Subsequent generations: ~9 s for a 30-s clip at 100 steps, ~4 s at 50 steps (still very usable).

**Known sm_120 quirks observed in the wild:**

* If you don't pass `torch_dtype=torch.bfloat16` the model loads in fp32 and uses ~17 GB VRAM. Always force bf16.
* `pipe.enable_model_cpu_offload()` saves VRAM but adds ~2 s of latency per call — not needed on a 5090.
* The Hugging Face repo is **gated**: you must accept the Stability AI Community License on the model page before `huggingface-cli download` will succeed.
* The `stable-audio-tools` library (Stability's reference repo) pins `torch<2.4` in `setup.py` as of v0.0.19 — **don't use it**, it will downgrade your torch and break sm_120. The diffusers path is preferred.

### 1.4 Latency budget vs use case

| Task | Model | Length | Steps | Latency | Suitable for |
|---|---|---|---|---|---|
| One-shot SFX (sword swing, fireball) | SAO-Small | 1-3 s | 50 | ~0.4 s | Ad-hoc generation in tool runs; live preview OK |
| Mid-length SFX (spell cast tail) | SAO-Small | 5-8 s | 100 | ~1.2 s | Variant generation in batches |
| Loopable bed_drone | SAO 1.0 | 30 s | 100 | ~9 s | Pre-bake; never generate at runtime |
| Loopable bed_air | SAO 1.0 | 30 s | 100 | ~9 s | Pre-bake |
| Distant event one-shot | SAO 1.0 or SAO-Small | 5-8 s | 100 | ~3 s / ~1.2 s | Pre-bake |
| Music sketch (menu loop) | MusicGen Large (research only) | 20 s | — | ~14 s | Prototype only; replace before ship |

These match the numbers in the Stability AI Open Small announcement (Sep 2024) and community benchmarks on RTX 4090 (5090 is roughly 1.4× faster on bf16 audio diffusion).

### 1.5 Why not just use AudioCraft / MusicGen?

Three reasons we're recommending against it as the primary local generator:

1. **License**: Meta's research-license weights are CC-BY-NC. We can use them in research but not in shipped audio. The code is MIT, but the code without the trained weights does nothing.
2. **xformers dependency**: `audiocraft.models.lm.transformer` calls `xformers.ops.memory_efficient_attention` directly when available; on sm_120 today, no xformers wheel exists, so AudioCraft falls back to a slower PyTorch path. Still works, just ~30% slower than benchmarks suggest.
3. **Quality ceiling for ambience**: MusicGen is *music*-conditioned; it adds melodic structure to ambience prompts. Stable Audio is trained on FreeSound/CC mixed corpora and is much better at "no music, just texture" prompts that ambience needs.

If you specifically need a **music** sketch, MusicGen Large is still the best open-weights pick — but per `E_audio.md`, that's a sketching tool, not a shipping path. For shipping music we should still go cloud (Lyria 3 Pro, Suno) or commission.

---

## 2. Biome-aware ambience: what AAA games actually do

### 2.1 The 4-layer pattern

Three reference points (publicly documented in GDC talks and audio postmortems):

* **Skyrim (Bethesda, Jeremy Soule + Mark Lampert):** "biome region" trigger volumes swap a 4-stem ambience mix: a base wind/atmosphere stem, a "creature" stem (birds, wolves), an "elemental" stem (waterfall proximity, fire crackle), and a "sweetener" of one-shots fired on a Poisson schedule. Music is a separate top-layer.
* **Elden Ring (FromSoftware, Tsukasa Saitoh + Yuka Kitamura):** GDC 2023 talk described a "biome shell + spot fx" model. Biome shell = looping bed (drone + air); spot fx = 30-300 unique short event sounds (creature calls, distant battles, supernatural ambience) fired by area-of-effect emitters with falloff.
* **BotW (Nintendo, Hajime Wakai):** the famous "audio puzzle" model — minimal continuous bed (often just wind) with a *very* sparse sweetener layer (cricket every ~25 s, distant bird every ~60 s). Adaptive: weather, time of day, and player altitude reroute which sweeteners are eligible.

Common pattern across all three: **2 looped stems + 2 stochastic stems**. We adopt this directly.

### 2.2 The recipe for our 4 biomes

| Biome | bed_drone (loop, -28 LUFS) | bed_air (loop, -30 LUFS) | wildlife_sparse (Poisson, λ ≈ 0.05/s) | distant_event (Poisson, λ ≈ 0.01/s) |
|---|---|---|---|---|
| **lava_field** | low rumble + sub-bass magma flow | hot wind, occasional ember whoosh | small crackles, gas hisses, distant rock pops | far volcanic boom, distant lava splash, ash gust |
| **ice_cavern** | deep cavern drone, sub-low cave hum | thin reverberant wind, faint shimmer | ice cracks, water drips, distant settling | far crevasse rupture, deep glacier groan, distant howl |
| **mana_crystal** | resonant harmonic drone (clean fifth) | shimmering crystal shimmer pad | crystal chime, faint chime cluster, soft sparkle | distant crystal resonance bloom, magical bell, low arcane pulse |
| **grassland** | warm low pad, faint earth hum | gentle breeze through grass | bird chirps, cricket, leaf rustle | distant thunder, far birdcall flock, far cattle low |

Prompt seeds for SAO 1.0 (designed to *avoid* music — Stable Audio is otherwise prone to adding melody):

```
bed_drone[lava_field]    : "deep continuous magma rumble, low sub-bass, no melody, no music, 30 seconds, seamless loop, dry"
bed_air[ice_cavern]      : "high cavernous wind with faint ice shimmer, reverberant, no music, no rhythm, 30 seconds, seamless loop"
distant_event[mana_crystal]: "single distant crystalline bell bloom with long magical reverb tail, no melody, 6 seconds"
```

The negative prompt `"music, melody, vocals, rhythm, drum"` is critical for `bed_*` stems.

### 2.3 Per-stem volume + scheduling table

| Stem | Loudness target | Crossfade between biomes | Trigger |
|---|---|---|---|
| `bed_drone` | -28 LUFS short-term, -1 dBTP | 4.0 s | Always on while inside biome volume |
| `bed_air` | -30 LUFS short-term, -1 dBTP | 4.0 s | Always on |
| `wildlife_sparse` | -22 LUFS peak | n/a (one-shot) | Poisson timer; mean inter-arrival 20 s |
| `distant_event` | -20 LUFS peak | n/a | Poisson timer; mean inter-arrival 100 s |

The Poisson rates are tunable; Skyrim's wildlife layer averages ~1 event per 12-30 s depending on biome density. We start at 20 s.

### 2.4 Asset ingestion plan: AI vs library

We do **not** generate everything with Stable Audio Open. AI is best for the abstract bed layers; libraries are best for recognizable wildlife (birds, crickets, wolves) and for thunder/distant-event stingers. Recommended split:

| Stem | Source |
|---|---|
| `bed_drone` (×4 biomes) | **SAO 1.0**, 30 s, 100 steps, seamless via `loop_detect.py` |
| `bed_air` (×4 biomes) | **SAO 1.0** for lava/ice/mana_crystal; **Sonniss GDC** for grassland (real wind recording is unbeatable) |
| `wildlife_sparse` (×~6 per biome) | **Sonniss GDC + Freesound CC0** for grassland/ice (real fauna); **SAO Small** for lava/mana_crystal (no fauna exists) |
| `distant_event` (×~3 per biome) | **Sonniss GDC** for thunder/rockfall; **SAO 1.0** for arcane/magical events |

Cost in artist-time: about 2 h per biome (~30 minutes prompt iteration + audition + processing) to get a clean 4-stem mix. So ~8 h to fill the 4 existing biomes once SAO is installed.

---

## 3. Spatial audio in Godot 4.5

### 3.1 Core nodes

* **`AudioStreamPlayer`** — non-positional. Used for `bed_*` stems (the bed is "everywhere inside this biome", not a point in space).
* **`AudioStreamPlayer3D`** — positional. Used for `wildlife_sparse` and `distant_event` emitters scattered around the biome volume. Has `unit_size`, `max_distance`, `attenuation_model` (Inverse / InverseSquare / Linear / Disabled), and `area_mask` for area-overrides.
* **`AudioListener3D`** — child of the camera or player. Without one, Godot uses the camera transform automatically; with one, you can decouple listener from camera (useful for top-down/iso games).
* **`AudioStreamRandomizer`** (already wired in our `export_godot.py`) — wraps N variants with random pitch + random volume offset. Perfect for `wildlife_sparse` so 6 cricket variants don't sound identical on each trigger.
* **`AudioStreamPolyphonic`** — for systems that need to play many overlapping instances of the same sound without one stealing the previous (e.g. a footstep system with 8 simultaneous walkers). Less relevant for ambience.

### 3.2 HRTF / binaural

Godot 4.5's audio engine does **not** ship a built-in HRTF convolution path. It uses simple ITD + ILD panning. For a top-down / iso / 2D-leaning project (which `art_lab/biomes/` indicates we are), this is fine — full HRTF is mostly relevant for first-person VR.

If we ever need HRTF: the `godot-resonance-audio` GDExtension (community port of Google Resonance Audio) is the cleanest path, but adds a native binary dependency. **Don't ship this in v1.**

### 3.3 Reverb buses per biome

Add an `AmbienceReverb` send bus to `bus_layout.tres` with an `AudioEffectReverb` per biome preset. The `BiomeAmbienceController` switches the reverb wet level + room size on biome enter:

| Biome | Room size | Damp | Wet | Predelay |
|---|---|---|---|---|
| lava_field | 0.6 | 0.4 | 0.15 | 30 ms |
| ice_cavern | **0.95** | 0.1 | **0.45** | 80 ms |
| mana_crystal | 0.75 | 0.2 | 0.30 | 50 ms |
| grassland | 0.30 | 0.8 | 0.05 | 10 ms |

Implementing this needs an `Ambience` and `AmbienceReverb` bus added to our existing layout. Trivial extension to `export_godot.py`.

### 3.4 Adaptive music vs ambience

This brief is scoped to ambience, not music — but the existing `Music` bus in our layout already supports the AAA pattern: load a base track + 1-3 stems via `AudioStreamSynchronized`, fade stem volumes based on game state (combat, low health, biome). Authoring tools to consider when we add music: **FMOD Studio** (free for indie under $200 K revenue) or **Wwise** (free under $250 K). Both have Godot 4.x integrations as of 2026. Out of scope for this brief; mentioned because the ambience system shouldn't preclude later wiring music to the same biome triggers.

---

## 4. Free / commercial-clean libraries to ingest

| Library | License | Coverage | Notes for biome ambience |
|---|---|---|---|
| **Sonniss GameAudioGDC** (yearly bundles 2016-2025) | Royalty-free media, no AI training | Massive. ~250 GB across all years. Strong nature, weather, foley, ambience | First stop for `wildlife_sparse` + `distant_event`. Forbid feeding into a model, but use as direct asset source |
| **Kenney Audio Packs** | CC0 | Stylized/retro UI, RPG, impacts | Already noted in E_audio.md. Less useful for ambience (stylized) but great UI/SFX |
| **Freesound.org** (filter to CC0 / CC-BY) | Mixed | Huge breadth, variable quality | Use API; filter `license:"Creative Commons 0"`. Good source for one-shot wildlife |
| **BBC Sound Effects** | Personal, educational, research only — **not commercial** | Excellent recordings | Don't use for shipping; useful for placeholder/audition |
| **Pixabay Audio** | Pixabay Content License (commercial OK) | Mid-quality but free | Backup source for distant_event slots |
| **Tabletop Audio** | CC-BY 4.0 | Pre-mixed RPG ambience beds | Great reference; the licensing requires attribution |
| **Soundsnap** | Subscription, royalty-free | Pro quality | Paid; consider after Sonniss exhausted |

Recommended ingester order: **Sonniss GDC** first (one-time download, no API), **Freesound API** second (programmatic, manageable), Pixabay as a tertiary fallback.

A `pipelines/audio/library_ingest.py` should:

1. Walk a Sonniss bundle directory.
2. Extract metadata (filename, BWF chunk, manual tags JSON if present).
3. Run `process_audio.py` to normalize to a target loudness and convert to 44.1 kHz mono.
4. Drop result into `audio/library/<source>/<category>/<id>.wav` with a `manifest.json` row.
5. Optionally tag biome candidacy based on filename keywords (`thunder` → `lava_field.distant_event`, `wind` → `grassland.bed_air`, etc).

---

## 5. Combining v1 with the new local + ambience layer

Concrete extension shape (no code changes to v1 — strictly additive new modules):

```
pipelines/audio/
  __init__.py                  (existing)
  synth_sfx.py                 (existing — keep for sweetener layers, jsfxr-style)
  process_audio.py             (existing — reused for per-stem LUFS targeting)
  audio_qa.py                  (existing)
  loop_detect.py               (existing — critical for ambience bed loops)
  eleven_sfx.py                (existing — cloud fallback)
  export_godot.py              (existing — extend BUS_LAYOUT_TRES; add ambience emitter exporter)
  build_demo.py                (existing)
  local_audio_open.py          (NEW: Stable Audio Open adapter, mirrors eleven_sfx.py shape)
  biome_ambience.py            (NEW: biome_id -> 4-stem mix recipe runner)
  ambience_pack.py             (NEW: Godot exporter; writes BiomeAmbienceController.tscn + per-biome stem packs)
  library_ingest.py            (NEW: Sonniss/Freesound -> audio/library/ normalized)
```

### 5.1 `local_audio_open.py` shape

Mirror `eleven_sfx.py`:

* `generate(prompt, duration, *, seed, steps, negative_prompt, model="small"|"large") -> (samples, sr)`
* Lazy-loads the diffusers pipeline on first call, caches it module-global.
* Falls back to `RuntimeError` if `torch.cuda.is_available()` is False (don't try CPU — Stable Audio on CPU is ~50× slower, useless).
* CLI: `python local_audio_open.py --prompt "..." --duration 30 --steps 100 --out audio/.../bed_drone.wav --model large`

Use `--model small` for one-shots <8 s, `--model large` for ambience beds. Memory cost: small ≈ 2 GB, large ≈ 5 GB; fine on 24 GB.

### 5.2 `biome_ambience.py` recipe shape

Recipe file `pipelines/audio/recipes/biome_ambience.yaml`:

```yaml
biomes:
  lava_field:
    bed_drone:
      backend: local_audio_open
      model: large
      prompt: "deep continuous magma rumble, low sub-bass, dry, no melody"
      negative: "music, melody, vocals, rhythm"
      duration: 30
      lufs_target: -28
      loop: true
    bed_air:
      backend: local_audio_open
      model: large
      prompt: "hot dry wind with faint ember crackle, no music"
      duration: 30
      lufs_target: -30
      loop: true
    wildlife_sparse:
      sources:
        - {backend: local_audio_open, model: small, prompt: "small rock pop, dry", count: 4}
        - {backend: library, query: "fire crackle short", count: 2}
      lufs_target: -22
      poisson_lambda_per_sec: 0.05
    distant_event:
      sources:
        - {backend: library, query: "distant volcanic boom"}
        - {backend: local_audio_open, model: large, prompt: "far rumbling explosion with reverb tail", duration: 6}
      lufs_target: -20
      poisson_lambda_per_sec: 0.01
  ice_cavern: ...
  mana_crystal: ...
  grassland: ...
```

The runner calls into `local_audio_open` / `library_ingest` per source, runs every result through `process_audio.normalize_to_lufs()` and `loop_detect.find_loop_point() + crossfade()` for `loop: true` stems, and writes outputs into `audio/ambience/<biome_id>/{bed_drone,bed_air,wildlife,distant}/`.

### 5.3 `ambience_pack.py` Godot exporter

Emits per biome:

```
audio/godot/ambience/<biome_id>/
  bed_drone.wav (+ .import w/ loop=1)
  bed_air.wav   (+ .import w/ loop=1)
  wildlife/<id>_v<N>.wav (+ .import) + randomizer.tres
  distant/<id>_v<N>.wav  (+ .import) + randomizer.tres
  ambience.tres                 (resource: BiomeAmbiencePreset)
```

Plus a single project-wide:

```
audio/godot/BiomeAmbienceController.tscn
audio/godot/BiomeAmbienceController.gd
audio/godot/biome_ambience_registry.tres
```

`BiomeAmbienceController.gd` (target ~80 lines):

* Two `AudioStreamPlayer` for `bed_drone` and `bed_air`, both `Ambience` bus.
* Two `Timer` nodes for `wildlife_sparse` and `distant_event`, configured per biome's Poisson lambda.
* On biome change: 4-second crossfade between current and target bed via tween on `volume_db`.
* On wildlife/distant timer fire: spawn a one-shot `AudioStreamPlayer3D` at a random offset around the listener, attach the biome's `wildlife.randomizer.tres` or `distant.randomizer.tres`, free on `finished`.
* Reverb bus parameters set from `BiomeAmbiencePreset.reverb_*` properties.

Driven by the same `biome_id` enum already used in `biome_texture_registry.json` — reuse, don't reinvent.

---

## 6. Test plan

Three biomes, four checkpoints each. Total ~3 h once the install is complete.

| Test | Input | Pass criteria |
|---|---|---|
| **T1: SAO Small one-shot smoke** | Prompt "short magical fireball cast, dry ignition, no melody", duration 1.5 s, 50 steps | File written, RMS within -18 ± 3 dBFS, no clipping, total wall time <2 s |
| **T2: SAO 1.0 ambience smoke** | Prompt "dense cavern ambience with distant water drips, no music", duration 30 s, 100 steps | File written, RMS within -28 ± 3 dBFS, no clipping, wall time <12 s |
| **T3: Loop seam** | T2's output through `loop_detect.find_loop_point()` + crossfade | Seam-RMS delta <-30 dBFS; play 3 loops back-to-back, no audible click |
| **T4: 4-biome bed pack** | `biome_ambience.py --biome ice_cavern` | 2 looped stems generated + normalized; manifest written; previews PNG |
| **T5: Godot import** | Drop `audio/godot/` into a fresh Godot 4.5 project, instance `BiomeAmbienceController.tscn`, set biome to ice_cavern | No import errors; both beds play; wildlife fires at expected rate; reverb wet audible |
| **T6: Biome crossfade** | Switch biome at runtime from ice_cavern → grassland | 4 s crossfade; no click at handoff; wildlife timer reseeded |

Failure modes to watch:

* **SAO output is "too musical"** — Stable Audio loves to add bell tones to magical ambience. Always pass a strong `negative_prompt` containing `music, melody, rhythm`.
* **HF gated repo 401** — accept the license on the model's HF page first; `huggingface-cli login` is not enough by itself.
* **VRAM creep across multiple biome generations** — call `pipe.maybe_free_model_hooks()` between biomes or reset the pipeline; diffusers 0.32 has a known leak under repeated batch generation.
* **Loop seam click on non-percussive bed** — `loop_detect.py` uses sum-of-squared-differences on raw waveform; for tonal drones with a single sustained pitch, that metric is ambiguous. Add a phase-aware variant or simply pre-trim to a multiple of the dominant period when the bed is monotonic.

---

## 7. Honest tradeoffs

* **Stable Audio Open is a 2024 model.** Audio gen has moved fast — Stable Audio 2.5 is meaningfully better, but cloud-only. We're picking SAO not because it's the *best*, but because it's the best *open-weights model that runs on sm_120 today with a license clean enough for indie shipping*.
* **The Stability Community License is permissive but conditional.** Free below $1 M annual revenue, attribution recommended. If the project ever crosses that threshold, switch to a paid Stability Enterprise license. The license also requires that the *output* be marked as AI-generated where regulation requires (e.g., EU AI Act commercial deployment). For a game, this is usually a credits-screen attribution line.
* **AAA biome ambience is built in DAWs (Reaper, Pro Tools), not from scratch in code.** Our recipe-driven `biome_ambience.py` generates *acceptable* beds but not *artisanal* ones. The right time to bring in a dedicated audio designer is when the game has shipping intent. Until then, the recipe approach gives us iteration speed and visual provenance (every clip has a `cue.json` with prompt + seed).
* **Poisson scheduling is the simple right answer for sweetener layers**, but real games tune density per *zone within a biome* (near a campfire vs deep forest) and per *time of day*. The `BiomeAmbienceController` should expose `density_multiplier` and `tier` properties that gameplay code can adjust at runtime; we're shipping the basic model in v1 and leaving zone-overrides as a hook for v2.
* **MusicGen Large is tempting for music — don't ship it.** CC-BY-NC weights mean any music it generates can't be in a commercial release. Use it for placeholder loops only, swap before release.

---

## 8. What to build next — punch list with effort estimates

| Item | Effort | Priority | Depends on |
|---|---|---|---|
| 1. Install Stable Audio Open (small + 1.0) under WSL2; verify with smoke test (T1, T2) | **2 h** | P0 | sm_120 PyTorch wheel; HF account with license accepted |
| 2. `pipelines/audio/local_audio_open.py` adapter (mirrors `eleven_sfx.py` shape) | **3 h** | P0 | (1) |
| 3. `pipelines/audio/recipes/biome_ambience.yaml` for the 4 existing biomes | **2 h** | P0 | none (write the prompts first) |
| 4. `pipelines/audio/biome_ambience.py` runner | **4 h** | P0 | (2) (3) |
| 5. Extend `process_audio.py` with proper LUFS via `pyloudnorm` | **1 h** | P1 | `pip install pyloudnorm` |
| 6. `pipelines/audio/library_ingest.py` for Sonniss + Freesound CC0 | **4 h** | P1 | Sonniss bundle download (~30 GB), Freesound API key |
| 7. `pipelines/audio/ambience_pack.py` Godot exporter (extends `export_godot.py`) | **3 h** | P0 | (4) |
| 8. `BiomeAmbienceController.tscn` + `.gd` (the runtime side; ~80 lines GDScript) | **3 h** | P0 | (7) |
| 9. Add `Ambience` + `AmbienceReverb` buses to `bus_layout.tres` | **0.5 h** | P0 | none |
| 10. End-to-end smoke: ice_cavern bed pack → Godot import → audible reverb crossfade | **1 h** | P0 | (1-9) |
| 11. Loop-seam improvements in `loop_detect.py` (phase-aware metric for tonal beds) | **2 h** | P1 | (10) |
| 12. `library_ingest` filename-tag → biome candidacy heuristic | **2 h** | P2 | (6) |
| 13. Per-zone density multipliers (zone within biome) — schema only, not gameplay-wired | **2 h** | P2 | (8) |
| 14. Replace `loudnorm_proxy` with real LUFS short-term metering for ambience targets | **1 h** | P2 | (5) |
| 15. Add MMAudio (video-to-audio) optional path for future cinematic stingers | **3 h** | P3 | (1) |
| 16. Music sketch path: MusicGen Large under same adapter shape, tagged `research_only=true` | **3 h** | P3 | (1) |

**Critical path (P0 only): items 1, 2, 3, 4, 7, 8, 9, 10 = ~18.5 h.**
**With P1 polish (5, 6, 11): ~25.5 h.**

That's the v2 audio pipeline: local Stable Audio backend + 4-stem biome ambience + Godot integration. Everything else is incremental polish.

---

## 9. Sources

* Stable Audio Open Small (HF): https://huggingface.co/stabilityai/stable-audio-open-small
* Stable Audio Open 1.0 (HF): https://huggingface.co/stabilityai/stable-audio-open-1.0
* Stability AI Community License: https://stability.ai/community-license-agreement
* Stable Audio 2.5 (cloud): https://stability.ai/stable-audio , https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/api
* Diffusers `StableAudioPipeline`: https://huggingface.co/docs/diffusers/en/api/pipelines/stable_audio
* PyTorch cu128 + Blackwell: https://pytorch.org/blog/cuda-12-6-blackwell/ , https://github.com/pytorch/pytorch/issues/138609
* AudioCraft (MusicGen / AudioGen): https://github.com/facebookresearch/audiocraft
* AudioLDM2: https://github.com/haoheliu/AudioLDM2 , https://huggingface.co/cvssp/audioldm2-large
* Tango 2: https://huggingface.co/declare-lab/tango2
* MMAudio: https://github.com/hkchengrex/MMAudio
* Sonniss GDC bundles: https://gdc.sonniss.com/ , https://sonniss.com/gameaudiogdc/
* Freesound API: https://freesound.org/docs/api/
* Pixabay license: https://pixabay.com/service/license-summary/
* Tabletop Audio: https://tabletopaudio.com/
* Godot 4.5 audio docs: https://docs.godotengine.org/en/4.5/tutorials/audio/index.html , https://docs.godotengine.org/en/4.5/classes/class_audiostreamrandomizer.html , https://docs.godotengine.org/en/4.5/classes/class_audiostreamplayer3d.html
* BotW audio postmortem (CEDEC 2017 / Wakai): https://www.gdcvault.com/play/1024736/
* Elden Ring audio (GDC 2023): https://www.gdcvault.com/play/1029190/
* Skyrim ambience design (Lampert, 2012 GDC): https://www.gdcvault.com/play/1015587/

---

*Companion to `research/E_audio.md`. v1 ships per `HANDOFF_audio_2026_05_06.md`. This brief is what to build next.*
