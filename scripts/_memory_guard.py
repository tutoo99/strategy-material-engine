#!/opt/miniconda3/bin/python3

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class MemorySnapshot:
    page_size: int
    free_mb: float
    speculative_mb: float
    inactive_mb: float
    compressed_mb: float
    swapouts: int

    @property
    def readily_available_mb(self) -> float:
        return self.free_mb + self.speculative_mb + self.inactive_mb


_PAGE_SIZE_RE = re.compile(r"page size of (\d+) bytes")
_VALUE_RE = re.compile(r"^([^:]+):\s+(\d+)\.")


def read_memory_snapshot() -> MemorySnapshot | None:
    try:
        output = subprocess.check_output(["vm_stat"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return None

    page_size = 16384
    page_match = _PAGE_SIZE_RE.search(output)
    if page_match:
        page_size = int(page_match.group(1))

    values: dict[str, int] = {}
    for line in output.splitlines():
        match = _VALUE_RE.match(line.strip())
        if match:
            values[match.group(1)] = int(match.group(2))

    def pages_to_mb(key: str) -> float:
        return values.get(key, 0) * page_size / 1024 / 1024

    return MemorySnapshot(
        page_size=page_size,
        free_mb=pages_to_mb("Pages free"),
        speculative_mb=pages_to_mb("Pages speculative"),
        inactive_mb=pages_to_mb("Pages inactive"),
        compressed_mb=pages_to_mb("Pages occupied by compressor"),
        swapouts=values.get("Swapouts", 0),
    )


def memory_pressure_reason(
    *,
    min_readily_available_mb: float = 2048.0,
    max_compressed_mb: float = 2048.0,
) -> str:
    snapshot = read_memory_snapshot()
    if snapshot is None:
        return ""
    if snapshot.swapouts > 0 and snapshot.readily_available_mb < min_readily_available_mb * 1.5:
        return f"swapouts={snapshot.swapouts}"
    if snapshot.readily_available_mb < min_readily_available_mb:
        return f"readily_available_mb={snapshot.readily_available_mb:.0f}"
    if snapshot.compressed_mb > max_compressed_mb and snapshot.free_mb < min_readily_available_mb:
        return f"compressed_mb={snapshot.compressed_mb:.0f}"
    return ""


def wait_for_memory_budget(
    *,
    timeout_seconds: float = 20.0,
    poll_seconds: float = 2.0,
    min_readily_available_mb: float = 2048.0,
    max_compressed_mb: float = 2048.0,
) -> tuple[bool, str, float]:
    started = time.time()
    reason = memory_pressure_reason(
        min_readily_available_mb=min_readily_available_mb,
        max_compressed_mb=max_compressed_mb,
    )
    while reason and time.time() - started < timeout_seconds:
        time.sleep(poll_seconds)
        reason = memory_pressure_reason(
            min_readily_available_mb=min_readily_available_mb,
            max_compressed_mb=max_compressed_mb,
        )
    elapsed = time.time() - started
    return (not reason, reason, elapsed)
