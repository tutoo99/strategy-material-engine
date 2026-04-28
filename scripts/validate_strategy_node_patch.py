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
    "patch_id",
    "title",
    "status",
    "source_stage2_ref",
    "target_node_id",
    "node_type",
    "date",
]

REQUIRED_SECTIONS = [
    "来源专家模型",
    "节点定义",
    "路由边补丁",
    "资源调用索引",
    "Structured Strategy Node Patch",
]

ALLOWED_NODE_TYPES = {"strategy", "situation", "goal", "resource"}
ALLOWED_SOURCE_TYPES = {"manual", "session", "practicum"}
ALLOWED_EDGE_TYPES = {"goal_strategy", "situation_strategy", "strategy_situation", "strategy_resource"}


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
        r"##\s+Structured Strategy Node Patch\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1).strip()) or {}
    if not isinstance(payload, dict):
        return {}
    patch = payload.get("strategy_node_patch", {})
    return patch if isinstance(patch, dict) else {}


def validate_ref(root: Path, ref: str) -> bool:
    normalized = str(ref).strip()
    if not normalized:
        return False
    return (root / normalized).exists()


def validate_strategy_node_patch(path: Path) -> tuple[list[str], list[str]]:
    root = path.resolve().parent.parent.parent
    meta, body = read_markdown(path)
    sections = {normalize_heading(key): value for key, value in extract_sections(body).items()}
    payload = extract_payload(body)

    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_META_FIELDS:
        if field not in meta:
            errors.append(f"缺少 strategy_node_patch frontmatter 字段：{field}")

    for section in REQUIRED_SECTIONS:
        if normalize_heading(section) not in sections:
            errors.append(f"缺少正文区块：{section}")

    if str(meta.get("artifact_type", "")).strip() != "strategy_node_patch":
        errors.append("`artifact_type` 必须是 `strategy_node_patch`。")
    if str(meta.get("status", "")).strip() not in {"draft", "ready"}:
        errors.append("`status` 必须是 `draft / ready`。")

    node_type = str(meta.get("node_type", "")).strip()
    if node_type not in ALLOWED_NODE_TYPES:
        errors.append("`node_type` 不在允许范围内。")

    source_ref = str(meta.get("source_stage2_ref", "")).strip()
    if not source_ref or not validate_ref(root, source_ref):
        errors.append("`source_stage2_ref` 指向的文件不存在。")

    if not payload:
        errors.append("缺少有效的 `Structured Strategy Node Patch` YAML 区块。")
        return errors, warnings

    if str(payload.get("patch_id", "")).strip() != str(meta.get("patch_id", "")).strip():
        warnings.append("frontmatter 与 structured payload 的 `patch_id` 不一致。")
    if str(payload.get("source_ref", "")).strip() != source_ref:
        warnings.append("frontmatter 与 structured payload 的 `source_ref` 不一致。")

    source_type = str(payload.get("source_type", "")).strip()
    if source_type not in ALLOWED_SOURCE_TYPES:
        errors.append("`strategy_node_patch.source_type` 不在允许范围内。")

    node = payload.get("node", {})
    if not isinstance(node, dict):
        errors.append("`strategy_node_patch.node` 必须是对象。")
    else:
        if not str(node.get("node_id", "")).strip():
            errors.append("`strategy_node_patch.node.node_id` 不能为空。")
        if not str(node.get("node_name", "")).strip():
            errors.append("`strategy_node_patch.node.node_name` 不能为空。")
        if str(node.get("node_type", "")).strip() not in ALLOWED_NODE_TYPES:
            errors.append("`strategy_node_patch.node.node_type` 不在允许范围内。")
        for key in ["trigger_conditions", "applicable_params", "action_refs", "template_refs", "tool_refs", "preferred_case_refs", "evidence_case_refs"]:
            if not isinstance(node.get(key, []), list):
                errors.append(f"`strategy_node_patch.node.{key}` 必须是列表。")
        for case_ref in node.get("preferred_case_refs", []) + node.get("evidence_case_refs", []):
            if str(case_ref).strip() and not validate_ref(root, str(case_ref).strip()):
                errors.append(f"案例引用不存在：{case_ref}")

    proposed_edges = payload.get("proposed_edges", [])
    if not isinstance(proposed_edges, list) or not proposed_edges:
        errors.append("`strategy_node_patch.proposed_edges` 必须是非空列表。")
    else:
        for index, edge in enumerate(proposed_edges, start=1):
            if not isinstance(edge, dict):
                errors.append(f"边补丁 {index} 必须是对象。")
                continue
            if str(edge.get("edge_type", "")).strip() not in ALLOWED_EDGE_TYPES:
                errors.append(f"边补丁 {index} 的 `edge_type` 不在允许范围内。")
            for key in ["from_ref", "to_ref", "reason"]:
                if not str(edge.get(key, "")).strip():
                    errors.append(f"边补丁 {index} 缺少 `{key}`。")
            for key in ["trigger_conditions", "call_output"]:
                if not isinstance(edge.get(key, []), list):
                    errors.append(f"边补丁 {index} 的 `{key}` 必须是列表。")
    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Buildmate strategy node patch artifact.")
    parser.add_argument("patch_file")
    args = parser.parse_args()

    patch_path = Path(args.patch_file).resolve()
    errors, warnings = validate_strategy_node_patch(patch_path)

    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        sys.exit(1)
    print("OK: strategy node patch passed validation.")


if __name__ == "__main__":
    main()
