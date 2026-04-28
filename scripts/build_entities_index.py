#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
from pathlib import Path

from _incremental_index import build_incremental_vector_index
from _knowledge_lib import (
    DEFAULT_MODEL_NAME,
    ensure_string_list,
    list_markdown_files,
    read_markdown,
)


def build_entity_doc(path: Path, root: Path) -> tuple[list[dict], list[str]]:
    meta, body = read_markdown(path)
    entity_type = str(meta.get("entity_type", "") or "").strip() or "entity"
    name = str(meta.get("name", path.stem) or path.stem).strip()
    payload = {
        "id": str(path.relative_to(root)),
        "path": str(path.relative_to(root)),
        "asset_type": "entity",
        "subtype": f"{entity_type}_profile",
        "entity_type": entity_type,
        "name": name,
        "title": str(meta.get("title", name) or name).strip(),
        "summary": str(meta.get("summary", "") or "").strip(),
        "background_summary": str(meta.get("background_summary", "") or "").strip(),
        "achievement_summary": str(meta.get("achievement_summary", "") or "").strip(),
        "methodology_summary": str(meta.get("methodology_summary", "") or "").strip(),
        "aliases": ensure_string_list(meta.get("aliases")),
        "tags": ensure_string_list(meta.get("tags")),
        "source_count": int(meta.get("source_count", 0) or 0),
        "source_refs": ensure_string_list(meta.get("source_refs")),
        "origin_refs": ensure_string_list(meta.get("origin_refs")),
        "review_status": str(meta.get("review_status", "draft") or "draft").strip(),
        "body": body,
    }
    payload["embed_text"] = "\n".join(
        [
            f"entity_type: {payload['entity_type']}",
            f"name: {payload['name']}",
            f"title: {payload['title']}",
            f"aliases: {' '.join(payload['aliases'])}",
            f"summary: {payload['summary']}",
            f"background_summary: {payload['background_summary']}",
            f"achievement_summary: {payload['achievement_summary']}",
            f"methodology_summary: {payload['methodology_summary']}",
            f"tags: {' '.join(payload['tags'])}",
            f"origin_refs: {' '.join(payload['origin_refs'])}",
            body,
        ]
    )
    return [payload], [payload["embed_text"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="为实体卡构建向量索引")
    parser.add_argument("--root", default=".")
    parser.add_argument("--entities-dir", default="assets/entities")
    parser.add_argument("--index-output", default="index/entities/entities.faiss")
    parser.add_argument("--meta-output", default="index/entities/entities_meta.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    entities_dir = root / args.entities_dir
    index_output = root / args.index_output
    meta_output = root / args.meta_output
    summary = build_incremental_vector_index(
        root=root,
        bucket="entities",
        source_paths=list_markdown_files(entities_dir),
        build_doc_payload=build_entity_doc,
        index_output_path=index_output,
        meta_output_path=meta_output,
        model_name=args.model,
        device=args.device,
        batch_size=args.batch_size,
    )
    print(
        f"Built entities vector index: {index_output} "
        f"({summary['row_count']} entities, changed_docs={summary['changed_document_count']}, "
        f"reused_docs={summary['reused_document_count']})"
    )


if __name__ == "__main__":
    main()
