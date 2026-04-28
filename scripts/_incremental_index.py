#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from _material_lib import encode_texts, write_jsonl

EMBED_DIMENSION = 1024
# Current assembly path still materializes all vectors in-memory before handing off
# to the FAISS writer subprocess. This is intentional for simplicity, but once a
# single bucket routinely exceeds roughly 50k vectors we should switch to shard-
# level assembly or streamed merge to avoid large vstack memory spikes.
VSTACK_REVIEW_THRESHOLD = 50_000


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_text(text: str) -> str:
    return hashlib.sha1(str(text).encode("utf-8")).hexdigest()


def cache_key_for_relpath(relative_path: str) -> str:
    return hashlib.sha1(str(relative_path).encode("utf-8")).hexdigest()


def manifest_path(root: Path, bucket: str) -> Path:
    return root / "index" / "_state" / f"{bucket}_manifest.json"


def cache_dir(root: Path, bucket: str) -> Path:
    return root / "index" / "_state" / "cache" / bucket


def load_manifest(root: Path, bucket: str) -> dict:
    path = manifest_path(root, bucket)
    if not path.exists():
        return {"version": 1, "bucket": bucket, "documents": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("version", 1)
    payload.setdefault("bucket", bucket)
    documents = payload.get("documents")
    if not isinstance(documents, dict):
        documents = {}
    payload["documents"] = documents
    return payload


def write_manifest(root: Path, bucket: str, payload: dict) -> None:
    path = manifest_path(root, bucket)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def rows_cache_path(root: Path, bucket: str, cache_key: str) -> Path:
    return cache_dir(root, bucket) / f"{cache_key}.rows.json"


def vectors_cache_path(root: Path, bucket: str, cache_key: str) -> Path:
    return cache_dir(root, bucket) / f"{cache_key}.vectors.npy"


def has_cache(root: Path, bucket: str, cache_key: str) -> bool:
    return rows_cache_path(root, bucket, cache_key).exists() and vectors_cache_path(root, bucket, cache_key).exists()


def remove_cache(root: Path, bucket: str, cache_key: str) -> None:
    rows_path = rows_cache_path(root, bucket, cache_key)
    vectors_path = vectors_cache_path(root, bucket, cache_key)
    if rows_path.exists():
        rows_path.unlink()
    if vectors_path.exists():
        vectors_path.unlink()


def load_cached_doc(root: Path, bucket: str, cache_key: str) -> tuple[list[dict], np.ndarray]:
    rows = json.loads(rows_cache_path(root, bucket, cache_key).read_text(encoding="utf-8"))
    vectors = np.load(vectors_cache_path(root, bucket, cache_key), allow_pickle=False)
    return rows, np.asarray(vectors, dtype="float32")


def save_cached_doc(root: Path, bucket: str, cache_key: str, rows: list[dict], vectors: np.ndarray) -> None:
    target_dir = cache_dir(root, bucket)
    target_dir.mkdir(parents=True, exist_ok=True)
    rows_cache_path(root, bucket, cache_key).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    np.save(vectors_cache_path(root, bucket, cache_key), np.asarray(vectors, dtype="float32"), allow_pickle=False)


def empty_vectors() -> np.ndarray:
    return np.zeros((0, EMBED_DIMENSION), dtype="float32")


def write_faiss_index_via_subprocess(index_output_path: Path, vectors: np.ndarray) -> None:
    with tempfile.NamedTemporaryFile(prefix="sme_vectors_", suffix=".npy", delete=False) as handle:
        temp_vectors_path = Path(handle.name)
    try:
        np.save(temp_vectors_path, np.asarray(vectors, dtype="float32"), allow_pickle=False)
        stable_env = os.environ.copy()
        stable_env.setdefault("OMP_NUM_THREADS", "1")
        stable_env.setdefault("MKL_NUM_THREADS", "1")
        stable_env.setdefault("OPENBLAS_NUM_THREADS", "1")
        stable_env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
        writer_script = Path(__file__).resolve().parent / "_faiss_write_index.py"
        result = subprocess.run(
            [sys.executable, str(writer_script), "--vectors", str(temp_vectors_path), "--output", str(index_output_path)],
            capture_output=True,
            text=True,
            env=stable_env,
        )
        if result.returncode != 0:
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
            raise RuntimeError(f"FAISS writer failed for {index_output_path}")
    finally:
        temp_vectors_path.unlink(missing_ok=True)


def build_incremental_vector_index(
    *,
    root: Path,
    bucket: str,
    source_paths: list[Path],
    build_doc_payload: Callable[[Path, Path], tuple[list[dict], list[str]]],
    index_output_path: Path,
    meta_output_path: Path,
    model_name: str,
    device: str,
    batch_size: int,
) -> dict:
    manifest = load_manifest(root, bucket)
    previous_docs = manifest.get("documents", {})
    previous_cache_by_hash: dict[str, str] = {}
    if isinstance(previous_docs, dict):
        for previous in previous_docs.values():
            if not isinstance(previous, dict):
                continue
            previous_hash = str(previous.get("source_hash", "") or "")
            previous_cache_key = str(previous.get("cache_key", "") or "")
            if previous_hash and previous_cache_key and has_cache(root, bucket, previous_cache_key):
                previous_cache_by_hash.setdefault(previous_hash, previous_cache_key)
    current_relpaths: list[str] = []
    next_docs: dict[str, dict] = {}
    changed_docs: list[dict] = []
    pending_embed_texts: list[str] = []

    for path in sorted(source_paths):
        relative_path = str(path.relative_to(root))
        current_relpaths.append(relative_path)
        source_hash = hash_text(path.read_text(encoding="utf-8"))
        previous = previous_docs.get(relative_path, {}) if isinstance(previous_docs, dict) else {}
        cache_key = str(previous.get("cache_key") or cache_key_for_relpath(relative_path))
        unchanged = (
            str(previous.get("source_hash", "")) == source_hash
            and has_cache(root, bucket, cache_key)
        )
        if unchanged:
            next_docs[relative_path] = {
                "cache_key": cache_key,
                "source_hash": source_hash,
                "cached_at": str(previous.get("cached_at") or ""),
                "row_count": int(previous.get("row_count", 0) or 0),
                "vector_count": int(previous.get("vector_count", 0) or 0),
            }
            continue

        rows, embed_texts = build_doc_payload(path, root)
        vector_cache_key = previous_cache_by_hash.get(source_hash, "")
        if vector_cache_key:
            _cached_rows, cached_vectors = load_cached_doc(root, bucket, vector_cache_key)
            if int(cached_vectors.shape[0]) != len(embed_texts):
                vector_cache_key = ""
        changed_docs.append(
            {
                "relative_path": relative_path,
                "cache_key": cache_key,
                "source_hash": source_hash,
                "rows": rows,
                "embed_text_count": len(embed_texts),
                "vector_cache_key": vector_cache_key,
            }
        )
        if not vector_cache_key:
            pending_embed_texts.extend(embed_texts)

    if pending_embed_texts:
        encoded_vectors = encode_texts(
            pending_embed_texts,
            model_name=model_name,
            device=device,
            batch_size=batch_size,
        )
    else:
        encoded_vectors = empty_vectors()

    vector_offset = 0
    cached_at = now_iso()
    for document in changed_docs:
        text_count = int(document["embed_text_count"])
        vector_cache_key = str(document.get("vector_cache_key") or "")
        if vector_cache_key:
            _cached_rows, vectors = load_cached_doc(root, bucket, vector_cache_key)
        elif text_count > 0:
            vectors = encoded_vectors[vector_offset : vector_offset + text_count]
            vector_offset += text_count
        else:
            vectors = empty_vectors()
        save_cached_doc(root, bucket, str(document["cache_key"]), list(document["rows"]), vectors)
        next_docs[str(document["relative_path"])] = {
            "cache_key": str(document["cache_key"]),
            "source_hash": str(document["source_hash"]),
            "cached_at": cached_at,
            "row_count": len(document["rows"]),
            "vector_count": int(vectors.shape[0]),
        }

    deleted_docs = sorted(set(previous_docs.keys()) - set(current_relpaths)) if isinstance(previous_docs, dict) else []
    for relative_path in deleted_docs:
        previous = previous_docs.get(relative_path, {})
        cache_key = str(previous.get("cache_key") or cache_key_for_relpath(relative_path))
        remove_cache(root, bucket, cache_key)

    rows: list[dict] = []
    vector_groups: list[np.ndarray] = []
    for relative_path in sorted(current_relpaths):
        cache_key = str(next_docs[relative_path]["cache_key"])
        cached_rows, cached_vectors = load_cached_doc(root, bucket, cache_key)
        rows.extend(cached_rows)
        if cached_vectors.size:
            vector_groups.append(cached_vectors)
        next_docs[relative_path]["row_count"] = len(cached_rows)
        next_docs[relative_path]["vector_count"] = int(cached_vectors.shape[0])

    total_vector_count = sum(int(group.shape[0]) for group in vector_groups)
    if total_vector_count >= VSTACK_REVIEW_THRESHOLD:
        print(
            f"Warning: {bucket} assembled {total_vector_count} vectors in-memory; "
            "consider sharding or streamed merge for larger corpora."
        )
    final_vectors = np.vstack(vector_groups).astype("float32") if vector_groups else empty_vectors()
    index_output_path.parent.mkdir(parents=True, exist_ok=True)
    meta_output_path.parent.mkdir(parents=True, exist_ok=True)
    write_faiss_index_via_subprocess(index_output_path, final_vectors)
    write_jsonl(meta_output_path, rows)

    next_manifest = {
        "version": 1,
        "bucket": bucket,
        "updated_at": now_iso(),
        "documents": next_docs,
        "summary": {
            "document_count": len(current_relpaths),
            "row_count": len(rows),
            "vector_count": int(final_vectors.shape[0]),
            "changed_document_count": len(changed_docs),
            "deleted_document_count": len(deleted_docs),
            "reused_document_count": max(len(current_relpaths) - len(changed_docs), 0),
            "model_name": model_name,
            "device": device,
            "batch_size": batch_size,
        },
    }
    write_manifest(root, bucket, next_manifest)
    return next_manifest["summary"]
