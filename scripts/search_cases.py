#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _buildmate_lib import lexical_score, read_jsonl


def matches_filter(item: dict, args: argparse.Namespace) -> bool:
    if args.platform and item.get("platform") != args.platform:
        return False
    if args.domain and item.get("domain") != args.domain:
        return False
    if args.status and item.get("status") != args.status:
        return False
    if args.tool and args.tool not in item.get("tools", []):
        return False
    if args.result_tag and args.result_tag not in item.get("result_tags", []):
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Buildmate cases with lexical scoring.")
    parser.add_argument("query")
    parser.add_argument("--root", default=".")
    parser.add_argument("--meta", default="index/cases/cases_meta.jsonl")
    parser.add_argument("--platform")
    parser.add_argument("--domain")
    parser.add_argument("--status")
    parser.add_argument("--tool")
    parser.add_argument("--result-tag")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    items = read_jsonl(root / args.meta)
    scored: list[dict] = []
    for item in items:
        if not matches_filter(item, args):
            continue
        texts = [
            item.get("title", ""),
            item.get("platform", ""),
            item.get("domain", ""),
            item.get("result_summary", ""),
            item.get("search_text", ""),
            " ".join(item.get("result_tags", [])),
            " ".join(item.get("tools", [])),
        ]
        score = lexical_score(args.query, texts)
        if score <= 0:
            continue
        scored.append(
            {
                "case_id": item.get("case_id"),
                "title": item.get("title"),
                "path": item.get("path"),
                "platform": item.get("platform"),
                "domain": item.get("domain"),
                "status": item.get("status"),
                "content_source": item.get("content_source"),
                "body_lock": item.get("body_lock"),
                "quality_score": item.get("quality_score"),
                "result_summary": item.get("result_summary"),
                "tools": item.get("tools", []),
                "resource_refs": item.get("resource_refs", []),
                "score": round(score, 4),
            }
        )

    scored.sort(key=lambda item: (item["score"], item.get("quality_score", 0)), reverse=True)
    for item in scored[: args.limit]:
        print(json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
