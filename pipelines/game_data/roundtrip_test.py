"""End-to-end round-trip smoke test.

Pydantic record -> generate -> validate -> .tres -> parse .tres back -> Pydantic record

Confirms field values survive the trip both ways. Run after every schema change.

The .tres parser here is intentionally small and only handles the subset of
GDScript value literals we emit: strings, ints, floats, bools, null, arrays,
dictionaries. It is not a general Godot parser.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import RECORD_TYPES, plural  # noqa: E402

GAME_DATA = Path(r"D:\assets\game_data")
VALIDATED = GAME_DATA / "validated"
GODOT_RES = GAME_DATA / "godot" / "resources"


def _decode_value(text: str) -> tuple[object, str]:
    """Return (value, remaining-text) for one value at the start of `text`."""
    text = text.lstrip()
    if not text:
        return None, ""
    c = text[0]
    if c == '"':
        # find unescaped closing quote
        i = 1
        out = []
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
            elif text[i] == '"':
                return "".join(out), text[i + 1 :]
            else:
                out.append(text[i])
                i += 1
        raise ValueError("unterminated string")
    if c == "[":
        items = []
        rest = text[1:]
        while True:
            rest = rest.lstrip()
            if rest.startswith("]"):
                return items, rest[1:]
            v, rest = _decode_value(rest)
            items.append(v)
            rest = rest.lstrip()
            if rest.startswith(","):
                rest = rest[1:]
        # unreachable
    if c == "{":
        out: dict[str, object] = {}
        rest = text[1:]
        while True:
            rest = rest.lstrip()
            if rest.startswith("}"):
                return out, rest[1:]
            k, rest = _decode_value(rest)
            rest = rest.lstrip()
            if rest.startswith(":"):
                rest = rest[1:]
            v, rest = _decode_value(rest)
            out[str(k)] = v
            rest = rest.lstrip()
            if rest.startswith(","):
                rest = rest[1:]
    if text.startswith("null"):
        return None, text[4:]
    if text.startswith("true"):
        return True, text[4:]
    if text.startswith("false"):
        return False, text[5:]
    # number
    j = 0
    while j < len(text) and (text[j] in "+-0123456789.eE"):
        j += 1
    token = text[:j]
    rest = text[j:]
    try:
        if "." in token or "e" in token or "E" in token:
            return float(token), rest
        return int(token), rest
    except ValueError:
        # last resort - eat one token
        return None, rest


def parse_tres(path: Path) -> dict[str, object]:
    """Pull `key = value` pairs from the [resource] block. Skips ext_resource."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_resource = False
    out: dict[str, object] = {}
    pending = ""
    for line in lines:
        stripped = line.strip()
        if stripped == "[resource]":
            in_resource = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_resource = False
            continue
        if not in_resource:
            continue
        if not stripped:
            continue
        # We may need to support multi-line values eventually but for our
        # emitter every key=value is on one line.
        if "=" not in stripped:
            continue
        key, _, rhs = stripped.partition("=")
        key = key.strip()
        if key == "script":
            # skip ExtResource("1") line
            continue
        val, leftover = _decode_value(rhs)
        out[key] = val
    return out


def main() -> int:
    fails = 0
    total = 0
    for record_type, cls in RECORD_TYPES.items():
        jsonl_path = VALIDATED / f"{plural(record_type)}.jsonl"
        tres_dir = GODOT_RES / plural(record_type)
        if not jsonl_path.exists() or not tres_dir.exists():
            continue
        records = [
            json.loads(line)
            for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for orig in records:
            total += 1
            tres = tres_dir / f"{orig['id']}.tres"
            if not tres.exists():
                print(f"FAIL: missing tres for {record_type}/{orig['id']}")
                fails += 1
                continue
            parsed = parse_tres(tres)
            # Try to re-validate as Pydantic
            try:
                cls.model_validate(parsed)
            except Exception as e:
                print(f"FAIL: pydantic re-validate {record_type}/{orig['id']}: {e}")
                fails += 1
                continue
            # Compare key-by-key with original
            for k, v in orig.items():
                if parsed.get(k) != v:
                    print(f"DIFF: {record_type}/{orig['id']}.{k} "
                          f"original={v!r} tres={parsed.get(k)!r}")
                    fails += 1
                    break

    print(f"\n[roundtrip] {total - fails}/{total} passed")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
