#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from _buildmate_lib import read_markdown


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


def extract_yaml_block(body: str, heading: str) -> dict:
    match = re.search(
        rf"##\s+{re.escape(heading)}\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1).strip()) or {}
    return payload if isinstance(payload, dict) else {}


def validate_ref(root: Path, ref: str) -> bool:
    normalized = str(ref).strip()
    if not normalized:
        return False
    return (root / normalized).exists()


def validate_owner_profile(root: Path, meta: dict, body: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required_meta = [
        "artifact_type",
        "profile_id",
        "title",
        "owner_name",
        "status",
        "review_cycle",
        "primary_goal",
        "risk_score",
        "focus_area",
        "frontlines",
        "date",
    ]
    required_sections = ["资源画像", "目标与偏好", "当前主战场", "业务前线总表", "交互协议", "交互人格", "主动关怀里程碑", "红色警报协议", "人类判断协议", "数据同步协议", "档案维护", "Structured Owner Profile"]
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_yaml_block(body, "Structured Owner Profile").get("owner_profile", {})

    for field in required_meta:
        if field not in meta:
            errors.append(f"缺少 owner_profile frontmatter 字段：{field}")
    for section in required_sections:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    try:
        risk_score = int(meta.get("risk_score", 0))
    except (TypeError, ValueError):
        risk_score = 0
    if not 1 <= risk_score <= 10:
        errors.append("`risk_score` 必须是 1 到 10 的整数。")
    if str(meta.get("status", "")).strip() != "active":
        errors.append("`status` 必须是 `active`。")
    if str(meta.get("review_cycle", "")).strip() not in {"weekly", "monthly", "quarterly"}:
        errors.append("`review_cycle` 必须是 `weekly / monthly / quarterly`。")
    if not isinstance(meta.get("frontlines"), list):
        errors.append("`frontlines` 必须是列表。")

    if not isinstance(payload, dict):
        errors.append("缺少有效的 `Structured Owner Profile` YAML 区块。")
        return errors, warnings

    resource_profile = payload.get("resource_profile", {})
    goals_and_preferences = payload.get("goals_and_preferences", {})
    human_judgment_policy = payload.get("human_judgment_policy", {})
    if not isinstance(resource_profile, dict):
        errors.append("`owner_profile.resource_profile` 必须是对象。")
    if not isinstance(goals_and_preferences, dict):
        errors.append("`owner_profile.goals_and_preferences` 必须是对象。")
    if not isinstance(human_judgment_policy, dict):
        errors.append("`owner_profile.human_judgment_policy` 必须是对象。")
    if str(payload.get("owner_name", "")).strip() != str(meta.get("owner_name", "")).strip():
        warnings.append("frontmatter 与 structured payload 的 `owner_name` 不一致。")
    return errors, warnings


def validate_dashboard(root: Path, meta: dict, body: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required_meta = [
        "artifact_type",
        "dashboard_id",
        "title",
        "profile_ref",
        "frontline_name",
        "platform",
        "domain",
        "status",
        "alert_level",
        "last_synced_at",
        "latest_feedback_ref",
        "latest_review_ref",
        "date",
    ]
    required_sections = ["前线概览", "核心指标", "内容表现", "内容表现采集口径", "待办事项", "主动关怀消息", "红色警报协议", "红色警报消息", "手动同步机制", "预警状态", "Structured Frontline Dashboard"]
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_yaml_block(body, "Structured Frontline Dashboard").get("dashboard", {})

    for field in required_meta:
        if field not in meta:
            errors.append(f"缺少 dashboard frontmatter 字段：{field}")
    for section in required_sections:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("status", "")).strip() != "active":
        errors.append("`status` 必须是 `active`。")
    if str(meta.get("alert_level", "")).strip() not in {"normal", "warning", "critical"}:
        errors.append("`alert_level` 必须是 `normal / warning / critical`。")
    if not validate_ref(root, str(meta.get("profile_ref", "")).strip()):
        errors.append("`profile_ref` 指向的文件不存在。")
    for key in ["latest_feedback_ref", "latest_review_ref"]:
        ref = str(meta.get(key, "")).strip()
        if ref and not validate_ref(root, ref):
            errors.append(f"`{key}` 指向的文件不存在：{ref}")

    if not isinstance(payload, dict):
        errors.append("缺少有效的 `Structured Frontline Dashboard` YAML 区块。")
        return errors, warnings
    if not isinstance(payload.get("metrics", []), list):
        errors.append("`dashboard.metrics` 必须是列表。")
    if not isinstance(payload.get("todos", []), list):
        errors.append("`dashboard.todos` 必须是列表。")
    for key in ["generated_stage2_session_ref", "generated_red_alert_dispatch_ref"]:
        ref = str(payload.get(key, "")).strip()
        if ref and not validate_ref(root, ref):
            errors.append(f"`dashboard.{key}` 指向的文件不存在：{ref}")
    return errors, warnings


def validate_feedback(root: Path, meta: dict, body: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required_meta = [
        "artifact_type",
        "feedback_id",
        "title",
        "status",
        "profile_ref",
        "dashboard_ref",
        "source_stage3_session",
        "generated_review_ref",
        "improved",
        "date",
    ]
    required_sections = ["反馈背景", "执行结果", "学习判断", "学习动作", "模型修正项", "Structured Stage4 Feedback"]
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_yaml_block(body, "Structured Stage4 Feedback").get("stage4_feedback", {})

    for field in required_meta:
        if field not in meta:
            errors.append(f"缺少 feedback frontmatter 字段：{field}")
    for section in required_sections:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("status", "")).strip() != "ready":
        errors.append("`status` 必须是 `ready`。")
    if str(meta.get("improved", "")).strip() not in {"yes", "partial", "no"}:
        errors.append("`improved` 必须是 `yes / partial / no`。")
    for key in ["profile_ref", "dashboard_ref", "source_stage3_session"]:
        if not validate_ref(root, str(meta.get(key, "")).strip()):
            errors.append(f"`{key}` 指向的文件不存在。")
    generated_review_ref = str(meta.get("generated_review_ref", "")).strip()
    if generated_review_ref and not validate_ref(root, generated_review_ref):
        errors.append(f"`generated_review_ref` 指向的文件不存在：{generated_review_ref}")

    if not isinstance(payload, dict):
        errors.append("缺少有效的 `Structured Stage4 Feedback` YAML 区块。")
        return errors, warnings

    authorization = payload.get("authorization", {})
    if not isinstance(authorization, dict):
        errors.append("`stage4_feedback.authorization` 必须是对象。")
    learning_actions = payload.get("learning_actions", [])
    if not isinstance(learning_actions, list):
        errors.append("`stage4_feedback.learning_actions` 必须是列表。")
    model_corrections = payload.get("model_corrections", {})
    if not isinstance(model_corrections, dict):
        errors.append("`stage4_feedback.model_corrections` 必须是对象。")
    return errors, warnings


def validate_review(root: Path, meta: dict, body: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required_meta = [
        "artifact_type",
        "review_id",
        "title",
        "status",
        "profile_ref",
        "dashboard_refs",
        "feedback_refs",
        "week_range",
        "date",
    ]
    required_sections = ["生成依据", "本周核心判断", "决策留白", "交互人格输出", "主动关怀与警报", "本周任务包", "授权项", "学习动作", "Structured Weekly Review"]
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_yaml_block(body, "Structured Weekly Review").get("weekly_review", {})

    for field in required_meta:
        if field not in meta:
            errors.append(f"缺少 weekly_review frontmatter 字段：{field}")
    for section in required_sections:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("status", "")).strip() != "ready":
        errors.append("`status` 必须是 `ready`。")
    if not validate_ref(root, str(meta.get("profile_ref", "")).strip()):
        errors.append("`profile_ref` 指向的文件不存在。")
    for key in ["dashboard_refs", "feedback_refs"]:
        refs = meta.get(key, [])
        if not isinstance(refs, list) or not refs:
            errors.append(f"`{key}` 必须是非空列表。")
            continue
        for ref in refs:
            if not validate_ref(root, str(ref).strip()):
                errors.append(f"`{key}` 中存在无效引用：{ref}")

    if not isinstance(payload, dict):
        errors.append("缺少有效的 `Structured Weekly Review` YAML 区块。")
        return errors, warnings

    task_package = payload.get("task_package", [])
    if not isinstance(task_package, list) or not task_package:
        errors.append("`weekly_review.task_package` 必须是非空列表。")
    decision_options = payload.get("decision_options", [])
    if not isinstance(decision_options, list) or not decision_options:
        errors.append("`weekly_review.decision_options` 必须是非空列表。")
    decision_prompt = str(payload.get("decision_prompt", "")).strip()
    if not decision_prompt:
        errors.append("`weekly_review.decision_prompt` 不能为空。")
    if not isinstance(payload.get("human_judgment_policy", {}), dict):
        errors.append("`weekly_review.human_judgment_policy` 必须是对象。")
    authorizations = payload.get("authorizations", {})
    if not isinstance(authorizations, dict):
        errors.append("`weekly_review.authorizations` 必须是对象。")
    learning_actions = payload.get("learning_actions", [])
    if not isinstance(learning_actions, list):
        errors.append("`weekly_review.learning_actions` 必须是列表。")
    return errors, warnings


def validate_monthly_model_review(root: Path, meta: dict, body: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required_meta = [
        "artifact_type",
        "review_id",
        "title",
        "status",
        "profile_ref",
        "feedback_refs",
        "month_range",
        "date",
    ]
    required_sections = ["生成依据", "本月反馈概览", "模型修正清单", "修正执行决议", "Structured Monthly Model Review"]
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_yaml_block(body, "Structured Monthly Model Review").get("monthly_model_review", {})

    for field in required_meta:
        if field not in meta:
            errors.append(f"缺少 monthly_model_review frontmatter 字段：{field}")
    for section in required_sections:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("status", "")).strip() != "ready":
        errors.append("`status` 必须是 `ready`。")
    if not validate_ref(root, str(meta.get("profile_ref", "")).strip()):
        errors.append("`profile_ref` 指向的文件不存在。")
    refs = meta.get("feedback_refs", [])
    if not isinstance(refs, list) or not refs:
        errors.append("`feedback_refs` 必须是非空列表。")
    else:
        for ref in refs:
            if not validate_ref(root, str(ref).strip()):
                errors.append(f"`feedback_refs` 中存在无效引用：{ref}")

    if not isinstance(payload, dict):
        errors.append("缺少有效的 `Structured Monthly Model Review` YAML 区块。")
        return errors, warnings
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        errors.append("`monthly_model_review.summary` 必须是对象。")
    correction_backlog = payload.get("correction_backlog", [])
    if not isinstance(correction_backlog, list):
        errors.append("`monthly_model_review.correction_backlog` 必须是列表。")
    execution_decisions = payload.get("execution_decisions", [])
    if not isinstance(execution_decisions, list):
        errors.append("`monthly_model_review.execution_decisions` 必须是列表。")
    return errors, warnings


def validate_red_alert_dispatch(root: Path, meta: dict, body: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required_meta = [
        "artifact_type",
        "dispatch_id",
        "title",
        "status",
        "profile_ref",
        "dashboard_ref",
        "generated_stage2_session_ref",
        "trigger_type",
        "alert_level",
        "date",
    ]
    required_sections = ["触发背景", "系统判断", "阶段二自修正派发", "阶段一补库派发", "跟进条件", "Structured Red Alert Dispatch"]
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_yaml_block(body, "Structured Red Alert Dispatch").get("red_alert_dispatch", {})

    for field in required_meta:
        if field not in meta:
            errors.append(f"缺少 red_alert_dispatch frontmatter 字段：{field}")
    for section in required_sections:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("status", "")).strip() != "ready":
        errors.append("`status` 必须是 `ready`。")
    if str(meta.get("trigger_type", "")).strip() != "red_alert":
        errors.append("`trigger_type` 必须是 `red_alert`。")
    if str(meta.get("alert_level", "")).strip() != "critical":
        errors.append("`alert_level` 必须是 `critical`。")
    for key in ["profile_ref", "dashboard_ref", "generated_stage2_session_ref"]:
        if not validate_ref(root, str(meta.get(key, "")).strip()):
            errors.append(f"`{key}` 指向的文件不存在。")

    if not isinstance(payload, dict):
        errors.append("缺少有效的 `Structured Red Alert Dispatch` YAML 区块。")
        return errors, warnings

    if str(payload.get("trigger_type", "")).strip() != "red_alert":
        errors.append("`red_alert_dispatch.trigger_type` 必须是 `red_alert`。")
    stage2_dispatch = payload.get("stage2_dispatch", {})
    if not isinstance(stage2_dispatch, dict):
        errors.append("`red_alert_dispatch.stage2_dispatch` 必须是对象。")
    else:
        session_ref = str(stage2_dispatch.get("session_ref", "")).strip()
        if not session_ref or not validate_ref(root, session_ref):
            errors.append("`red_alert_dispatch.stage2_dispatch.session_ref` 指向的文件不存在。")
    stage1_replenishment = payload.get("stage1_replenishment", {})
    if not isinstance(stage1_replenishment, dict):
        errors.append("`red_alert_dispatch.stage1_replenishment` 必须是对象。")
    next_gate = payload.get("next_gate", {})
    if not isinstance(next_gate, dict):
        errors.append("`red_alert_dispatch.next_gate` 必须是对象。")
    return errors, warnings


def validate_stage4_artifact(path: Path) -> tuple[list[str], list[str]]:
    root = path.resolve().parent.parent.parent
    meta, body = read_markdown(path)
    artifact_type = str(meta.get("artifact_type", "")).strip()

    if artifact_type == "owner_profile":
        return validate_owner_profile(root, meta, body)
    if artifact_type == "frontline_dashboard":
        return validate_dashboard(root, meta, body)
    if artifact_type == "stage4_feedback_record":
        return validate_feedback(root, meta, body)
    if artifact_type == "weekly_strategy_review":
        return validate_review(root, meta, body)
    if artifact_type == "monthly_model_review":
        return validate_monthly_model_review(root, meta, body)
    if artifact_type == "red_alert_dispatch":
        return validate_red_alert_dispatch(root, meta, body)
    return [f"未识别的 stage4 artifact_type：{artifact_type or '空'}"], []


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Buildmate stage-4 artifact file.")
    parser.add_argument("artifact_file")
    args = parser.parse_args()

    artifact_path = Path(args.artifact_file).resolve()
    errors, warnings = validate_stage4_artifact(artifact_path)

    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        sys.exit(1)
    print("OK: stage4 artifact passed validation.")


if __name__ == "__main__":
    main()
