#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _buildmate_lib import (
    ALLOWED_CAUSAL_STATUS,
    REQUIRED_CASE_SECTIONS,
    has_action_specificity,
    parse_case_body,
    principle_is_vague,
    read_markdown,
)


REQUIRED_META_FIELDS = [
    "case_id",
    "title",
    "author_identity",
    "domain",
    "platform",
    "stage",
    "result_summary",
    "source_path",
    "quality_score",
    "status",
]

ALLOWED_VERIFICATION_STATUS = {"verified", "weakly_verified", "unverified"}
ALLOWED_TRUST_LEVEL = {"production", "observation", "excluded"}
RECOMMENDED_CASE_SECTIONS = ["故事线", "归因与边界", "作战序列", "资源清单"]

RESULT_HINTS = ["赚", "变现", "增长", "成交", "粉丝", "阅读", "复购", "用户", "月入", "起盘"]
AUTO_REPAIRABLE_PATTERNS = [
    "的“是否推测”必须是“是”或“否”",
]


def validate_case(path: Path) -> tuple[list[str], list[str]]:
    meta, body = read_markdown(path)
    parsed = parse_case_body(body)
    sections = parsed["sections"]
    decisions = parsed["decisions"]
    principles = parsed["principles"]
    pitfall = parsed["pitfall"]

    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_META_FIELDS:
        value = meta.get(field)
        if value is None or str(value).strip() == "":
            errors.append(f"缺少 frontmatter 字段：{field}")

    required_sections = list(REQUIRED_CASE_SECTIONS)
    if meta.get("body_lock") is True and meta.get("content_source") in {"human_provided", "human_approved"}:
        required_sections = [section for section in required_sections if section != "待验证推测"]

    for section in required_sections:
        if section not in sections or not sections[section].strip():
            errors.append(f"缺少正文区块：{section}")

    if meta.get("stage") != "gene-library":
        warnings.append("`stage` 不是 `gene-library`。")

    if meta.get("status") == "approved" and meta.get("body_lock") is not True:
        errors.append("`approved` 案例必须设置 `body_lock: true`。")
    if meta.get("body_lock") is True and meta.get("content_source") not in {"human_provided", "human_approved"}:
        warnings.append("正文已锁定，但 `content_source` 不是 `human_provided/human_approved`。")
    if meta.get("status") == "approved" and not str(meta.get("last_human_reviewed_at", "")).strip():
        warnings.append("`approved` 案例建议填写 `last_human_reviewed_at`。")
    if meta.get("status") == "approved" and not str(meta.get("approved_from", "")).strip():
        warnings.append("`approved` 案例建议填写 `approved_from`，指向人工确认来源。")

    verification_status = str(meta.get("verification_status", "")).strip()
    trust_level = str(meta.get("trust_level", "")).strip()
    reproducibility_raw = meta.get("reproducibility_score")
    proof_refs = meta.get("proof_refs", [])
    context_constraints = meta.get("context_constraints", [])
    causal_status = str(meta.get("causal_status", "")).strip()
    cross_case_refs = meta.get("cross_case_refs", [])
    counterfactual_notes = meta.get("counterfactual_notes", [])
    action_granularity_raw = meta.get("action_granularity_score")
    sequence_steps = meta.get("sequence_steps", [])
    resource_links = meta.get("resource_links", [])
    platform_context = str(meta.get("platform_context", "")).strip()
    account_context = str(meta.get("account_context", "")).strip()
    time_context = str(meta.get("time_context", "")).strip()
    resource_last_checked_at = str(meta.get("resource_last_checked_at", "")).strip()

    reproducibility_score = None
    if reproducibility_raw not in {None, ""}:
        try:
            reproducibility_score = int(reproducibility_raw)
        except (TypeError, ValueError):
            errors.append("`reproducibility_score` 必须是整数。")

    action_granularity_score = None
    if action_granularity_raw not in {None, ""}:
        try:
            action_granularity_score = int(action_granularity_raw)
        except (TypeError, ValueError):
            errors.append("`action_granularity_score` 必须是整数。")

    if verification_status and verification_status not in ALLOWED_VERIFICATION_STATUS:
        errors.append("`verification_status` 不在允许范围内。")
    if trust_level and trust_level not in ALLOWED_TRUST_LEVEL:
        errors.append("`trust_level` 不在允许范围内。")
    if causal_status and causal_status not in ALLOWED_CAUSAL_STATUS:
        errors.append("`causal_status` 不在允许范围内。")
    if proof_refs and not isinstance(proof_refs, list):
        errors.append("`proof_refs` 必须是列表。")
    if context_constraints and not isinstance(context_constraints, list):
        errors.append("`context_constraints` 必须是列表。")
    if cross_case_refs and not isinstance(cross_case_refs, list):
        errors.append("`cross_case_refs` 必须是列表。")
    if counterfactual_notes and not isinstance(counterfactual_notes, list):
        errors.append("`counterfactual_notes` 必须是列表。")
    if sequence_steps and not isinstance(sequence_steps, list):
        errors.append("`sequence_steps` 必须是列表。")
    if resource_links and not isinstance(resource_links, list):
        errors.append("`resource_links` 必须是列表。")
    if action_granularity_score is not None and not 1 <= action_granularity_score <= 5:
        errors.append("`action_granularity_score` 必须在 1 到 5 之间。")

    for section in RECOMMENDED_CASE_SECTIONS:
        if section not in sections or not sections[section].strip():
            warnings.append(f"建议补充正文区块：{section}")

    if meta.get("status") in {"approved", "reviewed"}:
        if not verification_status:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `verification_status`。")
        if not trust_level:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `trust_level`。")
        if reproducibility_score is None:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `reproducibility_score`。")
        if not proof_refs:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `proof_refs`，至少提供 1 个可交叉验证证据。")
        if not context_constraints:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `context_constraints`，说明适用边界。")
        if not causal_status:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `causal_status`。")
        if not cross_case_refs:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `cross_case_refs`，做多案例交叉验证。")
        if not counterfactual_notes:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `counterfactual_notes`。")
        if action_granularity_score is None:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `action_granularity_score`。")
        if not sequence_steps:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `sequence_steps`，沉淀作战序列。")
        if not platform_context:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `platform_context`。")
        if not account_context:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `account_context`。")
        if not time_context:
            warnings.append("已进入 reviewed/approved 的案例建议填写 `time_context`。")
        if resource_links and not resource_last_checked_at:
            warnings.append("已登记 `resource_links` 的案例建议填写 `resource_last_checked_at`。")

    if trust_level == "production":
        if verification_status == "unverified":
            errors.append("`trust_level=production` 的案例不能同时是 `verification_status=unverified`。")
        if reproducibility_score is not None and reproducibility_score < 3:
            errors.append("`trust_level=production` 的案例，`reproducibility_score` 不能低于 3。")
        if isinstance(proof_refs, list) and not proof_refs:
            warnings.append("`trust_level=production` 的案例建议提供 `proof_refs`，否则应降级为 observation。")
        if causal_status in {"", "unknown", "refuted"}:
            warnings.append("`trust_level=production` 的案例建议补强 `causal_status`，避免把相关性动作当成正式生产知识。")
        if action_granularity_score is not None and action_granularity_score < 3:
            errors.append("`trust_level=production` 的案例，`action_granularity_score` 不能低于 3。")
        if isinstance(sequence_steps, list) and len(sequence_steps) < 2:
            warnings.append("`trust_level=production` 的案例建议至少提供 2 条 `sequence_steps`。")

    if not any(hint in str(meta.get("title", "")) for hint in RESULT_HINTS):
        warnings.append("标题不像“作者身份 + 核心打法 + 结果”，建议补充结果关键词。")

    if not decisions:
        errors.append("决策地图为空。至少补 1 个决策点。")
    for index, decision in enumerate(decisions, start=1):
        for field in ["decision_point", "choice", "basis", "evidence"]:
            if not str(decision.get(field, "")).strip():
                errors.append(f"决策点 {index} 缺少字段：{field}")
        action_steps = decision.get("action_steps", [])
        if not action_steps:
            errors.append(f"决策点 {index} 没有动作步骤。")
        elif not any(has_action_specificity(step) for step in action_steps):
            warnings.append(f"决策点 {index} 的动作步骤仍偏空泛，建议补到按钮级或参数级。")
        if decision.get("is_inferred") not in {"是", "否"}:
            errors.append(f"决策点 {index} 的“是否推测”必须是“是”或“否”。")

    if isinstance(sequence_steps, list) and sequence_steps:
        if len(sequence_steps) < len(decisions) and len(decisions) >= 2:
            warnings.append("`sequence_steps` 数量少于决策点数量，建议补足完整作战序列。")

    if action_granularity_score is None and decisions:
        specific_decisions = sum(
            1 for decision in decisions if any(has_action_specificity(step) for step in decision.get("action_steps", []))
        )
        if specific_decisions < len(decisions):
            warnings.append("部分决策动作仍偏空泛，建议填写 `action_granularity_score` 并继续补细。")

    if len(principles) < 3:
        warnings.append("作战三原则不足 3 条。")
    for index, principle in enumerate(principles, start=1):
        if principle_is_vague(principle):
            warnings.append(f"原则 {index} 偏空泛，建议改成可检查动作纪律。")

    if not pitfall.get("坑点"):
        warnings.append("最大一个坑缺少“坑点”。")
    if not pitfall.get("解决方案"):
        warnings.append("最大一个坑缺少“解决方案”。")

    pending = sections.get("待验证推测", "")
    if pending and "推测" not in pending and "暂无" not in pending:
        warnings.append("存在不确定信息时，建议在“待验证推测”中显式记录。")

    return errors, warnings


def is_auto_repairable_error(error: str) -> bool:
    return any(pattern in error for pattern in AUTO_REPAIRABLE_PATTERNS)


def split_case_errors(errors: list[str]) -> tuple[list[str], list[str]]:
    auto_repairable: list[str] = []
    blocking: list[str] = []
    for error in errors:
        if is_auto_repairable_error(error):
            auto_repairable.append(error)
        else:
            blocking.append(error)
    return auto_repairable, blocking


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Buildmate case file.")
    parser.add_argument("case_file")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    case_path = Path(args.case_file).resolve()
    errors, warnings = validate_case(case_path)

    for error in errors:
        print(f"ERROR: {error}")
        if is_auto_repairable_error(error):
            print(f"AUTO-REPAIRABLE: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    if not errors and not warnings:
        print("OK: case passed validation.")
        return
    if errors or (args.strict and warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
