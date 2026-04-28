#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from _buildmate_lib import list_markdown_files, read_jsonl, read_markdown


REQUIRED_SESSION_META_FIELDS = [
    "session_id",
    "title",
    "router_ref",
    "input_goal",
    "normalized_goal",
    "user_type",
    "platform",
    "domain",
    "constraints",
    "status",
    "evidence_status",
    "evidence_case_count",
    "route_confidence",
    "progress_protocol",
    "progress_event_count",
    "selected_strategy_refs",
    "selected_case_refs",
    "selected_resource_refs",
    "date",
]

REQUIRED_SESSION_SECTIONS = [
    "用户原始目标",
    "收敛后的标准目标",
    "用户情境卡",
    "图谱召回记录",
    "路由判断记录",
    "证据状态",
    "方案包组装逻辑",
    "Markdown 方案包",
    "Structured Solution Package",
    "风险提示",
    "7天执行反馈指标",
    "进度播报记录",
]

AUTONOMOUS_REQUIRED_SECTION = "自主学习记录"

REQUIRED_PROGRESS_LABELS = [
    "时间",
    "触发类型",
    "当前阶段",
    "当前步骤",
    "当前动作",
    "下一步需要你提供",
    "预计剩余时间",
]

REQUIRED_READY_STAGE_MARKERS = [
    "阶段三（1/7）目标收集",
    "阶段三（2/7）情境收敛",
    "阶段三（3/7）图谱召回",
    "阶段三（4/7）路由判断",
    "阶段三（5/7）方案包组装",
    "阶段三（6/7）校验收口",
    "阶段三（7/7）交付执行",
]


def extract_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^##\s+(.+)$", body, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[title] = body[start:end].strip()
    return sections


def normalize_heading(title: str) -> str:
    return re.sub(r"\s+", "", title.strip())


def extract_solution_package(body: str) -> dict:
    match = re.search(
        r"##\s+Structured Solution Package\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1).strip()) or {}
    if not isinstance(payload, dict):
        return {}
    package = payload.get("solution_package", {})
    return package if isinstance(package, dict) else {}


def parse_progress_blocks(body: str) -> list[str]:
    return re.findall(r"^###\s+进度播报\s+\d+.+?(?=^###\s+进度播报\s+\d+|\Z)", body, flags=re.DOTALL | re.MULTILINE)


def extract_bold_value(block: str, label: str) -> str:
    match = re.search(rf"\*\*{re.escape(label)}[：:]?\*\*\s*(.+)", block)
    return match.group(1).strip() if match else ""


def load_strategy_labels(root: Path) -> set[str]:
    path = root / "strategy_models/routes/strategy_profiles.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    strategies = payload.get("strategies", [])
    return {str(item.get("label", "")).strip() for item in strategies if isinstance(item, dict) and str(item.get("label", "")).strip()}


def load_resource_catalog(root: Path) -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    resources_root = root / "strategy_models/resources"
    for path in list_markdown_files(resources_root):
        meta, _body = read_markdown(path)
        resource_id = str(meta.get("resource_id", "")).strip()
        if resource_id:
            catalog[resource_id] = meta
    return catalog


def load_platform_resource_refs(root: Path) -> set[str]:
    rows = read_jsonl(root / "index/stage3/resource_nodes.jsonl")
    return {str(row.get("label", "")).strip() for row in rows if str(row.get("label", "")).strip()}


def load_case_status_map(root: Path) -> dict[str, str]:
    status_map: dict[str, str] = {}
    cases_dir = root / "assets/cases"
    for path in list_markdown_files(cases_dir):
        meta, _body = read_markdown(path)
        case_ref = str(path.relative_to(root))
        status_map[case_ref] = str(meta.get("status", "")).strip()
    return status_map


def validate_stage3_session(path: Path) -> tuple[list[str], list[str], list[str]]:
    root = path.resolve().parent.parent.parent
    meta, body = read_markdown(path)
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    solution_package = extract_solution_package(body)
    strategy_labels = load_strategy_labels(root)
    resource_catalog = load_resource_catalog(root)
    platform_resource_refs = load_platform_resource_refs(root)
    case_status_map = load_case_status_map(root)

    errors: list[str] = []
    warnings: list[str] = []
    repairs: list[str] = []

    for field in REQUIRED_SESSION_META_FIELDS:
        value = meta.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"缺少阶段三 session frontmatter 字段：{field}")

    for section in REQUIRED_SESSION_SECTIONS:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    evidence_status = str(meta.get("evidence_status", "")).strip()
    if evidence_status not in {"formal", "bootstrap"}:
        errors.append("`evidence_status` 必须是 `formal` 或 `bootstrap`。")

    route_confidence = str(meta.get("route_confidence", "")).strip()
    if route_confidence not in {"low", "medium", "high"}:
        errors.append("`route_confidence` 必须是 `low / medium / high`。")

    autonomous_mode = meta.get("autonomous_mode")
    if autonomous_mode is not None and not isinstance(autonomous_mode, bool):
        errors.append("`autonomous_mode` 必须是布尔值。")
        autonomous_mode = False
    if autonomous_mode is True:
        if normalize_heading(AUTONOMOUS_REQUIRED_SECTION) not in sections:
            errors.append("自治模式会话必须包含 `自主学习记录` 区块。")
        audit_ref = str(meta.get("audit_ref", "")).strip()
        if not audit_ref:
            errors.append("自治模式会话必须填写 `audit_ref`。")
        elif not (root / audit_ref).exists():
            errors.append(f"`audit_ref` 指向的文件不存在：{audit_ref}")
        generation_mode = str(meta.get("generation_mode", "")).strip()
        if generation_mode != "synthesized_bootstrap":
            errors.append("自治模式会话的 `generation_mode` 必须是 `synthesized_bootstrap`。")
        gap_type = str(meta.get("gap_type", "")).strip()
        if gap_type not in {"stage2_translation_gap", "stage3_route_gap", "stage1_evidence_gap", "mixed"}:
            errors.append("自治模式会话的 `gap_type` 不在允许范围内。")

    if str(meta.get("progress_protocol", "")).strip() != "hybrid-3min":
        errors.append("`progress_protocol` 必须固定为 `hybrid-3min`。")

    selected_strategy_refs = meta.get("selected_strategy_refs", [])
    if not isinstance(selected_strategy_refs, list) or not selected_strategy_refs:
        errors.append("`selected_strategy_refs` 必须是非空列表。")
        selected_strategy_refs = []
    else:
        for item in selected_strategy_refs:
            label = str(item).strip()
            if label not in strategy_labels:
                errors.append(f"未识别的策略引用：{label}")

    selected_case_refs = meta.get("selected_case_refs", [])
    if not isinstance(selected_case_refs, list) or not selected_case_refs:
        errors.append("`selected_case_refs` 必须是非空列表。")
        selected_case_refs = []
    else:
        for case_ref in selected_case_refs:
            normalized = str(case_ref).strip()
            if normalized not in case_status_map:
                errors.append(f"未找到案例引用：{normalized}")

    selected_resource_refs = meta.get("selected_resource_refs", [])
    if not isinstance(selected_resource_refs, list) or not selected_resource_refs:
        errors.append("`selected_resource_refs` 必须是非空列表。")
        selected_resource_refs = []
    else:
        for resource_id in selected_resource_refs:
            normalized = str(resource_id).strip()
            if normalized not in resource_catalog:
                errors.append(f"未找到资源引用：{normalized}")

    try:
        evidence_case_count = int(meta.get("evidence_case_count", 0))
    except (TypeError, ValueError):
        evidence_case_count = -1
        errors.append("`evidence_case_count` 必须是整数。")

    if evidence_case_count != len(selected_case_refs):
        warnings.append("`evidence_case_count` 与 `selected_case_refs` 数量不一致。")
        repairs.append("将 `evidence_case_count` 修正为 `selected_case_refs` 的真实数量。")

    if solution_package:
        primary_strategy = str(solution_package.get("primary_strategy", "")).strip()
        if not primary_strategy:
            errors.append("`solution_package.primary_strategy` 不能为空。")
        elif primary_strategy not in selected_strategy_refs:
            errors.append("`solution_package.primary_strategy` 必须包含在 `selected_strategy_refs` 中。")

        secondary_strategies = solution_package.get("secondary_strategies", [])
        if not isinstance(secondary_strategies, list):
            errors.append("`solution_package.secondary_strategies` 必须是列表。")
            secondary_strategies = []
        else:
            for item in secondary_strategies:
                label = str(item).strip()
                if label and label not in selected_strategy_refs:
                    errors.append(f"`secondary_strategies` 中存在未选中的策略：{label}")

        case_refs = solution_package.get("case_refs", [])
        if not isinstance(case_refs, list) or not case_refs:
            errors.append("`solution_package.case_refs` 必须是非空列表。")
            case_refs = []
        else:
            for case_ref in case_refs:
                normalized = str(case_ref).strip()
                if normalized not in selected_case_refs:
                    errors.append(f"`solution_package.case_refs` 引用了未选中案例：{normalized}")

        resource_bundle = solution_package.get("resource_bundle", {})
        if not isinstance(resource_bundle, dict):
            errors.append("`solution_package.resource_bundle` 必须是对象。")
            resource_bundle = {}

        for key in ["action_refs", "template_refs", "tool_refs"]:
            refs = resource_bundle.get(key, [])
            if not isinstance(refs, list):
                errors.append(f"`resource_bundle.{key}` 必须是列表。")
                continue
            for resource_id in refs:
                normalized = str(resource_id).strip()
                if normalized not in resource_catalog:
                    errors.append(f"`resource_bundle.{key}` 引用了未登记资源：{normalized}")

        platform_refs = resource_bundle.get("platform_resource_refs", [])
        if not isinstance(platform_refs, list):
            errors.append("`resource_bundle.platform_resource_refs` 必须是列表。")
            platform_refs = []
        else:
            for item in platform_refs:
                normalized = str(item).strip()
                if normalized not in platform_resource_refs:
                    errors.append(f"`platform_resource_refs` 引用了未知标准资源词：{normalized}")

        tasks = solution_package.get("tasks", [])
        if not isinstance(tasks, list) or not tasks:
            errors.append("`solution_package.tasks` 必须是非空列表。")
            tasks = []
        else:
            for index, task in enumerate(tasks, start=1):
                if not isinstance(task, dict):
                    errors.append(f"任务 {index} 必须是对象。")
                    continue
                strategy_ref = str(task.get("strategy_ref", "")).strip()
                if strategy_ref not in selected_strategy_refs:
                    errors.append(f"任务 {index} 的 `strategy_ref` 未被选中：{strategy_ref}")
                task_case_refs = task.get("case_refs", [])
                if not isinstance(task_case_refs, list) or not task_case_refs:
                    errors.append(f"任务 {index} 缺少 `case_refs`。")
                else:
                    for case_ref in task_case_refs:
                        normalized = str(case_ref).strip()
                        if normalized not in selected_case_refs:
                            errors.append(f"任务 {index} 引用了未选中案例：{normalized}")
                task_resource_refs = task.get("resource_refs", [])
                if not isinstance(task_resource_refs, list) or not task_resource_refs:
                    errors.append(f"任务 {index} 缺少 `resource_refs`。")
                else:
                    for resource_id in task_resource_refs:
                        normalized = str(resource_id).strip()
                        if normalized not in resource_catalog:
                            errors.append(f"任务 {index} 引用了未登记资源：{normalized}")
                if not str(task.get("success_check", "")).strip():
                    errors.append(f"任务 {index} 缺少 `success_check`。")
    else:
        errors.append("缺少有效的 `Structured Solution Package` YAML 区块。")

    selected_approved_cases = [case_ref for case_ref in selected_case_refs if case_status_map.get(str(case_ref).strip()) == "approved"]
    if evidence_status == "formal" and not selected_approved_cases:
        errors.append("`evidence_status` 为 `formal` 时，必须至少包含 1 个 approved 案例。")
    if route_confidence == "high" and evidence_status != "formal":
        errors.append("`route_confidence` 为 `high` 时，`evidence_status` 必须是 `formal`。")

    progress_blocks = parse_progress_blocks(body)
    if not progress_blocks:
        errors.append("缺少有效的“进度播报记录”条目。")
    else:
        for index, block in enumerate(progress_blocks, start=1):
            for label in REQUIRED_PROGRESS_LABELS:
                if not extract_bold_value(block, label):
                    errors.append(f"进度播报 {index} 缺少字段：{label}")

        try:
            progress_event_count = int(meta.get("progress_event_count", 0))
        except (TypeError, ValueError):
            errors.append("`progress_event_count` 必须是整数。")
        else:
            if progress_event_count != len(progress_blocks):
                warnings.append("`progress_event_count` 与实际进度播报条目数量不一致。")
                repairs.append("将 `progress_event_count` 修正为实际进度播报条目数量。")

        if meta.get("status") == "ready":
            progress_text = "\n\n".join(progress_blocks)
            for marker in REQUIRED_READY_STAGE_MARKERS:
                if marker not in progress_text:
                    errors.append(f"已交付会话缺少关键进度节点：{marker}")

    return errors, warnings, repairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Buildmate stage-3 strategy session file.")
    parser.add_argument("session_file")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    session_path = Path(args.session_file).resolve()
    errors, warnings, repairs = validate_stage3_session(session_path)

    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for repair in repairs:
        print(f"SELF-REPAIR: {repair}")

    if not errors and not warnings:
        print("OK: stage3 session passed validation.")
        return
    if errors or (args.strict and warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
