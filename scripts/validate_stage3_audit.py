#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from _buildmate_lib import read_markdown


REQUIRED_META_FIELDS = [
    "audit_id",
    "title",
    "scope",
    "status",
    "input_goal",
    "platform",
    "user_type",
    "domain",
    "constraints",
    "failure_mode",
    "gap_type",
    "decision",
    "manual_fallback_required",
    "generated_session_ref",
    "date",
]

REQUIRED_SECTIONS = [
    "触发背景",
    "失败诊断",
    "阶段二反问结果",
    "阶段一补库动作",
    "自治学习动作",
    "Structured Autonomous Audit",
]

ALLOWED_FAILURE_MODES = {"unmatched_goal", "zero_case_recall", "no_strategy_candidates"}
ALLOWED_GAP_TYPES = {"stage2_translation_gap", "stage3_route_gap", "stage1_evidence_gap", "mixed"}
ALLOWED_DECISIONS = {"synthesized_bootstrap", "stage1_replenishment_only"}


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


def extract_audit_payload(body: str) -> dict:
    match = re.search(
        r"##\s+Structured Autonomous Audit\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1).strip()) or {}
    if not isinstance(payload, dict):
        return {}
    audit = payload.get("autonomous_audit", {})
    return audit if isinstance(audit, dict) else {}


def validate_stage3_audit(path: Path) -> tuple[list[str], list[str]]:
    root = path.resolve().parent.parent.parent
    meta, body = read_markdown(path)
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_audit_payload(body)

    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_META_FIELDS:
        if field not in meta:
            errors.append(f"缺少自治审计 frontmatter 字段：{field}")

    for section in REQUIRED_SECTIONS:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("scope", "")).strip() != "stage3":
        errors.append("`scope` 必须是 `stage3`。")
    if str(meta.get("status", "")).strip() != "ready":
        errors.append("`status` 必须是 `ready`。")

    failure_mode = str(meta.get("failure_mode", "")).strip()
    if failure_mode not in ALLOWED_FAILURE_MODES:
        errors.append("`failure_mode` 不在允许范围内。")

    gap_type = str(meta.get("gap_type", "")).strip()
    if gap_type not in ALLOWED_GAP_TYPES:
        errors.append("`gap_type` 不在允许范围内。")

    decision = str(meta.get("decision", "")).strip()
    if decision not in ALLOWED_DECISIONS:
        errors.append("`decision` 不在允许范围内。")

    manual_flag = meta.get("manual_fallback_required")
    if not isinstance(manual_flag, bool):
        errors.append("`manual_fallback_required` 必须是布尔值。")

    if not isinstance(meta.get("constraints"), list):
        errors.append("`constraints` 必须是列表。")

    if not payload:
        errors.append("缺少有效的 `Structured Autonomous Audit` YAML 区块。")
        return errors, warnings

    if str(payload.get("input_goal", "")).strip() != str(meta.get("input_goal", "")).strip():
        warnings.append("frontmatter 与 structured audit 的 `input_goal` 不一致。")
    if str(payload.get("failure_mode", "")).strip() != failure_mode:
        warnings.append("frontmatter 与 structured audit 的 `failure_mode` 不一致。")
    if str(payload.get("gap_type", "")).strip() != gap_type:
        warnings.append("frontmatter 与 structured audit 的 `gap_type` 不一致。")
    if str(payload.get("decision", "")).strip() != decision:
        warnings.append("frontmatter 与 structured audit 的 `decision` 不一致。")

    stage2_feedback = payload.get("stage2_feedback", {})
    stage1_replenishment = payload.get("stage1_replenishment", {})
    if not isinstance(stage2_feedback, dict):
        errors.append("`stage2_feedback` 必须是对象。")
    else:
        if stage2_feedback.get("owner") != "system":
            errors.append("`stage2_feedback.owner` 必须固定为 `system`。")
        if not str(stage2_feedback.get("result", "")).strip():
            errors.append("`stage2_feedback.result` 不能为空。")
    if not isinstance(stage1_replenishment, dict):
        errors.append("`stage1_replenishment` 必须是对象。")
    else:
        if stage1_replenishment.get("owner") != "system":
            errors.append("`stage1_replenishment.owner` 必须固定为 `system`。")
        if stage1_replenishment.get("user_action_required") is not False:
            errors.append("`stage1_replenishment.user_action_required` 必须是 `false`。")
        if stage1_replenishment.get("required") is True:
            try:
                target_case_count = int(stage1_replenishment.get("target_case_count", 0))
            except (TypeError, ValueError):
                target_case_count = 0
            if target_case_count <= 0:
                errors.append("`stage1_replenishment.target_case_count` 必须是正整数。")
            if not str(stage1_replenishment.get("search_brief", "")).strip():
                errors.append("`stage1_replenishment.search_brief` 不能为空。")
            intake_constraints = stage1_replenishment.get("intake_constraints", [])
            if not isinstance(intake_constraints, list) or not intake_constraints:
                errors.append("`stage1_replenishment.intake_constraints` 必须是非空列表。")
        if not str(stage1_replenishment.get("result", "")).strip():
            errors.append("`stage1_replenishment.result` 不能为空。")

    generated_session_ref = str(meta.get("generated_session_ref", "")).strip()
    if generated_session_ref:
        session_path = root / generated_session_ref
        if not session_path.exists():
            errors.append(f"`generated_session_ref` 指向的文件不存在：{generated_session_ref}")
    elif decision == "synthesized_bootstrap":
        errors.append("当 `decision` 为 `synthesized_bootstrap` 时，必须填写 `generated_session_ref`。")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Buildmate stage-3 autonomous audit file.")
    parser.add_argument("audit_file")
    args = parser.parse_args()

    audit_path = Path(args.audit_file).resolve()
    errors, warnings = validate_stage3_audit(audit_path)

    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        sys.exit(1)
    print("OK: stage3 autonomous audit passed validation.")


if __name__ == "__main__":
    main()
