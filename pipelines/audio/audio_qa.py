"""Audio QA: waveform PNG + spectrogram PNG + sanity checks.

No librosa, no matplotlib in the core path. Uses numpy + PIL only. Spectrogram
via STFT in numpy. Adequate for visually checking that a generated SFX
looks/sounds reasonable.

Two QA layers, additive, per brief #06:

  - **Sanity (DEFAULT, always runs):** LUFS-like RMS/peak/clip/click/DC checks.
    Pure numpy/PIL, runs anywhere. The original behavior — unchanged.
  - **--clap-prompt <text>:** CLAP audio-text similarity score. Catches the
    "sounds like noise/static" failure mode that LUFS-only QA misses (LUFS is
    spec-correct on noise; CLAP measures whether the audio actually matches
    the prompt). Requires the dedicated audio venv (torch + laion-clap):

        D:\\assets\\pipelines\\audio\\.venv\\Scripts\\python.exe \\
            pipelines\\audio\\audio_qa.py <wav> --clap-prompt "forest at dusk"

  - **--loop-check:** PyMusicLooper seam validation. For ambience loops only —
    flags WAVs where no clean loop point can be found. Same audio venv.

CLI:
  python audio_qa.py audio/sfx/processed.wav
    -> writes waveform.png + spectrogram.png + qa.json next to the input

  python audio_qa.py audio/ambience/forest.wav --clap-prompt "forest at dusk" --loop-check
    -> qa.json adds clap_score + loop_seam_score for content-correctness checks
"""
from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

import numpy as np
from PIL import Image


SAMPLE_RATE = 44_100


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 1:
        arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        arr = arr.reshape(-1, 2).mean(axis=1)
    return arr.astype(np.float32), sr


def waveform_png(samples: np.ndarray, w: int = 800, h: int = 200,
                 fg=(120, 200, 240), bg=(15, 15, 25)) -> Image.Image:
    img = Image.new("RGB", (w, h), bg)
    px = img.load()
    if len(samples) == 0:
        return img
    bins = np.array_split(samples, w)
    mid = h // 2
    # axis line
    for x in range(w):
        px[x, mid] = (40, 40, 60)
    for x, b in enumerate(bins):
        if len(b) == 0:
            continue
        lo = float(b.min())
        hi = float(b.max())
        y_lo = int(mid - lo * (h * 0.45))
        y_hi = int(mid - hi * (h * 0.45))
        y_lo = max(0, min(h - 1, y_lo))
        y_hi = max(0, min(h - 1, y_hi))
        for y in range(min(y_lo, y_hi), max(y_lo, y_hi) + 1):
            px[x, y] = fg
    return img


def stft_mag(samples: np.ndarray, win: int = 1024, hop: int = 256) -> np.ndarray:
    """Magnitude STFT. Returns shape (frames, win//2+1)."""
    if len(samples) < win:
        # pad
        samples = np.pad(samples, (0, win - len(samples)))
    window = np.hanning(win).astype(np.float32)
    n_frames = 1 + (len(samples) - win) // hop
    out = np.empty((n_frames, win // 2 + 1), dtype=np.float32)
    for i in range(n_frames):
        seg = samples[i * hop: i * hop + win] * window
        out[i] = np.abs(np.fft.rfft(seg))
    return out


def spectrogram_png(samples: np.ndarray, sr: int = SAMPLE_RATE,
                    w: int = 800, h: int = 256,
                    win: int = 1024, hop: int = 256) -> Image.Image:
    mag = stft_mag(samples, win=win, hop=hop)
    if mag.size == 0:
        return Image.new("RGB", (w, h), (15, 15, 25))
    db = 20 * np.log10(np.maximum(mag, 1e-6)).T  # (freq, frames)
    db = np.clip(db, -80, 0)
    norm = (db + 80) / 80  # 0..1
    # log-frequency squash so the bottom 1/3 of the image holds 0..3kHz
    n_freq, n_frames = norm.shape
    log_idx = np.geomspace(1, n_freq, h).astype(int) - 1
    log_idx = np.clip(log_idx, 0, n_freq - 1)
    norm_log = norm[log_idx]   # (h, n_frames)
    # resample horizontally to w
    if n_frames != w:
        x_old = np.linspace(0, 1, n_frames)
        x_new = np.linspace(0, 1, w)
        resampled = np.empty((h, w), dtype=np.float32)
        for r in range(h):
            resampled[r] = np.interp(x_new, x_old, norm_log[r])
        norm_log = resampled
    # invert vertical so high freqs are on top
    norm_log = norm_log[::-1]
    # colormap: viridis-ish manual
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[..., 0] = (norm_log * 230).astype(np.uint8)
    rgb[..., 1] = (np.power(norm_log, 0.7) * 220).astype(np.uint8)
    rgb[..., 2] = (np.sqrt(norm_log) * 200).astype(np.uint8)
    return Image.fromarray(rgb, "RGB")


def sanity(samples: np.ndarray, sr: int) -> dict:
    """Return a small QA summary dict."""
    if len(samples) == 0:
        return {"empty": True}
    rms = float(np.sqrt(np.mean(samples ** 2)))
    peak = float(np.max(np.abs(samples)))
    clipped = int(np.sum(np.abs(samples) >= 0.999))
    # look for DC offset
    dc = float(np.mean(samples))
    # look for sudden jumps (clicks)
    diffs = np.abs(np.diff(samples))
    click_count = int(np.sum(diffs > 0.5))
    return {
        "duration_s": float(len(samples) / sr),
        "samplerate": int(sr),
        "rms_dbfs": float(20 * np.log10(max(rms, 1e-10))),
        "peak_dbfs": float(20 * np.log10(max(peak, 1e-10))),
        "clipped_samples": clipped,
        "dc_offset": dc,
        "click_count_estimate": click_count,
    }


# ---------------------------------------------------------------------------
# Optional content-correctness scorers (lazy-imported so sanity QA keeps
# working without torch installed). Per brief #06 — additive, not replacement.
# Only runs when --clap-prompt or --loop-check are passed.
# ---------------------------------------------------------------------------

_CLAP_MODEL = None


def _lazy_clap():
    """Load LAION-CLAP once per process. Returns the model handle.

    Uses the default 630k-audioset checkpoint, which is the recommended
    general-purpose audio-text checkpoint per the LAION-CLAP README.
    """
    global _CLAP_MODEL
    if _CLAP_MODEL is None:
        import laion_clap  # type: ignore
        m = laion_clap.CLAP_Module(enable_fusion=False)
        m.load_ckpt()  # downloads on first call; cached in HF cache after
        _CLAP_MODEL = m
    return _CLAP_MODEL


def clap_score(in_path: Path, prompt: str) -> dict:
    """Return cosine similarity between audio embedding and prompt embedding.

    Score in roughly [-1, 1]; >0.30 = matches prompt well, <0.20 = "this
    audio does not sound like the prompt." Per brief #06, the noise/static
    archive would have scored well below 0.20 against its biome prompts.
    """
    model = _lazy_clap()
    # CLAP eats stereo or mono; resamples internally. Pass file path directly.
    audio_emb = model.get_audio_embedding_from_filelist([str(in_path)], use_tensor=False)
    text_emb = model.get_text_embedding([prompt], use_tensor=False)
    # Cosine similarity (both already L2-normalized by laion-clap).
    sim = float(np.dot(audio_emb[0], text_emb[0]))
    return {
        "prompt": prompt,
        "clap_score": sim,
        "interpretation": (
            "matches" if sim > 0.30
            else "weak" if sim > 0.20
            else "does_not_match"
        ),
    }


def loop_seam_check(in_path: Path) -> dict:
    """Find best loop point via PyMusicLooper. Returns seam quality + offsets.

    Per brief #06: "if PyMusicLooper can't find a seam, the loop isn't loopable."
    We expose the cross-correlation score at the loop point as `seam_score`.
    """
    from pymusiclooper.core import MusicLooper  # type: ignore
    looper = MusicLooper(filename=str(in_path))
    pairs = looper.find_loop_pairs()
    if not pairs:
        return {"loop_found": False, "seam_score": 0.0, "loop_start_s": None, "loop_end_s": None}
    # PyMusicLooper sorts pairs by score descending. Top one is the cleanest seam.
    top = pairs[0]
    return {
        "loop_found": True,
        "seam_score": float(getattr(top, "score", getattr(top, "loop_score", 0.0))),
        "loop_start_s": float(getattr(top, "loop_start", 0)) / float(getattr(looper, "rate", 44100)),
        "loop_end_s": float(getattr(top, "loop_end", 0)) / float(getattr(looper, "rate", 44100)),
        "candidate_count": len(pairs),
    }


def qa(in_path: Path, out_dir: Path | None = None,
       *, clap_prompt: str | None = None, run_loop_check: bool = False) -> dict:
    samples, sr = read_wav(in_path)
    out_dir = out_dir or in_path.parent / f"{in_path.stem}_qa"
    out_dir.mkdir(parents=True, exist_ok=True)

    waveform_png(samples).save(out_dir / "waveform.png")
    spectrogram_png(samples, sr).save(out_dir / "spectrogram.png")
    info = sanity(samples, sr)
    info["source"] = str(in_path)
    info["waveform"] = str(out_dir / "waveform.png")
    info["spectrogram"] = str(out_dir / "spectrogram.png")

    # Optional content-correctness layer — only runs when user asks. Keeps
    # the default path zero-torch.
    if clap_prompt:
        try:
            info["clap"] = clap_score(in_path, clap_prompt)
        except Exception as e:
            info["clap"] = {"error": f"{type(e).__name__}: {e}",
                            "hint": "run from pipelines/audio/.venv (needs torch + laion-clap)"}
    if run_loop_check:
        try:
            info["loop"] = loop_seam_check(in_path)
        except Exception as e:
            info["loop"] = {"error": f"{type(e).__name__}: {e}",
                            "hint": "run from pipelines/audio/.venv (needs pymusiclooper)"}

    (out_dir / "qa.json").write_text(json.dumps(info, indent=2))
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--clap-prompt", default=None,
                    help="If set, computes CLAP audio-text similarity to this prompt. "
                         "Catches the noise/static failure mode that LUFS-only QA misses. "
                         "Requires the dedicated pipelines/audio/.venv (torch + laion-clap).")
    ap.add_argument("--loop-check", action="store_true",
                    help="If set, runs PyMusicLooper seam validation. "
                         "Flags WAVs where no clean loop point can be found. "
                         "Requires the dedicated pipelines/audio/.venv (pymusiclooper).")
    args = ap.parse_args()
    info = qa(args.input, args.out, clap_prompt=args.clap_prompt,
              run_loop_check=args.loop_check)
    print(f"[audio_qa] {args.input.name}: dur={info['duration_s']:.3f}s "
          f"rms={info['rms_dbfs']:.1f}dBFS peak={info['peak_dbfs']:.1f}dBFS "
          f"clipped={info['clipped_samples']} clicks~={info['click_count_estimate']}")
    if "clap" in info and "clap_score" in info["clap"]:
        c = info["clap"]
        print(f"[audio_qa] clap: prompt={c['prompt']!r}  score={c['clap_score']:+.3f}  ({c['interpretation']})")
    if "loop" in info and info["loop"].get("loop_found"):
        print(f"[audio_qa] loop: seam_score={info['loop']['seam_score']:.3f}  "
              f"start={info['loop']['loop_start_s']:.2f}s  end={info['loop']['loop_end_s']:.2f}s")


if __name__ == "__main__":
    main()
