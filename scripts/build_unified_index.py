#!/opt/miniconda3/bin/python3

import argparse
from pathlib import Path

from _knowledge_lib import normalize_preview, read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="构建统一检索视图")
    parser.add_argument("--root", default=".")
    parser.add_argument("--cases-meta", default="index/cases/cases_vector_meta.jsonl")
    parser.add_argument("--materials-meta", default="index/materials/materials_meta.jsonl")
    parser.add_argument("--entities-meta", default="index/entities/entities_meta.jsonl")
    parser.add_argument("--sources-meta", default="index/sources/source_chunks_meta.jsonl")
    parser.add_argument("--output", default="index/unified/unified_assets.jsonl")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows = []

    for item in read_jsonl(root / args.cases_meta):
        rows.append({
            "asset_type": "case",
            "subtype": "case",
            "path": item.get("path", ""),
            "title": item.get("title", ""),
            "preview": item.get("preview") or normalize_preview(item.get("retrieval_summary", "")),
            "source_refs": item.get("source_refs", []),
        })

    for item in read_jsonl(root / args.materials_meta):
        if str(item.get("review_status", "") or "").strip() == "rejected":
            continue
        rows.append({
            "asset_type": "material",
            "subtype": item.get("type", "material"),
            "path": item.get("path", ""),
            "title": item.get("primary_claim", ""),
            "preview": normalize_preview(item.get("body", "")),
            "source_refs": item.get("source_refs", []),
            "source_uid": item.get("source_uid", ""),
            "content_sha256": item.get("content_sha256", ""),
            "duplicate_of": item.get("duplicate_of", ""),
        })

    for item in read_jsonl(root / args.entities_meta):
        rows.append({
            "asset_type": "entity",
            "subtype": item.get("subtype", "entity_profile"),
            "path": item.get("path", ""),
            "title": item.get("title", "") or item.get("name", ""),
            "preview": normalize_preview(item.get("summary", "") or item.get("body", "")),
            "source_refs": item.get("source_refs", []),
        })

    for item in read_jsonl(root / args.sources_meta):
        rows.append({
            "asset_type": "source",
            "subtype": item.get("chunk_role", "source_chunk"),
            "path": item.get("path", ""),
            "title": item.get("title", ""),
            "preview": normalize_preview(item.get("chunk_text", "")),
            "source_refs": [item.get("path", "")],
            "source_uid": item.get("source_uid", ""),
            "content_sha256": item.get("content_sha256", ""),
            "duplicate_of": item.get("duplicate_of", ""),
        })

    write_jsonl(root / args.output, rows)
    print(f"Built unified asset view: {root / args.output} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
