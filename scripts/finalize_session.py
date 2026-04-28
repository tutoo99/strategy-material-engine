#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from _buildmate_lib import read_markdown, write_markdown
from validate_session import (
    extract_work_order_yaml,
    parse_checkpoint_blocks,
    parse_markdown_tasks,
    parse_progress_blocks,
    validate_session,
)


def replace_heading_block(body: str, heading_regex: str, new_content: str, level: int = 2) -> str:
    pattern = re.compile(rf"^{'#' * level}\s+{heading_regex}\s*$", flags=re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return body
    start = match.end()
    next_match = re.search(rf"^{'#' * level}\s+.+$", body[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(body)
    replacement = f"\n\n{new_content.strip()}\n"
    return body[:start] + replacement + body[end:]


def replace_heading_block_with_title(body: str, heading_regex: str, new_title: str, new_content: str, level: int = 2) -> str:
    pattern = re.compile(rf"^{'#' * level}\s+{heading_regex}\s*$", flags=re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return body
    heading_start = match.start()
    content_start = match.end()
    next_match = re.search(rf"^{'#' * level}\s+.+$", body[content_start:], flags=re.MULTILINE)
    end = content_start + next_match.start() if next_match else len(body)
    replacement = f"{'#' * level} {new_title}\n\n{new_content.strip()}\n"
    return body[:heading_start] + replacement + body[end:]


def replace_markdown_plan_block(body: str, plan_title: str, plan_content: str) -> str:
    pattern = re.compile(
        r"^##\s+Markdown工单\s*.*?(?=^##\s+Structured Work Order)",
        flags=re.DOTALL | re.MULTILINE,
    )
    replacement = f"## Markdown工单\n\n## {plan_title}\n\n{plan_content.strip()}\n\n"
    if pattern.search(body):
        return pattern.sub(replacement, body, count=1)
    return body


def dedupe_markdown_plan_block(body: str) -> str:
    pattern = re.compile(
        r"(?P<prefix>^##\s+Markdown工单\s+##\s+您的专属优化方案.*?)(?:\n##\s+您的专属优化方案.*?)+(?=\n##\s+Structured Work Order)",
        flags=re.DOTALL | re.MULTILINE,
    )
    while pattern.search(body):
        body = pattern.sub(lambda match: match.group("prefix"), body, count=1)
    return body


def extract_line_value(body: str, label: str) -> str:
    match = re.search(rf"\*\*{re.escape(label)}\*\*[：:]\s*(.+)", body)
    return match.group(1).strip() if match else ""


def build_evidence_gap(case_count: int) -> str:
    if case_count >= 5:
        return "已达到正式会诊的最低病例数量要求。"
    if case_count <= 0:
        return "当前没有召回到任何已商业化验证正式病例，无法输出可靠诊断工单；已切换为阶段一补库模式。"
    return (
        f"当前只有 {case_count} 个已商业化验证正式病例，尚未达到 5~10 个正式病例的成熟会诊标准；"
        "本工单仅用于内测和流程验证。"
    )


def build_default_search_brief(meta: dict) -> str:
    platform = str(meta.get("platform", "")).strip()
    symptom = str(meta.get("input_symptom", "")).strip()
    parts = [part for part in [platform, symptom, "已商业化验证", "已赚到钱"] if part]
    return " / ".join(parts) if parts else "补充与当前靶子相关的已商业化验证正式阶段一病例"


def normalize_case_refs(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def block_has_case_ref(block: str, retrieved_case_refs: set[str]) -> bool:
    return any(case_ref in block for case_ref in retrieved_case_refs)


def extract_existing_work_order(body: str) -> dict:
    work_order = extract_work_order_yaml(body)
    return work_order if isinstance(work_order, dict) else {}


def dump_work_order(work_order: dict) -> str:
    payload = {"work_order": work_order}
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).strip()


def build_self_repair_section(actions: list[str], triggered: bool, reason: str) -> str:
    lines = [
        f"- **是否触发：** {'是' if triggered else '否'}",
        f"- **触发原因：** {reason}",
        "- **修正动作：**",
    ]
    if actions:
        for index, action in enumerate(actions, start=1):
            lines.append(f"  {index}. {action}")
    else:
        lines.append("  1. 无")
    return "\n".join(lines)


def build_replenishment_section(replenishment: dict) -> str:
    intake_constraints = replenishment.get("intake_constraints", [])
    lines = [
        f"- **是否触发：** {'是' if replenishment.get('required') else '否'}",
        f"- **执行方：** `{replenishment.get('owner', 'system')}`",
        f"- **是否需要用户补充：** {'是' if replenishment.get('user_action_required') else '否'}",
        f"- **目标病例数：** `{replenishment.get('target_case_count', 5)}`",
        f"- **当前缺口：** `{replenishment.get('gap_count', 0)}`",
        f"- **补库检索简报：** {replenishment.get('search_brief', '待补充')}",
        "- **收录约束：**",
    ]
    if intake_constraints:
        for index, item in enumerate(intake_constraints, start=1):
            lines.append(f"  {index}. {item}")
    else:
        lines.append("  1. 只接收已商业化验证且明确赚到钱的案例")
    return "\n".join(lines)


def build_evidence_section(evidence_status: str, case_count: int, evidence_gap: str) -> str:
    return "\n".join(
        [
            f"- **证据级别：** `{evidence_status}`",
            f"- **正式病例数：** `{case_count}`",
            f"- **证据缺口：** {evidence_gap}",
        ]
    )


def build_markdown_plan_section(
    diagnosis: str,
    case_count: int,
    task_blocks: list[str],
) -> tuple[str, str]:
    title = "您的专属优化方案"
    evidence_note = ""
    if case_count < 5:
        title = "您的专属优化方案（Bootstrap 内测版）"
        if case_count <= 0:
            evidence_note = (
                "**证据说明**：当前没有可用正式病例，因此本次不交付业务执行任务，"
                "仅交付阶段一补库动作。"
            )
        else:
            evidence_note = (
                f"**证据说明**：当前正式病例只有 `{case_count}` 个，因此这是一份 `bootstrap` 工单，"
                "用来验证流程是否有效，不代表已经完成成熟专家训练。"
            )

    lines = [f"**诊断结论**：{diagnosis or '待补充'}", ""]
    if evidence_note:
        lines.extend([evidence_note, ""])

    if task_blocks:
        lines.append("**✅ 请按顺序执行以下动作：**")
        lines.append("")
        for block in task_blocks:
            lines.append(block.strip())
            lines.append("")
    else:
        lines.append("**当前不交付业务执行任务。请先完成系统补库，再重新进入阶段二会话。**")
        lines.append("")

    return title, "\n".join(lines).strip()


def build_logic_section(case_count: int, checkpoint_blocks: list[str]) -> str:
    if case_count <= 0:
        return "- 当前没有召回到任何已商业化验证正式病例，已切换为阶段一补库模式。"
    if checkpoint_blocks:
        return "\n\n".join(block.strip() for block in checkpoint_blocks)
    return "- 当前没有可保留的检查站点；无证据支撑的站点已在自修正中删除。"


def build_retrieval_section(case_count: int, existing_section: str) -> str:
    if case_count <= 0:
        return "- 当前没有召回到任何已商业化验证正式病例，已切换为阶段一补库模式。"
    return existing_section.strip() or "- 待补充"


def finalize_session(path: Path, write: bool = True) -> tuple[dict, list[str], list[str]]:
    meta, body = read_markdown(path)
    work_order = extract_existing_work_order(body)

    retrieved_case_refs = normalize_case_refs(meta.get("retrieved_case_refs", []))
    retrieved_case_ref_set = set(retrieved_case_refs)
    evidence_case_count = len(retrieved_case_refs)
    evidence_status = "bootstrap" if evidence_case_count < 5 else str(meta.get("evidence_status") or "formal").strip() or "formal"
    evidence_gap = build_evidence_gap(evidence_case_count)

    diagnosis = extract_line_value(body, "诊断结论") or str(work_order.get("diagnosis", "")).strip() or "待补充"

    checkpoint_blocks = parse_checkpoint_blocks(body)
    kept_checkpoint_blocks: list[str] = []
    markdown_tasks = parse_markdown_tasks(body)
    kept_markdown_tasks: list[str] = []
    progress_blocks = parse_progress_blocks(body)
    original_tasks = work_order.get("tasks", [])
    tasks = original_tasks if isinstance(original_tasks, list) else []
    kept_yaml_tasks: list[dict] = []

    repair_actions: list[str] = []

    for block in checkpoint_blocks:
        if evidence_case_count > 0 and block_has_case_ref(block, retrieved_case_ref_set):
            kept_checkpoint_blocks.append(block)
        else:
            repair_actions.append("删除无病例支撑的检查站点。")

    for block in markdown_tasks:
        if evidence_case_count > 0 and block_has_case_ref(block, retrieved_case_ref_set):
            kept_markdown_tasks.append(block)
        else:
            repair_actions.append("删除无病例支撑的 Markdown 执行任务。")

    for task in tasks:
        if not isinstance(task, dict):
            repair_actions.append("删除结构错误的 YAML 任务。")
            continue
        case_refs = normalize_case_refs(task.get("case_refs", []))
        if evidence_case_count > 0 and case_refs and all(case_ref in retrieved_case_ref_set for case_ref in case_refs):
            clean_task = dict(task)
            clean_task["case_refs"] = case_refs
            kept_yaml_tasks.append(clean_task)
        else:
            repair_actions.append("删除无病例支撑的 YAML 执行任务。")

    if evidence_case_count < 5:
        repair_actions.append("将本次会话标记为 bootstrap。")
        repair_actions.append("开启阶段一补库动作，并将执行方固定为 system。")

    if evidence_case_count <= 0:
        repair_actions.append("当前无正式病例，切换为阶段一补库模式，不交付业务执行任务。")
        kept_checkpoint_blocks = []
        kept_markdown_tasks = []
        kept_yaml_tasks = []

    normalized_repair_actions: list[str] = []
    for action in repair_actions:
        if action not in normalized_repair_actions:
            normalized_repair_actions.append(action)

    replenishment = work_order.get("stage1_replenishment", {}) if isinstance(work_order.get("stage1_replenishment"), dict) else {}
    target_case_count = int(replenishment.get("target_case_count", 5) or 5)
    gap_count = max(target_case_count - evidence_case_count, 0)
    stage1_replenishment = {
        "required": evidence_case_count < 5,
        "owner": "system",
        "user_action_required": False,
        "target_case_count": target_case_count,
        "gap_count": gap_count,
        "search_brief": str(replenishment.get("search_brief", "")).strip() or build_default_search_brief(meta),
        "intake_constraints": replenishment.get("intake_constraints")
        if isinstance(replenishment.get("intake_constraints"), list) and replenishment.get("intake_constraints")
        else [
            "只接收已商业化验证且明确赚到钱的案例",
            "必须从原始帖子或复盘入口进入阶段一",
            "必须按阶段一六步拆解法完成后再注册到 cases/",
        ],
    }

    self_repair = {
        "required": evidence_case_count < 5 or len(normalized_repair_actions) > 0,
        "actions": normalized_repair_actions or ["无需修正。"],
    }

    work_order["target_symptom"] = str(work_order.get("target_symptom", "")).strip() or str(meta.get("input_symptom", "")).strip() or "待补充"
    work_order["diagnosis"] = diagnosis
    work_order["evidence_status"] = evidence_status
    work_order["evidence_case_count"] = evidence_case_count
    work_order["evidence_gap"] = evidence_gap
    work_order["self_repair"] = self_repair
    work_order["stage1_replenishment"] = stage1_replenishment
    work_order["tasks"] = kept_yaml_tasks
    if "writeback_eligible" not in work_order:
        work_order["writeback_eligible"] = False

    meta["evidence_status"] = evidence_status
    meta["evidence_case_count"] = evidence_case_count
    meta["evidence_gap"] = evidence_gap
    meta["retrieved_case_refs"] = retrieved_case_refs
    meta["progress_protocol"] = "hybrid-3min"
    meta["progress_event_count"] = len(progress_blocks)
    if progress_blocks:
        time_match = re.findall(r"\*\*时间：\*\*\s*(.+)", "\n\n".join(progress_blocks))
        if time_match:
            meta["last_progress_at"] = time_match[-1].strip()
    meta["status"] = "ready"

    retrieval_section_match = re.search(
        r"^##\s+熔炉内部召回记录\s*(.*?)(?=^##\s+证据状态|\Z)",
        body,
        flags=re.DOTALL | re.MULTILINE,
    )
    existing_retrieval_section = retrieval_section_match.group(1).strip() if retrieval_section_match else ""

    body = replace_heading_block(body, re.escape("熔炉内部召回记录"), build_retrieval_section(evidence_case_count, existing_retrieval_section))
    body = replace_heading_block(body, re.escape("证据状态"), build_evidence_section(evidence_status, evidence_case_count, evidence_gap))
    reason = (
        "当前正式病例不足 5 个，不能把证据缺口伪装成成熟专家知识。"
        if evidence_case_count < 5
        else "当前会话已通过校验，仅保留有病例支撑的内容。"
    )
    body = replace_heading_block(body, re.escape("自修正动作"), build_self_repair_section(self_repair["actions"], self_repair["required"], reason))
    body = replace_heading_block(body, re.escape("阶段一补库动作"), build_replenishment_section(stage1_replenishment))
    body = replace_heading_block(body, re.escape("熔炉内部组装逻辑"), build_logic_section(evidence_case_count, kept_checkpoint_blocks))
    plan_title, plan_content = build_markdown_plan_section(diagnosis, evidence_case_count, kept_markdown_tasks)
    body = replace_markdown_plan_block(body, plan_title, plan_content)
    body = dedupe_markdown_plan_block(body)
    body = replace_heading_block(body, re.escape("Structured Work Order"), f"```yaml\n{dump_work_order(work_order)}\n```")

    if write:
        write_markdown(path, meta, body)

    errors, warnings, repairs = validate_session(path)
    return {"errors": errors, "warnings": warnings, "repairs": repairs}, normalized_repair_actions, retrieved_case_refs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize a Buildmate stage-2 session: validate, self-repair safely, re-validate, then mark ready."
    )
    parser.add_argument("session_file")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    session_path = Path(args.session_file).resolve()
    result, actions, retrieved = finalize_session(session_path, write=not args.check_only)

    if actions:
        for action in actions:
            print(f"SELF-REPAIR-APPLIED: {action}")
    print(f"INFO: retrieved_case_refs={len(retrieved)}")

    for warning in result["warnings"]:
        print(f"WARNING: {warning}")
    for error in result["errors"]:
        print(f"ERROR: {error}")
    for repair in result["repairs"]:
        print(f"SELF-REPAIR-SUGGESTED: {repair}")

    if result["errors"]:
        sys.exit(1)
    print("OK: session finalized and ready for delivery.")


if __name__ == "__main__":
    main()
