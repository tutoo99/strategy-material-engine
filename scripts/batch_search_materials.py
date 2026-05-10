#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _material_lib import DEFAULT_MODEL_NAME, DEFAULT_QUERY_PREFIX, DEFAULT_RERANKER_NAME
from _material_lib import encode_texts, read_faiss_index, read_jsonl
from search_materials import format_search_result, search_materials_with_loaded_index


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _load_specs(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        specs = payload.get("queries") or []
    else:
        specs = payload
    if not isinstance(specs, list):
        raise ValueError("queries payload must be a list or an object with a queries list")
    normalized = []
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict):
            continue
        query = str(spec.get("query") or "").strip()
        if not query:
            continue
        item = dict(spec)
        item.setdefault("id", str(index))
        item["query"] = query
        normalized.append(item)
    return normalized


def _result_for_error(spec: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "id": spec.get("id"),
        "section": spec.get("section"),
        "query": spec.get("query"),
        "angle": spec.get("angle"),
        "source": spec.get("source"),
        "fallback": bool(spec.get("fallback")),
        "error": message,
        "results": [],
    }


def batch_search(
    *,
    root: Path,
    specs: list[dict[str, Any]],
    index_relpath: str,
    meta_relpath: str,
    model: str,
    reranker: str | None,
    device: str,
    batch_size: int,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    if not specs:
        return []

    items = read_jsonl(root / meta_relpath)
    if not items:
        return [_result_for_error(spec, "empty materials metadata") for spec in specs]

    index = read_faiss_index(root / index_relpath)
    query_vectors = encode_texts(
        [spec["query"] for spec in specs],
        model_name=model,
        device=device,
        batch_size=batch_size,
        query_prefix=DEFAULT_QUERY_PREFIX,
    )

    output = []
    for spec, query_vector in zip(specs, query_vectors):
        try:
            results = search_materials_with_loaded_index(
                items=items,
                index=index,
                query=spec["query"],
                query_vector=query_vector,
                limit=int(spec.get("limit") or 5),
                expected_type=spec.get("type"),
                expected_role=spec.get("role"),
                prefer_type=spec.get("prefer_type"),
                prefer_role=spec.get("prefer_role"),
                reranker=reranker,
                device=device,
                max_per_source=int(spec.get("max_per_source") or 1),
                domain_query=spec.get("domain_query"),
                min_domain_overlap=float(spec.get("min_domain_overlap") or 0.0),
                min_vector_score=float(spec.get("min_vector_score") or 0.0),
                require_terms=_as_list(spec.get("require_terms")),
                min_required_term_hits=int(spec.get("min_required_term_hits") or 0),
                block_terms=_as_list(spec.get("block_terms")),
            )
            output.append(
                {
                    "id": spec.get("id"),
                    "section": spec.get("section"),
                    "query": spec.get("query"),
                    "angle": spec.get("angle"),
                    "source": spec.get("source"),
                    "fallback": bool(spec.get("fallback")),
                    "results": [format_search_result(item, verbose=verbose) for item in results],
                }
            )
        except Exception as exc:
            output.append(_result_for_error(spec, str(exc)))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch material search with one model/index load.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--queries-json", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--index", default="index/materials/materials.faiss")
    parser.add_argument("--meta", default="index/materials/materials_meta.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument(
        "--reranker",
        default=DEFAULT_RERANKER_NAME,
        help="Reranker model name, or 'none' to disable",
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    specs = _load_specs(Path(args.queries_json))
    results = batch_search(
        root=Path(args.root).resolve(),
        specs=specs,
        index_relpath=args.index,
        meta_relpath=args.meta,
        model=args.model,
        reranker=None if args.reranker.lower() in ("none", "false", "0") else args.reranker,
        device=args.device,
        batch_size=args.batch_size,
        verbose=args.verbose,
    )

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    for row in results:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
