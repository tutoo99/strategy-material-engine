#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

from _material_lib import (
    DEFAULT_MODEL_NAME,
    DEFAULT_QUERY_PREFIX,
    DEFAULT_RERANKER_NAME,
    clamp_candidate_count,
    encode_texts,
    read_faiss_index,
    read_jsonl,
    rerank,
)


_LATIN_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._+-]*")
_CJK_BLOCK_RE = re.compile(r"[一-鿿]+")


def extract_query_terms(text: str) -> list[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return []

    terms: list[str] = []
    seen: set[str] = set()

    def push(term: str) -> None:
        cleaned = term.strip().lower()
        if len(cleaned) < 2 or cleaned in seen:
            return
        seen.add(cleaned)
        terms.append(cleaned)

    for term in raw.split():
        push(term)

    for token in _LATIN_TOKEN_RE.findall(raw):
        push(token)

    for block in _CJK_BLOCK_RE.findall(raw):
        if len(block) <= 8:
            push(block)
        for size in (2, 3):
            if len(block) < size:
                continue
            for idx in range(len(block) - size + 1):
                push(block[idx : idx + size])
    return terms


def lexical_overlap(query: str, text: str) -> float:
    query_terms = extract_query_terms(query)
    if not query_terms:
        return 0.0
    haystack = str(text or "").lower()
    hits = sum(1 for term in query_terms if term in haystack)
    return hits / len(query_terms)


def source_doc(item: dict) -> str:
    return " ".join(
        [
            str(item.get("title", "")),
            str(item.get("author", "")),
            str(item.get("origin", "")),
            str(item.get("summary", "")),
            str(item.get("chunk_summary", "")),
            str(item.get("chunk_text", ""))[:400],
        ]
    ).strip()


def source_field_score(query: str, item: dict) -> float:
    field_text = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("author", "")),
            str(item.get("summary", "")),
            str(item.get("chunk_summary", "")),
        ]
    )
    overlap = lexical_overlap(query, field_text)
    author = str(item.get("author", "")).strip()
    author_hit = 1.0 if author and author in query else 0.0
    if overlap <= 0.0 and author_hit <= 0.0:
        return 0.0
    return 0.34 + overlap * 0.18 + author_hit * 0.16


def collapse_duplicate_source_chunks(candidates: list[dict]) -> list[dict]:
    best_by_key: dict[str, dict] = {}
    passthrough: list[dict] = []
    for item in candidates:
        source_key = str(item.get("source_uid") or item.get("content_sha256") or "").strip()
        if not source_key:
            passthrough.append(item)
            continue
        key = f"{source_key}::chunk-{item.get('chunk_index', '')}"
        existing = best_by_key.get(key)
        if existing is None or float(item.get("_score", 0.0)) > float(existing.get("_score", 0.0)):
            best_by_key[key] = item
    collapsed = [*passthrough, *best_by_key.values()]
    collapsed.sort(key=lambda item: item["_score"], reverse=True)
    return collapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--root", default=".")
    parser.add_argument("--index", default="index/sources/source_chunks.faiss")
    parser.add_argument("--meta", default="index/sources/source_chunks_meta.jsonl")
    parser.add_argument("--source-type")
    parser.add_argument("--chunk-role")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--reranker", default=DEFAULT_RERANKER_NAME,
                        help="Reranker model name, or 'none' to disable")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    index_path = root / args.index
    meta_path = root / args.meta
    items = read_jsonl(meta_path)
    if not items:
        return

    index = read_faiss_index(index_path)
    query_vector = encode_texts(
        [args.query],
        model_name=args.model,
        device=args.device,
        batch_size=args.batch_size,
        query_prefix=DEFAULT_QUERY_PREFIX,
    )
    candidate_count = min(clamp_candidate_count(args.limit), len(items))
    scores, indices = index.search(query_vector, candidate_count)

    # Phase 1: filter candidates
    candidates = []
    for raw_score, idx in zip(scores[0].tolist(), indices[0].tolist()):
        if idx < 0 or idx >= len(items):
            continue
        item = dict(items[idx])
        if args.source_type and item.get("source_type") != args.source_type:
            continue
        if args.chunk_role and item.get("chunk_role") != args.chunk_role:
            continue
        item["_vector_score"] = float(raw_score)
        candidates.append(item)

    field_candidates = []
    for raw_item in items:
        item = dict(raw_item)
        if args.source_type and item.get("source_type") != args.source_type:
            continue
        if args.chunk_role and item.get("chunk_role") != args.chunk_role:
            continue
        field_score = source_field_score(args.query, item)
        if field_score <= 0.0:
            continue
        item["_vector_score"] = field_score
        field_candidates.append(item)

    merged_by_id = {str(item.get("id", "")): item for item in candidates}
    for item in sorted(field_candidates, key=lambda current: current["_vector_score"], reverse=True)[: max(args.limit * 4, 12)]:
        item_id = str(item.get("id", ""))
        existing = merged_by_id.get(item_id)
        if existing is None or float(item["_vector_score"]) > float(existing.get("_vector_score", 0.0)):
            merged_by_id[item_id] = item
    candidates = list(merged_by_id.values())

    if not candidates:
        return

    # Phase 2: rerank with cross-encoder
    use_reranker = args.reranker.lower() not in ("none", "false", "0")
    if use_reranker and len(candidates) > 1:
        docs_for_rerank = []
        for c in candidates:
            docs_for_rerank.append(source_doc(c))

        reranker_scores = rerank(args.query, docs_for_rerank,
                                 model_name=args.reranker, device=args.device)

        min_rs, max_rs = min(reranker_scores), max(reranker_scores)
        for i, item in enumerate(candidates):
            rs = reranker_scores[i] if i < len(reranker_scores) else 0.0
            item["_reranker_score"] = rs
            title_bonus = 0.02 if args.query in str(item.get("title", "")) else 0.0
            author_bonus = 0.10 if str(item.get("author", "")).strip() and str(item.get("author", "")) in args.query else 0.0
            field_overlap = lexical_overlap(
                args.query,
                " ".join(
                    [
                        str(item.get("title", "")),
                        str(item.get("author", "")),
                        str(item.get("summary", "")),
                        str(item.get("chunk_summary", "")),
                    ]
                ),
            )
            field_bonus = 0.08 if field_overlap >= 0.30 else 0.04 if field_overlap >= 0.12 else 0.0
            heuristic = item["_vector_score"] + title_bonus + author_bonus + field_bonus
            if max_rs > min_rs:
                norm = (rs - min_rs) / (max_rs - min_rs)
            else:
                norm = 0.5
            # 60% reranker (scaled to ~0.4-0.7) + 40% heuristic
            reranker_scaled = 0.4 + norm * 0.3
            item["_score"] = 0.6 * reranker_scaled + 0.4 * heuristic
    else:
        for item in candidates:
            title_bonus = 0.02 if args.query in str(item.get("title", "")) else 0.0
            author_bonus = 0.10 if str(item.get("author", "")).strip() and str(item.get("author", "")) in args.query else 0.0
            field_overlap = lexical_overlap(
                args.query,
                " ".join(
                    [
                        str(item.get("title", "")),
                        str(item.get("author", "")),
                        str(item.get("summary", "")),
                        str(item.get("chunk_summary", "")),
                    ]
                ),
            )
            field_bonus = 0.08 if field_overlap >= 0.30 else 0.04 if field_overlap >= 0.12 else 0.0
            item["_score"] = item["_vector_score"] + title_bonus + author_bonus + field_bonus

    candidates.sort(key=lambda x: x["_score"], reverse=True)
    candidates = collapse_duplicate_source_chunks(candidates)
    for item in candidates[: args.limit]:
        print(
            json.dumps(
                {
                    "id": item["id"],
                    "path": item["path"],
                    "score": round(item["_score"], 6),
                    "vector_score": round(item["_vector_score"], 6),
                    "source_type": item.get("source_type"),
                    "author": item.get("author"),
                    "chunk_role": item.get("chunk_role"),
                    "summary": item.get("chunk_summary"),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
