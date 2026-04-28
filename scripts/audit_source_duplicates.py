#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _buildmate_lib import assert_project_root
from _dedupe_lib import (
    DuplicateMatch,
    find_duplicate_matches,
    registry_from_sources,
    write_registry,
)


def render_match(record: dict, match: DuplicateMatch) -> dict:
    return {
        "path": record.get("path", ""),
        "title": record.get("title", ""),
        "match_path": match.path,
        "match_title": match.title,
        "match_type": match.match_type,
        "reason": match.reason,
        "distance": match.distance,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_markdown_report(path: Path, rows: list[dict], source_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row.get("match_type", ""))] = counts.get(str(row.get("match_type", "")), 0) + 1
    lines = [
        "# Source Duplicate Audit",
        "",
        f"- scanned_sources: {source_count}",
        f"- duplicate_pairs: {len(rows)}",
    ]
    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]}")
    lines.append("")
    if not rows:
        lines.append("No duplicate candidates found.")
    else:
        lines.extend(["## Candidates", ""])
        for row in rows:
            distance = row.get("distance")
            distance_text = f", simhash_distance={distance}" if distance is not None else ""
            lines.extend(
                [
                    f"### {row.get('match_type')} {distance_text}",
                    "",
                    f"- keep/review: `{row.get('match_path')}`",
                    f"- candidate: `{row.get('path')}`",
                    f"- match_title: {row.get('match_title')}",
                    f"- candidate_title: {row.get('title')}",
                    f"- reason: {row.get('reason')}",
                    "",
                ]
            )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit sources for exact and near duplicate imports.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--sources-dir", default="sources")
    parser.add_argument("--jsonl-output", default="index/_state/source_duplicate_report.jsonl")
    parser.add_argument("--md-output", default="index/_state/source_duplicate_report.md")
    parser.add_argument("--update-registry", action="store_true", help="Rebuild source_registry.json from current sources.")
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    registry = registry_from_sources(root, root / args.sources_dir)
    if args.update_registry:
        write_registry(root, registry)

    rows: list[dict] = []
    records = registry.get("sources", [])
    seen_pairs: set[tuple[str, str, str]] = set()
    for record in records:
        pseudo_registry = {
            "version": 1,
            "sources": [item for item in records if item.get("path") != record.get("path")],
        }
        fingerprint = type(
            "Fingerprint",
            (),
            {
                "canonical_url": record.get("canonical_url", ""),
                "content_sha256": record.get("content_sha256", ""),
                "simhash64": record.get("simhash64", ""),
                "metadata_hash": record.get("metadata_hash", ""),
                "content_length": int(record.get("content_length", 0) or 0),
            },
        )()
        matches = find_duplicate_matches(pseudo_registry, fingerprint, exclude_path=str(record.get("path", "")))
        for match in matches:
            left = str(record.get("path", ""))
            right = match.path
            pair = tuple(sorted([left, right]) + [match.match_type])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            rows.append(render_match(record, match))

    rows.sort(key=lambda item: (str(item.get("match_type", "")), str(item.get("path", ""))))
    write_jsonl(root / args.jsonl_output, rows)
    write_markdown_report(root / args.md_output, rows, len(records))
    print(f"Scanned sources: {len(records)}")
    print(f"Duplicate candidates: {len(rows)}")
    print(f"Wrote report: {root / args.md_output}")
    print(f"Wrote jsonl: {root / args.jsonl_output}")
    if args.update_registry:
        print(f"Rebuilt registry: {root / 'index/_state/source_registry.json'}")


if __name__ == "__main__":
    main()
