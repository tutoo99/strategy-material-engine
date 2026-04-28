#!/opt/miniconda3/bin/python3

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from search_materials import search_materials


DEFAULT_WANTED_COUNTS = [2, 5, 10]
DEFAULT_MIN_HIGH_CONFIDENCE = {2: 1, 5: 2, 10: 3}
DEFAULT_SCORE_THRESHOLD = 0.52
DEFAULT_QUALITY_THRESHOLD = 3.5


def precision_at_k(results: list[dict], known_good: set[str], k: int) -> float:
    subset = results[:k]
    if not subset:
        return 0.0
    hits = sum(1 for item in subset if item.get("path") in known_good)
    return hits / len(subset)


def recall_at_k(results: list[dict], known_good: set[str], k: int) -> float:
    if not known_good:
        return 0.0
    subset = results[:k]
    hits = sum(1 for item in subset if item.get("path") in known_good)
    return hits / len(known_good)


def bad_hit_at_k(results: list[dict], bad_paths: set[str], k: int) -> int:
    subset = results[:k]
    return sum(1 for item in subset if item.get("path") in bad_paths)


def diversity_at_k(results: list[dict], key: str, k: int) -> int:
    subset = results[:k]
    return len({str(item.get(key, "")) for item in subset if item.get(key)})


def high_confidence_count_at_k(
    results: list[dict],
    k: int,
    *,
    score_threshold: float,
    quality_threshold: float,
) -> int:
    subset = results[:k]
    total = 0
    for item in subset:
        score = float(item.get("_score", 0.0) or 0.0)
        quality = float(item.get("quality_score", 3.0) or 3.0)
        if score >= score_threshold and quality >= quality_threshold:
            total += 1
    return total


def direct_usable_count_at_k(
    results: list[dict],
    known_good: set[str],
    k: int,
    *,
    score_threshold: float,
) -> int:
    subset = results[:k]
    total = 0
    for item in subset:
        if item.get("path") not in known_good:
            continue
        score = float(item.get("_score", 0.0) or 0.0)
        if score >= score_threshold:
            total += 1
    return total


def mean_quality_at_k(results: list[dict], k: int) -> float:
    subset = results[:k]
    if not subset:
        return 0.0
    values = [float(item.get("quality_score", 3.0) or 3.0) for item in subset]
    return sum(values) / len(values)


def mean_source_reliability_at_k(results: list[dict], k: int) -> float:
    subset = results[:k]
    if not subset:
        return 0.0
    values = [float(item.get("source_reliability", 3.0) or 3.0) for item in subset]
    return sum(values) / len(values)


def classify_status(
    *,
    requested_count: int,
    available_count: int,
    high_confidence_count: int,
    direct_usable_count: int,
    bad_hits: int,
    min_high_confidence: int,
) -> tuple[str, str]:
    if available_count == 0:
        return ("insufficient", "没有返回任何结果")
    if bad_hits > 0 and direct_usable_count == 0 and high_confidence_count == 0:
        return ("low_quality", "命中了结果，但前排包含明显噪音且没有高置信候选")
    if available_count < requested_count:
        return ("insufficient", f"只返回了 {available_count} 条，少于期望的 {requested_count} 条")
    if direct_usable_count >= min_high_confidence or high_confidence_count >= min_high_confidence:
        return ("enough", f"高置信候选达到 {min_high_confidence} 条及以上")
    if high_confidence_count > 0 or direct_usable_count > 0:
        return ("low_quality", "有部分可用结果，但高质量候选数量不足")
    return ("insufficient", "有召回，但没有达到可直接使用的质量线")


def load_queries(path: Path) -> list[dict]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    queries = payload.get("queries", [])
    if not isinstance(queries, list):
        raise SystemExit("`queries` must be a list")
    return queries


def render_markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Retrieval Evaluation Report")
    lines.append("")
    lines.append(f"- Query file: `{report['query_file']}`")
    lines.append(f"- Total queries: `{report['total_queries']}`")
    lines.append("")

    aggregate = report.get("aggregate", {})
    if aggregate:
        lines.append("## Aggregate")
        lines.append("")
        lines.append("| K | Avg Precision | Avg Recall | Avg Bad Hits | Enough Rate | Low Quality Rate | Insufficient Rate |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for key, values in aggregate.items():
            lines.append(
                f"| {key} | {values.get('avg_precision', 0):.4f} | {values.get('avg_recall', 0):.4f} | "
                f"{values.get('avg_bad_hits', 0):.4f} | {values.get('enough_rate', 0):.4f} | "
                f"{values.get('low_quality_rate', 0):.4f} | {values.get('insufficient_rate', 0):.4f} |"
            )
        lines.append("")

    lines.append("## Queries")
    lines.append("")
    for entry in report.get("results", []):
        lines.append(f"### {entry.get('id')}")
        lines.append("")
        lines.append(f"- Query: {entry.get('query')}")
        if entry.get("expected_type") or entry.get("expected_role"):
            lines.append(
                f"- Expected: `type={entry.get('expected_type')}` `role={entry.get('expected_role')}`"
            )
        lines.append("")
        lines.append("| K | Precision | Recall | High Confidence | Direct Usable | Mean Quality | Mean Reliability | Bad Hits | Status | Reason |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
        for key, values in entry.get("metrics", {}).items():
            lines.append(
                f"| {key} | {values.get('precision', 0):.4f} | {values.get('recall', 0):.4f} | "
                f"{values.get('high_confidence_count', 0)} | {values.get('direct_usable_count', 0)} | "
                f"{values.get('mean_quality', 0):.4f} | {values.get('mean_source_reliability', 0):.4f} | "
                f"{values.get('bad_hits', 0)} | {values.get('status', '')} | {values.get('reason', '')} |"
            )
        lines.append("")
        lines.append("Top results:")
        for idx, item in enumerate(entry.get("top_results", []), start=1):
            lines.append(
                f"- {idx}. `{item.get('path')}` | score={item.get('score')} | "
                f"quality={item.get('quality_score')} | reliability={item.get('source_reliability')} | "
                f"review={item.get('review_status')} | use_count={item.get('use_count')}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--queries", default="evals/eval_queries.yaml")
    parser.add_argument("--model")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    parser.add_argument("--quality-threshold", type=float, default=DEFAULT_QUALITY_THRESHOLD)
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    query_path = root / args.queries
    queries = load_queries(query_path)
    report = {
        "query_file": str(query_path),
        "total_queries": len(queries),
        "results": [],
    }

    aggregate: dict[int, dict[str, float]] = {}

    for entry in queries:
        query = str(entry.get("query", "")).strip()
        if not query:
            continue
        wanted_counts = entry.get("wanted_counts") or DEFAULT_WANTED_COUNTS
        known_good = {str(item) for item in entry.get("known_good_paths", [])}
        bad_paths = {str(item) for item in entry.get("bad_paths", [])}
        expected_type = entry.get("expected_type")
        expected_role = entry.get("expected_role")
        max_k = max(int(count) for count in wanted_counts)
        results = search_materials(
            root=root,
            query=query,
            limit=max_k,
            expected_type=expected_type,
            expected_role=expected_role,
            device=args.device,
            batch_size=args.batch_size,
            model=args.model or "BAAI/bge-large-zh-v1.5",
        )

        metrics = {}
        for count in wanted_counts:
            k = int(count)
            min_high_confidence = int(entry.get("min_high_confidence", DEFAULT_MIN_HIGH_CONFIDENCE.get(k, max(1, k // 3))))
            high_confidence_count = high_confidence_count_at_k(
                results,
                k,
                score_threshold=args.score_threshold,
                quality_threshold=args.quality_threshold,
            )
            direct_usable_count = direct_usable_count_at_k(
                results,
                known_good,
                k,
                score_threshold=args.score_threshold,
            )
            bad_hits = bad_hit_at_k(results, bad_paths, k)
            status, reason = classify_status(
                requested_count=k,
                available_count=min(len(results), k),
                high_confidence_count=high_confidence_count,
                direct_usable_count=direct_usable_count,
                bad_hits=bad_hits,
                min_high_confidence=min_high_confidence,
            )
            metrics[str(k)] = {
                "precision": round(precision_at_k(results, known_good, k), 4),
                "recall": round(recall_at_k(results, known_good, k), 4),
                "bad_hits": bad_hits,
                "source_diversity": diversity_at_k(results, "source", k),
                "type_diversity": diversity_at_k(results, "type", k),
                "high_confidence_count": high_confidence_count,
                "direct_usable_count": direct_usable_count,
                "mean_quality": round(mean_quality_at_k(results, k), 4),
                "mean_source_reliability": round(mean_source_reliability_at_k(results, k), 4),
                "status": status,
                "reason": reason,
            }
            aggregate.setdefault(
                k,
                {
                    "precision": 0.0,
                    "recall": 0.0,
                    "bad_hits": 0.0,
                    "enough": 0.0,
                    "low_quality": 0.0,
                    "insufficient": 0.0,
                },
            )
            aggregate[k]["precision"] += metrics[str(k)]["precision"]
            aggregate[k]["recall"] += metrics[str(k)]["recall"]
            aggregate[k]["bad_hits"] += metrics[str(k)]["bad_hits"]
            aggregate[k][status] += 1

        report["results"].append(
            {
                "id": entry.get("id"),
                "query": query,
                "expected_type": expected_type,
                "expected_role": expected_role,
                "metrics": metrics,
                "top_results": [
                    {
                        "path": item.get("path"),
                        "score": round(float(item.get("_score", 0.0)), 6),
                        "quality_score": item.get("quality_score"),
                        "source_reliability": item.get("source_reliability"),
                        "review_status": item.get("review_status"),
                        "use_count": item.get("use_count"),
                    }
                    for item in results[:max_k]
                ],
            }
        )

    if report["total_queries"] > 0:
        report["aggregate"] = {
            str(k): {
                "avg_precision": round(values["precision"] / report["total_queries"], 4),
                "avg_recall": round(values["recall"] / report["total_queries"], 4),
                "avg_bad_hits": round(values["bad_hits"] / report["total_queries"], 4),
                "enough_rate": round(values["enough"] / report["total_queries"], 4),
                "low_quality_rate": round(values["low_quality"] / report["total_queries"], 4),
                "insufficient_rate": round(values["insufficient"] / report["total_queries"], 4),
            }
            for k, values in sorted(aggregate.items())
        }

    if args.output_json:
        output_json_path = root / args.output_json
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    markdown = render_markdown_report(report)
    if args.output_md:
        output_md_path = root / args.output_md
        output_md_path.parent.mkdir(parents=True, exist_ok=True)
        output_md_path.write_text(markdown, encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
