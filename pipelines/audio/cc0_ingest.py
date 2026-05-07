"""CC0 / royalty-free library ingester for Sonniss + Freesound.

Per `research/E2_audio_local_ambience.md` section 5.4 + 4. Two modes:

  --sonniss <DIR>     Walk a Sonniss GameAudioGDC bundle directory, normalize
                      every WAV, write to audio/library/sonniss/<category>/<id>.wav
                      with a manifest row. Royalty-free media license; no AI
                      training but direct asset use is fine.

  --freesound TERMS   Query Freesound API filtered to license:"Creative
                      Commons 0", download top N matches, normalize, manifest.
                      Gated on FREESOUND_API_KEY env var.

Both feed the same `audio/library/manifest.json` consumed by `biome_ambience.py`
when a recipe entry has `backend: library`.

Manifest row shape:
  {
    "id":       "sonniss_grass_wind_a01",
    "source":   "sonniss" | "freesound",
    "title":    "Wind through grass field",
    "tags":     ["wind", "grass", "outdoor", "ambience"],
    "license":  "royalty-free media" | "CC0",
    "attribution": "...",
    "wav":      "sonniss/ambience/sonniss_grass_wind_a01.wav",  # relative to library root
    "duration_s": 12.3,
    "samplerate": 44100,
    "rms_dbfs":  -25.4,
    "peak_dbfs": -2.8,
    "biome_candidates": ["grassland"],   # heuristic from filename keywords
    "ingested_at": "2026-05-06T..."
  }

Heuristic biome tagging: filename or directory path keyword matches against the
biome registry; matches are advisory only (the recipe still has to specifically
call `query: "..."` to use it).

CLI:
  # Sonniss bundle ingest (one-time after manual download)
  python cc0_ingest.py --sonniss /mnt/d/sound_libraries/sonniss_2024/ \
        --target ambience --max 200

  # Freesound CC0 search
  python cc0_ingest.py --freesound "wind through grass" --max 5

  # Index-only (no downloads; rebuild manifest from existing files)
  python cc0_ingest.py --reindex
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import process_audio  # noqa: E402


ASSETS = Path(r"D:\assets")
LIBRARY_ROOT = ASSETS / "audio" / "library"

# Filename keyword -> biome candidate. Matches are case-insensitive substring.
BIOME_KEYWORDS = {
    "lava_field":  ["lava", "magma", "volcan", "ember", "ash", "geyser"],
    "ice_cavern":  ["ice", "frost", "glacier", "crevasse", "cavern", "drip", "frozen"],
    "mana_crystal": ["crystal", "arcane", "magic", "sparkle", "chime", "bell", "harmonic"],
    "grassland":   ["grass", "meadow", "wind", "leaf", "rustle", "breeze", "bird",
                    "chirp", "cricket", "thunder", "outdoor"],
}


@dataclass
class LibraryEntry:
    id: str
    source: str
    title: str
    tags: list[str]
    license: str
    attribution: str
    wav: str
    duration_s: float
    samplerate: int
    rms_dbfs: float
    peak_dbfs: float
    biome_candidates: list[str] = field(default_factory=list)
    ingested_at: str = ""


def slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:60] or "untitled"


def derive_tags(path: Path) -> list[str]:
    """Cheap tag extraction from path components + filename stem."""
    parts = [p for p in path.parts if p not in ("/", "\\", "")]
    stem = path.stem
    blob = " ".join(parts + [stem]).lower()
    tags = sorted(set(re.findall(r"[a-z]{3,}", blob)))
    return tags[:32]


def biome_candidates_from_path(path: Path) -> list[str]:
    """Match filename/path against BIOME_KEYWORDS heuristic."""
    blob = str(path).lower()
    out = []
    for biome, kws in BIOME_KEYWORDS.items():
        if any(k in blob for k in kws):
            out.append(biome)
    return out


def measure(samples: np.ndarray, sr: int) -> tuple[float, float]:
    rms = float(process_audio.rms_lufs_proxy(samples))
    peak = float(process_audio.peak_db(samples))
    return rms, peak


def normalize_and_write(samples: np.ndarray, sr: int, dst: Path,
                       *, target_rms_db: float = -23.0,
                       peak_ceiling_db: float = -1.0) -> None:
    """Library entries are normalized to a permissive -23 dBFS target so the
    biome ambience runner can pull them and re-target per-stem (-28/-30/-22/-20)
    without losing too much headroom."""
    out, _rep = process_audio.process(
        samples, sr,
        target_rms_db=target_rms_db,
        peak_ceiling_db=peak_ceiling_db,
        fade_in_ms=5.0, fade_out_ms=10.0,
        trim=True,
    )
    process_audio.write_wav(dst, out, sr)


# ---------- Sonniss walker ----------


def walk_sonniss(bundle_root: Path, *, library_root: Path,
                 target_category: Optional[str] = None,
                 max_files: int = 0) -> list[LibraryEntry]:
    """Walk a Sonniss bundle (or any flat WAV tree) and ingest.

    Sonniss GameAudioGDC bundles vary in tree shape; we just recursively glob
    for `.wav` and use the parent-directory name as the category bucket.
    """
    out: list[LibraryEntry] = []
    if not bundle_root.exists():
        print(f"[cc0_ingest] sonniss path not found: {bundle_root}", file=sys.stderr)
        return out
    wavs = sorted(bundle_root.rglob("*.wav"))
    if max_files:
        wavs = wavs[:max_files]
    for src in wavs:
        try:
            samples, sr = process_audio.read_wav(src)
        except Exception as e:
            print(f"[cc0_ingest]   skip {src.name}: {e}", file=sys.stderr)
            continue
        if len(samples) < int(0.1 * sr):  # too short to be useful
            continue
        category = (target_category
                    or (src.parent.name.lower() if src.parent.name else "uncategorized"))
        sid = f"sonniss_{slug(src.stem)}"
        rel = Path("sonniss") / category / f"{sid}.wav"
        dst = library_root / rel
        normalize_and_write(samples, sr, dst, target_rms_db=-23.0)
        # measure post-normalization
        out_samples, out_sr = process_audio.read_wav(dst)
        rms, peak = measure(out_samples, out_sr)
        out.append(LibraryEntry(
            id=sid,
            source="sonniss",
            title=src.stem.replace("_", " "),
            tags=derive_tags(src),
            license="royalty-free media (Sonniss GameAudioGDC; no AI training)",
            attribution="Sonniss GDC bundle",
            wav=str(rel).replace("\\", "/"),
            duration_s=float(len(out_samples) / out_sr),
            samplerate=int(out_sr),
            rms_dbfs=rms,
            peak_dbfs=peak,
            biome_candidates=biome_candidates_from_path(src),
            ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ))
    return out


# ---------- Freesound API ----------


FREESOUND_URL = "https://freesound.org/apiv2/search/text/"


def freesound_search(query: str, max_results: int = 5) -> list[dict]:
    """Hit Freesound API, return list of {id,name,download_url,tags}.

    Filters license to CC0 only. Caller-supplied API key via FREESOUND_API_KEY.
    Docs: https://freesound.org/docs/api/resources_apiv2.html
    """
    key = os.environ.get("FREESOUND_API_KEY")
    if not key:
        raise RuntimeError(
            "cc0_ingest: FREESOUND_API_KEY not set. Get one at "
            "https://freesound.org/apiv2/apply/"
        )
    import requests  # type: ignore
    params = {
        "query": query,
        "filter": 'license:"Creative Commons 0"',
        "fields": "id,name,tags,license,username,previews,duration,samplerate",
        "page_size": int(max_results),
        "token": key,
    }
    resp = requests.get(FREESOUND_URL, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"freesound: HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("results", []) or []


def freesound_download(result: dict, *, library_root: Path,
                       category: str = "freesound") -> Optional[LibraryEntry]:
    """Fetch a Freesound preview WAV. Free preview is hq mp3 by default; we
    prefer ogg if available so we don't need an mp3 decoder.

    The free `previews` dict shape:
      {
        "preview-hq-mp3": "...",
        "preview-hq-ogg": "...",
        "preview-lq-mp3": "...",
        "preview-lq-ogg": "..."
      }
    Authenticated download endpoint requires OAuth2; previews work with a
    plain API key. For ingestion-quality work, OAuth2 is recommended later;
    previews are good enough for placeholder/iteration.
    """
    import requests  # type: ignore
    previews = result.get("previews", {}) or {}
    url = previews.get("preview-hq-ogg") or previews.get("preview-hq-mp3")
    if not url:
        return None
    sid = f"freesound_{result['id']}_{slug(result.get('name', 'untitled'))}"
    fmt = "ogg" if url.endswith(".ogg") else "mp3"
    src = library_root / "freesound" / category / f"{sid}.{fmt}"
    src.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        return None
    src.write_bytes(resp.content)

    # Decode -> WAV. Two-tier: prefer `soundfile` (ogg/flac), fall back to
    # the optional `ffmpeg_decode` helper for MP3 / Opus / M4A previews.
    wav_path = src.with_suffix(".wav")
    decoded = False
    decode_err = None
    try:
        import soundfile as sf  # type: ignore
        data, sr = sf.read(str(src), dtype="float32", always_2d=False)
        if data.ndim == 2:
            data = data.mean(axis=1)
        normalize_and_write(data.astype(np.float32), int(sr), wav_path)
        decoded = True
    except Exception as e:
        decode_err = e
    if not decoded:
        # Optional ffmpeg fallback (handles MP3 + anything soundfile rejects).
        try:
            import ffmpeg_decode  # type: ignore
            res = ffmpeg_decode.decode_or_none(src, sr=44_100)
            if res is not None:
                data, sr = res
                normalize_and_write(data.astype(np.float32), int(sr), wav_path)
                decoded = True
            elif decode_err is not None:
                print(f"[cc0_ingest]   {sid}: WAV decode failed ({decode_err}); "
                      f"ffmpeg not in PATH; kept {fmt} source",
                      file=sys.stderr)
        except Exception as e:
            print(f"[cc0_ingest]   {sid}: WAV decode failed ({decode_err}); "
                  f"ffmpeg fallback also failed ({e}); kept {fmt} source",
                  file=sys.stderr)
    if not decoded:
        return None
    src.unlink(missing_ok=True)
    out_samples, out_sr = process_audio.read_wav(wav_path)
    rms, peak = measure(out_samples, out_sr)
    rel = Path("freesound") / category / wav_path.name

    return LibraryEntry(
        id=sid,
        source="freesound",
        title=result.get("name", ""),
        tags=list(result.get("tags", []))[:32],
        license="CC0",
        attribution=f"Freesound user '{result.get('username', 'unknown')}'",
        wav=str(rel).replace("\\", "/"),
        duration_s=float(len(out_samples) / out_sr),
        samplerate=int(out_sr),
        rms_dbfs=rms,
        peak_dbfs=peak,
        biome_candidates=biome_candidates_from_path(Path(result.get("name", ""))),
        ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ---------- manifest ----------


def load_manifest(library_root: Path) -> dict:
    manifest_path = library_root / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"version": 1, "entries": []}


def write_manifest(library_root: Path, manifest: dict) -> None:
    library_root.mkdir(parents=True, exist_ok=True)
    manifest_path = library_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def upsert(manifest: dict, entries: list[LibraryEntry]) -> int:
    """Add/replace by id. Returns number added or replaced."""
    existing = {e["id"]: i for i, e in enumerate(manifest["entries"])}
    n = 0
    for e in entries:
        d = asdict(e)
        if e.id in existing:
            manifest["entries"][existing[e.id]] = d
        else:
            manifest["entries"].append(d)
        n += 1
    return n


def reindex(library_root: Path) -> dict:
    """Rebuild manifest from disk (every .wav under library_root/{sonniss,freesound}/...)."""
    entries: list[LibraryEntry] = []
    for src_kind in ("sonniss", "freesound"):
        root = library_root / src_kind
        if not root.exists():
            continue
        for wav in sorted(root.rglob("*.wav")):
            try:
                samples, sr = process_audio.read_wav(wav)
            except Exception:
                continue
            rms, peak = measure(samples, sr)
            rel = wav.relative_to(library_root)
            sid = wav.stem
            entries.append(LibraryEntry(
                id=sid,
                source=src_kind,
                title=sid.replace("_", " "),
                tags=derive_tags(wav),
                license=("CC0" if src_kind == "freesound"
                         else "royalty-free media (Sonniss GameAudioGDC; no AI training)"),
                attribution=src_kind,
                wav=str(rel).replace("\\", "/"),
                duration_s=float(len(samples) / sr),
                samplerate=int(sr),
                rms_dbfs=rms,
                peak_dbfs=peak,
                biome_candidates=biome_candidates_from_path(wav),
                ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ))
    manifest = {"version": 1, "entries": [asdict(e) for e in entries]}
    write_manifest(library_root, manifest)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--library-root", type=Path, default=LIBRARY_ROOT)
    ap.add_argument("--sonniss", type=Path, default=None,
                    help="Path to a Sonniss bundle directory; recursively ingest WAVs.")
    ap.add_argument("--target", default=None,
                    help="Override the category bucket (default: parent dir name).")
    ap.add_argument("--freesound", type=str, default=None,
                    help="Search query for the Freesound CC0 API.")
    ap.add_argument("--max", type=int, default=10,
                    help="Max files per source pass.")
    ap.add_argument("--reindex", action="store_true",
                    help="Rebuild manifest from existing on-disk files only; no fetches.")
    args = ap.parse_args()

    args.library_root.mkdir(parents=True, exist_ok=True)
    if args.reindex:
        m = reindex(args.library_root)
        print(f"[cc0_ingest] reindexed: {len(m['entries'])} entries -> "
              f"{args.library_root / 'manifest.json'}")
        return 0

    manifest = load_manifest(args.library_root)
    added = 0
    if args.sonniss:
        entries = walk_sonniss(args.sonniss,
                               library_root=args.library_root,
                               target_category=args.target,
                               max_files=args.max)
        added += upsert(manifest, entries)
        print(f"[cc0_ingest] sonniss: {len(entries)} entries from {args.sonniss}")
    if args.freesound:
        try:
            results = freesound_search(args.freesound, max_results=args.max)
        except RuntimeError as e:
            print(f"[cc0_ingest] {e}", file=sys.stderr)
            return 2
        ingested = []
        for r in results:
            time.sleep(0.2)  # be polite
            entry = freesound_download(
                r, library_root=args.library_root,
                category=args.target or "uncategorized",
            )
            if entry:
                ingested.append(entry)
        added += upsert(manifest, ingested)
        print(f"[cc0_ingest] freesound: {len(ingested)}/{len(results)} CC0 results "
              f"for query {args.freesound!r}")

    if added:
        write_manifest(args.library_root, manifest)
        print(f"[cc0_ingest] manifest updated: total entries = "
              f"{len(manifest['entries'])} -> {args.library_root / 'manifest.json'}")
    else:
        print("[cc0_ingest] nothing added; pass --sonniss DIR or --freesound QUERY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
