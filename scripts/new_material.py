#!/opt/miniconda3/bin/python3

import argparse
import re
from pathlib import Path

from _io_safety import atomic_write_text, file_lock
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


def default_ammo_type(material_type: str) -> str:
    return {
        "story": "hook",
        "insight": "dual",
        "method": "substance",
        "data": "substance",
        "quote": "hook",
        "association": "hook",
        "playbook": "substance",
    }.get(material_type, "dual")


def default_strength(material_type: str) -> str:
    return {
        "story": "anecdote",
        "data": "data",
        "quote": "observation",
    }.get(material_type, "observation")


def render_inline_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(render_scalar(value) for value in values) + "]"


def render_scalar(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("title")
    parser.add_argument("--root", default=".")
    parser.add_argument("--type", choices=["story", "insight", "data", "method", "quote", "association", "playbook"], default="story")
    parser.add_argument("--date", default="2026-04-20")
    parser.add_argument("--source", default="待补充")
    parser.add_argument("--source-ref", action="append", default=[])
    parser.add_argument("--channel-fit", action="append", default=[])
    parser.add_argument("--role", default="argument")
    parser.add_argument("--strength")
    parser.add_argument("--ammo-type", choices=["hook", "substance", "dual"])
    parser.add_argument("--quality-score", type=float, default=3.0)
    parser.add_argument("--source-reliability", type=float, default=3.0)
    parser.add_argument(
        "--review-status",
        choices=["draft", "queued_for_repair", "rejected", "reviewed", "approved"],
        default="draft",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Create the material and immediately rebuild the materials index.",
    )
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    file_name = f"{slugify(args.title)}.md"
    output_path = root / "assets/materials" / args.type / file_name

    ammo_default = args.ammo_type or default_ammo_type(args.type)
    strength_default = args.strength or default_strength(args.type)
    channel_fit = args.channel_fit or ["general"]
    source_refs = [str(ref).strip() for ref in args.source_ref if str(ref).strip()]

    body = default_body(args.type)
    content_sha256 = sha256_text(normalize_content(body))
    content = f"""---
type: {args.type}
title: {render_scalar(args.title)}
primary_claim: {render_scalar(args.title)}
claims:
  - {render_scalar(args.title)}
tags: []
ammo_type: {ammo_default}
role: {render_scalar(args.role)}
strength: {render_scalar(strength_default)}
channel_fit: {render_inline_list(channel_fit)}
source: {render_scalar(args.source)}
source_refs: {render_inline_list(source_refs)}
derived_from_case:
source_uid:
duplicate_of:
content_sha256: {content_sha256}
date: {render_scalar(args.date)}
quality_score: {args.quality_score}
use_count: 0
last_used_at:
used_in_articles: []
impact_log: []
source_reliability: {args.source_reliability}
review_status: {render_scalar(args.review_status)}
---

{body}
    """
    with file_lock(root, "ingest"):
        if output_path.exists():
            raise SystemExit(f"File already exists: {output_path}")
        atomic_write_text(output_path, content, encoding="utf-8")
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
