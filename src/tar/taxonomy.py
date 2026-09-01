"""Data-driven capability taxonomy. New ids do not change the wire protocol."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent / "data" / "taxonomy.json"

LEVELS = ("beginner", "intermediate", "advanced", "expert")


def _load_file() -> dict[str, Any]:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _categories_map(raw: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    data = raw if raw is not None else _load_file()
    out: dict[str, dict[str, Any]] = {}
    for cat in data["categories"]:
        out[cat["id"]] = cat
    return out


TAXONOMY: dict[str, dict[str, Any]] = _categories_map()


def reload_taxonomy() -> None:
    """Reload from disk after a safe add or an operator edit."""
    global TAXONOMY, CAPABILITY_INDEX
    TAXONOMY = _categories_map()
    CAPABILITY_INDEX = _index()


def _index() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cat in TAXONOMY.values():
        for cap in cat["capabilities"]:
            item = dict(cap)
            item["category"] = cat["id"]
            item["category_name"] = cat["name"]
            if cat.get("disclaimer"):
                item["disclaimer"] = cat["disclaimer"]
            out[cap["id"]] = item
    return out


CAPABILITY_INDEX = _index()


def all_categories() -> list[dict[str, Any]]:
    return [deepcopy(c) for c in TAXONOMY.values()]


def get_category(category_id: str) -> dict[str, Any] | None:
    cat = TAXONOMY.get(category_id)
    return deepcopy(cat) if cat else None


def get_capability(capability_id: str) -> dict[str, Any] | None:
    item = CAPABILITY_INDEX.get(capability_id)
    return deepcopy(item) if item else None


def list_capabilities(category: str | None = None) -> list[dict[str, Any]]:
    if category:
        cat = TAXONOMY.get(category)
        if not cat:
            return []
        return [get_capability(c["id"]) for c in cat["capabilities"]]  # type: ignore[misc]
    return [deepcopy(v) for v in CAPABILITY_INDEX.values()]


def known_capability_ids() -> set[str]:
    return set(CAPABILITY_INDEX)


def known_category_ids() -> set[str]:
    return set(TAXONOMY)


def add_capability(
    category_id: str,
    cap: dict[str, Any],
    *,
    persist: bool = False,
) -> dict[str, Any]:
    """Register a new capability id without a protocol bump. Idempotent.

    Safe add: unknown category is rejected; duplicate ids in another category
    are rejected; the same id in the same category is a no-op.
    """
    global CAPABILITY_INDEX
    if category_id not in TAXONOMY:
        raise ValueError(f"unknown category: {category_id}")
    cid = cap.get("id")
    if not cid or not isinstance(cid, str):
        raise ValueError("capability id is required")
    existing = CAPABILITY_INDEX.get(cid)
    if existing and existing["category"] != category_id:
        raise ValueError(f"capability {cid} already belongs to {existing['category']}")
    if existing and existing["category"] == category_id:
        return deepcopy(existing)
    record = {
        "id": cid,
        "name": cap.get("name") or cid,
        "description": cap.get("description") or "",
    }
    TAXONOMY[category_id]["capabilities"].append(record)
    if persist:
        raw = _load_file()
        for cat in raw["categories"]:
            if cat["id"] == category_id:
                if not any(c["id"] == cid for c in cat["capabilities"]):
                    cat["capabilities"].append(record)
                break
        _DATA_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        reload_taxonomy()
    else:
        CAPABILITY_INDEX = _index()
    item = get_capability(cid)
    assert item is not None
    return item
