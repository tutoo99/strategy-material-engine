#!/opt/miniconda3/bin/python3

import argparse
import json
from pathlib import Path

from _dedupe_lib import normalize_content, sha256_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chunk_id")
    parser.add_argument("--root", default=".")
    parser.add_argument("--index", default="index/sources/source_chunks_meta.jsonl")
    parser.add_argument("--type", default="story")
    parser.add_argument("--output")
    args = parser.parse_args()

    index_path = Path(args.root).resolve() / args.index
    items = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [item for item in items if item.get("id") == args.chunk_id]
    if not matches:
        raise SystemExit(f"Chunk not found: {args.chunk_id}")

    chunk = matches[0]
    body = chunk.get('chunk_text', '').strip()
    ammo_default = {
        "story": "hook",
        "insight": "dual",
        "method": "substance",
        "data": "substance",
        "quote": "hook",
        "association": "hook",
        "playbook": "substance",
    }.get(args.type, "dual")

    draft = f"""---
type: {args.type}
primary_claim: 待补充
claims:
  - 待补充
tags: [{', '.join(chunk.get('tags', []))}]
ammo_type: {ammo_default}
role: argument
strength: observation
channel_fit: [general]
source: {chunk.get('title', '')}
source_refs:
  - {chunk.get('path', '')}
derived_from_case:
source_uid: {chunk.get('source_uid', '')}
content_sha256: {sha256_text(normalize_content(body))}
date: {chunk.get('date', '')}
quality_score: 3.0
use_count: 0
last_used_at:
used_in_articles: []
impact_log: []
source_reliability: 3.0
review_status: draft
---

{body}
"""
    if args.output:
        output_path = Path(args.root).resolve() / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(draft, encoding="utf-8")
        print(f"Wrote draft material: {output_path}")
        return
    print(draft)


if __name__ == "__main__":
    main()
