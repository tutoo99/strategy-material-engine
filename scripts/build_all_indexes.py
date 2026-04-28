#!/opt/miniconda3/bin/python3

import argparse
import os
import subprocess
import sys
from pathlib import Path

from _buildmate_lib import assert_project_root

SCRIPTS = [
    ("build_entity_cards.py", False),
    ("build_sources_index.py", True),
    ("build_materials_index.py", True),
    ("build_entities_index.py", True),
    ("build_case_index.py", False),
    ("build_cases_vector_index.py", True),
    ("build_unified_index.py", False),
]


def main() -> None:
    parser = argparse.ArgumentParser(description='一键构建 strategy-material-engine 全部索引')
    parser.add_argument('--root', default='.')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--batch-size', type=int, default=2)
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    scripts_dir = Path(__file__).resolve().parent
    stable_env = os.environ.copy()
    stable_env.setdefault('OMP_NUM_THREADS', '1')
    stable_env.setdefault('MKL_NUM_THREADS', '1')
    stable_env.setdefault('OPENBLAS_NUM_THREADS', '1')
    stable_env.setdefault('VECLIB_MAXIMUM_THREADS', '1')
    for name, uses_encoder in SCRIPTS:
        script = scripts_dir / name
        cmd = [sys.executable, str(script), '--root', str(root)]
        if uses_encoder:
            cmd.extend(['--device', args.device, '--batch-size', str(args.batch_size)])
        result = subprocess.run(cmd, capture_output=True, text=True, env=stable_env)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(f'Index build failed: {name}')
        if result.stdout.strip():
            print(result.stdout.strip())
    print('All indexes built successfully.')


if __name__ == '__main__':
    main()
