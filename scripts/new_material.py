#!/opt/miniconda3/bin/python3

import argparse
import re
from pathlib import Path

from _index_state import mark_dirty
from _buildmate_lib import assert_project_root
from _dedupe_lib import normalize_content, sha256_text


def slugify(text: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", text).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "untitled"


def default_body(material_type: str) -> str:
    if material_type == "story":
        return "这里写可直接嵌入文章的故事素材。"
    if material_type == "insight":
        return "这里写一条完整洞见。"
    if material_type == "data":
        return "这里写数据证据与解释。"
    if material_type == "quote":
        return "这里写适合直接引用的短句或口语化表达。"
    if material_type == "association":
        return "这里写跨领域联想或类比。"
    if material_type == "playbook":
        return "这里写一组可直接执行的步骤。"
    return "这里写方法、步骤或SOP。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("title")
    parser.add_argument("--root", default=".")
    parser.add_argument("--type", choices=["story", "insight", "data", "method", "quote", "association", "playbook"], default="story")
    parser.add_argument("--date", default="2026-04-20")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Create the material and immediately rebuild the materials index.",
    )
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    file_name = f"{slugify(args.title)}.md"
    output_path = root / "assets/materials" / args.type / file_name

    # 按类型给默认ammo_type
    ammo_default = {
        "story": "hook",
        "insight": "dual",
        "method": "substance",
        "data": "substance",
        "quote": "hook",
        "association": "hook",
        "playbook": "substance",
    }.get(args.type, "dual")

    if output_path.exists():
        raise SystemExit(f"File already exists: {output_path}")

    body = default_body(args.type)
    content_sha256 = sha256_text(normalize_content(body))
    content = f"""---
type: {args.type}
primary_claim: {args.title}
claims:
  - {args.title}
tags: []
ammo_type: {ammo_default}
role: argument
strength: observation
channel_fit: [general]
source: 待补充
content_sha256: {content_sha256}
date: {args.date}
quality_score: 3.0
use_count: 0
last_used_at:
used_in_articles: []
impact_log: []
source_reliability: 3.0
review_status: draft
---

{body}
    """
    output_path.write_text(content, encoding="utf-8")
    mark_dirty(root, "materials", reason="new_material")
    print(f"Created material draft: {output_path}")

    if not args.rebuild:
        print(
            f"Materials index not rebuilt. Run {build_script_hint(root)} when your batch is ready,"
        )
        print("or pass --rebuild to make this material searchable immediately.")
        return

    # 显式触发索引重建，让新素材立即可搜索
    import subprocess, sys
    build_script = Path(__file__).parent / "flush_indexes.py"
    result = subprocess.run(
        [sys.executable, str(build_script), "--root", str(root), "--bucket", "materials"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode == 0:
        print(f"Index rebuilt: {result.stdout.strip()}")
    else:
        print(f"Warning: index build failed — run manually: {build_script} --root {root}")
        if result.stderr:
            print(f"  {result.stderr.strip()}")


def build_script_hint(root: Path) -> str:
    return f"/opt/miniconda3/bin/python3 scripts/flush_indexes.py --root {root} --bucket materials"


if __name__ == "__main__":
    main()
