#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _material_lib import build_faiss_index, write_faiss_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a FAISS index from a numpy vectors file.")
    parser.add_argument("--vectors", required=True, help="Path to .npy float32 vectors file")
    parser.add_argument("--output", required=True, help="Path to output .faiss index")
    args = parser.parse_args()

    vectors = np.load(Path(args.vectors), allow_pickle=False)
    index = build_faiss_index(np.asarray(vectors, dtype="float32"))
    write_faiss_index(Path(args.output), index)
    print(f"Wrote FAISS index: {args.output} ({index.ntotal} vectors)")


if __name__ == "__main__":
    main()
