#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

STATE_DIR = Path("index/_state")
DIRTY_STATE_PATH = STATE_DIR / "dirty.json"
KNOWN_BUCKETS = ("sources", "materials", "cases", "entities", "unified")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def state_dir(root: Path) -> Path:
    return root / STATE_DIR


def dirty_state_path(root: Path) -> Path:
    return root / DIRTY_STATE_PATH


def ensure_state_dir(root: Path) -> Path:
    target = state_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    return target


def load_dirty_state(root: Path) -> dict:
    path = dirty_state_path(root)
    if not path.exists():
        return {"version": 1, "buckets": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("version", 1)
    buckets = payload.get("buckets")
    if not isinstance(buckets, dict):
        buckets = {}
    payload["buckets"] = buckets
    return payload


def write_dirty_state(root: Path, payload: dict) -> None:
    ensure_state_dir(root)
    dirty_state_path(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def mark_dirty(root: Path, *buckets: str, reason: str = "") -> dict:
    payload = load_dirty_state(root)
    registry = payload["buckets"]
    changed_at = now_iso()
    for bucket in buckets:
        cleaned = str(bucket or "").strip()
        if not cleaned:
            continue
        entry = registry.get(cleaned)
        if not isinstance(entry, dict):
            entry = {}
        entry["dirty"] = True
        entry["updated_at"] = changed_at
        if reason:
            entry["reason"] = reason
        registry[cleaned] = entry
    write_dirty_state(root, payload)
    return payload


def clear_dirty(root: Path, *buckets: str) -> dict:
    payload = load_dirty_state(root)
    registry = payload["buckets"]
    cleared_at = now_iso()
    for bucket in buckets:
        cleaned = str(bucket or "").strip()
        if not cleaned:
            continue
        entry = registry.get(cleaned)
        if not isinstance(entry, dict):
            entry = {}
        entry["dirty"] = False
        entry["cleared_at"] = cleared_at
        registry[cleaned] = entry
    write_dirty_state(root, payload)
    return payload


def dirty_buckets(root: Path) -> list[str]:
    payload = load_dirty_state(root)
    registry = payload.get("buckets", {})
    buckets: list[str] = []
    for bucket in KNOWN_BUCKETS:
        entry = registry.get(bucket)
        if isinstance(entry, dict) and entry.get("dirty"):
            buckets.append(bucket)
    for bucket, entry in registry.items():
        if bucket in KNOWN_BUCKETS:
            continue
        if isinstance(entry, dict) and entry.get("dirty"):
            buckets.append(bucket)
    return buckets
