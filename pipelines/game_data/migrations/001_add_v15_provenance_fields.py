"""Ensure v1.5 provenance audit fields exist on older records."""
from __future__ import annotations

from typing import Any

MIGRATION_ID = "001_add_v15_provenance_fields"

FIELDS = (
    "target_file_sha256",
    "constraint_technique",
    "constraint_pass",
    "sim_digest",
    "parent_id",
)


def migrate(record: dict[str, Any], record_type: str) -> dict[str, Any]:
    out = dict(record)
    provenance = dict(out.get("provenance") or {})
    for field in FIELDS:
        provenance.setdefault(field, None)
    out["provenance"] = provenance
    return out

