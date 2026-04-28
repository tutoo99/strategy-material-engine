#!/opt/miniconda3/bin/python3
"""Incremental source indexer — append only NEW source chunks to existing faiss index.

Avoids full rebuild. Works around faiss+torch 2.9.1 segfault in Hermes sandbox
by encoding with torch first, saving to temp file, freeing torch, then loading faiss.

Usage:
    /opt/miniconda3/bin/python3 scripts/incremental_sources_index.py --root .
"""

import argparse
import gc
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

MODEL_MAX_LENGTH = 512
DEFAULT_MODEL = "BAAI/bge-large-zh-v1.5"


def mean_pool(last_hidden_state, attention_mask):
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    return (last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def chunk_body(body: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    return blocks


def load_existing_paths(meta_path: Path) -> set[str]:
    if not meta_path.exists():
        return set()
    paths = set()
    with open(meta_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                paths.add(json.loads(line).get("path", ""))
    return paths


def find_new_files(root: Path, existing_paths: set[str]) -> list[Path]:
    sources_dir = root / "sources"
    md_files = sorted(sources_dir.rglob("*.md"))
    return [
        f for f in md_files
        if f.is_file()
        and not f.name.startswith("_")
        and str(f.relative_to(root)) not in existing_paths
    ]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text.strip()
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text.strip()
    import yaml
    raw_meta = parts[0][4:]
    body = parts[1].strip()
    meta = yaml.safe_load(raw_meta) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def main():
    parser = argparse.ArgumentParser(description="Incremental source indexer")
    parser.add_argument("--root", default=".")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="Show new files without encoding")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    meta_path = root / "index/sources/source_chunks_meta.jsonl"
    faiss_path = root / "index/sources/source_chunks.faiss"
    tmp_vec_path = Path("/tmp/_sme_incremental_vectors.npy")

    existing_paths = load_existing_paths(meta_path)
    new_files = find_new_files(root, existing_paths)

    print(f"Existing sources: {len(existing_paths)}, New files: {len(new_files)}")

    if not new_files:
        print("Nothing to do.")
        return

    for f in new_files:
        print(f"  + {f.relative_to(root)}")

    if args.dry_run:
        return

    if not faiss_path.exists():
        print("ERROR: No existing faiss index. Run full build first.")
        sys.exit(1)

    # --- Phase 1: encode with torch (no faiss in memory) ---
    print(f"\nLoading model {args.model}...")
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model, use_safetensors=False)
    model.eval()
    print("Model loaded.")

    new_chunks = []
    for f in new_files:
        text = f.read_text(encoding="utf-8")
        _, body = parse_frontmatter(text)
        blocks = chunk_body(body)
        for i, block in enumerate(blocks):
            new_chunks.append({
                "path": str(f.relative_to(root)),
                "chunk_index": i,
                "content": block,
            })

    print(f"Encoding {len(new_chunks)} new chunks (batch_size={args.batch_size})...")
    vectors = []
    for start in range(0, len(new_chunks), args.batch_size):
        bt = [c["content"] for c in new_chunks[start:start + args.batch_size]]
        tokens = tok(bt, padding=True, truncation=True, max_length=MODEL_MAX_LENGTH, return_tensors="pt")
        with torch.no_grad():
            out = model(**tokens)
            pooled = mean_pool(out.last_hidden_state, tokens["attention_mask"])
            emb = F.normalize(pooled, p=2, dim=1)
            vectors.append(emb.numpy().astype("float32"))

    vectors = np.vstack(vectors)
    print(f"Encoded {vectors.shape[0]} vectors, dim={vectors.shape[1]}")

    # Save to temp file
    np.save(str(tmp_vec_path), vectors)
    print("Vectors saved to temp file.")

    # Free torch completely
    del model, tok, vectors
    gc.collect()
    print("Torch freed.")

    # --- Phase 2: load faiss and append ---
    import faiss
    index = faiss.read_index(str(faiss_path))
    print(f"Faiss loaded: {index.ntotal} existing vectors")

    new_vecs = np.load(str(tmp_vec_path))
    index.add(new_vecs)
    faiss.write_index(index, str(faiss_path))
    print(f"Faiss updated: {index.ntotal} vectors")

    # Cleanup temp
    tmp_vec_path.unlink(missing_ok=True)

    # Append meta
    with open(meta_path, "a", encoding="utf-8") as f:
        for chunk in new_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"Meta appended: {len(new_chunks)} chunks")
    print("Done!")


if __name__ == "__main__":
    main()
