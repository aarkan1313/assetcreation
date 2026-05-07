"""Biome ambience runner.

Per `research/E2_audio_local_ambience.md` sections 2.2-2.4 and 5.2. Reads
`recipes/biome_ambience.json`, generates the 4-layer ambience pack per
biome:

  bed_drone        loop, -28 LUFS,  always-on
  bed_air          loop, -30 LUFS,  always-on
  wildlife_sparse  one-shots, -22 LUFS peak, Poisson lambda~0.05/s
  distant_event    one-shots, -20 LUFS peak, Poisson lambda~0.01/s

Each source's `backend` field selects:
  - `local_audio_open` -> Stable Audio Open small/large via local_audio_open.py
  - `library`          -> CC0 lookup via cc0_ingest.py manifest
  - `synth`            -> jsfxr-style via synth_sfx.py (placeholder)

If `--dry-run` is passed (or local_audio_open is requested without a GPU and
`--allow-fallback` is set), beds use a duration-correct silent placeholder
and one-shots use synth_sfx.py presets so the rest of the pipeline (process,
QA, Godot exporter) can run end-to-end without GPU. The provenance
(`backend_actual`, `dry_run`) is recorded in every cue.json.

Output tree:
  audio/ambience/<biome>/
    bed_drone.wav  + .cue.json
    bed_air.wav    + .cue.json
    wildlife/
      <id_prefix>_v0.wav   ... + .cue.json (per-source)
    distant/
      <id_prefix>_v0.wav   ... + .cue.json
    biome_ambience.json    (per-biome manifest, consumed by ambience_pack.py)

CLI:
  # All four biomes, dry-run for plumbing
  python biome_ambience.py --recipe pipelines/audio/recipes/biome_ambience.json \
        --out audio/ambience --dry-run

  # Single biome, real GPU run
  python biome_ambience.py --biome ice_cavern \
        --recipe pipelines/audio/recipes/biome_ambience.json --out audio/ambience
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Local-pipeline imports
import local_audio_open as sao  # noqa: E402
import synth_sfx                 # noqa: E402
import process_audio             # noqa: E402
import audio_qa                  # noqa: E402
import loop_detect               # noqa: E402


SAMPLE_RATE = 44_100


@dataclass
class StemReport:
    biome: str
    stem: str
    backend_requested: str
    backend_actual: str
    out_path: str
    duration_s: float
    samplerate: int
    rms_dbfs: float
    peak_dbfs: float
    lufs_target: float
    seed: Optional[int]
    prompt: Optional[str]
    dry_run: bool
    loop: bool
    seam_rms: Optional[float] = None
    fitness: Optional[float] = None


@dataclass
class BiomeReport:
    biome: str
    stems: list[StemReport] = field(default_factory=list)
    reverb: dict = field(default_factory=dict)
    poisson_lambda: dict = field(default_factory=dict)
    timestamp: str = ""


# ---------- backend dispatch ----------


def _gen_local_audio_open(*, prompt: str, duration: float, model: str,
                          steps: int, seed: Optional[int],
                          negative_prompt: Optional[str],
                          dry_run: bool) -> tuple[np.ndarray, int, str]:
    """Try Stable Audio Open. On RuntimeError + dry_run, return placeholder."""
    if dry_run:
        return sao.silent_placeholder(duration), SAMPLE_RATE, "dry_run_silent"
    try:
        samples, sr = sao.generate(
            prompt, duration,
            model=model, steps=steps, seed=seed,
            negative_prompt=negative_prompt,
        )
        return samples, sr, "stable_audio_open"
    except RuntimeError as e:
        # GPU not available or model missing — caller decides.
        raise


def _gen_library(*, query: str, duration: float,
                 dry_run: bool, library_root: Path) -> tuple[np.ndarray, int, str]:
    """Look up a CC0 entry from cc0_ingest manifest. If missing or dry_run,
    return a silent placeholder so the pipeline keeps moving."""
    manifest_path = library_root / "manifest.json"
    if not manifest_path.exists() or dry_run:
        # No library yet, or dry-run - use placeholder.
        return sao.silent_placeholder(duration), SAMPLE_RATE, "library_placeholder"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Simple keyword-AND match across `tags` + `title` of each entry
        terms = [t.lower() for t in query.split() if t.strip()]
        for entry in manifest.get("entries", []):
            blob = " ".join([entry.get("title", ""),
                             " ".join(entry.get("tags", []))]).lower()
            if all(t in blob for t in terms):
                wav_path = Path(entry["wav"])
                if not wav_path.is_absolute():
                    wav_path = (library_root / wav_path).resolve()
                if wav_path.exists():
                    samples, sr = process_audio.read_wav(wav_path)
                    if sr != SAMPLE_RATE:
                        # naive resample to 44.1 via numpy.interp
                        n_target = int(round(len(samples) * SAMPLE_RATE / sr))
                        x_old = np.linspace(0, 1, len(samples))
                        x_new = np.linspace(0, 1, n_target)
                        samples = np.interp(x_new, x_old, samples).astype(np.float32)
                        sr = SAMPLE_RATE
                    # trim or loop-pad to target duration
                    n_target = int(round(duration * SAMPLE_RATE))
                    if len(samples) >= n_target:
                        samples = samples[:n_target]
                    else:
                        # tile then trim (for ambience beds)
                        reps = math.ceil(n_target / max(len(samples), 1))
                        samples = np.tile(samples, reps)[:n_target]
                    return samples.astype(np.float32), SAMPLE_RATE, f"library:{entry.get('id', 'unknown')}"
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    return sao.silent_placeholder(duration), SAMPLE_RATE, "library_placeholder"


def _gen_synth(*, preset: str, seed: int) -> tuple[np.ndarray, int, str]:
    samples = synth_sfx.synthesize(preset, seed=seed)
    return samples, SAMPLE_RATE, f"synth:{preset}"


def _generate_source(spec: dict, *,
                     dry_run: bool,
                     library_root: Path,
                     negative_prompt_default: Optional[str]) -> tuple[np.ndarray, int, str, dict]:
    """Run one `source` entry's backend. Returns
    (samples, sr, backend_actual, meta).
    """
    backend = spec.get("backend", "local_audio_open")
    duration = float(spec.get("duration", 1.5))
    seed = spec.get("seed")
    if backend == "local_audio_open":
        s, sr, actual = _gen_local_audio_open(
            prompt=spec["prompt"],
            duration=duration,
            model=spec.get("model", "small"),
            steps=int(spec.get("steps", 100)),
            seed=int(seed) if seed is not None else None,
            negative_prompt=spec.get("negative_prompt", negative_prompt_default),
            dry_run=dry_run,
        )
        return s, sr, actual, {
            "prompt": spec["prompt"],
            "model": spec.get("model", "small"),
            "steps": int(spec.get("steps", 100)),
        }
    if backend == "library":
        s, sr, actual = _gen_library(
            query=spec.get("query", ""),
            duration=duration,
            dry_run=dry_run,
            library_root=library_root,
        )
        # If library missed (placeholder) and a fallback is configured, try it.
        if actual == "library_placeholder" and spec.get("fallback_backend") == "local_audio_open" and not dry_run:
            try:
                s2, sr2, actual2 = _gen_local_audio_open(
                    prompt=spec["fallback_prompt"],
                    duration=duration,
                    model=spec.get("fallback_model", "large"),
                    steps=int(spec.get("steps", 100)),
                    seed=int(seed) if seed is not None else None,
                    negative_prompt=negative_prompt_default,
                    dry_run=False,
                )
                return s2, sr2, f"fallback->{actual2}", {
                    "library_query": spec.get("query"),
                    "fallback_prompt": spec["fallback_prompt"],
                }
            except RuntimeError:
                pass
        return s, sr, actual, {"library_query": spec.get("query")}
    if backend == "synth":
        s, sr, actual = _gen_synth(preset=spec["preset"], seed=int(spec.get("seed", 0)))
        return s, sr, actual, {"preset": spec["preset"]}
    raise ValueError(f"unknown backend {backend!r}")


# ---------- bed/sweetener stem builders ----------


def _build_bed(biome: str, stem: str, spec: dict, biome_dir: Path, *,
               dry_run: bool, library_root: Path,
               negative_prompt_default: Optional[str]) -> StemReport:
    out_path = biome_dir / f"{stem}.wav"
    samples, sr, backend_actual, meta = _generate_source(
        spec, dry_run=dry_run,
        library_root=library_root,
        negative_prompt_default=negative_prompt_default,
    ) if "backend" in spec else (
        sao.silent_placeholder(spec["duration"]), SAMPLE_RATE, "fallback_silent", {}
    )

    # Loop-detect + crossfade if requested
    seam_rms = None
    fitness = None
    if spec.get("loop", False) and len(samples) > sr:
        idx, fit = loop_detect.find_loop_end(samples, sr)
        samples = loop_detect.make_seamless_loop(samples, idx, crossfade_ms=80.0, sr=sr)
        seam_rms = float(loop_detect.loop_seam_rms(samples))
        fitness = float(fit)

    # LUFS-target normalize. We use the existing process_audio path; trim
    # disabled for beds (we want the whole loop preserved). Fades short
    # because beds will be looped at runtime.
    target = float(spec.get("lufs_target", -28.0))
    out, _rep = process_audio.process(
        samples, sr,
        target_rms_db=target,
        peak_ceiling_db=-1.0,
        fade_in_ms=20.0, fade_out_ms=20.0,
        trim=False,
    )
    process_audio.write_wav(out_path, out, sr)

    rms = float(process_audio.rms_lufs_proxy(out))
    peak = float(process_audio.peak_db(out))
    report = StemReport(
        biome=biome,
        stem=stem,
        backend_requested=spec.get("backend", "local_audio_open"),
        backend_actual=backend_actual,
        out_path=str(out_path),
        duration_s=float(len(out) / sr),
        samplerate=int(sr),
        rms_dbfs=rms,
        peak_dbfs=peak,
        lufs_target=target,
        seed=spec.get("seed"),
        prompt=spec.get("prompt") or spec.get("query"),
        dry_run=("dry_run" in backend_actual or "placeholder" in backend_actual),
        loop=bool(spec.get("loop", False)),
        seam_rms=seam_rms,
        fitness=fitness,
    )
    # cue.json next to the stem
    cue = asdict(report)
    cue.update(meta)
    out_path.with_suffix(".cue.json").write_text(json.dumps(cue, indent=2))
    return report


def _build_sweeteners(biome: str, stem: str, group: dict, biome_dir: Path, *,
                      dry_run: bool, library_root: Path,
                      negative_prompt_default: Optional[str]) -> list[StemReport]:
    """Generate N variants of each source in the sweetener group.

    Output structure:
      <biome_dir>/<stem>/<id_prefix>_v0.wav, _v1.wav, ...
    Each gets its own cue.json with provenance.
    """
    sub = biome_dir / stem
    sub.mkdir(parents=True, exist_ok=True)
    target_peak = float(group.get("lufs_target_peak", -22.0))
    out: list[StemReport] = []

    for src in group.get("sources", []):
        count = int(src.get("count", 1))
        id_prefix = src.get("id_prefix", "sweet")
        for v in range(count):
            # Seed per-variant so variants differ but are reproducible
            spec_v = dict(src)
            base_seed = int(src.get("seed", 0))
            spec_v["seed"] = base_seed + v
            samples, sr, backend_actual, meta = _generate_source(
                spec_v, dry_run=dry_run,
                library_root=library_root,
                negative_prompt_default=negative_prompt_default,
            )
            # Sweeteners get full processing (trim+fade+normalize). Per E2 we
            # target a peak loudness, not RMS, but our existing path normalizes
            # by RMS first then ceiling-limits — close enough for one-shots
            # under a peak cap. We pass target_rms_db = target_peak - 6 to
            # leave headroom under the peak ceiling.
            rms_target = target_peak - 6.0
            out_samples, _rep = process_audio.process(
                samples, sr,
                target_rms_db=rms_target,
                peak_ceiling_db=target_peak,  # ceiling acts as peak limit
                fade_in_ms=5.0, fade_out_ms=12.0,
                trim=True,
            )
            out_path = sub / f"{id_prefix}_v{v}.wav"
            process_audio.write_wav(out_path, out_samples, sr)

            report = StemReport(
                biome=biome,
                stem=f"{stem}/{id_prefix}_v{v}",
                backend_requested=spec_v.get("backend", "local_audio_open"),
                backend_actual=backend_actual,
                out_path=str(out_path),
                duration_s=float(len(out_samples) / sr),
                samplerate=int(sr),
                rms_dbfs=float(process_audio.rms_lufs_proxy(out_samples)),
                peak_dbfs=float(process_audio.peak_db(out_samples)),
                lufs_target=target_peak,
                seed=spec_v.get("seed"),
                prompt=spec_v.get("prompt") or spec_v.get("query"),
                dry_run=("dry_run" in backend_actual or "placeholder" in backend_actual),
                loop=False,
            )
            cue = asdict(report)
            cue.update(meta)
            out_path.with_suffix(".cue.json").write_text(json.dumps(cue, indent=2))
            out.append(report)

    return out


# ---------- top-level driver ----------


def build_biome(biome_id: str, biome_spec: dict, recipe: dict, out_root: Path, *,
                dry_run: bool,
                library_root: Path) -> BiomeReport:
    biome_dir = out_root / biome_id
    biome_dir.mkdir(parents=True, exist_ok=True)
    neg = recipe.get("negative_prompt_default")

    report = BiomeReport(biome=biome_id)
    report.reverb = biome_spec.get("reverb", {})
    report.timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Beds
    for stem in ("bed_drone", "bed_air"):
        spec = biome_spec.get(stem)
        if not spec:
            continue
        sr = _build_bed(
            biome_id, stem, spec, biome_dir,
            dry_run=dry_run, library_root=library_root,
            negative_prompt_default=neg,
        )
        report.stems.append(sr)
        print(f"[biome_ambience] {biome_id}.{stem}: "
              f"{sr.backend_actual:24s} dur={sr.duration_s:5.1f}s "
              f"rms={sr.rms_dbfs:6.1f} peak={sr.peak_dbfs:6.1f} loop={sr.loop} "
              f"seam={sr.seam_rms}")

    # Sweeteners (Poisson)
    for stem in ("wildlife_sparse", "distant_event"):
        group = biome_spec.get(stem)
        if not group:
            continue
        report.poisson_lambda[stem] = float(group.get("poisson_lambda_per_sec", 0.0))
        children = _build_sweeteners(
            biome_id, stem, group, biome_dir,
            dry_run=dry_run, library_root=library_root,
            negative_prompt_default=neg,
        )
        report.stems.extend(children)
        print(f"[biome_ambience] {biome_id}.{stem}: {len(children)} variants "
              f"(lambda={report.poisson_lambda[stem]:.3f}/s)")

    # Per-biome manifest (consumed by ambience_pack.py)
    manifest = {
        "biome": biome_id,
        "reverb": report.reverb,
        "poisson_lambda_per_sec": report.poisson_lambda,
        "timestamp": report.timestamp,
        "stems": [asdict(s) for s in report.stems],
    }
    (biome_dir / "biome_ambience.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return report


def build_all(recipe: dict, out_root: Path, *,
              dry_run: bool, library_root: Path,
              biomes: Optional[list[str]] = None) -> list[BiomeReport]:
    out_root.mkdir(parents=True, exist_ok=True)
    selected = biomes or list(recipe["biomes"].keys())
    reports = []
    for bid in selected:
        if bid not in recipe["biomes"]:
            print(f"[biome_ambience] WARN: biome {bid!r} not in recipe; skipping",
                  file=sys.stderr)
            continue
        print(f"\n=== {bid} ===")
        rep = build_biome(
            bid, recipe["biomes"][bid], recipe, out_root,
            dry_run=dry_run, library_root=library_root,
        )
        reports.append(rep)

    # Top-level manifest
    summary = {
        "version": recipe.get("version", 1),
        "schema_version": recipe.get("schema_version", 1),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "biomes": {r.biome: {
            "reverb": r.reverb,
            "poisson_lambda_per_sec": r.poisson_lambda,
            "stem_count": len(r.stems),
            "all_dry_run": all(s.dry_run for s in r.stems),
        } for r in reports},
        "total_stems": sum(len(r.stems) for r in reports),
        "dry_run": dry_run,
    }
    (out_root / "ambience_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return reports


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", type=Path,
                    default=Path(r"D:\assets\pipelines\audio\recipes\biome_ambience.json"))
    ap.add_argument("--out", type=Path,
                    default=Path(r"D:\assets\audio\ambience"))
    ap.add_argument("--biome", action="append", default=None,
                    help="Restrict to one or more biomes (can be passed multiple times)")
    ap.add_argument("--library", type=Path,
                    default=Path(r"D:\assets\audio\library"),
                    help="CC0 library root (cc0_ingest output).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip GPU; use silent placeholders for all AI sources.")
    args = ap.parse_args()

    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    started = time.monotonic()
    reports = build_all(
        recipe, args.out,
        dry_run=args.dry_run, library_root=args.library,
        biomes=args.biome,
    )
    wall = time.monotonic() - started
    total = sum(len(r.stems) for r in reports)
    print(f"\n[biome_ambience] built {len(reports)} biomes / {total} stems "
          f"in {wall:.1f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
