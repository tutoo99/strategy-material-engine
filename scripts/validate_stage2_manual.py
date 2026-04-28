#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _buildmate_lib import read_markdown


REQUIRED_META_FIELDS = [
    "manual_id",
    "title",
    "training_ground_ref",
    "consultation_ref",
    "status",
    "evidence_status",
    "date",
]

REQUIRED_STATION_LABELS = [
    "**检查项：**",
    "**判断方法：**",
    "**动作：**",
    "**参数：**",
    "**资源编号：**",
    "**资源内容：**",
    "**来源病例：**",
    "**病例引用：**",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a stage2 diagnosis manual.")
    parser.add_argument("manual_file", help="Path to expert_models/manuals/*.md")
    return parser.parse_args()


def parse_station_blocks(body: str) -> list[str]:
    return re.findall(r"^##\s+第.+?站.+?(?=^##\s+第.+?站|\Z)", body, flags=re.DOTALL | re.MULTILINE)


def validate_manual(path: Path) -> tuple[list[str], list[str]]:
    meta, body = read_markdown(path)
    errors: list[str] = []
    repairs: list[str] = []

    for field in REQUIRED_META_FIELDS:
        value = meta.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"缺少 manual frontmatter 字段：{field}")

    if "## 资源编号规则" not in body:
        errors.append("缺少“资源编号规则”区块。")
        repairs.append("在手册开头补写 `R-01 / R-02 / R-03` 的编号规则。")

    station_blocks = parse_station_blocks(body)
    if not station_blocks:
        errors.append("缺少检查站点。")
        repairs.append("至少补出 1 个 `## 第X站` 区块。")
        return errors, repairs

    seen_resource_ids: set[str] = set()
    for index, block in enumerate(station_blocks, start=1):
        for label in REQUIRED_STATION_LABELS:
            if label not in block:
                errors.append(f"检查站点 {index} 缺少字段：{label}")
                repairs.append(f"给检查站点 {index} 补上 {label}")

        resource_ids = re.findall(r"`(R-\d{2})`", block)
        if not resource_ids:
            errors.append(f"检查站点 {index} 没有合法资源编号。")
            repairs.append(f"给检查站点 {index} 补写 `R-{index:02d}` 形式的资源编号。")
        for resource_id in resource_ids:
            if resource_id in seen_resource_ids:
                errors.append(f"资源编号重复：{resource_id}")
                repairs.append(f"将重复的资源编号 {resource_id} 改成新的唯一编号。")
            seen_resource_ids.add(resource_id)

        if "`cases/" not in block:
            errors.append(f"检查站点 {index} 没有病例回链。")
            repairs.append(f"给检查站点 {index} 补写来源病例和病例引用。")

    return errors, repairs


def main() -> int:
    args = parse_args()
    path = Path(args.manual_file).resolve()
    errors, repairs = validate_manual(path)
    if not errors:
        print(f"OK: {path}")
        return 0

    print(f"FAILED: {path}")
    for error in errors:
        print(f"- ERROR: {error}")
    for repair in repairs:
        print(f"- REPAIR: {repair}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
