"""OpenAI Text-to-Speech adapter.

Same shape as `eleven_sfx.py` and parallel to UI's `openai_icons.py`. Used
for **draft voice lines** during pre-production: NPC barks, placeholder
dialog, accessibility narration. The 2026 OpenAI Audio API exposes:

  - `gpt-4o-mini-tts`  : default; expressive, supports the `instructions=`
                          field for tone/style steering.
  - `tts-1`            : older / faster / cheaper; no instructions.
  - `tts-1-hd`         : higher fidelity tier of the older family.

Voice presets shipped by OpenAI (alphabetical, all 6 voices stable across
both model families): `alloy`, `ash`, `coral`, `echo`, `fable`, `onyx`,
`nova`, `sage`, `shimmer`. The set may grow; pass `--voice` arbitrary if
the SDK accepts it.

Output formats: `wav` is the simplest sink for our pipeline (no mp3 decode
needed). We default to `wav` so the rest of the chain (process_audio /
audio_qa / export_godot) can read the result with `wave.open(...)`. mp3 /
opus / aac / flac available too, but require ffmpeg / soundfile downstream.

Cost shape (2026 pricing, subject to change):
  gpt-4o-mini-tts ~ $0.60 / 1 M input chars   (~$0.001 per ~1700-char line)
  tts-1            ~ $15.00 / 1 M input chars
  tts-1-hd         ~ $30.00 / 1 M input chars

Per the brief this is **build-only** today. We never spend cloud money
without explicit user approval. This adapter:

  - Default mode (no `--run`): writes a *plan JSON* mirroring the
    `pipelines/ui/pixellab_icons.py` pattern: prompt + voice + model + cost
    estimate to `audio/tts_plans/<id>.openai_tts_plan.json`. No HTTP.
  - `--run` mode: requires `OPENAI_API_KEY` AND `--max-cost-usd <cap>`.
    Estimated cost is computed up front; if it exceeds the cap, the tool
    refuses without calling the API.

CLI:
  # Plan one line (no spend)
  python openai_tts.py --text "Halt, traveler." --id npc_guard_halt --voice ash

  # Plan a batch from a JSONL of {id, text, voice, model, instructions}
  python openai_tts.py --batch lines.jsonl --out audio/voice/

  # Real run (requires key + cap)
  python openai_tts.py --batch lines.jsonl --out audio/voice/ \\
        --run --max-cost-usd 0.50

  # Module API (mirrors eleven_sfx.generate)
  from openai_tts import generate
  samples, sr = generate("Hello.", voice="alloy", model="gpt-4o-mini-tts")

Mode contract (parallels eleven_sfx.py):
  - `generate(text, *, voice, model, instructions, response_format='wav')
       -> (samples_float32_mono, samplerate)`
  - Raises RuntimeError if no key, on HTTP error, or on unknown format.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import wave
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

DEFAULT_ENDPOINT = "https://api.openai.com/v1/audio/speech"
DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"
DEFAULT_FORMAT = "wav"

# Pricing per 1 M input characters (USD, 2026 list price; periodically refresh).
PRICE_PER_M_CHARS = {
    "gpt-4o-mini-tts": 0.60,
    "tts-1":          15.00,
    "tts-1-hd":       30.00,
}

VALID_VOICES = {
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "onyx", "nova", "sage", "shimmer", "verse",
}


@dataclass
class TtsPlan:
    id: str
    text: str
    voice: str
    model: str
    instructions: Optional[str]
    response_format: str
    chars: int
    estimated_usd: float
    out_path: Optional[str] = None


@dataclass
class TtsResult(TtsPlan):
    actual_usd_billed: Optional[float] = None
    duration_s: Optional[float] = None
    samplerate: Optional[int] = None
    timestamp: str = ""


def _has_key() -> tuple[bool, str | None]:
    if not os.environ.get("OPENAI_API_KEY"):
        return False, "OPENAI_API_KEY not set"
    return True, None


def estimate_cost_usd(text: str, model: str = DEFAULT_MODEL) -> float:
    """Rough USD cost. Conservative: count chars (not tokens) as the meter."""
    rate = PRICE_PER_M_CHARS.get(model, PRICE_PER_M_CHARS[DEFAULT_MODEL])
    return (len(text) / 1_000_000.0) * rate


def make_plan(*, text: str, id: str, voice: str = DEFAULT_VOICE,
              model: str = DEFAULT_MODEL,
              instructions: Optional[str] = None,
              response_format: str = DEFAULT_FORMAT,
              out_path: Optional[Path] = None) -> TtsPlan:
    if voice not in VALID_VOICES:
        # Soft-warn; the API may know voices we don't.
        print(f"[openai_tts] WARN: voice {voice!r} not in known set "
              f"{sorted(VALID_VOICES)}; trying anyway.", file=sys.stderr)
    return TtsPlan(
        id=id,
        text=text,
        voice=voice,
        model=model,
        instructions=instructions,
        response_format=response_format,
        chars=len(text),
        estimated_usd=estimate_cost_usd(text, model),
        out_path=str(out_path) if out_path else None,
    )


def _parse_wav_bytes(buf: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(buf), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 4:
        arr = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sw == 1:
        arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        raise RuntimeError(f"openai_tts: unsupported WAV sample width {sw}")
    if ch == 2:
        arr = arr.reshape(-1, 2).mean(axis=1)
    return arr.astype(np.float32), int(sr)


def generate(text: str, *,
             voice: str = DEFAULT_VOICE,
             model: str = DEFAULT_MODEL,
             instructions: Optional[str] = None,
             response_format: str = DEFAULT_FORMAT,
             endpoint: str = DEFAULT_ENDPOINT,
             timeout_s: float = 60.0) -> tuple[np.ndarray, int]:
    """Call OpenAI TTS. Returns (samples_float32_mono, samplerate).

    Raises RuntimeError if no key, or on any HTTP / decode error.
    """
    ok, reason = _has_key()
    if not ok:
        raise RuntimeError(f"openai_tts: {reason}")

    import requests  # available
    payload: dict = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": response_format,
    }
    if instructions:
        payload["instructions"] = instructions
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_s)
    if resp.status_code != 200:
        raise RuntimeError(f"openai_tts: HTTP {resp.status_code}: {resp.text[:300]}")
    raw = resp.content
    if response_format == "wav":
        return _parse_wav_bytes(raw)
    if response_format == "pcm":
        # API spec: 16-bit signed LE, 24 kHz mono
        arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        return arr, 24_000
    raise RuntimeError(
        f"openai_tts: response_format {response_format!r} requires ffmpeg; "
        f"use response_format='wav' or 'pcm' to avoid that dependency."
    )


def write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())


# ---------- CLI ----------

def _load_batch(path: Path) -> list[dict]:
    rows: list[dict] = []
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and "lines" in data:
            rows = data["lines"]
        else:
            raise RuntimeError(f"unexpected JSON shape for batch: {path}")
    else:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rows.append(json.loads(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="Single TTS line (use --batch for many).")
    ap.add_argument("--id", default=None, help="Output stem id (no extension).")
    ap.add_argument("--batch", type=Path,
                    help="JSON or JSONL of rows: {id, text, voice?, model?, "
                         "instructions?, response_format?}.")
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--instructions", default=None,
                    help="Style/tone steering (gpt-4o-mini-tts only).")
    ap.add_argument("--response-format", default=DEFAULT_FORMAT,
                    choices=("wav", "pcm", "mp3", "opus", "aac", "flac"))
    ap.add_argument("--out", type=Path, default=Path(r"D:\assets\audio\voice"))
    ap.add_argument("--plans-dir", type=Path,
                    default=Path(r"D:\assets\audio\tts_plans"))
    ap.add_argument("--run", action="store_true",
                    help="Actually call the API. Requires OPENAI_API_KEY AND "
                         "--max-cost-usd. Default is plan-only.")
    ap.add_argument("--max-cost-usd", type=float, default=None,
                    help="Hard cap. Tool refuses to call if estimate exceeds.")
    args = ap.parse_args()

    # Build the row list
    rows: list[dict] = []
    if args.batch:
        rows = _load_batch(args.batch)
    elif args.text:
        if not args.id:
            print("[openai_tts] --text requires --id", file=sys.stderr)
            return 2
        rows = [{"id": args.id, "text": args.text}]
    else:
        print("[openai_tts] need --text + --id, or --batch <file>",
              file=sys.stderr)
        return 2

    # Plan every row first (works without a key)
    plans: list[TtsPlan] = []
    for r in rows:
        if "id" not in r or "text" not in r:
            print(f"[openai_tts] skip row (missing id/text): {r}", file=sys.stderr)
            continue
        out_path = args.out / f"{r['id']}.wav"
        plans.append(make_plan(
            text=r["text"],
            id=r["id"],
            voice=r.get("voice", args.voice),
            model=r.get("model", args.model),
            instructions=r.get("instructions", args.instructions),
            response_format=r.get("response_format", args.response_format),
            out_path=out_path,
        ))

    total_cost = sum(p.estimated_usd for p in plans)
    print(f"[openai_tts] planned {len(plans)} line(s), total chars="
          f"{sum(p.chars for p in plans)}, est ~${total_cost:.4f} USD")

    # Always write the plan JSON, even in --run mode (provenance).
    args.plans_dir.mkdir(parents=True, exist_ok=True)
    for p in plans:
        plan_path = args.plans_dir / f"{p.id}.openai_tts_plan.json"
        plan_path.write_text(json.dumps(asdict(p), indent=2), encoding="utf-8")
    print(f"[openai_tts] wrote {len(plans)} plan JSON(s) to {args.plans_dir}")

    if not args.run:
        print("[openai_tts] PLAN ONLY (no API spend). Pass --run --max-cost-usd <cap> to execute.")
        return 0

    # --run: gates
    ok, reason = _has_key()
    if not ok:
        print(f"[openai_tts] {reason}; pass OPENAI_API_KEY=... to enable --run.",
              file=sys.stderr)
        return 2
    if args.max_cost_usd is None:
        print("[openai_tts] --run requires --max-cost-usd <cap>.", file=sys.stderr)
        return 2
    if total_cost > args.max_cost_usd:
        print(f"[openai_tts] REFUSING: estimated ${total_cost:.4f} > cap "
              f"${args.max_cost_usd:.4f}", file=sys.stderr)
        return 2

    # Run
    args.out.mkdir(parents=True, exist_ok=True)
    results: list[TtsResult] = []
    for p in plans:
        try:
            samples, sr = generate(
                p.text, voice=p.voice, model=p.model,
                instructions=p.instructions,
                response_format=p.response_format,
            )
        except RuntimeError as e:
            print(f"[openai_tts]   {p.id}: FAILED {e}", file=sys.stderr)
            continue
        out_path = Path(p.out_path) if p.out_path else (args.out / f"{p.id}.wav")
        write_wav(out_path, samples, sr)
        result = TtsResult(
            **asdict(p),
            actual_usd_billed=None,  # API doesn't expose; trust the estimate
            duration_s=float(len(samples) / sr),
            samplerate=int(sr),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        results.append(result)
        print(f"[openai_tts]   {p.id} -> {out_path} "
              f"({result.duration_s:.2f}s @ {sr} Hz)")

    # Per-batch result manifest
    manifest_path = args.out / "openai_tts_manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        existing = {"version": 1, "lines": []}
    existing["lines"].extend(asdict(r) for r in results)
    manifest_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"[openai_tts] manifest -> {manifest_path} (+{len(results)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
