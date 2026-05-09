#!/opt/miniconda3/bin/python3

import argparse
from pathlib import Path

from _incremental_index import build_incremental_vector_index
from _dedupe_lib import normalize_content, sha256_text
from _material_lib import (
    DEFAULT_MODEL_NAME,
    ensure_float,
    ensure_int,
    ensure_string_list,
    list_markdown_files,
    parse_frontmatter,
)


def build_material_doc(path: Path, root: Path) -> tuple[list[dict], list[str]]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    claims = ensure_string_list(meta.get("claims"))
    tags = ensure_string_list(meta.get("tags"))
    channel_fit = ensure_string_list(meta.get("channel_fit"))
    content_sha256 = str(meta.get("content_sha256") or sha256_text(normalize_content(body)))
    payload = {
        "id": str(path.relative_to(root)),
        "path": str(path.relative_to(root)),
        "asset_type": "material",
        "subtype": meta.get("type", ""),
        "type": meta.get("type", ""),
        "story_arc": meta.get("story_arc", ""),
        "primary_claim": meta.get("primary_claim", ""),
        "claims": claims,
        "tags": tags,
        "ammo_type": meta.get("ammo_type", "dual"),
        "role": meta.get("role", ""),
        "strength": meta.get("strength", ""),
        "channel_fit": channel_fit,
        "source": meta.get("source", ""),
        "source_refs": ensure_string_list(meta.get("source_refs")),
        "source_uid": meta.get("source_uid", ""),
        "content_sha256": content_sha256,
        "duplicate_of": meta.get("duplicate_of", ""),
        "derived_from_case": meta.get("derived_from_case", ""),
        "date": meta.get("date", ""),
        "quality_score": ensure_float(meta.get("quality_score"), 3.0),
        "use_count": ensure_int(meta.get("use_count"), 0),
        "last_used_at": meta.get("last_used_at", ""),
        "used_in_articles": ensure_string_list(meta.get("used_in_articles")),
        "source_reliability": ensure_float(meta.get("source_reliability"), 3.0),
        "review_status": meta.get("review_status", "draft"),
        "body": body,
    }
    embed_text = "\n".join(
        [
            f"type: {payload['type']}",
            f"story_arc: {payload['story_arc']}",
            f"primary_claim: {payload['primary_claim']}",
            f"claims: {' | '.join(payload['claims'])}",
            f"tags: {' '.join(payload['tags'])}",
            f"ammo_type: {payload['ammo_type']}",
            f"role: {payload['role']}",
            f"strength: {payload['strength']}",
            f"channel_fit: {' '.join(payload['channel_fit'])}",
            f"source: {payload['source']}",
            f"source_refs: {' '.join(payload['source_refs'])}",
            f"derived_from_case: {payload['derived_from_case']}",
            f"quality_score: {payload['quality_score']}",
            f"source_reliability: {payload['source_reliability']}",
            body,
        ]
    )
    payload["embed_text"] = embed_text
    return [payload], [embed_text]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--materials-dir", default="assets/materials")
    parser.add_argument("--index-output", default="index/materials/materials.faiss")
    parser.add_argument("--meta-output", default="index/materials/materials_meta.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    # Index builds prioritize stability over peak throughput on this host.
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    materials_dir = root / args.materials_dir
    index_output_path = root / args.index_output
    meta_output_path = root / args.meta_output

    summary = build_incremental_vector_index(
        root=root,
        bucket="materials",
        source_paths=list_markdown_files(materials_dir),
        build_doc_payload=build_material_doc,
        index_output_path=index_output_path,
        meta_output_path=meta_output_path,
        model_name=args.model,
        device=args.device,
        batch_size=args.batch_size,
    )
    print(
        f"Built materials vector index: {index_output_path} "
        f"({summary['row_count']} items, changed_docs={summary['changed_document_count']}, "
        f"reused_docs={summary['reused_document_count']}, meta: {meta_output_path})"
    )


if __name__ == "__main__":
    main()
