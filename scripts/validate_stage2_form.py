#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _buildmate_lib import read_markdown


REQUIRED_META_FIELDS = [
    "form_id",
    "title",
    "training_ground_ref",
    "manual_ref",
    "status",
    "evidence_status",
    "date",
]

REQUIRED_TOP_LEVEL_SECTIONS = [
    "## 症状采集",
    "## 诊断报告输出格式",
    "## 您的专属优化方案",
]

REQUIRED_TASK_FIELDS = [
    "**动作：**",
    "**参数：**",
    "**参考案例：**",
    "**SOP / 资源：**",
    "**预计耗时：**",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a stage2 questionnaire form.")
    parser.add_argument("form_file", help="Path to expert_models/forms/*.md")
    return parser.parse_args()


def parse_task_blocks(body: str) -> list[str]:
    return re.findall(r"^###\s+任务.+?(?=^###\s+任务|\Z)", body, flags=re.DOTALL | re.MULTILINE)


def validate_form(path: Path) -> tuple[list[str], list[str]]:
    meta, body = read_markdown(path)
    errors: list[str] = []
    repairs: list[str] = []

    for field in REQUIRED_META_FIELDS:
        value = meta.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"缺少 form frontmatter 字段：{field}")

    for section in REQUIRED_TOP_LEVEL_SECTIONS:
        if section not in body:
            errors.append(f"缺少区块：{section}")
            repairs.append(f"补写 {section}")

    if "**诊断结论**：" not in body:
        errors.append("缺少 `诊断结论`。")
        repairs.append("在诊断报告部分补写 `**诊断结论**：...`")

    if "✅ 请按顺序执行以下动作" not in body:
        errors.append("缺少按顺序执行的动作提示。")
        repairs.append("补写 `**✅ 请按顺序执行以下动作（预计总耗时：...）**`")

    task_blocks = parse_task_blocks(body)
    if len(task_blocks) < 2:
        errors.append("任务数量不足，至少需要 2 个任务。")
        repairs.append("至少补出 `任务一` 和 `任务二`。")

    for index, block in enumerate(task_blocks, start=1):
        for label in REQUIRED_TASK_FIELDS:
            if label not in block:
                errors.append(f"任务 {index} 缺少字段：{label}")
                repairs.append(f"给任务 {index} 补上 {label}")
        if "`cases/" not in block:
            errors.append(f"任务 {index} 没有参考案例回链。")
            repairs.append(f"给任务 {index} 补写 `cases/...` 参考案例。")

    return errors, repairs


def main() -> int:
    args = parse_args()
    path = Path(args.form_file).resolve()
    errors, repairs = validate_form(path)
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
