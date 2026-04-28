#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from _buildmate_lib import read_markdown


REQUIRED_SESSION_META_FIELDS = [
    "session_id",
    "title",
    "furnace_ref",
    "input_symptom",
    "platform",
    "status",
    "evidence_status",
    "evidence_case_count",
    "evidence_gap",
    "progress_protocol",
    "retrieved_case_refs",
    "date",
]

REQUIRED_SESSION_SECTIONS = [
    "用户原始问题",
    "澄清后的标准靶子",
    "熔炉内部召回记录",
    "证据状态",
    "熔炉内部组装逻辑",
    "自修正动作",
    "阶段一补库动作",
    "Markdown工单",
    "Structured Work Order",
    "进度播报记录",
    "用户反馈",
    "是否具备回写资格",
]

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
    "阶段二（1/6）问题收集",
    "阶段二（2/6）靶子澄清",
    "阶段二（3/6）病例召回",
    "阶段二（4/6）工单组装",
    "阶段二（5/6）校验收口",
    "阶段二（6/6）交付执行",
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


def extract_work_order_yaml(body: str) -> dict:
    match = re.search(
        r"##\s+Structured Work Order\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    raw = match.group(1).strip()
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        return {}
    return data.get("work_order", {}) if isinstance(data.get("work_order", {}), dict) else {}


def parse_checkpoint_blocks(body: str) -> list[str]:
    return re.findall(r"^###\s+检查站点.+?(?=^###\s+检查站点|^##\s+Markdown工单|\Z)", body, flags=re.DOTALL | re.MULTILINE)


def parse_markdown_tasks(body: str) -> list[str]:
    return re.findall(r"^###\s+任务.+?(?=^###\s+任务|^##\s+Structured Work Order|\Z)", body, flags=re.DOTALL | re.MULTILINE)


def block_has_case_ref(block: str, retrieved_case_refs: set[str]) -> bool:
    return any(case_ref in block for case_ref in retrieved_case_refs)


def parse_progress_blocks(body: str) -> list[str]:
    return re.findall(r"^###\s+进度播报\s+\d+.+?(?=^###\s+进度播报\s+\d+|^##\s+用户反馈|\Z)", body, flags=re.DOTALL | re.MULTILINE)


def extract_bold_value(block: str, label: str) -> str:
    match = re.search(rf"\*\*{re.escape(label)}[：:]?\*\*\s*(.+)", block)
    if not match:
        match = re.search(rf"\*\*{re.escape(label)}\*\*[：:]\s*(.+)", block)
    return match.group(1).strip() if match else ""


def validate_session(path: Path) -> tuple[list[str], list[str], list[str]]:
    meta, body = read_markdown(path)
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    work_order = extract_work_order_yaml(body)

    errors: list[str] = []
    warnings: list[str] = []
    repairs: list[str] = []

    for field in REQUIRED_SESSION_META_FIELDS:
        value = meta.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"缺少 session frontmatter 字段：{field}")

    for section in REQUIRED_SESSION_SECTIONS:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    evidence_status = str(meta.get("evidence_status", "")).strip()
    if evidence_status not in {"formal", "bootstrap"}:
        errors.append("`evidence_status` 必须是 `formal` 或 `bootstrap`。")

    progress_protocol = str(meta.get("progress_protocol", "")).strip()
    if progress_protocol != "hybrid-3min":
        errors.append("`progress_protocol` 必须固定为 `hybrid-3min`。")

    try:
        evidence_case_count = int(meta.get("evidence_case_count", 0))
    except (TypeError, ValueError):
        evidence_case_count = -1
        errors.append("`evidence_case_count` 必须是整数。")

    retrieved_case_refs = meta.get("retrieved_case_refs", [])
    if not isinstance(retrieved_case_refs, list):
        errors.append("`retrieved_case_refs` 必须是列表。")
        retrieved_case_refs = []
    retrieved_case_ref_set = {str(item).strip() for item in retrieved_case_refs if str(item).strip()}

    if evidence_case_count != len(retrieved_case_ref_set):
        warnings.append("`evidence_case_count` 与 `retrieved_case_refs` 数量不一致。")

    self_repair = work_order.get("self_repair", {})
    stage1_replenishment = work_order.get("stage1_replenishment", {})
    tasks = work_order.get("tasks", [])
    if not isinstance(tasks, list):
        errors.append("`work_order.tasks` 必须是列表。")
        tasks = []

    if not isinstance(self_repair, dict):
        errors.append("`work_order.self_repair` 必须是对象。")
        self_repair = {}
    if not isinstance(stage1_replenishment, dict):
        errors.append("`work_order.stage1_replenishment` 必须是对象。")
        stage1_replenishment = {}

    if work_order:
        work_order_evidence_status = str(work_order.get("evidence_status", "")).strip()
        if work_order_evidence_status and work_order_evidence_status != evidence_status:
            errors.append("frontmatter 与 `work_order.evidence_status` 不一致。")
            repairs.append("将 YAML 中的 `evidence_status` 与 frontmatter 保持一致。")

        try:
            work_order_case_count = int(work_order.get("evidence_case_count", evidence_case_count))
        except (TypeError, ValueError):
            work_order_case_count = None
            errors.append("`work_order.evidence_case_count` 必须是整数。")
            repairs.append("将 YAML 中的 `evidence_case_count` 修正为整数，并与 frontmatter 一致。")

        if work_order_case_count is not None and work_order_case_count != evidence_case_count:
            errors.append("frontmatter 与 `work_order.evidence_case_count` 不一致。")
            repairs.append("将 YAML 中的 `evidence_case_count` 与 frontmatter 保持一致。")

        work_order_evidence_gap = str(work_order.get("evidence_gap", "")).strip()
        if work_order_evidence_gap and work_order_evidence_gap != str(meta.get("evidence_gap", "")).strip():
            warnings.append("frontmatter 与 `work_order.evidence_gap` 不一致。")

    if evidence_case_count < 5:
        if evidence_status != "bootstrap":
            errors.append("正式病例少于 5 时，`evidence_status` 必须为 `bootstrap`。")
            repairs.append("将 `evidence_status` 修正为 `bootstrap`。")
        if self_repair.get("required") is not True:
            errors.append("正式病例少于 5 时，必须开启 `self_repair.required: true`。")
            repairs.append("打开 `self_repair.required`，并记录删减无证据支撑站点的动作。")
        if stage1_replenishment.get("required") is not True:
            errors.append("正式病例少于 5 时，必须开启 `stage1_replenishment.required: true`。")
            repairs.append("补写阶段一补库动作，并将执行方设为 `system`。")

    if stage1_replenishment:
        if stage1_replenishment.get("required") is True:
            if stage1_replenishment.get("owner") != "system":
                errors.append("阶段一补库动作的 `owner` 必须为 `system`。")
                repairs.append("将 `stage1_replenishment.owner` 修正为 `system`。")
            if stage1_replenishment.get("user_action_required") is not False:
                errors.append("阶段一补库动作的 `user_action_required` 必须为 `false`。")
                repairs.append("将 `stage1_replenishment.user_action_required` 修正为 `false`。")

    checkpoint_blocks = parse_checkpoint_blocks(body)
    markdown_tasks = parse_markdown_tasks(body)
    progress_blocks = parse_progress_blocks(body)
    retrieval_section = sections.get(normalize_heading("熔炉内部召回记录"), "")

    if not progress_blocks:
        errors.append("缺少有效的“进度播报记录”条目。")
        repairs.append("至少记录一次阶段播报，并在会话收口前补齐阶段二 1/6~6/6 关键节点。")
    else:
        for index, block in enumerate(progress_blocks, start=1):
            for label in REQUIRED_PROGRESS_LABELS:
                if not extract_bold_value(block, label):
                    errors.append(f"进度播报 {index} 缺少字段：{label}")
                    repairs.append(f"补齐进度播报 {index} 的 `{label}` 字段。")

            trigger_type = extract_bold_value(block, "触发类型")
            if trigger_type == "timeout":
                if not extract_bold_value(block, "当前已完成"):
                    errors.append(f"超时进度播报 {index} 缺少字段：当前已完成")
                    repairs.append(f"补齐超时进度播报 {index} 的 `当前已完成`。")
                if not extract_bold_value(block, "仍在处理的原因"):
                    errors.append(f"超时进度播报 {index} 缺少字段：仍在处理的原因")
                    repairs.append(f"补齐超时进度播报 {index} 的 `仍在处理的原因`。")
                if not extract_bold_value(block, "剩余缺口"):
                    errors.append(f"超时进度播报 {index} 缺少字段：剩余缺口")
                    repairs.append(f"补齐超时进度播报 {index} 的 `剩余缺口`。")

        if meta.get("status") == "ready":
            progress_text = "\n\n".join(progress_blocks)
            for marker in REQUIRED_READY_STAGE_MARKERS:
                if marker not in progress_text:
                    errors.append(f"已交付会话缺少关键进度节点：{marker}")
                    repairs.append(f"补记 `{marker}` 的进度播报，确保 ready 会话覆盖完整 1/6~6/6 链路。")

        progress_event_count = meta.get("progress_event_count")
        if progress_event_count is not None:
            try:
                parsed_progress_event_count = int(progress_event_count)
            except (TypeError, ValueError):
                errors.append("`progress_event_count` 必须是整数。")
                repairs.append("将 `progress_event_count` 修正为进度播报条目数量。")
            else:
                if parsed_progress_event_count != len(progress_blocks):
                    warnings.append("`progress_event_count` 与实际进度播报条目数量不一致。")
                    repairs.append("将 `progress_event_count` 修正为实际进度播报条目数量。")

    if evidence_case_count == 0:
        if "cases/" in retrieval_section:
            errors.append("正式病例为 0 时，不应保留病例召回记录。")
            repairs.append("清空“熔炉内部召回记录”，并切换为补库说明。")
        if checkpoint_blocks:
            errors.append("正式病例为 0 时，不应保留检查站点。")
            repairs.append("删除所有检查站点，切换为补库专用会话。")
        if tasks:
            errors.append("正式病例为 0 时，不应输出业务执行任务。")
            repairs.append("删除业务执行任务，仅保留阶段一补库动作。")
    else:
        for index, block in enumerate(checkpoint_blocks, start=1):
            if not block_has_case_ref(block, retrieved_case_ref_set):
                errors.append(f"检查站点 {index} 没有引用已召回病例。")
                repairs.append(f"删除或改写检查站点 {index}，使其只引用已召回正式病例。")

        for index, task in enumerate(tasks, start=1):
            case_refs = task.get("case_refs", [])
            if not isinstance(case_refs, list) or not case_refs:
                errors.append(f"YAML 任务 {index} 缺少 `case_refs`。")
                repairs.append(f"为 YAML 任务 {index} 绑定已召回病例；若无法绑定则删除该任务。")
                continue
            if any(str(case_ref).strip() not in retrieved_case_ref_set for case_ref in case_refs):
                errors.append(f"YAML 任务 {index} 引用了未召回病例。")
                repairs.append(f"修正 YAML 任务 {index} 的 `case_refs`，仅允许使用已召回正式病例。")

        for index, block in enumerate(markdown_tasks, start=1):
            if not block_has_case_ref(block, retrieved_case_ref_set):
                errors.append(f"Markdown 任务 {index} 没有引用已召回病例。")
                repairs.append(f"删除或改写 Markdown 任务 {index}，使其只引用已召回正式病例。")

    if evidence_case_count < 5 and not str(meta.get("evidence_gap", "")).strip():
        errors.append("正式病例少于 5 时，必须填写 `evidence_gap`。")
        repairs.append("补写当前证据缺口及其对会话置信度的影响。")

    return errors, warnings, repairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Buildmate stage-2 session file.")
    parser.add_argument("session_file")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    session_path = Path(args.session_file).resolve()
    errors, warnings, repairs = validate_session(session_path)

    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for repair in repairs:
        print(f"SELF-REPAIR: {repair}")

    if not errors and not warnings:
        print("OK: session passed validation.")
        return
    if errors or (args.strict and warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
