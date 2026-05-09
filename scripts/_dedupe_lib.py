#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from _io_safety import atomic_write_json, file_lock


REGISTRY_PATH = Path("index/_state/source_registry.json")
NOISE_QUERY_PREFIXES = ("utm_",)
NOISE_QUERY_KEYS = {
    "spm",
    "from",
    "from_source",
    "share_from",
    "share_source",
    "share_token",
    "timestamp",
    "ts",
}


@dataclass
class SourceFingerprint:
    source_uid: str
    canonical_url: str
    content_sha256: str
    simhash64: str
    metadata_key: str
    metadata_hash: str
    content_length: int


@dataclass
class DuplicateMatch:
    match_type: str
    path: str
    title: str
    reason: str
    distance: int | None = None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text.strip()
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text.strip()
    meta = yaml.safe_load(parts[0][4:]) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, parts[1].strip()


def normalize_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    split = urlsplit(text)
    scheme = (split.scheme or "https").lower()
    netloc = split.netloc.lower()
    if scheme == "http":
        scheme = "https"
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query_items = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in NOISE_QUERY_KEYS or any(lowered.startswith(prefix) for prefix in NOISE_QUERY_PREFIXES):
            continue
        query_items.append((key, value))
    query = urlencode(sorted(query_items), doseq=True)
    path = re.sub(r"/+$", "", split.path or "/")
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_title(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = re.sub(r"[\s　]+", "", normalized)
    normalized = re.sub(r"[《》「」『』【】\[\]（）()<>\"'“”‘’:_\-—|/\\.,，。!！?？·•]+", "", normalized)
    return normalized


def normalize_content(text: str) -> str:
    _meta, body = parse_frontmatter(str(text or ""))
    normalized = body
    normalized = normalized.replace("\ufeff", "")
    normalized = re.sub(r"```.*?```", "", normalized, flags=re.S)
    normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", normalized)
    normalized = re.sub(r"\[[^\]]+\]\(([^)]+)\)", r"\1", normalized)
    normalized = re.sub(r"https?://\S+", "", normalized)
    normalized = normalized.lower()
    normalized = normalized.translate(
        str.maketrans(
            {
                "，": ",",
                "。": ".",
                "！": "!",
                "？": "?",
                "：": ":",
                "；": ";",
                "（": "(",
                "）": ")",
                "【": "[",
                "】": "]",
                "“": '"',
                "”": '"',
                "‘": "'",
                "’": "'",
            }
        )
    )
    normalized = re.sub(r"[ \t\r\n　]+", "", normalized)
    normalized = re.sub(r"[#>*_`~\-—=]+", "", normalized)
    return normalized.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _simhash_features(text: str) -> list[str]:
    normalized = normalize_content(text)
    if not normalized:
        return []
    features: list[str] = []
    for size in (3, 4, 5):
        if len(normalized) < size:
            continue
        features.extend(normalized[index : index + size] for index in range(0, len(normalized) - size + 1))
    return features


def simhash64(text: str) -> str:
    features = _simhash_features(text)
    if not features:
        return "0" * 16
    vector = [0] * 64
    for feature in features:
        digest = int(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).hexdigest(), 16)
        for bit in range(64):
            vector[bit] += 1 if digest & (1 << bit) else -1
    value = 0
    for bit, weight in enumerate(vector):
        if weight >= 0:
            value |= 1 << bit
    return f"{value:016x}"


def hamming_distance_hex(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 64


def build_metadata_key(meta: dict[str, Any], title: str = "") -> str:
    parts = [
        str(meta.get("origin", "") or "").strip().lower(),
        str(meta.get("author", "") or "").strip().lower(),
        normalize_title(str(meta.get("title", "") or title)),
        str(meta.get("date", "") or "").strip()[:10],
        str(meta.get("source_id", "") or "").strip(),
    ]
    return "|".join(parts)


def fingerprint_source(meta: dict[str, Any], body: str, *, title: str = "") -> SourceFingerprint:
    link = str(meta.get("canonical_url") or meta.get("link") or meta.get("source_url") or "").strip()
    canonical_url = normalize_url(link)
    normalized_content = normalize_content(body)
    content_sha = sha256_text(normalized_content)
    metadata_key = build_metadata_key(meta, title=title)
    metadata_hash = sha256_text(metadata_key)
    if canonical_url:
        source_uid = f"url:{sha256_text(canonical_url)[:24]}"
    elif normalized_content:
        source_uid = f"content:{content_sha[:24]}"
    else:
        source_uid = f"meta:{metadata_hash[:24]}"
    return SourceFingerprint(
        source_uid=source_uid,
        canonical_url=canonical_url,
        content_sha256=content_sha,
        simhash64=simhash64(body),
        metadata_key=metadata_key,
        metadata_hash=metadata_hash,
        content_length=len(normalized_content),
    )


def registry_file(root: Path) -> Path:
    return root / REGISTRY_PATH


def load_registry(root: Path) -> dict[str, Any]:
    path = registry_file(root)
    if not path.exists():
        return {"version": 1, "sources": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("version", 1)
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []
    payload["sources"] = [item for item in sources if isinstance(item, dict)]
    return payload


def write_registry(root: Path, payload: dict[str, Any]) -> None:
    path = registry_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = now_iso()
    atomic_write_json(path, payload)


def make_registry_record(
    *,
    path: str,
    title: str,
    author: str,
    origin: str,
    fingerprint: SourceFingerprint,
    status: str = "active",
    imported_at: str | None = None,
) -> dict[str, Any]:
    timestamp = imported_at or now_iso()
    return {
        "source_uid": fingerprint.source_uid,
        "path": path,
        "title": title,
        "author": author,
        "origin": origin,
        "canonical_url": fingerprint.canonical_url,
        "content_sha256": fingerprint.content_sha256,
        "simhash64": fingerprint.simhash64,
        "metadata_hash": fingerprint.metadata_hash,
        "metadata_key": fingerprint.metadata_key,
        "content_length": fingerprint.content_length,
        "imported_at": timestamp,
        "last_seen_at": timestamp,
        "status": status,
    }


def upsert_registry_record(root: Path, record: dict[str, Any]) -> None:
    with file_lock(root, "source_registry"):
        payload = load_registry(root)
        sources = payload["sources"]
        now = now_iso()
        for existing in sources:
            if existing.get("path") == record.get("path"):
                existing.update(record)
                existing.setdefault("imported_at", record.get("imported_at") or now)
                existing["last_seen_at"] = record.get("last_seen_at") or now
                write_registry(root, payload)
                return
        sources.append(record)
        write_registry(root, payload)


def refresh_registry_match(root: Path, match_path: str) -> None:
    with file_lock(root, "source_registry"):
        payload = load_registry(root)
        for existing in payload["sources"]:
            if existing.get("path") == match_path:
                existing["last_seen_at"] = now_iso()
                write_registry(root, payload)
                return


def find_duplicate_matches(
    registry: dict[str, Any],
    fingerprint: SourceFingerprint,
    *,
    exclude_path: str = "",
    near_distance: int = 3,
    loose_near_distance: int = 6,
    length_ratio_floor: float = 0.85,
    length_ratio_ceiling: float = 1.15,
) -> list[DuplicateMatch]:
    matches: list[DuplicateMatch] = []
    for item in registry.get("sources", []):
        path = str(item.get("path", "") or "")
        if exclude_path and path == exclude_path:
            continue
        title = str(item.get("title", "") or "")
        if fingerprint.canonical_url and fingerprint.canonical_url == str(item.get("canonical_url", "") or ""):
            matches.append(DuplicateMatch("exact_url", path, title, "canonical_url matched"))
            continue
        if fingerprint.content_sha256 and fingerprint.content_sha256 == str(item.get("content_sha256", "") or ""):
            matches.append(DuplicateMatch("exact_content", path, title, "content_sha256 matched"))
            continue
        item_length = int(item.get("content_length", 0) or 0)
        if fingerprint.content_length and item_length:
            ratio = fingerprint.content_length / item_length
        else:
            ratio = 0.0
        distance = hamming_distance_hex(fingerprint.simhash64, str(item.get("simhash64", "") or ""))
        if distance <= near_distance and length_ratio_floor <= ratio <= length_ratio_ceiling:
            matches.append(DuplicateMatch("near_content", path, title, "simhash and length matched", distance))
            continue
        if distance <= loose_near_distance and fingerprint.metadata_hash == str(item.get("metadata_hash", "") or ""):
            matches.append(DuplicateMatch("near_metadata", path, title, "simhash and metadata matched", distance))
    return matches


def strongest_match(matches: list[DuplicateMatch]) -> DuplicateMatch | None:
    priority = {"exact_url": 0, "exact_content": 1, "near_content": 2, "near_metadata": 3}
    if not matches:
        return None
    return sorted(matches, key=lambda item: (priority.get(item.match_type, 99), item.distance or 0))[0]


def registry_from_sources(root: Path, sources_dir: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for path in sorted(sources_dir.rglob("*.md")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        title = str(meta.get("title") or path.stem)
        fingerprint = fingerprint_source(meta, body, title=title)
        relative_path = str(path.relative_to(root))
        seen_paths.add(relative_path)
        records.append(
            make_registry_record(
                path=relative_path,
                title=title,
                author=str(meta.get("author", "") or ""),
                origin=str(meta.get("origin", "") or ""),
                fingerprint=fingerprint,
                imported_at=str(meta.get("imported_at") or ""),
            )
        )
    return {"version": 1, "sources": records, "rebuilt_at": now_iso(), "source_count": len(seen_paths)}
