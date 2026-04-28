#!/opt/miniconda3/bin/python3

import argparse
from pathlib import Path

from _incremental_index import build_incremental_vector_index
from _knowledge_lib import DEFAULT_MODEL_NAME, case_embed_payload, list_markdown_files

SKIP_DIR_NAMES = {"imported", "drafts"}


def build_case_doc(path: Path, root: Path) -> tuple[list[dict], list[str]]:
    payload = case_embed_payload(path, root)
    return [payload], [payload["embed_text"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="为统一 skill 构建案例向量索引")
    parser.add_argument("--root", default=".")
    parser.add_argument("--cases-dir", default="assets/cases")
    parser.add_argument("--index-output", default="index/cases/cases.faiss")
    parser.add_argument("--meta-output", default="index/cases/cases_vector_meta.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    # Index builds prioritize stability over peak throughput on this host.
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    cases_dir = root / args.cases_dir
    index_output = root / args.index_output
    meta_output = root / args.meta_output
    source_paths = [
        path
        for path in list_markdown_files(cases_dir)
        if not any(part in SKIP_DIR_NAMES for part in path.parts)
    ]
    summary = build_incremental_vector_index(
        root=root,
        bucket="cases_vector",
        source_paths=source_paths,
        build_doc_payload=build_case_doc,
        index_output_path=index_output,
        meta_output_path=meta_output,
        model_name=args.model,
        device=args.device,
        batch_size=args.batch_size,
    )
    print(
        f"Built cases vector index: {index_output} "
        f"({summary['row_count']} cases, changed_docs={summary['changed_document_count']}, "
        f"reused_docs={summary['reused_document_count']})"
    )


if __name__ == "__main__":
    main()
