#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from _buildmate_lib import assert_project_root
from _io_safety import file_lock
from _index_state import KNOWN_BUCKETS, clear_dirty, dirty_buckets

DEPENDENCIES = {
    "sources": ["sources", "entities", "unified"],
    "materials": ["materials", "unified"],
    "cases": ["cases", "unified"],
    "entities": ["entities", "unified"],
    "unified": ["unified"],
}

FLUSH_ORDER = ["sources", "materials", "cases", "entities", "unified"]
SCRIPT_GROUPS = {
    "sources": [("build_sources_index.py", True)],
    "materials": [("build_materials_index.py", True)],
    "cases": [("build_case_index.py", False), ("build_cases_vector_index.py", True)],
    "entities": [("build_entities_index.py", True)],
    "unified": [("build_unified_index.py", False)],
}


def expand_buckets(requested: list[str]) -> list[str]:
    expanded: set[str] = set()
    for bucket in requested:
        expanded.update(DEPENDENCIES.get(bucket, [bucket]))
    return [bucket for bucket in FLUSH_ORDER if bucket in expanded]


def run_script(
    *,
    root: Path,
    scripts_dir: Path,
    script_name: str,
    uses_encoder: bool,
    device: str,
    batch_size: int,
    stable_env: dict[str, str],
) -> None:
    script = scripts_dir / script_name
    cmd = [sys.executable, str(script), "--root", str(root)]
    if uses_encoder:
        cmd.extend(["--device", device, "--batch-size", str(batch_size)])
    result = subprocess.run(cmd, capture_output=True, text=True, env=stable_env)
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        raise SystemExit(f"Index flush failed: {script_name}")
    if result.stdout.strip():
        print(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Flush dirty index buckets with dependency-aware ordering.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--bucket", action="append", choices=list(KNOWN_BUCKETS), default=[])
    parser.add_argument("--all", action="store_true", help="Flush all buckets regardless of dirty state.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned buckets without executing builders.")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    requested = list(args.bucket)
    if args.all:
        requested = list(KNOWN_BUCKETS)
    elif not requested:
        requested = dirty_buckets(root)

    buckets = expand_buckets(requested)
    if not buckets:
        print("No dirty index buckets to flush.")
        return

    print(f"Flushing buckets: {', '.join(buckets)}")
    if args.dry_run:
        return

    with file_lock(root, "index"):
        scripts_dir = Path(__file__).resolve().parent
        stable_env = os.environ.copy()
        stable_env.setdefault("OMP_NUM_THREADS", "1")
        stable_env.setdefault("MKL_NUM_THREADS", "1")
        stable_env.setdefault("OPENBLAS_NUM_THREADS", "1")
        stable_env.setdefault("VECLIB_MAXIMUM_THREADS", "1")

        executed_buckets: list[str] = []
        needs_entity_cards = "sources" in buckets
        if needs_entity_cards:
            run_script(
                root=root,
                scripts_dir=scripts_dir,
                script_name="build_entity_cards.py",
                uses_encoder=False,
                device=args.device,
                batch_size=args.batch_size,
                stable_env=stable_env,
            )
        for bucket in buckets:
            for script_name, uses_encoder in SCRIPT_GROUPS.get(bucket, []):
                run_script(
                    root=root,
                    scripts_dir=scripts_dir,
                    script_name=script_name,
                    uses_encoder=uses_encoder,
                    device=args.device,
                    batch_size=args.batch_size,
                    stable_env=stable_env,
                )
            executed_buckets.append(bucket)

        clear_dirty(root, *executed_buckets)
    print("Dirty index buckets flushed successfully.")


if __name__ == "__main__":
    main()
