#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _buildmate_lib import assert_project_root, has_case_structure, list_markdown_files, read_markdown
from auto_repair_case import auto_repair_case
from extract_case import extract_case
from register_case import register_case
from validate_case import split_case_errors, validate_case


def emit_progress(stage: str, action: str, next_step: str, eta: str) -> None:
    print(f"当前阶段：{stage}")
    print(f"当前动作：{action}")
    print(f"下一步：{next_step}")
    print(f"预计剩余时间：{eta}")
    print("")


def build_delivery_summary(
    input_type: str,
    case_path: Path,
    draft_path: Path | None,
    warnings: list[str],
    repair_actions: list[str],
    indexed_count: int,
) -> str:
    lines = [
        "当前阶段：阶段一（完成）",
        "当前动作：交付阶段一结果摘要，不默认展开完整拆解稿",
        "交付方式：文件路径 + 简短摘要 + 校验/入库结果",
        f"输入类型：{input_type}",
    ]
    if draft_path:
        lines.append(f"草稿文件：{draft_path}")
    lines.append(f"案例文件：{case_path}")
    lines.append("校验结果：通过")
    lines.append(f"自动修复次数：{len(repair_actions)}")
    if repair_actions:
        for index, action in enumerate(repair_actions, start=1):
            lines.append(f"自动修复 {index}：{action}")
    lines.append(f"索引结果：已重建，当前收录 {indexed_count} 个案例")
    if warnings:
        lines.append("提醒：存在以下 warning，已继续入库")
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("提醒：无 warning")
    lines.append("下一步：如需查看全文，再打开对应文件；默认不在对话里粘贴整稿")
    return "\n".join(lines)


def detect_input_type(input_path: Path) -> str:
    _meta, body = read_markdown(input_path)
    return "case" if has_case_structure(body) else "source"


def derive_source_path(input_path: Path, root: Path, explicit_source_path: str) -> str:
    if explicit_source_path.strip():
        return explicit_source_path.strip()
    if input_path.is_relative_to(root):
        return str(input_path.relative_to(root))
    return str(input_path)


def count_registered_cases(root: Path) -> int:
    cases_dir = root / "assets/cases"
    skip_dir_names = {"imported", "case_drafts", "drafts"}
    return sum(
        1
        for path in list_markdown_files(cases_dir)
        if not any(part in skip_dir_names for part in path.parts)
    )


def flush_case_indexes(root: Path) -> None:
    flush_script = Path(__file__).resolve().parent / "flush_indexes.py"
    result = subprocess.run(
        [sys.executable, str(flush_script), "--root", str(root), "--bucket", "cases"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        raise SystemExit("Case index flush failed.")


def validate_with_auto_repair(case_path: Path) -> tuple[list[str], list[str], list[str]]:
    errors, warnings = validate_case(case_path)
    repair_actions: list[str] = []

    auto_repairable, blocking = split_case_errors(errors)
    if auto_repairable:
        changes, changed = auto_repair_case(case_path, write=True)
        if changed:
            repair_actions.extend(changes)
        errors, warnings = validate_case(case_path)
        auto_repairable, blocking = split_case_errors(errors)

    return blocking + auto_repairable, warnings, repair_actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Buildmate stage-1 pipeline in one serial flow.")
    parser.add_argument("input_file")
    parser.add_argument("--root", default=".")
    parser.add_argument("--input-type", choices=["auto", "source", "case"], default="auto")
    parser.add_argument("--draft-output", default="")
    parser.add_argument("--case-output", default="")
    parser.add_argument("--source-path", default="")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    input_path = Path(args.input_file).resolve()
    input_type = args.input_type if args.input_type != "auto" else detect_input_type(input_path)

    emit_progress(
        stage="阶段一（1/4）输入判别",
        action=f"判断输入属于 `{input_type}` 类型，并准备进入自动串行流程",
        next_step="进入六步拆解 / 结构化稿准备",
        eta="约 1 分钟内",
    )

    working_case_path = input_path
    created_draft_path: Path | None = None

    emit_progress(
        stage="阶段一（2/4）六步拆解",
        action="准备结构化案例稿，并执行第六步格式自检",
        next_step="进入质量校验",
        eta="约 3 分钟内",
    )
    if input_type == "source":
        draft_output = Path(args.draft_output).resolve() if args.draft_output else None
        created_draft_path = extract_case(
            source_path=input_path,
            root=root,
            output_path=draft_output,
            overwrite=args.overwrite,
        )
        working_case_path = created_draft_path

    emit_progress(
        stage="阶段一（3/4）质量校验",
        action="运行 validate_case，并对白名单格式错误先自动修复再复检",
        next_step="校验通过后直接注册入库",
        eta="约 3 分钟内",
    )
    errors, warnings, repair_actions = validate_with_auto_repair(working_case_path)
    if errors:
        print("ERROR: stage-1 pipeline stopped because validation still failed after auto-repair.")
        for error in errors:
            print(f"ERROR: {error}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        sys.exit(1)

    emit_progress(
        stage="阶段一（4/4）注册入库",
        action="注册 case 并重建索引，不等待额外确认",
        next_step="输出结果文件路径与摘要",
        eta="约 1 分钟内",
    )
    case_output = Path(args.case_output).resolve() if args.case_output else None
    registered_path = register_case(
        input_path=working_case_path,
        root=root,
        output_path=case_output,
        source_path=derive_source_path(input_path=input_path, root=root, explicit_source_path=args.source_path),
        overwrite=args.overwrite,
        skip_preflight=False,
    )
    flush_case_indexes(root=root)
    indexed_count = count_registered_cases(root)

    print(
        build_delivery_summary(
            input_type=input_type,
            case_path=registered_path,
            draft_path=created_draft_path,
            warnings=warnings,
            repair_actions=repair_actions,
            indexed_count=indexed_count,
        )
    )


if __name__ == "__main__":
    main()
