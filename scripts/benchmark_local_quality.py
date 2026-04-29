#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import yaml

from _memory_guard import read_memory_snapshot
from _knowledge_lib import DEFAULT_MODEL_NAME, DEFAULT_RERANKER_NAME
from search_knowledge import search_knowledge


DEFAULT_QUERIES = [
    "账号多了以后总记不清该发哪个号，怎么拆系统更稳",
    "小红书低成本获客",
    "我想找一个适合放在前面开场的失败案例",
    "底层逻辑跨体量跨阶段通用的依据是什么",
    "介绍一下亦仁",
]


def load_queries(path: Path | None, limit: int) -> list[str]:
    if path is None or not path.exists():
        return DEFAULT_QUERIES[:limit]
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    queries: list[str] = []
    if isinstance(payload, dict):
        candidates = payload.get("queries") or payload.get("evals") or payload.get("items") or []
    else:
        candidates = payload
    for item in candidates:
        if isinstance(item, str):
            query = item.strip()
        elif isinstance(item, dict):
            query = str(item.get("query", "")).strip()
        else:
            query = ""
        if query:
            queries.append(query)
        if len(queries) >= limit:
            break
    return queries or DEFAULT_QUERIES[:limit]


def memory_payload() -> dict[str, Any]:
    snapshot = read_memory_snapshot()
    if snapshot is None:
        return {}
    return {
        "readily_available_mb": round(snapshot.readily_available_mb, 1),
        "free_mb": round(snapshot.free_mb, 1),
        "inactive_mb": round(snapshot.inactive_mb, 1),
        "compressed_mb": round(snapshot.compressed_mb, 1),
        "swapouts": snapshot.swapouts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local_quality search memory/performance.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--queries", default="evals/knowledge_eval_queries.yaml")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--result-limit", type=int, default=8)
    parser.add_argument("--mode", choices=["strategy", "writing", "source", "hybrid"], default="hybrid")
    parser.add_argument("--profile", choices=["local_quality", "local_fast", "local_deep", "legacy"], default="local_quality")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--reranker", default=DEFAULT_RERANKER_NAME)
    parser.add_argument("--query-planner-provider", choices=["auto", "rule", "llm"], default="rule")
    parser.add_argument("--disable-query-rewrite", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    query_path = root / args.queries if args.queries else None
    queries = load_queries(query_path, args.limit)
    reranker_name = None if str(args.reranker).lower() in {"none", "false", "0"} else args.reranker

    print(json.dumps({"event": "benchmark_start", "profile": args.profile, "query_count": len(queries), "memory": memory_payload()}, ensure_ascii=False))
    started_all = time.time()
    for index, query in enumerate(queries, start=1):
        started = time.time()
        results = search_knowledge(
            root,
            query,
            args.mode,
            args.result_limit,
            args.model,
            reranker_name,
            "auto",
            0,
            None,
            conversation_history=[],
            context_info="",
            enable_query_rewrite=not args.disable_query_rewrite,
            planner_provider=args.query_planner_provider,
            profile_name=args.profile,
        )
        elapsed = time.time() - started
        stats = results[0].get("_search_stats", {}) if results else {}
        top_paths = [str(item.get("path", "")) for item in results[:5]]
        print(
            json.dumps(
                {
                    "event": "query_result",
                    "index": index,
                    "query": query,
                    "elapsed_seconds": round(elapsed, 3),
                    "result_count": len(results),
                    "top_paths": top_paths,
                    "stats": stats,
                    "memory": memory_payload(),
                },
                ensure_ascii=False,
            )
        )
    print(json.dumps({"event": "benchmark_done", "elapsed_seconds": round(time.time() - started_all, 3), "memory": memory_payload()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
