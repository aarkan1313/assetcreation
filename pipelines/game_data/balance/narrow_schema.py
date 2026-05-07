"""Derive per-slot JSON Schemas from Pydantic schemas and balance targets."""
from __future__ import annotations

import copy
from typing import Any

from balance.schema import BalanceTargets, Bounds


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with local `$ref` entries expanded.

    Provider strict modes are easiest to satisfy when the payload schema is a
    single object tree. Pydantic emits `$defs`; this resolves only local refs.
    """
    root = copy.deepcopy(schema)
    defs = root.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"].split("/")[-1]
                if ref in defs:
                    merged = copy.deepcopy(defs[ref])
                    for k, v in node.items():
                        if k != "$ref":
                            merged[k] = v
                    return resolve(merged)
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    resolved = resolve(root)
    resolved.pop("$defs", None)
    return resolved


def forbid_extra_properties(schema: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                node.setdefault("additionalProperties", False)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(out)
    return out


def set_const(schema: dict[str, Any], path: str, value: object) -> None:
    prop = _property_at(schema, path)
    prop["const"] = value
    if isinstance(value, str):
        prop.setdefault("type", "string")
    elif isinstance(value, int):
        prop.setdefault("type", "integer")
    elif isinstance(value, float):
        prop.setdefault("type", "number")


def set_bounds(schema: dict[str, Any], path: str, bounds: Bounds) -> None:
    prop = _property_at(schema, path)
    prop["minimum"] = bounds.min
    prop["maximum"] = bounds.max


def _property_at(schema: dict[str, Any], path: str) -> dict[str, Any]:
    node = schema
    for part in path.split("."):
        props = node.setdefault("properties", {})
        if part not in props:
            props[part] = {}
        node = props[part]
    return node


def slot_consts(record_type: str, slot: dict[str, object]) -> dict[str, object]:
    if record_type == "item":
        return {
            "category": "weapon",
            "rarity": slot.get("rarity", "common"),
            "stack_max": 1,
        }
    if record_type == "ability":
        out: dict[str, object] = {
            "kind": "active",
            "tier": int(slot.get("tier", 1)),
        }
        if slot.get("school"):
            out["school"] = slot["school"]
        return out
    return {}


def narrow_schema(
    base_schema: dict[str, Any],
    targets: BalanceTargets,
    record_type: str,
    slot: dict[str, object],
    *,
    strict: bool = True,
) -> dict[str, Any]:
    schema = inline_refs(base_schema)
    for path, value in slot_consts(record_type, slot).items():
        set_const(schema, path, value)
    for path, bounds in targets.bounds_for_slot(record_type, slot).items():
        set_bounds(schema, path, bounds)
    if strict:
        schema = forbid_extra_properties(schema)
    return schema

