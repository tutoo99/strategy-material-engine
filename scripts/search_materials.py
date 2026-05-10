#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Any

from _material_lib import (
    DEFAULT_MODEL_NAME,
    DEFAULT_QUERY_PREFIX,
    DEFAULT_RERANKER_NAME,
    clamp_candidate_count,
    days_since,
    encode_texts,
    lexical_overlap_ratio,
    read_faiss_index,
    read_jsonl,
    rerank,
)


def item_relevance_text(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("primary_claim", "")),
        " ".join(str(entry) for entry in item.get("claims", []) if entry),
        " ".join(str(entry) for entry in item.get("tags", []) if entry),
        " ".join(str(entry) for entry in item.get("channel_fit", []) if entry),
        str(item.get("source", "")),
        str(item.get("body", ""))[:600],
    ]
    return " ".join(part for part in parts if part.strip())


def normalize_term_list(values: list[str] | None) -> list[str]:
    terms = []
    for value in values or []:
        for part in str(value).replace("，", ",").split(","):
            term = part.strip().lower()
            if term and term not in terms:
                terms.append(term)
    return terms


def count_term_hits(terms: list[str], text: str) -> int:
    haystack = str(text or "").lower()
    return sum(1 for term in terms if term and term in haystack)


def collapse_duplicate_materials(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for item in candidates:
        key = str(item.get("source_uid") or item.get("content_sha256") or "").strip()
        if not key:
            passthrough.append(item)
            continue
        existing = best_by_key.get(key)
        if existing is None or float(item.get("_score", 0.0)) > float(existing.get("_score", 0.0)):
            best_by_key[key] = item
    collapsed = [*passthrough, *best_by_key.values()]
    collapsed.sort(key=lambda item: item["_score"], reverse=True)
    return collapsed


def material_rank(
    item: dict[str, Any],
    *,
    query: str,
    vector_score: float,
    expected_type: str | None = None,
    expected_role: str | None = None,
    prefer_type: str | None = None,
    prefer_role: str | None = None,
) -> dict[str, float]:
    claim_texts = [str(item.get("primary_claim", ""))] + [str(entry) for entry in item.get("claims", [])]
    lexical_ratio = lexical_overlap_ratio(query, claim_texts + [str(item.get("body", ""))[:300]])
    claim_bonus = 0.03 if lexical_ratio >= 0.45 else 0.015 if lexical_ratio >= 0.2 else 0.0
    type_bonus = 0.04 if expected_type and item.get("type") == expected_type else 0.0
    role_bonus = 0.04 if expected_role and item.get("role") == expected_role else 0.0
    prefer_type_bonus = 0.0
    if prefer_type:
        prefer_type_bonus = 0.06 if item.get("type") == prefer_type else -0.015
    prefer_role_bonus = 0.0
    if prefer_role:
        prefer_role_bonus = 0.06 if item.get("role") == prefer_role else -0.015
    quality_score = float(item.get("quality_score", 3.0) or 3.0)
    quality_bonus = max(min((quality_score - 3.0) * 0.015, 0.045), -0.045)
    source_reliability = float(item.get("source_reliability", 3.0) or 3.0)
    reliability_bonus = max(min((source_reliability - 3.0) * 0.008, 0.024), -0.024)
    use_count = int(item.get("use_count", 0) or 0)
    reuse_penalty = min(use_count * 0.006, 0.06)
    age_days = days_since(item.get("last_used_at"))
    freshness_bonus = 0.015 if age_days is None else -0.02 if age_days <= 7 else -0.01 if age_days <= 30 else 0.0
    review_status = str(item.get("review_status", "draft"))
    review_bonus = 0.015 if review_status == "reviewed" else 0.025 if review_status == "approved" else 0.0
    final_score = (
        vector_score
        + claim_bonus
        + type_bonus
        + role_bonus
        + prefer_type_bonus
        + prefer_role_bonus
        + quality_bonus
        + reliability_bonus
        + freshness_bonus
        + review_bonus
        - reuse_penalty
    )
    return {
        "final_score": final_score,
        "vector_score": vector_score,
        "claim_bonus": claim_bonus,
        "type_bonus": type_bonus,
        "role_bonus": role_bonus,
        "prefer_type_bonus": prefer_type_bonus,
        "prefer_role_bonus": prefer_role_bonus,
        "quality_bonus": quality_bonus,
        "reliability_bonus": reliability_bonus,
        "freshness_bonus": freshness_bonus,
        "review_bonus": review_bonus,
        "reuse_penalty": reuse_penalty,
    }


def search_materials(
    *,
    root: Path,
    query: str,
    limit: int = 5,
    expected_type: str | None = None,
    expected_role: str | None = None,
    prefer_type: str | None = None,
    prefer_role: str | None = None,
    model: str = DEFAULT_MODEL_NAME,
    reranker: str = DEFAULT_RERANKER_NAME,
    device: str = "auto",
    batch_size: int = 8,
    rerank_top_k: int = 20,
    index_relpath: str = "index/materials/materials.faiss",
    meta_relpath: str = "index/materials/materials_meta.jsonl",
    max_per_source: int = 1,
    domain_query: str | None = None,
    min_domain_overlap: float = 0.0,
    min_vector_score: float = 0.0,
    require_terms: list[str] | None = None,
    min_required_term_hits: int = 0,
    block_terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    index_path = root / index_relpath
    meta_path = root / meta_relpath
    items = read_jsonl(meta_path)
    if not items:
        return []

    index = read_faiss_index(index_path)
    query_vector = encode_texts(
        [query],
        model_name=model,
        device=device,
        batch_size=batch_size,
        query_prefix=DEFAULT_QUERY_PREFIX,
    )
    return search_materials_with_loaded_index(
        items=items,
        index=index,
        query=query,
        query_vector=query_vector[0],
        limit=limit,
        expected_type=expected_type,
        expected_role=expected_role,
        prefer_type=prefer_type,
        prefer_role=prefer_role,
        reranker=reranker,
        device=device,
        max_per_source=max_per_source,
        domain_query=domain_query,
        min_domain_overlap=min_domain_overlap,
        min_vector_score=min_vector_score,
        require_terms=require_terms,
        min_required_term_hits=min_required_term_hits,
        block_terms=block_terms,
    )


def search_materials_with_loaded_index(
    *,
    items: list[dict[str, Any]],
    index: Any,
    query: str,
    query_vector: Any,
    limit: int = 5,
    expected_type: str | None = None,
    expected_role: str | None = None,
    prefer_type: str | None = None,
    prefer_role: str | None = None,
    reranker: str | None = DEFAULT_RERANKER_NAME,
    device: str = "auto",
    max_per_source: int = 1,
    domain_query: str | None = None,
    min_domain_overlap: float = 0.0,
    min_vector_score: float = 0.0,
    require_terms: list[str] | None = None,
    min_required_term_hits: int = 0,
    block_terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not items:
        return []

    candidate_count = clamp_candidate_count(limit)
    if expected_type or expected_role:
        # Hard filters reduce the usable pool, so widen the first-pass recall window.
        candidate_count = max(candidate_count, limit * 8)
    candidate_count = min(candidate_count, len(items))
    scores, indices = index.search(query_vector.reshape(1, -1), candidate_count)

    # Phase 1: collect candidates
    candidates: list[dict[str, Any]] = []
    normalized_require_terms = normalize_term_list(require_terms)
    normalized_block_terms = normalize_term_list(block_terms)
    for raw_score, idx in zip(scores[0].tolist(), indices[0].tolist()):
        if idx < 0 or idx >= len(items):
            continue
        if raw_score < min_vector_score:
            continue
        item = dict(items[idx])
        if str(item.get("review_status", "") or "").strip() == "rejected":
            continue
        relevance_text = item_relevance_text(item)
        domain_overlap = lexical_overlap_ratio(domain_query, [relevance_text]) if domain_query else 0.0
        if domain_query and min_domain_overlap > 0 and domain_overlap < min_domain_overlap:
            continue
        required_term_hits = count_term_hits(normalized_require_terms, relevance_text)
        if normalized_require_terms and required_term_hits < min_required_term_hits:
            continue
        block_term_hits = count_term_hits(normalized_block_terms, relevance_text)
        if normalized_block_terms and block_term_hits > 0:
            continue
        item["_vector_score"] = float(raw_score)
        item["_domain_overlap"] = float(domain_overlap)
        item["_required_term_hits"] = int(required_term_hits)
        item["_block_term_hits"] = int(block_term_hits)
        candidates.append(item)

    if not candidates:
        return []

    requested_type = str(expected_type or "").strip()
    if requested_type:
        candidates = [item for item in candidates if str(item.get("type", "")).strip() == requested_type]
    requested_role = str(expected_role or "").strip()
    if requested_role:
        candidates = [item for item in candidates if str(item.get("role", "")).strip() == requested_role]
    if not candidates:
        return []

    # Phase 2: rerank with cross-encoder
    use_reranker = reranker and len(candidates) > 1
    reranker_scores: list[float] | None = None
    if use_reranker:
        docs_for_rerank = []
        for c in candidates:
            # Combine primary_claim + claims + body preview for reranker
            parts = [str(c.get("primary_claim", ""))]
            parts.extend(str(x) for x in c.get("claims", []) if x)
            body = str(c.get("body", ""))
            if body:
                parts.append(body[:400])
            docs_for_rerank.append(" ".join(parts))
        reranker_scores = rerank(
            query,
            docs_for_rerank,
            model_name=reranker,
            device=device,
        )

    # Phase 3: apply heuristic bonuses on top of reranker scores
    for i, item in enumerate(candidates):
        vector_score = item["_vector_score"]
        if use_reranker and reranker_scores:
            # Normalize reranker score to a comparable scale
            # reranker scores can be negative, shift to be around vector score range
            rs = reranker_scores[i] if i < len(reranker_scores) else 0.0
            base_score = rs
        else:
            base_score = vector_score

        components = material_rank(
            item,
            query=query,
            vector_score=base_score if not use_reranker else vector_score,
            expected_type=expected_type,
            expected_role=expected_role,
            prefer_type=prefer_type,
            prefer_role=prefer_role,
        )

        # Override: if reranker was used, its score replaces vector_score in the final mix
        if use_reranker and reranker_scores:
            components["reranker_score"] = reranker_scores[i] if i < len(reranker_scores) else 0.0
            # Blend: 60% reranker, 40% heuristic (which already includes vector score)
            heuristic_score = components["final_score"]
            reranker_norm = reranker_scores[i] if i < len(reranker_scores) else 0.0
            # Shift reranker scores to 0-1 range for blending
            if reranker_scores:
                min_rs = min(reranker_scores)
                max_rs = max(reranker_scores)
                if max_rs > min_rs:
                    reranker_norm = (reranker_scores[i] - min_rs) / (max_rs - min_rs)
                else:
                    reranker_norm = 0.5
            # Rescale to similar magnitude as heuristic scores (~0.4-0.7)
            reranker_scaled = 0.4 + reranker_norm * 0.3
            components["final_score"] = 0.6 * reranker_scaled + 0.4 * heuristic_score
            components["reranker_scaled"] = reranker_scaled

        item["_score"] = components["final_score"]
        components["domain_overlap"] = item.get("_domain_overlap", 0.0)
        components["required_term_hits"] = item.get("_required_term_hits", 0)
        item["_rank_components"] = components

    candidates.sort(key=lambda item: item["_score"], reverse=True)
    candidates = collapse_duplicate_materials(candidates)

    # Per-source dedup: keep at most max_per_source items per source
    source_counts: dict[str, int] = {}
    filtered: list[dict[str, Any]] = []
    for item in candidates:
        source = item.get("source") or item.get("path") or item.get("primary_claim", "")
        source = str(source)
        if source_counts.get(source, 0) < max_per_source:
            source_counts[source] = source_counts.get(source, 0) + 1
            filtered.append(item)
            if len(filtered) >= limit:
                break

    return filtered


def format_search_result(item: dict[str, Any], *, verbose: bool = False) -> dict[str, Any]:
    preview = str(item.get("body", "")).replace("\n", " ")[:120]
    payload = {
        "path": item["path"],
        "score": round(item["_score"], 6),
        "vector_score": round(item["_rank_components"]["vector_score"], 6),
        "type": item.get("type"),
        "primary_claim": item.get("primary_claim"),
        "role": item.get("role"),
        "source": item.get("source"),
        "quality_score": item.get("quality_score"),
        "source_reliability": item.get("source_reliability"),
        "review_status": item.get("review_status"),
        "use_count": item.get("use_count"),
        "last_used_at": item.get("last_used_at"),
        "domain_overlap": round(float(item.get("_domain_overlap", 0.0)), 6),
        "required_term_hits": item.get("_required_term_hits", 0),
        "preview": preview,
    }
    if verbose:
        payload["rank_components"] = {
            key: round(value, 6) for key, value in item["_rank_components"].items()
        }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--root", default=".")
    parser.add_argument("--index", default="index/materials/materials.faiss")
    parser.add_argument("--meta", default="index/materials/materials_meta.jsonl")
    parser.add_argument("--type")
    parser.add_argument("--role")
    parser.add_argument("--prefer-type")
    parser.add_argument("--prefer-role")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--reranker", default=DEFAULT_RERANKER_NAME,
                        help="Reranker model name, or 'none' to disable")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--max-per-source", type=int, default=1,
                        help="Max candidates to return per source (default: 1)")
    parser.add_argument("--domain-query", default=None,
                        help="Topic/domain signature used as a generic relevance gate")
    parser.add_argument("--min-domain-overlap", type=float, default=0.0,
                        help="Minimum lexical overlap with --domain-query")
    parser.add_argument("--min-vector-score", type=float, default=0.0,
                        help="Minimum vector score before heuristic bonuses")
    parser.add_argument("--require-term", action="append", default=[],
                        help="Required domain term; may be repeated or comma-separated")
    parser.add_argument("--min-required-term-hits", type=int, default=0,
                        help="Minimum required-term hits when --require-term is provided")
    parser.add_argument("--block-term", action="append", default=[],
                        help="Block candidates containing this term; may be repeated or comma-separated")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    results = search_materials(
        root=root,
        query=args.query,
        limit=args.limit,
        expected_type=args.type,
        expected_role=args.role,
        prefer_type=args.prefer_type,
        prefer_role=args.prefer_role,
        model=args.model,
        reranker=None if args.reranker.lower() in ("none", "false", "0") else args.reranker,
        device=args.device,
        batch_size=args.batch_size,
        index_relpath=args.index,
        meta_relpath=args.meta,
        max_per_source=args.max_per_source,
        domain_query=args.domain_query,
        min_domain_overlap=args.min_domain_overlap,
        min_vector_score=args.min_vector_score,
        require_terms=args.require_term,
        min_required_term_hits=args.min_required_term_hits,
        block_terms=args.block_term,
    )
    for item in results:
        payload = format_search_result(item, verbose=args.verbose)
        print(
            json.dumps(
                payload,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
