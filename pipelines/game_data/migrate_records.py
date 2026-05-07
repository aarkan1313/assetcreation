"""Apply sequential JSONL migrations to generated or validated records."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import RECORD_TYPES, plural  # noqa: E402

GAME_DATA = Path(r"D:\assets\game_data")
MIGRATIONS_DIR = ROOT / "migrations"


def _migration_modules() -> list[Any]:
    modules = []
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.py")):
        modules.append(importlib.import_module(f"migrations.{path.stem}"))
    return modules


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def migrate_records(records: list[dict[str, Any]], record_type: str) -> list[dict[str, Any]]:
    out = records
    for module in _migration_modules():
        migrate: Callable[[dict[str, Any], str], dict[str, Any]] = module.migrate
        out = [migrate(rec, record_type) for rec in out]
    cls = RECORD_TYPES[record_type]
    return [cls.model_validate(rec).model_dump() for rec in out]


def migrate_dir(base_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record_type in RECORD_TYPES:
        path = base_dir / f"{plural(record_type)}.jsonl"
        records = _read_jsonl(path)
        if not records:
            counts[record_type] = 0
            continue
        migrated = migrate_records(records, record_type)
        _write_jsonl(path, migrated)
        counts[record_type] = len(migrated)
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=GAME_DATA / "validated",
                    help="Directory containing <type>s.jsonl files")
    args = ap.parse_args()
    counts = migrate_dir(args.dir)
    print(f"[migrate_records] applied {len(_migration_modules())} migration(s) in {args.dir}")
    for record_type, count in counts.items():
        if count:
            print(f"  {record_type:11s}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

