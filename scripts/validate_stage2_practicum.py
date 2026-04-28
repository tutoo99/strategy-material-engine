#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _buildmate_lib import read_markdown


REQUIRED_META_FIELDS = [
    "practicum_id",
    "title",
    "training_ground_ref",
    "form_ref",
    "manual_ref",
    "status",
    "required_test_count",
    "completed_test_count",
    "date",
]

REQUIRED_TOP_SECTIONS = [
    "## 测试计划",
    "## 迭代决策",
    "## 阶段一回写候选",
]

FIXED_QUESTIONS = [
    "表单问题看得懂吗",
    "诊断结论你觉得说到点上了吗",
    "行动建议你觉得能直接操作吗",
]

REQUIRED_TEST_FIELDS = [
    "**对象标签：**",
    "**测试前原始内容：**",
    "**测试前原始数据：**",
    "**执行任务：**",
    "**1~2 天后结果变化：**",
    "**是否改善：**",
    "**有效动作：**",
    "**无效动作：**",
    "**新暴露卡点：**",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a stage2 practicum record.")
    parser.add_argument("practicum_file", help="Path to expert_models/practicums/*.md")
    return parser.parse_args()


def parse_test_blocks(body: str) -> list[str]:
    return re.findall(r"^##\s+测试对象\s+\d+.+?(?=^##\s+测试对象\s+\d+|^##\s+迭代决策|\Z)", body, flags=re.DOTALL | re.MULTILINE)


def validate_practicum(path: Path) -> tuple[list[str], list[str]]:
    meta, body = read_markdown(path)
    errors: list[str] = []
    repairs: list[str] = []

    for field in REQUIRED_META_FIELDS:
        value = meta.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"缺少 practicum frontmatter 字段：{field}")

    for section in REQUIRED_TOP_SECTIONS:
        if section not in body:
            errors.append(f"缺少区块：{section}")
            repairs.append(f"补写 {section}")

    for question in FIXED_QUESTIONS:
        if question not in body:
            errors.append(f"缺少固定问题：{question}")
            repairs.append(f"补写固定问题：{question}")

    test_blocks = parse_test_blocks(body)
    required_test_count = int(meta.get("required_test_count", 0) or 0)
    completed_test_count = int(meta.get("completed_test_count", 0) or 0)
    if len(test_blocks) < required_test_count:
        errors.append(f"测试对象数量不足：需要 {required_test_count} 个，当前只有 {len(test_blocks)} 个区块。")
        repairs.append("补齐测试对象 1/2/3 区块。")

    if completed_test_count > required_test_count:
        errors.append("`completed_test_count` 不能大于 `required_test_count`。")
        repairs.append("修正 practicum frontmatter 中的完成数量。")

    for index, block in enumerate(test_blocks, start=1):
        for field in REQUIRED_TEST_FIELDS:
            if field not in block:
                errors.append(f"测试对象 {index} 缺少字段：{field}")
                repairs.append(f"给测试对象 {index} 补上 {field}")
        for question in FIXED_QUESTIONS:
            if question not in block:
                errors.append(f"测试对象 {index} 缺少三问回答：{question}")
                repairs.append(f"给测试对象 {index} 补写三问回答。")

    if "**如果反馈看不懂：**" not in body or "**如果反馈不准：**" not in body:
        errors.append("缺少迭代决策分支。")
        repairs.append("在 `## 迭代决策` 中补写看不懂 / 不准 / 有效 / 无效四类处理。")

    for field in [
        "**是否生成：**",
        "**候选对象：**",
        "**候选原因：**",
        "**是否已经赚到钱：**",
        "**金额 / 结果：**",
        "**下一步：**",
    ]:
        if field not in body:
            errors.append(f"缺少阶段一回写候选字段：{field}")
            repairs.append(f"在 `## 阶段一回写候选` 中补写 {field}")

    return errors, repairs


def main() -> int:
    args = parse_args()
    path = Path(args.practicum_file).resolve()
    errors, repairs = validate_practicum(path)
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
