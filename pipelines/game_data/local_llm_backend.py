"""Local constrained-generation backend scaffold.

CPU/default mode does not load a model. It builds the prompt, exports the JSON
Schema, runs a parser/enforcer smoke test against a synthetic sample, and
writes a dry-run report. Runtime model loading is gated behind:

  --device cuda --run-model

Phase 9 adds the production local path:

  vLLM OpenAI-compatible server + guided_json + xgrammar

The old outlines path remains as a direct-transformers fallback.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import generate_records  # noqa: E402
from schemas import RECORD_TYPES, plural  # noqa: E402

GAME_DATA = Path(r"D:\assets\game_data")
REPORTS = GAME_DATA / "reports"
GENERATED = GAME_DATA / "generated"


def build_prompt(record_type: str, count: int, brief: str | None = None) -> str:
    cls = RECORD_TYPES[record_type]
    fields = ", ".join(cls.model_json_schema().get("properties", {}).keys())
    prompt = (
        f"Generate exactly {count} {record_type} record(s) for TLTE. "
        "Return JSON only, shaped as {\"records\": [...]}. "
        f"Required schema fields include: {fields}. "
        "Use lowercase snake_case IDs, coherent fantasy ARPG naming, and no duplicate display names."
    )
    if brief:
        prompt += "\nDesign brief:\n" + brief.strip()
    return prompt


def parse_records_payload(record_type: str, payload: str | dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload
    if isinstance(data, dict) and "records" in data:
        raw_records = data["records"]
    elif isinstance(data, list):
        raw_records = data
    else:
        raw_records = [data]
    cls = RECORD_TYPES[record_type]
    return [cls.model_validate(raw).model_dump() for raw in raw_records]


def wrapper_schema(record_type: str, count: int) -> dict[str, Any]:
    cls = RECORD_TYPES[record_type]
    return {
        "type": "object",
        "properties": {
            "records": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": cls.model_json_schema(),
            }
        },
        "required": ["records"],
        "additionalProperties": False,
    }


def build_vllm_request(
    record_type: str,
    count: int,
    *,
    seed: int,
    model: str,
    brief: str | None,
    guided_backend: str,
    max_tokens: int,
) -> dict[str, Any]:
    prompt = build_prompt(record_type, count, brief)
    prompt += (
        f"\nSeed hint: {seed}.\n"
        "Return exactly one JSON object and no markdown."
    )
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You generate strictly valid JSON game-data records for TLTE.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "guided_json": wrapper_schema(record_type, count),
        "guided_decoding_backend": guided_backend,
    }


def dry_run(
    record_type: str,
    count: int,
    *,
    seed: int,
    model: str,
    brief: str | None,
    guided_backend: str = "xgrammar",
    max_tokens: int = 2048,
) -> dict[str, Any]:
    prompt = build_prompt(record_type, count, brief)
    schema = RECORD_TYPES[record_type].model_json_schema()
    sample = generate_records.generate(record_type, count, backend="synthetic", seed=seed, model_name=model)
    parsed = parse_records_payload(record_type, {"records": sample})
    return {
        "schema": "local_llm_backend_dryrun.v1",
        "record_type": record_type,
        "count": count,
        "model": model,
        "device": "cpu",
        "model_loaded": False,
        "prompt": prompt,
        "json_schema_keys": sorted(schema.get("properties", {}).keys()),
        "vllm_request_preview": build_vllm_request(
            record_type,
            count,
            seed=seed,
            model=model,
            brief=brief,
            guided_backend=guided_backend,
            max_tokens=max_tokens,
        ),
        "parser_ok": len(parsed) == count,
        "sample_records": parsed,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"vLLM request failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"vLLM request failed: {exc}") from exc


def run_vllm(
    record_type: str,
    count: int,
    *,
    seed: int,
    model: str,
    brief: str | None,
    server: str,
    guided_backend: str,
    max_tokens: int,
    timeout_s: float,
) -> list[dict[str, Any]]:
    base = server.rstrip("/")
    payload = build_vllm_request(
        record_type,
        count,
        seed=seed,
        model=model,
        brief=brief,
        guided_backend=guided_backend,
        max_tokens=max_tokens,
    )
    result = _post_json(f"{base}/chat/completions", payload, timeout_s)
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"unexpected vLLM response shape: {result!r}") from exc
    return parse_records_payload(record_type, content)


def run_outlines_cuda(record_type: str, count: int, *, seed: int, model: str, brief: str | None) -> list[dict[str, Any]]:
    """Load outlines + transformers only in the explicit CUDA path."""
    import outlines

    prompt = build_prompt(record_type, count, brief)
    cls = RECORD_TYPES[record_type]
    llm = outlines.models.transformers(model, device="cuda")
    generator = outlines.generate.json(llm, cls)
    records = []
    for i in range(count):
        result = generator(prompt + f"\nRecord index: {i}. Seed hint: {seed + i}.", max_tokens=1024)
        if hasattr(result, "model_dump"):
            records.append(result.model_dump())
        else:
            records.append(cls.model_validate(result).model_dump())
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("record_type", choices=sorted(RECORD_TYPES))
    ap.add_argument("--max-records", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ")
    ap.add_argument("--backend", choices=("vllm", "outlines"), default="vllm")
    ap.add_argument("--server", default="http://127.0.0.1:8000/v1",
                    help="OpenAI-compatible vLLM base URL.")
    ap.add_argument("--guided-backend", default="xgrammar",
                    choices=("xgrammar", "outlines", "lm-format-enforcer"))
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--timeout-s", type=float, default=120.0)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true",
                    help="Actually load the local model. Requires --device cuda.")
    ap.add_argument("--brief", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.device != "cuda" or not args.run_model:
        report = dry_run(
            args.record_type,
            args.max_records,
            seed=args.seed,
            model=args.model,
            brief=args.brief,
            guided_backend=args.guided_backend,
            max_tokens=args.max_tokens,
        )
        out = args.out or (REPORTS / f"local_llm_backend_dryrun_{args.record_type}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[local_llm_backend] dry-run prompt/parser ok={report['parser_ok']} -> {out}")
        print("[local_llm_backend] no model import/load performed")
        return 0 if report["parser_ok"] else 1

    if args.device == "cuda" and not args.run_model:
        print("[local_llm_backend] --device cuda needs --run-model to load a model", file=sys.stderr)
        return 2

    try:
        if args.backend == "vllm":
            records = run_vllm(
                args.record_type,
                args.max_records,
                seed=args.seed,
                model=args.model,
                brief=args.brief,
                server=args.server,
                guided_backend=args.guided_backend,
                max_tokens=args.max_tokens,
                timeout_s=args.timeout_s,
            )
        else:
            records = run_outlines_cuda(
                args.record_type,
                args.max_records,
                seed=args.seed,
                model=args.model,
                brief=args.brief,
            )
    except RuntimeError as exc:
        print(f"[local_llm_backend] FAILED: {exc}", file=sys.stderr)
        return 1
    out = args.out or (GENERATED / f"{plural(args.record_type)}.local_llm.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[local_llm_backend] wrote {len(records)} {args.record_type} record(s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
