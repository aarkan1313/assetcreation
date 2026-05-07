"""Dump Pydantic JSON Schema files for every game-data record type."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import RECORD_TYPES  # noqa: E402

GAME_DATA = Path(r"D:\assets\game_data")
SCHEMA_OUT = GAME_DATA / "schemas"


def dump_schemas(out_dir: Path = SCHEMA_OUT) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for record_type, cls in RECORD_TYPES.items():
        path = out_dir / f"{record_type}.schema.json"
        path.write_text(json.dumps(cls.model_json_schema(), indent=2), encoding="utf-8")
        written[record_type] = path
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=SCHEMA_OUT)
    args = ap.parse_args()
    written = dump_schemas(args.out)
    for record_type, path in written.items():
        print(f"[dump_schemas] {record_type:9s} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

