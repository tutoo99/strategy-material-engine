#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from search_knowledge import DEFAULT_MODEL_NAME, canonical_source_key, search_knowledge


def load_queries(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    queries = payload.get("queries", [])
    if not isinstance(queries, list):
        raise SystemExit("`queries` must be a list")
    return queries


def hit_at_k(results: list[dict[str, Any]], known_good: set[str], k: int) -> int:
    return sum(1 for item in results[:k] if str(item.get("path", "")) in known_good)


def diversity_bucket_key(item: dict[str, Any]) -> str:
    source_key = canonical_source_key(item)
    if source_key:
        return source_key
    path = str(item.get("path", "")).strip()
    asset_type = str(item.get("asset_type", "")).strip()
    return f"{asset_type}:{path}" if path else asset_type or "unknown"


def unique_source_count_at_k(results: list[dict[str, Any]], k: int) -> int:
    keys = {diversity_bucket_key(item) for item in results[:k] if diversity_bucket_key(item)}
    return len(keys)


def max_source_repeat_at_k(results: list[dict[str, Any]], k: int) -> int:
    counts: dict[str, int] = {}
    for item in results[:k]:
        key = diversity_bucket_key(item)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return max(counts.values(), default=0)


def render_report(report: dict[str, Any]) -> str:
    lines = ["# Knowledge Search Evaluation Report", ""]
    lines.append(f"- Query file: `{report['query_file']}`")
    lines.append(f"- Total queries: `{report['total_queries']}`")
    lines.append("")
    lines.append("| Query ID | Mode | Hit@1 | Hit@3 | Hit@5 | Unique@5 | MaxRepeat@5 | Top1 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for row in report.get("results", []):
        top1 = row.get("top_results", [{}])[0].get("path", "") if row.get("top_results") else ""
        lines.append(
            f"| {row.get('id')} | {row.get('mode')} | {row['metrics']['1']} | {row['metrics']['3']} | {row['metrics']['5']} | {row['diversity']['unique_5']} | {row['diversity']['max_repeat_5']} | `{top1}` |"
        )
    lines.append("")
    for row in report.get("results", []):
        lines.append(f"## {row.get('id')}")
        lines.append("")
        lines.append(f"- Query: {row.get('query')}")
        lines.append(f"- Mode: `{row.get('mode')}`")
        lines.append(f"- Notes: {row.get('notes', '')}")
        lines.append(
            f"- Metrics: `hit@1={row['metrics']['1']}` `hit@3={row['metrics']['3']}` `hit@5={row['metrics']['5']}` "
            f"`unique_source@3={row['diversity']['unique_3']}` `unique_source@5={row['diversity']['unique_5']}` "
            f"`max_source_repeat@5={row['diversity']['max_repeat_5']}`"
        )
        lines.append("- Top results:")
        for idx, item in enumerate(row.get("top_results", []), start=1):
            lines.append(
                f"  - {idx}. `{item.get('path')}` | asset={item.get('asset_type')} | source_key={item.get('source_key')} | score={item.get('score')} | why={item.get('why_matched')}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="评估统一知识搜索的 query family 命中情况")
    parser.add_argument("--root", default=".")
    parser.add_argument("--queries", default="evals/knowledge_eval_queries.yaml")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--reranker", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    query_file = root / args.queries
    queries = load_queries(query_file)

    report: dict[str, Any] = {
        "query_file": str(query_file),
        "total_queries": len(queries),
        "results": [],
    }

    reranker_name = None if str(args.reranker).lower() in {"none", "false", "0"} else args.reranker

    for entry in queries:
        query = str(entry.get("query", "")).strip()
        if not query:
            continue
        mode = str(entry.get("mode", "hybrid")).strip() or "hybrid"
        known_good = {str(item).strip() for item in entry.get("known_good_paths", []) if str(item).strip()}
        results = search_knowledge(
            root=root,
            query=query,
            mode=mode,
            limit=5,
            model=args.model,
            reranker_name=reranker_name,
            device=args.device,
            batch_size=args.batch_size,
            planner_provider="rule",
        )
        report["results"].append(
            {
                "id": str(entry.get("id", query)),
                "query": query,
                "mode": mode,
                "notes": str(entry.get("notes", "")),
                "metrics": {
                    "1": hit_at_k(results, known_good, 1),
                    "3": hit_at_k(results, known_good, 3),
                    "5": hit_at_k(results, known_good, 5),
                },
                "diversity": {
                    "unique_3": unique_source_count_at_k(results, 3),
                    "unique_5": unique_source_count_at_k(results, 5),
                    "max_repeat_5": max_source_repeat_at_k(results, 5),
                },
                "top_results": [
                    {
                        "path": item.get("path", ""),
                        "asset_type": item.get("asset_type", ""),
                        "source_key": diversity_bucket_key(item),
                        "score": round(float(item.get("_score", 0.0) or 0.0), 6),
                        "why_matched": item.get("why_matched", ""),
                    }
                    for item in results[:5]
                ],
            }
        )

    output_json = Path(args.output_json).resolve() if args.output_json else root / "evals" / "reports" / "knowledge_search_report.json"
    output_md = Path(args.output_md).resolve() if args.output_md else root / "evals" / "reports" / "knowledge_search_report.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_report(report), encoding="utf-8")
    print(f"Wrote knowledge search report: {output_md}")


if __name__ == "__main__":
    main()
