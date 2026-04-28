#!/opt/miniconda3/bin/python3

import argparse
import re
from pathlib import Path

from _incremental_index import build_incremental_vector_index
from _material_lib import (
    DEFAULT_MODEL_NAME,
    ensure_string_list,
    list_markdown_files,
    parse_frontmatter,
)


def chunk_body(body: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
    return blocks


def detect_role(chunk: str) -> str:
    if re.search(r"\d+%|\d+万|\d+个|\d+天|\d+年", chunk):
        return "data"
    if any(word in chunk for word in ["方法", "步骤", "做法", "SOP", "流程"]):
        return "method"
    if any(word in chunk for word in ["我", "他", "她", "后来", "结果", "当时"]):
        return "story"
    return "note"


def build_source_doc(path: Path, root: Path) -> tuple[list[dict], list[str]]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    tags = ensure_string_list(meta.get("tags"))
    summary = str(meta.get("summary", "") or "").strip()
    rows: list[dict] = []
    embed_texts: list[str] = []
    for idx, chunk in enumerate(chunk_body(body), start=1):
        payload = {
            "id": f"{path.relative_to(root)}::chunk-{idx}",
            "path": str(path.relative_to(root)),
            "chunk_index": idx,
            "source_type": meta.get("source_type", ""),
            "title": meta.get("title", path.stem),
            "author": meta.get("author", ""),
            "origin": meta.get("origin", ""),
            "date": meta.get("date", ""),
            "summary": summary,
            "tags": tags,
            "source_uid": meta.get("source_uid", ""),
            "canonical_url": meta.get("canonical_url", ""),
            "content_sha256": meta.get("content_sha256", ""),
            "simhash64": meta.get("simhash64", ""),
            "duplicate_of": meta.get("duplicate_of", ""),
            "chunk_role": detect_role(chunk),
            "chunk_text": chunk,
            "chunk_summary": chunk[:80].replace("\n", " "),
            "embed_text": "\n".join(
                [
                    f"title: {meta.get('title', path.stem)}",
                    f"author: {meta.get('author', '')}",
                    f"origin: {meta.get('origin', '')}",
                    f"source_type: {meta.get('source_type', '')}",
                    f"summary: {summary}",
                    f"tags: {' '.join(tags)}",
                    chunk,
                ]
            ),
        }
        rows.append(payload)
        embed_texts.append(payload["embed_text"])
    return rows, embed_texts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--sources-dir", default="sources")
    parser.add_argument("--index-output", default="index/sources/source_chunks.faiss")
    parser.add_argument("--meta-output", default="index/sources/source_chunks_meta.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    # Index builds prioritize stability over peak throughput on this host.
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sources_dir = root / args.sources_dir
    index_output_path = root / args.index_output
    meta_output_path = root / args.meta_output

    summary = build_incremental_vector_index(
        root=root,
        bucket="sources",
        source_paths=list_markdown_files(sources_dir),
        build_doc_payload=build_source_doc,
        index_output_path=index_output_path,
        meta_output_path=meta_output_path,
        model_name=args.model,
        device=args.device,
        batch_size=args.batch_size,
    )
    print(
        f"Built sources vector index: {index_output_path} "
        f"({summary['row_count']} chunks, changed_docs={summary['changed_document_count']}, "
        f"reused_docs={summary['reused_document_count']}, meta: {meta_output_path})"
    )


if __name__ == "__main__":
    main()
