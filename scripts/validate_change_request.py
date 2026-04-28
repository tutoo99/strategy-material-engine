#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from _buildmate_lib import read_markdown


REQUIRED_META_FIELDS = [
    "artifact_type",
    "change_request_id",
    "title",
    "status",
    "source_ref",
    "target_stage",
    "change_type",
    "target_ref",
    "patch_mode",
    "manual_fallback_required",
    "date",
]

REQUIRED_SECTIONS = [
    "触发来源",
    "变更目标",
    "执行补丁",
    "验证与重建",
    "Structured Change Request",
]

ALLOWED_TARGET_STAGES = {"stage1", "stage2", "stage3", "stage4"}
ALLOWED_CHANGE_TYPES = {
    "stage1_case_patch",
    "stage2_manual_patch",
    "stage3_route_patch",
    "stage3_resource_patch",
    "stage3_node_patch",
    "stage4_rule_patch",
}
ALLOWED_PATCH_MODES = {"append", "append_section", "create_file"}
ALLOWED_TARGET_PREFIXES = ("cases/", "expert_models/", "strategy_models/", "stage4_models/", "index/")


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


def extract_payload(body: str) -> dict:
    match = re.search(
        r"##\s+Structured Change Request\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1).strip()) or {}
    if not isinstance(payload, dict):
        return {}
    request = payload.get("change_request", {})
    return request if isinstance(request, dict) else {}


def validate_ref(root: Path, ref: str, allow_missing: bool = False) -> bool:
    normalized = str(ref).strip()
    if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
        return False
    target = root / normalized
    if allow_missing:
        return target.parent.exists()
    return target.exists()


def validate_target_prefix(ref: str) -> bool:
    normalized = str(ref).strip()
    return normalized.startswith(ALLOWED_TARGET_PREFIXES)


def validate_change_request(path: Path) -> tuple[list[str], list[str]]:
    root = path.resolve().parent.parent.parent
    meta, body = read_markdown(path)
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_payload(body)

    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_META_FIELDS:
        if field not in meta:
            errors.append(f"缺少 change_request frontmatter 字段：{field}")

    for section in REQUIRED_SECTIONS:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("artifact_type", "")).strip() != "change_request":
        errors.append("`artifact_type` 必须是 `change_request`。")
    if str(meta.get("status", "")).strip() not in {"draft", "ready", "applied"}:
        errors.append("`status` 必须是 `draft / ready / applied`。")
    if str(meta.get("target_stage", "")).strip() not in ALLOWED_TARGET_STAGES:
        errors.append("`target_stage` 不在允许范围内。")
    if str(meta.get("change_type", "")).strip() not in ALLOWED_CHANGE_TYPES:
        errors.append("`change_type` 不在允许范围内。")
    patch_mode = str(meta.get("patch_mode", "")).strip()
    if patch_mode not in ALLOWED_PATCH_MODES:
        errors.append("`patch_mode` 不在允许范围内。")
    if not isinstance(meta.get("manual_fallback_required"), bool):
        errors.append("`manual_fallback_required` 必须是布尔值。")

    source_ref = str(meta.get("source_ref", "")).strip()
    if not source_ref or not validate_ref(root, source_ref):
        errors.append("`source_ref` 指向的文件不存在。")

    target_ref = str(meta.get("target_ref", "")).strip()
    if not validate_target_prefix(target_ref):
        errors.append("`target_ref` 必须指向系统正式目录。")
    elif not validate_ref(root, target_ref, allow_missing=(patch_mode == "create_file")):
        errors.append("`target_ref` 指向的目标不存在，或父目录不存在。")

    if not payload:
        errors.append("缺少有效的 `Structured Change Request` YAML 区块。")
        return errors, warnings

    if str(payload.get("request_id", "")).strip() != str(meta.get("change_request_id", "")).strip():
        warnings.append("frontmatter 与 structured payload 的 `request_id` 不一致。")
    if str(payload.get("source_ref", "")).strip() != source_ref:
        warnings.append("frontmatter 与 structured payload 的 `source_ref` 不一致。")

    if str(payload.get("target_stage", "")).strip() not in ALLOWED_TARGET_STAGES:
        errors.append("`change_request.target_stage` 不在允许范围内。")
    if str(payload.get("change_type", "")).strip() not in ALLOWED_CHANGE_TYPES:
        errors.append("`change_request.change_type` 不在允许范围内。")
    if not isinstance(payload.get("manual_fallback_required"), bool):
        errors.append("`change_request.manual_fallback_required` 必须是布尔值。")

    changes = payload.get("changes", [])
    if not isinstance(changes, list) or not changes:
        errors.append("`change_request.changes` 必须是非空列表。")
    else:
        for index, change in enumerate(changes, start=1):
            if not isinstance(change, dict):
                errors.append(f"变更项 {index} 必须是对象。")
                continue
            mode = str(change.get("patch_mode", "")).strip()
            ref = str(change.get("target_ref", "")).strip()
            content = str(change.get("content", "")).rstrip()
            if not str(change.get("change_id", "")).strip():
                errors.append(f"变更项 {index} 缺少 `change_id`。")
            if mode not in ALLOWED_PATCH_MODES:
                errors.append(f"变更项 {index} 的 `patch_mode` 不在允许范围内。")
            if not validate_target_prefix(ref):
                errors.append(f"变更项 {index} 的 `target_ref` 不在允许目录内。")
            elif not validate_ref(root, ref, allow_missing=(mode == "create_file")):
                errors.append(f"变更项 {index} 的 `target_ref` 不可用：{ref}")
            if not content:
                errors.append(f"变更项 {index} 的 `content` 不能为空。")
            if mode == "append_section" and not str(change.get("section_title", "")).strip():
                errors.append(f"变更项 {index} 使用 `append_section` 时必须填写 `section_title`。")
            if not str(change.get("reason", "")).strip():
                errors.append(f"变更项 {index} 缺少 `reason`。")

    if not isinstance(payload.get("validation_commands", []), list):
        errors.append("`change_request.validation_commands` 必须是列表。")
    if not isinstance(payload.get("rebuild_actions", []), list):
        errors.append("`change_request.rebuild_actions` 必须是列表。")
    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Buildmate change-request artifact.")
    parser.add_argument("request_file")
    args = parser.parse_args()

    request_path = Path(args.request_file).resolve()
    errors, warnings = validate_change_request(request_path)

    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        sys.exit(1)
    print("OK: change request passed validation.")


if __name__ == "__main__":
    main()
