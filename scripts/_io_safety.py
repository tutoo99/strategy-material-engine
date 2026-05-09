#!/usr/bin/env python3

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def runtime_dir(root: Path) -> Path:
    target = root / ".runtime"
    target.mkdir(parents=True, exist_ok=True)
    return target


@contextmanager
def file_lock(root: Path, name: str) -> Iterator[None]:
    """Process-wide advisory lock for shared repository state."""
    lock_path = runtime_dir(root) / f"{name}.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding=encoding,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def atomic_write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows)
    atomic_write_text(path, lines, encoding="utf-8")
