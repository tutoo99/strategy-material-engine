#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from _buildmate_lib import read_jsonl, read_markdown, slugify, write_markdown
from validate_stage3_session import validate_stage3_session


DEFAULT_GOAL_PROFILES_PATH = "strategy_models/routes/goal_profiles.yaml"
DEFAULT_STRATEGY_PROFILES_PATH = "strategy_models/routes/strategy_profiles.yaml"
DEFAULT_ROUTER_PATH = "strategy_models/router.md"
DEFAULT_OUTPUT_DIR = "strategy_models/sessions"
DEFAULT_AUDIT_DIR = "strategy_models/audits"
DEFAULT_SITUATION_NODES_PATH = "index/stage3/situation_nodes.jsonl"
DEFAULT_SITUATION_STRATEGY_EDGES_PATH = "index/stage3/situation_strategy_edges.jsonl"
DEFAULT_STRATEGY_SITUATION_EDGES_PATH = "index/stage3/strategy_situation_edges.jsonl"

STAGE3_STEPS = [
    ("阶段三（1/7）目标收集", "目标收集", "收集用户本轮最明确的目标"),
    ("阶段三（2/7）情境收敛", "情境收敛", "收敛平台、用户类型、领域和资源约束"),
    ("阶段三（3/7）图谱召回", "图谱召回", "召回与目标最相关的策略节点、资源节点和证据案例"),
    ("阶段三（4/7）路由判断", "路由判断", "判断主策略、组合策略和不适用路径"),
    ("阶段三（5/7）方案包组装", "方案包组装", "把动作包、模板和工具组装成可执行方案"),
    ("阶段三（6/7）校验收口", "校验收口", "校验证据等级、资源引用和会话结构"),
    ("阶段三（7/7）交付执行", "交付执行", "交付 Markdown 方案包与 YAML solution_package"),
]

DEFAULT_FEEDBACK_METRICS = [
    "首轮执行次数",
    "高意图互动数",
    "留资 / 付款信号",
    "需要回流阶段二的异常点",
]


@dataclass
class Stage3RoutingError(RuntimeError):
    failure_mode: str
    detail: str


def emit_progress(stage: str, action: str, next_step: str, eta: str) -> None:
    print(f"当前阶段：{stage}")
    print(f"当前动作：{action}")
    print(f"下一步：{next_step}")
    print(f"预计剩余时间：{eta}")
    print("")


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def load_goal_profiles(path: Path) -> list[dict]:
    return [item for item in load_yaml(path).get("goals", []) if isinstance(item, dict)]


def load_strategy_profiles(path: Path) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for item in load_yaml(path).get("strategies", []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if label:
            profiles[label] = item
    return profiles


def load_resource_catalog(root: Path) -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    resources_root = root / "strategy_models/resources"
    for path in sorted(resources_root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        meta, _body = read_markdown(path)
        resource_id = str(meta.get("resource_id", "")).strip()
        if not resource_id:
            continue
        catalog[resource_id] = {
            "resource_id": resource_id,
            "title": str(meta.get("title", "")).strip(),
            "resource_type": str(meta.get("resource_type", "")).strip(),
            "path": str(path.relative_to(root)),
            "abs_path": str(path.resolve()),
        }
    return catalog


def load_case_catalog(root: Path) -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    cases_dir = root / "assets/cases"
    for path in sorted(cases_dir.glob("*.md")):
        meta, _body = read_markdown(path)
        case_ref = str(path.relative_to(root))
        catalog[case_ref] = {
            "case_ref": case_ref,
            "case_id": str(meta.get("case_id", "")).strip(),
            "title": str(meta.get("title", "")).strip(),
            "status": str(meta.get("status", "")).strip(),
            "platform": str(meta.get("platform", "")).strip(),
            "domain": str(meta.get("domain", "")).strip(),
            "quality_score": float(meta.get("quality_score", 0.0) or 0.0),
            "path": str(path.relative_to(root)),
            "abs_path": str(path.resolve()),
        }
    return catalog


def load_case_meta_catalog(root: Path) -> dict[str, dict]:
    rows = read_jsonl(root / "index/cases/cases_meta.jsonl")
    catalog: dict[str, dict] = {}
    for row in rows:
        case_ref = str(row.get("path", "")).strip()
        if case_ref:
            catalog[case_ref] = row
    return catalog


def load_strategy_nodes(root: Path) -> dict[str, dict]:
    rows = read_jsonl(root / "index/stage3/strategy_nodes.jsonl")
    return {str(row.get("label", "")).strip(): row for row in rows if str(row.get("label", "")).strip()}


def load_situation_nodes(root: Path, path: str = DEFAULT_SITUATION_NODES_PATH) -> dict[str, dict]:
    rows = read_jsonl(root / path)
    return {str(row.get("label", "")).strip(): row for row in rows if str(row.get("label", "")).strip()}


def load_edges_by_key(root: Path, path: str, key: str) -> dict[str, list[dict]]:
    rows = read_jsonl(root / path)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if not value:
            continue
        grouped.setdefault(value, []).append(row)
    return grouped


def normalize_goal(raw_goal: str, goal_profiles: list[dict]) -> dict:
    text = raw_goal.strip()
    best_match: dict | None = None
    best_score = -1
    for goal in goal_profiles:
        label = str(goal.get("label", "")).strip()
        aliases = [label, *[str(item).strip() for item in goal.get("aliases", [])]]
        score = 0
        for alias in aliases:
            if not alias:
                continue
            if text == alias:
                score = max(score, 100 + len(alias))
            elif alias in text:
                score = max(score, 50 + len(alias))
        if score > best_score:
            best_match = goal
            best_score = score
    if best_match is None or best_score <= 0:
        raise Stage3RoutingError("unmatched_goal", f"未找到与目标“{text}”匹配的阶段三目标族。")
    return best_match


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).strip().lower()


def text_similarity(left: str, right: str) -> float:
    left_text = normalize_text(left)
    right_text = normalize_text(right)
    if not left_text or not right_text:
        return 0.0
    ratio = SequenceMatcher(None, left_text, right_text).ratio()
    if left_text == right_text:
        return 1.0
    if left_text in right_text or right_text in left_text:
        ratio = max(ratio, min(len(left_text), len(right_text)) / max(len(left_text), len(right_text)))
    return round(ratio, 4)


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def case_rank(case_ref: str, preferred_case_refs: set[str], case_catalog: dict[str, dict], platform: str, domain: str) -> tuple[int, float, str]:
    item = case_catalog.get(case_ref, {})
    score = 0
    if case_ref in preferred_case_refs:
        score += 6
    status = str(item.get("status", "")).strip()
    if status == "approved":
        score += 4
    elif status == "reviewed":
        score += 2
    elif status == "draft":
        score += 1
    case_platform = str(item.get("platform", "")).strip()
    case_domain = str(item.get("domain", "")).strip()
    if platform and platform in case_platform:
        score += 2
    if domain and domain in case_domain:
        score += 1
    return (-score, -float(item.get("quality_score", 0.0) or 0.0), case_ref)


def select_case_refs(
    selected_strategy_refs: list[str],
    preferred_case_refs: list[str],
    strategy_nodes: dict[str, dict],
    case_catalog: dict[str, dict],
    platform: str,
    domain: str,
    limit: int = 5,
) -> list[str]:
    candidates: list[str] = []
    for case_ref in preferred_case_refs:
        if case_ref in case_catalog:
            candidates.append(case_ref)
    for strategy in selected_strategy_refs:
        node = strategy_nodes.get(strategy, {})
        candidates.extend([str(item).strip() for item in node.get("case_refs", []) if str(item).strip() in case_catalog])
    ranked = sorted(dedupe(candidates), key=lambda item: case_rank(item, set(preferred_case_refs), case_catalog, platform, domain))
    return ranked[:limit]


def select_resource_bundle(
    selected_strategy_refs: list[str],
    strategy_profiles: dict[str, dict],
    strategy_nodes: dict[str, dict],
) -> dict[str, list[str]]:
    action_refs: list[str] = []
    template_refs: list[str] = []
    tool_refs: list[str] = []
    platform_resource_refs: list[str] = []
    for strategy in selected_strategy_refs:
        profile = strategy_profiles[strategy]
        node = strategy_nodes.get(strategy, {})
        action_refs.extend(node.get("action_refs", []))
        template_refs.extend(node.get("template_refs", []))
        tool_refs.extend(node.get("tool_refs", []))
        platform_resource_refs.extend(node.get("platform_resource_refs", []))
        action_refs.extend(profile.get("action_refs", []))
        template_refs.extend(profile.get("template_refs", []))
        tool_refs.extend(profile.get("tool_refs", []))
        platform_resource_refs.extend(profile.get("platform_resource_refs", []))
    return {
        "action_refs": dedupe(action_refs),
        "template_refs": dedupe(template_refs),
        "tool_refs": dedupe(tool_refs),
        "platform_resource_refs": dedupe(platform_resource_refs),
    }


def select_task_case_refs(
    strategy_label: str,
    selected_case_refs: list[str],
    strategy_profiles: dict[str, dict],
    strategy_nodes: dict[str, dict],
) -> list[str]:
    preferred = dedupe(
        [
            *[str(item).strip() for item in strategy_nodes.get(strategy_label, {}).get("preferred_case_refs", [])],
            *[str(item).strip() for item in strategy_profiles[strategy_label].get("preferred_case_refs", [])],
        ]
    )
    hits = [case_ref for case_ref in preferred if case_ref in selected_case_refs]
    return hits[:2] if hits else selected_case_refs[:1]


def determine_evidence(
    selected_case_refs: list[str],
    primary_strategies: list[str],
    strategy_nodes: dict[str, dict],
    case_catalog: dict[str, dict],
) -> tuple[str, str]:
    if not primary_strategies:
        return "bootstrap", "low"

    approved_case_count = sum(1 for case_ref in selected_case_refs if case_catalog.get(case_ref, {}).get("status") == "approved")
    primary_supported = sum(1 for strategy in primary_strategies if int(strategy_nodes.get(strategy, {}).get("approved_case_count", 0) or 0) > 0)
    if primary_supported == len(primary_strategies) and approved_case_count >= 2:
        return "formal", "high"
    if primary_supported >= 1 and approved_case_count >= 1:
        return "formal", "medium"
    return "bootstrap", "low"


def build_situation_context(
    user_type: str,
    selected_strategy_refs: list[str],
    situation_nodes: dict[str, dict],
    situation_strategy_edges: dict[str, list[dict]],
    strategy_situation_edges: dict[str, list[dict]],
) -> dict:
    node = situation_nodes.get(user_type, {})
    matched_edges = situation_strategy_edges.get(user_type, [])
    positive_edges = [edge for edge in matched_edges if str(edge.get("relation", "")).strip() == "particularly_suits"]
    blocked_edges = [edge for edge in matched_edges if str(edge.get("relation", "")).strip() == "not_suitable_for"]
    selected_positive_edges = {
        str(edge.get("to_strategy", "")).strip(): edge
        for edge in positive_edges
        if str(edge.get("to_strategy", "")).strip() in selected_strategy_refs
    }
    selected_strategy_edges = {
        str(edge.get("from_strategy", "")).strip(): edge
        for strategy in selected_strategy_refs
        for edge in strategy_situation_edges.get(strategy, [])
        if str(edge.get("to_situation", "")).strip() == user_type
        and str(edge.get("relation", "")).strip() == "particularly_suits"
    }
    return {
        "node": node,
        "selected_positive_edges": selected_positive_edges,
        "selected_strategy_edges": selected_strategy_edges,
        "blocked_edges": blocked_edges,
    }


def remove_blocked_strategies(
    user_type: str,
    primary: list[str],
    secondary: list[str],
    situation_strategy_edges: dict[str, list[dict]],
) -> tuple[list[str], list[str]]:
    blocked_strategy_refs = {
        str(edge.get("to_strategy", "")).strip()
        for edge in situation_strategy_edges.get(user_type, [])
        if str(edge.get("relation", "")).strip() == "not_suitable_for"
    }
    filtered_primary = [strategy for strategy in primary if strategy not in blocked_strategy_refs]
    filtered_secondary = [strategy for strategy in secondary if strategy not in blocked_strategy_refs and strategy not in filtered_primary]
    if not filtered_primary and filtered_secondary:
        filtered_primary = [filtered_secondary[0]]
        filtered_secondary = filtered_secondary[1:]
    return filtered_primary, filtered_secondary


def build_route_notes(
    goal_profile: dict,
    selected_strategy_refs: list[str],
    strategy_profiles: dict[str, dict],
    strategy_nodes: dict[str, dict],
    constraints: list[str],
    situation_context: dict | None = None,
) -> str:
    lines = []
    selected_positive_edges = situation_context.get("selected_positive_edges", {}) if situation_context else {}
    selected_strategy_edges = situation_context.get("selected_strategy_edges", {}) if situation_context else {}
    situation_node = situation_context.get("node", {}) if situation_context else {}
    for index, strategy in enumerate(selected_strategy_refs, start=1):
        profile = strategy_profiles[strategy]
        node = strategy_nodes.get(strategy, {})
        relation = "是实现→" if strategy in [str(item).strip() for item in goal_profile.get("primary_strategies", [])] else "组合补充→"
        trigger_conditions = [
            f"用户目标={goal_profile.get('label', '')}",
            *[f"平台优先={item}" for item in goal_profile.get("preferred_platforms", []) if str(item).strip()],
            *[f"用户类型优先={item}" for item in goal_profile.get("preferred_user_types", []) if str(item).strip()],
            *[f"领域优先={item}" for item in goal_profile.get("preferred_domains", []) if str(item).strip()],
        ]
        applicable_params = constraints or [str(item).strip() for item in profile.get("activation_rules", []) if str(item).strip()]
        call_output = dedupe(
            [
                *[str(item).strip() for item in node.get("action_refs", [])],
                *[str(item).strip() for item in node.get("template_refs", [])],
                *[str(item).strip() for item in node.get("tool_refs", [])],
            ]
        )
        situation_edge = selected_positive_edges.get(strategy, {})
        strategy_edge = selected_strategy_edges.get(strategy, {})
        lines.extend(
            [
                f"### 路由节点 {index}：{strategy}",
                f"- **边关系：** `(目标:{goal_profile.get('label', '')}) --【{relation}】--> (策略:{strategy})`",
                (
                    f"- **情境关系：** `(策略:{strategy}) --【特别适用于→】--> "
                    f"(情境:{situation_node.get('situation_id', '待补充')} {situation_node.get('label', '')})`"
                    if situation_edge or strategy_edge
                    else "- **情境关系：** 无"
                ),
                f"- **策略摘要：** {profile.get('summary', '待补充')}",
                f"- **命中原因：** {'；'.join(profile.get('activation_rules', [])) or '待补充'}",
                f"- **情境命中原因：** {situation_edge.get('reason', '') or strategy_edge.get('reason', '无')}",
                f"- **触发条件：** {'；'.join(trigger_conditions)}",
                f"- **适用参数：** {'；'.join(applicable_params) if applicable_params else '待补充'}",
                f"- **不适用提醒：** {'；'.join(profile.get('not_applicable_rules', [])) or '无'}",
                f"- **调用产出：** {', '.join(call_output) if call_output else '无'}",
                f"- **证据病例数：** `{int(node.get('evidence_case_count', 0) or 0)}`",
                f"- **其中 approved：** `{int(node.get('approved_case_count', 0) or 0)}`",
                "",
            ]
        )
    blocked_edges = situation_context.get("blocked_edges", []) if situation_context else []
    if blocked_edges:
        lines.extend(["### 情境禁区路径"])
        for edge in blocked_edges:
            fallback_strategy_refs = [str(item).strip() for item in edge.get("call_output", {}).get("fallback_strategy_refs", []) if str(item).strip()]
            lines.extend(
                [
                    f"- **禁区边：** `(策略:{edge.get('to_strategy', '')}) --【不适用于→】--> "
                    f"(情境:{edge.get('from_situation_id', '')} {edge.get('from_situation', '')})`",
                    f"- **禁区原因：** {edge.get('reason', '无')}",
                    f"- **触发条件：** {'；'.join(str(item).strip() for item in edge.get('trigger_conditions', []) if str(item).strip()) or '无'}",
                    f"- **警报：** {edge.get('not_applicable_warning', '无')}",
                    f"- **替代策略：** {', '.join(fallback_strategy_refs) if fallback_strategy_refs else '无'}",
                    "",
                ]
            )
    return "\n".join(lines).strip()


def build_assembly_logic(
    selected_strategy_refs: list[str],
    resource_bundle: dict[str, list[str]],
    resource_catalog: dict[str, dict],
    autonomous_learning: dict | None = None,
) -> str:
    lines = [
        "- 先按目标族拿主策略和组合策略，再按当前平台 / 用户类型 / 资源约束过滤。",
        "- 资源包只调用已登记的 AP / TR / TC，不直接把平台资源词当动作包。",
        "- 证据优先级：approved > reviewed > draft。",
    ]
    if autonomous_learning:
        lines.append("- 标准路由失败后，系统进入自治审计，并在现有证据上自动合成 bootstrap 路径。")
    lines.extend(["", "### 已组装资源"])
    for key, label in [
        ("action_refs", "动作包"),
        ("template_refs", "模板资源"),
        ("tool_refs", "工具调用"),
    ]:
        refs = resource_bundle.get(key, [])
        if not refs:
            continue
        lines.append(f"- **{label}：**")
        for resource_id in refs:
            item = resource_catalog.get(resource_id, {})
            lines.append(f"  - `{resource_id}` {item.get('title', '')} -> {item.get('path', '')}")
    if resource_bundle.get("platform_resource_refs"):
        lines.append(f"- **平台资源词：** {', '.join(resource_bundle['platform_resource_refs'])}")
    return "\n".join(lines).strip()


def build_tasks(
    primary_strategies: list[str],
    secondary_strategies: list[str],
    selected_case_refs: list[str],
    strategy_profiles: dict[str, dict],
    strategy_nodes: dict[str, dict],
) -> list[dict]:
    tasks: list[dict] = []
    ordered_strategies = [*primary_strategies, *secondary_strategies]
    for index, strategy in enumerate(ordered_strategies, start=1):
        profile = strategy_profiles[strategy]
        node = strategy_nodes.get(strategy, {})
        task_case_refs = select_task_case_refs(strategy, selected_case_refs, strategy_profiles, strategy_nodes)
        resource_refs = dedupe(
            [
                *[str(item).strip() for item in node.get("action_refs", [])],
                *[str(item).strip() for item in node.get("template_refs", [])],
                *[str(item).strip() for item in node.get("tool_refs", [])],
                *[str(item).strip() for item in profile.get("action_refs", [])],
                *[str(item).strip() for item in profile.get("template_refs", [])],
                *[str(item).strip() for item in profile.get("tool_refs", [])],
            ]
        )
        tasks.append(
            {
                "id": f"T{index}",
                "title": str(profile.get("task_title", "")).strip(),
                "strategy_ref": strategy,
                "action": str(profile.get("task_action", "")).strip(),
                "resource_refs": resource_refs,
                "case_refs": task_case_refs,
                "estimated_time": str(profile.get("estimated_time", "")).strip(),
                "success_check": str(profile.get("success_check", "")).strip(),
            }
        )
    return tasks


def format_task_markdown(tasks: list[dict]) -> str:
    lines: list[str] = []
    for task in tasks:
        lines.extend(
            [
                f"### 任务 {task['id']}：{task['title']}",
                f"- **动作：** {task['action']}",
                f"- **策略引用：** `{task['strategy_ref']}`",
                f"- **资源引用：** {', '.join(f'`{item}`' for item in task['resource_refs'])}",
                f"- **参考案例：** {', '.join(f'`{item}`' for item in task['case_refs'])}",
                f"- **预计耗时：** {task['estimated_time']}",
                f"- **成功检查：** {task['success_check']}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def markdown_link(label: str, target: str) -> str:
    return f"[{label}]({target})"


def resource_link_action(resource_type: str) -> str:
    if resource_type == "action_pack":
        return "点击查看"
    if resource_type == "template_resource":
        return "点击使用"
    if resource_type == "tool_call":
        return "点击配置"
    return "点击打开"


def resource_display_role(resource_type: str) -> str:
    if resource_type == "action_pack":
        return "执行SOP"
    if resource_type == "template_resource":
        return "模板库"
    if resource_type == "tool_call":
        return "工具配置"
    return "资源文件"


def build_resource_packages(tasks: list[dict], resource_catalog: dict[str, dict]) -> list[dict]:
    packages: list[dict] = []
    icons = ["📦", "⚙️", "🧩", "🛠️", "🗂️"]
    for index, task in enumerate(tasks, start=1):
        resources: list[dict] = []
        for resource_id in task.get("resource_refs", []):
            item = resource_catalog.get(resource_id, {})
            if not item:
                continue
            resources.append(
                {
                    "resource_id": resource_id,
                    "title": str(item.get("title", "")).strip(),
                    "resource_type": str(item.get("resource_type", "")).strip(),
                    "path": str(item.get("path", "")).strip(),
                    "abs_path": str(item.get("abs_path", "")).strip(),
                    "display_role": resource_display_role(str(item.get("resource_type", "")).strip()),
                    "link_action": resource_link_action(str(item.get("resource_type", "")).strip()),
                }
            )
        packages.append(
            {
                "package_id": f"PKG{index:02d}",
                "icon": icons[(index - 1) % len(icons)],
                "title": str(task.get("title", "")).strip(),
                "strategy_ref": str(task.get("strategy_ref", "")).strip(),
                "action": str(task.get("action", "")).strip(),
                "estimated_time": str(task.get("estimated_time", "")).strip(),
                "success_check": str(task.get("success_check", "")).strip(),
                "resources": resources,
                "case_refs": [str(item).strip() for item in task.get("case_refs", []) if str(item).strip()],
            }
        )
    return packages


def format_case_link(case_ref: str, case_catalog: dict[str, dict]) -> str:
    item = case_catalog.get(case_ref, {})
    if not item:
        return f"`{case_ref}`"
    link = markdown_link("点击查看", str(item.get("abs_path", "")).strip() or str(item.get("path", "")).strip())
    case_id = str(item.get("case_id", "")).strip()
    title = str(item.get("title", "")).strip() or case_ref
    if case_id:
        return f"{link} `{case_id}` - {title}"
    return f"{link} {title}"


def build_route_path(goal_profile: dict, situation_context: dict, primary_strategies: list[str], secondary_strategies: list[str]) -> str:
    situation_node = situation_context.get("node", {}) if situation_context else {}
    situation_id = str(situation_node.get("situation_id", "")).strip() or "S_UNKNOWN"
    situation_label = str(situation_node.get("label", "")).strip() or "待补充"
    goal_id = str(goal_profile.get("goal_id", "")).strip() or f"G_{slugify(str(goal_profile.get('label', '')).strip())}"
    goal_label = str(goal_profile.get("label", "")).strip() or "待补充"
    primary_text = "、".join(primary_strategies) if primary_strategies else "无"
    route = f"情境({situation_id} {situation_label}) -> 目标({goal_id} {goal_label}) -> 首选策略({primary_text})"
    if secondary_strategies:
        route += f" -> 组合策略({'、'.join(secondary_strategies)})"
    return route


def build_dynamic_package_markdown(
    goal_profile: dict,
    situation_context: dict,
    primary_strategies: list[str],
    secondary_strategies: list[str],
    selected_case_refs: list[str],
    tasks: list[dict],
    resource_catalog: dict[str, dict],
    case_catalog: dict[str, dict],
    risk_notes: list[str],
) -> tuple[str, list[dict]]:
    resource_packages = build_resource_packages(tasks, resource_catalog)
    lines = [
        "## 为你动态组装的作战方案包",
        "",
        f"**推演路径**：{build_route_path(goal_profile, situation_context, primary_strategies, secondary_strategies)}",
        "",
        "**方案包内容**：",
        "",
    ]
    for index, package in enumerate(resource_packages, start=1):
        lines.append(f"### {package['icon']} 资源包{index}：{package['title']}")
        for resource in package["resources"]:
            link = markdown_link(resource["link_action"], resource["abs_path"] or resource["path"])
            lines.append(
                f"- **{resource['display_role']}**：{link} `{resource['resource_id']}` - {resource['title']}"
            )
        lines.extend(
            [
                f"- **绑定策略**：`{package['strategy_ref']}`",
                f"- **执行动作**：{package['action']}",
                f"- **预计耗时**：{package['estimated_time'] or '待补充'}",
                f"- **成功检查**：{package['success_check'] or '待补充'}",
                "",
            ]
        )

    lines.append("### 📄 关联案例")
    case_refs = selected_case_refs[:3]
    count = len(case_refs)
    if case_refs:
        lines.append(f"- 这是与您情况最相似的 {count} 个案例复盘，供您参考执行细节。")
        for case_ref in case_refs:
            lines.append(f"- {format_case_link(case_ref, case_catalog)}")
    else:
        lines.append("- 当前未召回到可展示的关联案例。")
    lines.append("")

    lines.append("### 🚨 风险提示")
    blocked_edges = situation_context.get("blocked_edges", []) if situation_context else []
    if blocked_edges:
        for edge in blocked_edges:
            fallback_strategy_refs = [str(item).strip() for item in edge.get("call_output", {}).get("fallback_strategy_refs", []) if str(item).strip()]
            fallback_text = f" 建议优先改走：{'、'.join(fallback_strategy_refs)}。" if fallback_strategy_refs else ""
            lines.append(
                f"- 根据您的情境参数，系统检测到【{edge.get('to_strategy', '待补充')}】策略当前不适用，请勿轻易尝试。"
                f"{edge.get('reason', '')}{fallback_text}"
            )
    for risk in risk_notes:
        lines.append(f"- {risk}")

    return "\n".join(lines).strip(), resource_packages


def build_progress_blocks() -> tuple[str, int, str]:
    started_at = datetime.now().replace(second=0, microsecond=0)
    lines: list[str] = []
    for index, (stage, step, action) in enumerate(STAGE3_STEPS, start=1):
        time_text = (started_at + timedelta(minutes=index - 1)).strftime("%Y-%m-%d %H:%M")
        next_step = STAGE3_STEPS[index][1] if index < len(STAGE3_STEPS) else "无需再提供，等待方案执行反馈"
        lines.extend(
            [
                f"### 进度播报 {index}",
                f"- **时间：** {time_text}",
                f"- **触发类型：** {'stage_start' if index == 1 else 'key_step_start'}",
                f"- **当前阶段：** {stage}",
                f"- **当前步骤：** {step}",
                f"- **当前动作：** {action}",
                f"- **下一步需要你提供：** {next_step}",
                f"- **预计剩余时间：** 约 {max(1, len(STAGE3_STEPS) - index + 1)} 分钟内",
                "",
            ]
        )
    return "\n".join(lines).strip(), len(STAGE3_STEPS), (started_at + timedelta(minutes=len(STAGE3_STEPS) - 1)).strftime("%Y-%m-%d %H:%M")


def build_session_body(
    raw_goal: str,
    goal_profile: dict,
    user_type: str,
    platform: str,
    domain: str,
    constraints: list[str],
    situation_context: dict,
    selected_case_refs: list[str],
    primary_strategies: list[str],
    secondary_strategies: list[str],
    evidence_status: str,
    route_confidence: str,
    route_notes: str,
    assembly_logic: str,
    tasks: list[dict],
    resource_bundle: dict[str, list[str]],
    resource_catalog: dict[str, dict],
    case_catalog: dict[str, dict],
    risk_notes: list[str],
    feedback_metrics: list[str],
    autonomous_learning: dict | None = None,
) -> str:
    dynamic_package_markdown, resource_packages = build_dynamic_package_markdown(
        goal_profile=goal_profile,
        situation_context=situation_context,
        primary_strategies=primary_strategies,
        secondary_strategies=secondary_strategies,
        selected_case_refs=selected_case_refs,
        tasks=tasks,
        resource_catalog=resource_catalog,
        case_catalog=case_catalog,
        risk_notes=risk_notes,
    )
    solution_package = {
        "solution_package": {
            "target_goal": raw_goal,
            "normalized_goal": str(goal_profile.get("label", "")).strip(),
            "route_path": build_route_path(goal_profile, situation_context, primary_strategies, secondary_strategies),
            "evidence_status": evidence_status,
            "evidence_case_count": len(selected_case_refs),
            "route_confidence": route_confidence,
            "primary_strategy": primary_strategies[0],
            "secondary_strategies": secondary_strategies,
            "case_refs": selected_case_refs,
            "resource_bundle": resource_bundle,
            "resource_packages": resource_packages,
            "tasks": tasks,
            "risks": risk_notes,
            "feedback_metrics": feedback_metrics,
        }
    }
    if autonomous_learning:
        solution_package["solution_package"]["autonomous_learning"] = autonomous_learning

    solution_yaml = yaml.safe_dump(solution_package, allow_unicode=True, sort_keys=False).strip()
    progress_blocks, _count, _last_progress_at = build_progress_blocks()
    situation_node = situation_context.get("node", {}) if situation_context else {}
    blocked_edges = situation_context.get("blocked_edges", []) if situation_context else []
    blocked_strategy_labels = [str(edge.get("to_strategy", "")).strip() for edge in blocked_edges if str(edge.get("to_strategy", "")).strip()]

    lines = [
        f"# 【策略推演会话】{platform} / {goal_profile.get('label', '')}",
        "",
        "## 用户原始目标",
        "",
        f"- {raw_goal}",
        "",
        "## 收敛后的标准目标",
        "",
        f"- **目标：** {raw_goal}",
        f"- **目标族：** {goal_profile.get('label', '')}",
        f"- **平台：** {platform}",
        f"- **用户类型：** {user_type}",
        "",
        "## 用户情境卡",
        "",
        f"- **情境节点：** {situation_node.get('situation_id', '待补充')} / {situation_node.get('label', user_type) or user_type}",
        f"- **情境标题：** {situation_node.get('title', user_type) or user_type}",
        f"- **情境定义：** {situation_node.get('summary', '待补充')}",
        f"- **平台：** {platform}",
        f"- **用户类型：** {user_type}",
        f"- **业务领域：** {domain}",
        f"- **资源特征：** {', '.join(situation_node.get('resource_features', [])) if situation_node.get('resource_features') else '待补充'}",
        f"- **技能特征：** {', '.join(situation_node.get('skill_features', [])) if situation_node.get('skill_features') else '待补充'}",
        f"- **心理特征：** {', '.join(situation_node.get('psychological_features', [])) if situation_node.get('psychological_features') else '待补充'}",
        f"- **代表案例：** {', '.join(f'`{item}`' for item in situation_node.get('representative_case_refs', [])) if situation_node.get('representative_case_refs') else '无'}",
        f"- **默认约束：** {', '.join(situation_node.get('default_constraints', [])) if situation_node.get('default_constraints') else '无'}",
        f"- **资源约束：** {', '.join(constraints) if constraints else '默认按当前输入处理'}",
        f"- **情境禁区：** {', '.join(blocked_strategy_labels) if blocked_strategy_labels else '无'}",
        f"- **不适合路径：** {'；'.join(risk_notes[:2]) if risk_notes else '无'}",
        "",
        "## 图谱召回记录",
        "",
    ]
    for index, case_ref in enumerate(selected_case_refs, start=1):
        lines.append(f"{index}. `{case_ref}`")
    lines.extend(
        [
            "",
            "## 路由判断记录",
            "",
            route_notes,
            "",
            "## 证据状态",
            "",
            f"- **证据级别：** `{evidence_status}`",
            f"- **证据病例数：** `{len(selected_case_refs)}`",
            f"- **路由置信度：** `{route_confidence}`",
            "",
            "## 方案包组装逻辑",
            "",
            assembly_logic,
            "",
        ]
    )
    if autonomous_learning:
        lines.extend(
            [
                "## 自主学习记录",
                "",
                f"- **触发原因：** {autonomous_learning.get('trigger_reason', '标准路由失败后自动进入自治审计')}",
                f"- **缺口分类：** `{autonomous_learning.get('gap_type', '待补充')}`",
                f"- **阶段二反问结果：** {autonomous_learning.get('stage2_result', '待补充')}",
                f"- **阶段一补库状态：** {autonomous_learning.get('stage1_result', '待补充')}",
                f"- **自治审计文件：** `{autonomous_learning.get('audit_ref', '待补充')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Markdown 方案包",
            "",
            dynamic_package_markdown,
            "",
            "## Structured Solution Package",
            "",
            "```yaml",
            solution_yaml,
            "```",
            "",
            "## 风险提示",
            "",
        ]
    )
    for risk in risk_notes:
        lines.append(f"- {risk}")
    lines.extend(["", "## 7天执行反馈指标", ""])
    for item in feedback_metrics:
        lines.append(f"- {item}")
    lines.extend(["", "## 进度播报记录", "", progress_blocks])
    return "\n".join(lines).strip()


def build_delivery_summary(
    session_path: Path,
    evidence_status: str,
    route_confidence: str,
    primary_strategies: list[str],
    resource_bundle: dict[str, list[str]],
    audit_path: Path | None = None,
    delivery_mode: str = "standard",
) -> str:
    lines = [
        "当前阶段：阶段三（完成）",
        "当前动作：交付阶段三策略推演会话与正式方案包",
        "交付方式：会话文件路径 + 证据状态 + 主策略 + 资源包摘要",
        f"会话文件：{session_path}",
        f"证据状态：{evidence_status}",
        f"路由置信度：{route_confidence}",
        f"主策略：{', '.join(primary_strategies)}",
        f"动作包数量：{len(resource_bundle['action_refs'])}",
        f"模板数量：{len(resource_bundle['template_refs'])}",
        f"工具数量：{len(resource_bundle['tool_refs'])}",
        f"交付模式：{delivery_mode}",
    ]
    if audit_path is not None:
        lines.append(f"自治审计：{audit_path}")
    return "\n".join(lines)


def build_replenishment_search_brief(raw_goal: str, platform: str, domain: str, user_type: str, strategy_refs: list[str]) -> str:
    parts = [platform, domain, user_type, raw_goal, "已商业化验证", "阶段三补库"]
    if strategy_refs:
        parts.append("策略词：" + " / ".join(strategy_refs))
    return " / ".join([item for item in parts if item])


def rank_goal_profiles(raw_goal: str, goal_profiles: list[dict], platform: str, domain: str, user_type: str) -> list[dict]:
    ranked: list[dict] = []
    for goal in goal_profiles:
        label = str(goal.get("label", "")).strip()
        aliases = [label, *[str(item).strip() for item in goal.get("aliases", [])]]
        score = max(text_similarity(raw_goal, alias) for alias in aliases if alias)
        if platform and platform in [str(item).strip() for item in goal.get("preferred_platforms", [])]:
            score += 0.08
        if domain and domain in [str(item).strip() for item in goal.get("preferred_domains", [])]:
            score += 0.06
        if user_type and user_type in [str(item).strip() for item in goal.get("preferred_user_types", [])]:
            score += 0.06
        ranked.append({"goal": goal, "label": label, "score": round(score, 4)})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def rank_strategy_profiles(raw_goal: str, strategy_profiles: dict[str, dict], platform: str, domain: str, user_type: str) -> list[dict]:
    ranked: list[dict] = []
    for label, profile in strategy_profiles.items():
        texts = [
            label,
            str(profile.get("summary", "")).strip(),
            str(profile.get("task_title", "")).strip(),
            str(profile.get("task_action", "")).strip(),
            " ".join(str(item).strip() for item in profile.get("activation_rules", [])),
        ]
        score = max(text_similarity(raw_goal, text) for text in texts if text)
        applicable_platforms = [str(item).strip() for item in profile.get("applicable_platforms", [])]
        applicable_domains = [str(item).strip() for item in profile.get("applicable_domains", [])]
        applicable_user_types = [str(item).strip() for item in profile.get("applicable_user_types", [])]
        if platform and platform in applicable_platforms:
            score += 0.1
        elif platform and applicable_platforms:
            score -= 0.08
        if domain and domain in applicable_domains:
            score += 0.08
        elif domain and applicable_domains:
            score -= 0.05
        if user_type and user_type in applicable_user_types:
            score += 0.08
        elif user_type and applicable_user_types:
            score -= 0.03
        ranked.append({"label": label, "profile": profile, "score": round(score, 4)})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def case_status_weight(status: str) -> float:
    if status == "approved":
        return 1.2
    if status == "reviewed":
        return 0.9
    if status == "draft":
        return 0.7
    return 0.5


def rank_case_candidates(raw_goal: str, case_meta_catalog: dict[str, dict], platform: str, domain: str, limit: int = 5) -> list[dict]:
    ranked: list[dict] = []
    for case_ref, item in case_meta_catalog.items():
        texts = [
            str(item.get("title", "")).strip(),
            str(item.get("result_summary", "")).strip(),
            str(item.get("search_text", "")).strip(),
            " ".join(str(value).strip() for value in item.get("strategy_tags", [])),
            " ".join(str(value).strip() for value in item.get("symptoms", [])),
        ]
        score = max(text_similarity(raw_goal, text) for text in texts if text)
        item_platform = str(item.get("platform", "")).strip()
        item_domain = str(item.get("domain", "")).strip()
        platform_match = bool(platform and platform in item_platform)
        domain_match = bool(domain and domain in item_domain)
        if platform_match:
            score += 0.12
        if domain_match:
            score += 0.08
        status = str(item.get("status", "")).strip()
        score *= case_status_weight(status)
        ranked.append(
            {
                "case_ref": case_ref,
                "title": str(item.get("title", "")).strip(),
                "status": status,
                "strategy_tags": [str(value).strip() for value in item.get("strategy_tags", []) if str(value).strip()],
                "resource_refs": [str(value).strip() for value in item.get("resource_refs", []) if str(value).strip()],
                "platform_match": platform_match,
                "domain_match": domain_match,
                "score": round(score, 4),
            }
        )
    ranked.sort(key=lambda item: (item["score"], 1 if item["status"] == "approved" else 0), reverse=True)
    filtered = [item for item in ranked if item["score"] >= 0.2 and (item["platform_match"] or item["domain_match"] or item["score"] >= 0.55)]
    if not filtered:
        filtered = [item for item in ranked if item["score"] >= 0.4]
    return filtered[:limit]


def select_synthesized_strategy_refs(
    case_candidates: list[dict],
    strategy_rankings: list[dict],
    strategy_profiles: dict[str, dict],
    limit: int = 3,
) -> list[str]:
    score_map: dict[str, float] = {}
    for candidate in case_candidates:
        weight = float(candidate.get("score", 0.0) or 0.0)
        for tag in candidate.get("strategy_tags", []):
            if tag not in strategy_profiles:
                continue
            score_map[tag] = score_map.get(tag, 0.0) + weight
    for rank in strategy_rankings[:6]:
        label = str(rank.get("label", "")).strip()
        if label not in strategy_profiles:
            continue
        score_map[label] = score_map.get(label, 0.0) + float(rank.get("score", 0.0) or 0.0)
    ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    return [label for label, _score in ranked[:limit]]


def infer_gap_type(
    failure_mode: str,
    best_goal_score: float,
    case_candidates: list[dict],
    selected_strategy_refs: list[str],
) -> tuple[str, str]:
    if not case_candidates:
        return "stage1_evidence_gap", "stage1_replenishment_only"
    same_platform_case_count = sum(1 for item in case_candidates if item.get("platform_match"))
    if same_platform_case_count <= 0:
        return "stage1_evidence_gap", "stage1_replenishment_only"
    if not selected_strategy_refs:
        return "stage3_route_gap", "stage1_replenishment_only"
    if failure_mode == "unmatched_goal" and best_goal_score >= 0.55:
        return "stage2_translation_gap", "synthesized_bootstrap"
    if failure_mode == "unmatched_goal":
        return "stage3_route_gap", "synthesized_bootstrap"
    if failure_mode == "zero_case_recall":
        return "mixed", "synthesized_bootstrap"
    return "mixed", "synthesized_bootstrap"


def build_stage2_result(gap_type: str, raw_goal: str, suggested_goal: str) -> str:
    if gap_type == "stage2_translation_gap":
        return f"系统判定阶段二目标翻译过窄，已自动把“{raw_goal}”重写为“{suggested_goal}”后重试。"
    if gap_type == "stage3_route_gap":
        return f"系统判定阶段二问题理解基本正确，但阶段三未配置该目标族，已用现有证据自动合成“{suggested_goal}”路径。"
    if gap_type == "mixed":
        return f"系统同时发现目标翻译和证据召回都偏弱，先按“{suggested_goal}”生成 bootstrap 路径，并继续挂起补库。"
    return "阶段二无需修正。"


def build_stage1_result(gap_type: str, approved_case_count: int) -> str:
    if gap_type == "stage1_evidence_gap":
        return "现有阶段一基因库没有足够证据，系统已自动开启补库工单。"
    if approved_case_count <= 0:
        return "虽然命中到相关案例，但没有 approved 证据，系统已自动挂起阶段一补库以提升可靠性。"
    if approved_case_count < 2:
        return "现有证据可以先合成 bootstrap，但 approved 证据仍偏少，系统已并行挂起补库。"
    return "当前证据可支撑本轮输出，阶段一无需立即补库。"


def build_synthesized_goal_profile(
    raw_goal: str,
    ranked_goals: list[dict],
    selected_strategy_refs: list[str],
    case_candidates: list[dict],
) -> dict:
    best_goal = ranked_goals[0] if ranked_goals else {}
    best_goal_payload = best_goal.get("goal", {}) if isinstance(best_goal.get("goal"), dict) else {}
    label = str(best_goal_payload.get("label", "")).strip()
    goal_id = str(best_goal_payload.get("goal_id", "")).strip()
    if not label or float(best_goal.get("score", 0.0) or 0.0) < 0.55:
        label = f"自主合成：{raw_goal}"
        goal_id = goal_id or f"G_{slugify(label)}"

    risk_notes = dedupe(
        [str(item).strip() for item in best_goal_payload.get("risk_notes", []) if str(item).strip()]
        + [
            "当前方案由阶段三自治学习链路自动合成，优先作为 bootstrap 路径执行。",
            "若 7 天内关键指标没有改善，系统应回流阶段二重新诊断，并继续扩大阶段一证据池。",
        ]
    )
    feedback_metrics = [str(item).strip() for item in best_goal_payload.get("feedback_metrics", []) if str(item).strip()]
    if not feedback_metrics:
        feedback_metrics = list(DEFAULT_FEEDBACK_METRICS)

    preferred_case_refs = [str(item.get("case_ref", "")).strip() for item in case_candidates if str(item.get("case_ref", "")).strip()]
    return {
        "goal_id": goal_id or f"G_{slugify(label)}",
        "label": label,
        "primary_strategies": selected_strategy_refs[:1],
        "secondary_strategies": selected_strategy_refs[1:],
        "preferred_case_refs": preferred_case_refs,
        "risk_notes": risk_notes,
        "feedback_metrics": feedback_metrics,
        "_autonomous_synthesized": True,
    }


def build_route_payload(
    raw_goal: str,
    goal_profile: dict,
    strategy_profiles: dict[str, dict],
    strategy_nodes: dict[str, dict],
    situation_nodes: dict[str, dict],
    situation_strategy_edges: dict[str, list[dict]],
    strategy_situation_edges: dict[str, list[dict]],
    case_catalog: dict[str, dict],
    resource_catalog: dict[str, dict],
    user_type: str,
    platform: str,
    domain: str,
    constraints: list[str],
    primary_strategies: list[str] | None = None,
    secondary_strategies: list[str] | None = None,
    selected_case_refs: list[str] | None = None,
    autonomous_learning: dict | None = None,
) -> dict:
    primary = dedupe(primary_strategies if primary_strategies is not None else [item for item in goal_profile.get("primary_strategies", []) if item in strategy_profiles])
    secondary = dedupe(secondary_strategies if secondary_strategies is not None else [item for item in goal_profile.get("secondary_strategies", []) if item in strategy_profiles and item not in primary])
    primary, secondary = remove_blocked_strategies(user_type, primary, secondary, situation_strategy_edges)
    selected_strategy_refs = dedupe([*primary, *secondary])
    if not selected_strategy_refs:
        raise Stage3RoutingError("no_strategy_candidates", "阶段三无法为当前目标选出任何正式策略。")

    if selected_case_refs is None:
        preferred_case_refs = [str(item).strip() for item in goal_profile.get("preferred_case_refs", [])]
        selected_case_refs = select_case_refs(
            selected_strategy_refs=selected_strategy_refs,
            preferred_case_refs=preferred_case_refs,
            strategy_nodes=strategy_nodes,
            case_catalog=case_catalog,
            platform=platform,
            domain=domain,
        )

    if not selected_case_refs:
        raise Stage3RoutingError("zero_case_recall", "当前目标没有召回到任何阶段三证据案例。")

    evidence_status, route_confidence = determine_evidence(
        selected_case_refs=selected_case_refs,
        primary_strategies=primary,
        strategy_nodes=strategy_nodes,
        case_catalog=case_catalog,
    )
    if autonomous_learning:
        evidence_status = "bootstrap"
        if route_confidence == "high":
            route_confidence = "medium"

    resource_bundle = select_resource_bundle(
        selected_strategy_refs=selected_strategy_refs,
        strategy_profiles=strategy_profiles,
        strategy_nodes=strategy_nodes,
    )
    situation_context = build_situation_context(
        user_type=user_type,
        selected_strategy_refs=selected_strategy_refs,
        situation_nodes=situation_nodes,
        situation_strategy_edges=situation_strategy_edges,
        strategy_situation_edges=strategy_situation_edges,
    )
    selected_resource_refs = dedupe([*resource_bundle["action_refs"], *resource_bundle["template_refs"], *resource_bundle["tool_refs"]])
    route_notes = build_route_notes(
        goal_profile=goal_profile,
        selected_strategy_refs=selected_strategy_refs,
        strategy_profiles=strategy_profiles,
        strategy_nodes=strategy_nodes,
        constraints=constraints,
        situation_context=situation_context,
    )
    tasks = build_tasks(
        primary_strategies=primary,
        secondary_strategies=secondary,
        selected_case_refs=selected_case_refs,
        strategy_profiles=strategy_profiles,
        strategy_nodes=strategy_nodes,
    )
    risk_notes = dedupe(
        [str(item).strip() for item in goal_profile.get("risk_notes", [])]
        + (["当前路径含有 draft 证据，属于 bootstrap 内测版方案。"] if evidence_status == "bootstrap" else [])
    )
    feedback_metrics = [str(item).strip() for item in goal_profile.get("feedback_metrics", []) if str(item).strip()] or list(DEFAULT_FEEDBACK_METRICS)
    assembly_logic = build_assembly_logic(selected_strategy_refs, resource_bundle, resource_catalog, autonomous_learning=autonomous_learning)

    body = build_session_body(
        raw_goal=raw_goal,
        goal_profile=goal_profile,
        user_type=user_type,
        platform=platform,
        domain=domain,
        constraints=constraints,
        situation_context=situation_context,
        selected_case_refs=selected_case_refs,
        primary_strategies=primary,
        secondary_strategies=secondary,
        evidence_status=evidence_status,
        route_confidence=route_confidence,
        route_notes=route_notes,
        assembly_logic=assembly_logic,
        tasks=tasks,
        resource_bundle=resource_bundle,
        resource_catalog=resource_catalog,
        case_catalog=case_catalog,
        risk_notes=risk_notes,
        feedback_metrics=feedback_metrics,
        autonomous_learning=autonomous_learning,
    )
    return {
        "goal_profile": goal_profile,
        "selected_strategy_refs": selected_strategy_refs,
        "selected_case_refs": selected_case_refs,
        "selected_resource_refs": selected_resource_refs,
        "primary_strategies": primary,
        "secondary_strategies": secondary,
        "situation_context": situation_context,
        "evidence_status": evidence_status,
        "route_confidence": route_confidence,
        "resource_bundle": resource_bundle,
        "body": body,
    }


def write_stage3_session(
    root: Path,
    output_dir: str,
    router_ref: str,
    raw_goal: str,
    route_payload: dict,
    user_type: str,
    platform: str,
    domain: str,
    constraints: list[str],
    audit_ref: str | None = None,
    autonomous_learning: dict | None = None,
) -> Path:
    progress_blocks, progress_event_count, last_progress_at = build_progress_blocks()
    _ = progress_blocks
    goal_profile = route_payload["goal_profile"]
    goal_slug = slugify(str(goal_profile.get("label", "")).strip())
    platform_slug = slugify(platform)
    session_id = f"stage3_{datetime.now().strftime('%Y%m%d')}_{platform_slug}_{goal_slug}".lower()
    session_path = root / output_dir / f"{datetime.now().date()}_{platform_slug}_{goal_slug}.md"
    meta = {
        "session_id": session_id,
        "title": f"【策略推演会话】{platform} / {goal_profile.get('label', '')}",
        "router_ref": router_ref,
        "input_goal": raw_goal,
        "normalized_goal": goal_profile.get("label", ""),
        "user_type": user_type,
        "platform": platform,
        "domain": domain,
        "constraints": constraints,
        "status": "draft",
        "evidence_status": route_payload["evidence_status"],
        "evidence_case_count": len(route_payload["selected_case_refs"]),
        "route_confidence": route_payload["route_confidence"],
        "progress_protocol": "hybrid-3min",
        "progress_event_count": progress_event_count,
        "last_progress_at": last_progress_at,
        "selected_strategy_refs": route_payload["selected_strategy_refs"],
        "selected_case_refs": route_payload["selected_case_refs"],
        "selected_resource_refs": route_payload["selected_resource_refs"],
        "date": str(datetime.now().date()),
    }
    if autonomous_learning:
        meta["autonomous_mode"] = True
        meta["generation_mode"] = "synthesized_bootstrap"
        meta["gap_type"] = autonomous_learning.get("gap_type", "")
    if audit_ref:
        meta["audit_ref"] = audit_ref

    write_markdown(session_path, meta, route_payload["body"])
    errors, warnings, _repairs = validate_stage3_session(session_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        raise SystemExit(1)

    meta["status"] = "ready"
    write_markdown(session_path, meta, route_payload["body"])
    errors, warnings, _repairs = validate_stage3_session(session_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        raise SystemExit(1)

    for warning in warnings:
        print(f"WARNING: {warning}")
    return session_path


def predict_session_ref(root: Path, output_dir: str, platform: str, goal_label: str) -> str:
    platform_slug = slugify(platform)
    goal_slug = slugify(goal_label)
    session_path = root / output_dir / f"{datetime.now().date()}_{platform_slug}_{goal_slug}.md"
    return str(session_path.relative_to(root))


def build_audit_body(
    raw_goal: str,
    platform: str,
    user_type: str,
    domain: str,
    constraints: list[str],
    failure_mode: str,
    failure_detail: str,
    gap_type: str,
    decision: str,
    goal_candidates: list[dict],
    strategy_refs: list[str],
    case_candidates: list[dict],
    stage2_result: str,
    stage1_result: str,
    replenishment_search_brief: str,
    replenishment_target_case_count: int,
    replenishment_intake_constraints: list[str],
    audit_ref: str,
    generated_session_ref: str | None,
) -> str:
    best_goal_labels = [str(item.get("label", "")).strip() for item in goal_candidates[:3] if str(item.get("label", "")).strip()]
    case_lines = [f"- `{item['case_ref']}` ({item['status']}, score={item['score']})" for item in case_candidates]
    structured = {
        "autonomous_audit": {
            "input_goal": raw_goal,
            "failure_mode": failure_mode,
            "failure_detail": failure_detail,
            "gap_type": gap_type,
            "decision": decision,
            "manual_fallback_required": False,
            "goal_candidates": best_goal_labels,
            "selected_strategy_refs": strategy_refs,
            "case_refs": [item["case_ref"] for item in case_candidates],
            "stage2_feedback": {
                "required": gap_type in {"stage2_translation_gap", "mixed"},
                "owner": "system",
                "result": stage2_result,
            },
            "stage1_replenishment": {
                "required": gap_type in {"stage1_evidence_gap", "mixed"} or not case_candidates,
                "owner": "system",
                "user_action_required": False,
                "target_case_count": replenishment_target_case_count,
                "search_brief": replenishment_search_brief,
                "intake_constraints": replenishment_intake_constraints,
                "result": stage1_result,
            },
            "generated_session_ref": generated_session_ref or "",
            "audit_ref": audit_ref,
        }
    }
    structured_yaml = yaml.safe_dump(structured, allow_unicode=True, sort_keys=False).strip()

    lines = [
        f"# 【阶段三自治审计】{platform} / {raw_goal}",
        "",
        "## 触发背景",
        "",
        f"- **原始目标：** {raw_goal}",
        f"- **平台：** {platform}",
        f"- **用户类型：** {user_type}",
        f"- **业务领域：** {domain}",
        f"- **资源约束：** {', '.join(constraints) if constraints else '默认按当前输入处理'}",
        "",
        "## 失败诊断",
        "",
        f"- **失败模式：** `{failure_mode}`",
        f"- **错误明细：** {failure_detail}",
        f"- **缺口分类：** `{gap_type}`",
        f"- **系统决策：** `{decision}`",
        f"- **最接近的目标族：** {', '.join(best_goal_labels) if best_goal_labels else '无'}",
        f"- **拟采用策略：** {', '.join(strategy_refs) if strategy_refs else '无'}",
        "- **相关证据案例：**",
    ]
    if case_lines:
        lines.extend(case_lines)
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 阶段二反问结果",
            "",
            f"- {stage2_result}",
            "",
            "## 阶段一补库动作",
            "",
            f"- {stage1_result}",
            f"- **补库检索简报：** {replenishment_search_brief}",
            f"- **目标病例数：** `{replenishment_target_case_count}`",
            "- **收录约束：**",
        ]
    )
    for index, item in enumerate(replenishment_intake_constraints, start=1):
        lines.append(f"  {index}. {item}")
    lines.extend(
        [
            "",
            "## 自治学习动作",
            "",
            f"- 系统已经把本次异常记录到 `{audit_ref}`。",
            "- 标准路由失败后，不再直接报错，而是自动进入缺口分类与证据重组。",
            "- 只要当前基因库还能支撑一条可执行路径，就优先交付 bootstrap 方案，而不是等待人工扩图。",
        ]
    )
    if generated_session_ref:
        lines.append(f"- 已同步生成会话：`{generated_session_ref}`。")
    lines.extend(
        [
            "",
            "## Structured Autonomous Audit",
            "",
            "```yaml",
            structured_yaml,
            "```",
        ]
    )
    return "\n".join(lines).strip()


def write_autonomous_audit(
    root: Path,
    audit_dir: str,
    raw_goal: str,
    platform: str,
    user_type: str,
    domain: str,
    constraints: list[str],
    failure_mode: str,
    failure_detail: str,
    gap_type: str,
    decision: str,
    goal_candidates: list[dict],
    strategy_refs: list[str],
    case_candidates: list[dict],
    stage2_result: str,
    stage1_result: str,
    replenishment_search_brief: str,
    replenishment_target_case_count: int,
    replenishment_intake_constraints: list[str],
    generated_session_ref: str | None,
) -> Path:
    goal_slug = slugify(raw_goal)
    platform_slug = slugify(platform)
    audit_id = f"stage3_audit_{datetime.now().strftime('%Y%m%d')}_{platform_slug}_{goal_slug}".lower()
    audit_path = root / audit_dir / f"{datetime.now().date()}_{platform_slug}_{goal_slug}.md"
    audit_ref = str(audit_path.relative_to(root))
    meta = {
        "audit_id": audit_id,
        "title": f"【阶段三自治审计】{platform} / {raw_goal}",
        "scope": "stage3",
        "status": "ready",
        "input_goal": raw_goal,
        "platform": platform,
        "user_type": user_type,
        "domain": domain,
        "constraints": constraints,
        "failure_mode": failure_mode,
        "gap_type": gap_type,
        "decision": decision,
        "manual_fallback_required": False,
        "generated_session_ref": generated_session_ref or "",
        "date": str(datetime.now().date()),
    }
    body = build_audit_body(
        raw_goal=raw_goal,
        platform=platform,
        user_type=user_type,
        domain=domain,
        constraints=constraints,
        failure_mode=failure_mode,
        failure_detail=failure_detail,
        gap_type=gap_type,
        decision=decision,
        goal_candidates=goal_candidates,
        strategy_refs=strategy_refs,
        case_candidates=case_candidates,
        stage2_result=stage2_result,
        stage1_result=stage1_result,
        replenishment_search_brief=replenishment_search_brief,
        replenishment_target_case_count=replenishment_target_case_count,
        replenishment_intake_constraints=replenishment_intake_constraints,
        audit_ref=audit_ref,
        generated_session_ref=generated_session_ref,
    )
    write_markdown(audit_path, meta, body)
    return audit_path


def run_autonomous_recovery(
    root: Path,
    args: argparse.Namespace,
    goal_profiles: list[dict],
    strategy_profiles: dict[str, dict],
    resource_catalog: dict[str, dict],
    case_catalog: dict[str, dict],
    case_meta_catalog: dict[str, dict],
    strategy_nodes: dict[str, dict],
    situation_nodes: dict[str, dict],
    situation_strategy_edges: dict[str, list[dict]],
    strategy_situation_edges: dict[str, list[dict]],
    failure: Stage3RoutingError,
) -> tuple[Path, Path | None, dict | None]:
    goal_candidates = rank_goal_profiles(args.goal, goal_profiles, args.platform, args.domain, args.user_type)
    strategy_rankings = rank_strategy_profiles(args.goal, strategy_profiles, args.platform, args.domain, args.user_type)
    case_candidates = rank_case_candidates(args.goal, case_meta_catalog, args.platform, args.domain)
    selected_strategy_refs = select_synthesized_strategy_refs(case_candidates, strategy_rankings, strategy_profiles)
    best_goal_score = float(goal_candidates[0]["score"]) if goal_candidates else 0.0
    gap_type, decision = infer_gap_type(failure.failure_mode, best_goal_score, case_candidates, selected_strategy_refs)

    suggested_goal = str(goal_candidates[0]["label"]).strip() if goal_candidates else f"自主合成：{args.goal}"
    if best_goal_score < 0.55:
        suggested_goal = f"自主合成：{args.goal}"
    approved_case_count = sum(1 for item in case_candidates if item.get("status") == "approved")

    stage2_result = build_stage2_result(gap_type, args.goal, suggested_goal)
    stage1_result = build_stage1_result(gap_type, approved_case_count)
    replenishment_search_brief = build_replenishment_search_brief(
        raw_goal=args.goal,
        platform=args.platform,
        domain=args.domain,
        user_type=args.user_type,
        strategy_refs=selected_strategy_refs,
    )
    replenishment_target_case_count = 5 if gap_type == "stage1_evidence_gap" else 3
    replenishment_intake_constraints = [
        "只收录已商业化验证且明确赚到钱的正式案例",
        "优先补充与当前平台直接匹配的案例",
        "必须带标准 strategy_tags 与 resource_refs，便于阶段三自动复用",
    ]

    session_path: Path | None = None
    route_payload: dict | None = None

    if decision == "synthesized_bootstrap" and selected_strategy_refs and case_candidates:
        synthesized_goal = build_synthesized_goal_profile(args.goal, goal_candidates, selected_strategy_refs, case_candidates)
        predicted_session_ref = predict_session_ref(root, args.output_dir, args.platform, str(synthesized_goal.get("label", "")).strip())
        autonomous_learning = {
            "trigger_reason": f"标准路由失败：{failure.detail}",
            "gap_type": gap_type,
            "stage2_result": stage2_result,
            "stage1_result": stage1_result,
            "audit_ref": str((root / args.audit_dir / f"{datetime.now().date()}_{slugify(args.platform)}_{slugify(args.goal)}.md").relative_to(root)),
        }
        route_payload = build_route_payload(
            raw_goal=args.goal,
            goal_profile=synthesized_goal,
            strategy_profiles=strategy_profiles,
            strategy_nodes=strategy_nodes,
            situation_nodes=situation_nodes,
            situation_strategy_edges=situation_strategy_edges,
            strategy_situation_edges=strategy_situation_edges,
            case_catalog=case_catalog,
            resource_catalog=resource_catalog,
            user_type=args.user_type,
            platform=args.platform,
            domain=args.domain,
            constraints=[str(item).strip() for item in args.constraint if str(item).strip()],
            primary_strategies=selected_strategy_refs[:1],
            secondary_strategies=selected_strategy_refs[1:3],
            selected_case_refs=[item["case_ref"] for item in case_candidates if item["case_ref"] in case_catalog][:5],
            autonomous_learning=autonomous_learning,
        )

        audit_ref = autonomous_learning["audit_ref"]
        write_autonomous_audit(
            root=root,
            audit_dir=args.audit_dir,
            raw_goal=args.goal,
            platform=args.platform,
            user_type=args.user_type,
            domain=args.domain,
            constraints=[str(item).strip() for item in args.constraint if str(item).strip()],
            failure_mode=failure.failure_mode,
            failure_detail=failure.detail,
            gap_type=gap_type,
            decision=decision,
            goal_candidates=goal_candidates,
            strategy_refs=selected_strategy_refs,
            case_candidates=case_candidates,
            stage2_result=stage2_result,
            stage1_result=stage1_result,
            replenishment_search_brief=replenishment_search_brief,
            replenishment_target_case_count=replenishment_target_case_count,
            replenishment_intake_constraints=replenishment_intake_constraints,
            generated_session_ref=predicted_session_ref,
        )
        session_path = write_stage3_session(
            root=root,
            output_dir=args.output_dir,
            router_ref=args.router_ref,
            raw_goal=args.goal,
            route_payload=route_payload,
            user_type=args.user_type,
            platform=args.platform,
            domain=args.domain,
            constraints=[str(item).strip() for item in args.constraint if str(item).strip()],
            audit_ref=audit_ref,
            autonomous_learning=autonomous_learning,
        )

    audit_path = write_autonomous_audit(
        root=root,
        audit_dir=args.audit_dir,
        raw_goal=args.goal,
        platform=args.platform,
        user_type=args.user_type,
        domain=args.domain,
        constraints=[str(item).strip() for item in args.constraint if str(item).strip()],
        failure_mode=failure.failure_mode,
        failure_detail=failure.detail,
        gap_type=gap_type,
        decision=decision,
        goal_candidates=goal_candidates,
        strategy_refs=selected_strategy_refs,
        case_candidates=case_candidates,
        stage2_result=stage2_result,
        stage1_result=stage1_result,
        replenishment_search_brief=replenishment_search_brief,
        replenishment_target_case_count=replenishment_target_case_count,
        replenishment_intake_constraints=replenishment_intake_constraints,
        generated_session_ref=str(session_path.relative_to(root)) if session_path else None,
    )
    return audit_path, session_path, route_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Buildmate stage-3 strategy session and output a formal solution package.")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--user-type", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--constraint", action="append", default=[])
    parser.add_argument("--root", default=".")
    parser.add_argument("--goals-config", default=DEFAULT_GOAL_PROFILES_PATH)
    parser.add_argument("--strategies-config", default=DEFAULT_STRATEGY_PROFILES_PATH)
    parser.add_argument("--router-ref", default=DEFAULT_ROUTER_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-dir", default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--disable-autonomous-learning", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    goal_profiles = load_goal_profiles(root / args.goals_config)
    strategy_profiles = load_strategy_profiles(root / args.strategies_config)
    resource_catalog = load_resource_catalog(root)
    case_catalog = load_case_catalog(root)
    case_meta_catalog = load_case_meta_catalog(root)
    strategy_nodes = load_strategy_nodes(root)
    situation_nodes = load_situation_nodes(root)
    situation_strategy_edges = load_edges_by_key(root, DEFAULT_SITUATION_STRATEGY_EDGES_PATH, "from_situation")
    strategy_situation_edges = load_edges_by_key(root, DEFAULT_STRATEGY_SITUATION_EDGES_PATH, "from_strategy")
    constraints = [str(item).strip() for item in args.constraint if str(item).strip()]

    emit_progress("阶段三（1/7）目标收集", "解析用户目标并准备进入正式路由链路", "进入情境收敛", "约 1 分钟内")
    try:
        goal_profile = normalize_goal(args.goal, goal_profiles)

        emit_progress("阶段三（2/7）情境收敛", "锁定平台、用户类型、领域和资源约束", "进入图谱召回", "约 1 分钟内")
        emit_progress("阶段三（3/7）图谱召回", "召回目标相关策略节点、资源节点和证据案例", "进入路由判断", "约 2 分钟内")
        route_payload = build_route_payload(
            raw_goal=args.goal,
            goal_profile=goal_profile,
            strategy_profiles=strategy_profiles,
            strategy_nodes=strategy_nodes,
            situation_nodes=situation_nodes,
            situation_strategy_edges=situation_strategy_edges,
            strategy_situation_edges=strategy_situation_edges,
            case_catalog=case_catalog,
            resource_catalog=resource_catalog,
            user_type=args.user_type,
            platform=args.platform,
            domain=args.domain,
            constraints=constraints,
        )

        emit_progress("阶段三（4/7）路由判断", "判断主策略、组合策略和证据等级", "进入方案包组装", "约 2 分钟内")
        emit_progress("阶段三（5/7）方案包组装", "组装动作包、模板和工具资源", "进入校验收口", "约 2 分钟内")
        session_path = write_stage3_session(
            root=root,
            output_dir=args.output_dir,
            router_ref=args.router_ref,
            raw_goal=args.goal,
            route_payload=route_payload,
            user_type=args.user_type,
            platform=args.platform,
            domain=args.domain,
            constraints=constraints,
        )
        emit_progress("阶段三（6/7）校验收口", "校验阶段三会话结构、证据和资源引用", "进入交付执行", "约 1 分钟内")
        emit_progress("阶段三（7/7）交付执行", "交付正式阶段三会话与方案包", "等待用户执行反馈", "约 1 分钟内")
        print(
            build_delivery_summary(
                session_path=session_path,
                evidence_status=route_payload["evidence_status"],
                route_confidence=route_payload["route_confidence"],
                primary_strategies=route_payload["primary_strategies"],
                resource_bundle=route_payload["resource_bundle"],
            )
        )
    except Stage3RoutingError as failure:
        if args.disable_autonomous_learning:
            raise SystemExit(f"ERROR: {failure.detail}") from failure

        emit_progress("阶段三（3/7）图谱召回", f"标准路由失败，进入自治审计：{failure.failure_mode}", "进入自治补救", "约 2 分钟内")
        audit_path, session_path, route_payload = run_autonomous_recovery(
            root=root,
            args=args,
            goal_profiles=goal_profiles,
            strategy_profiles=strategy_profiles,
            resource_catalog=resource_catalog,
            case_catalog=case_catalog,
            case_meta_catalog=case_meta_catalog,
            strategy_nodes=strategy_nodes,
            situation_nodes=situation_nodes,
            situation_strategy_edges=situation_strategy_edges,
            strategy_situation_edges=strategy_situation_edges,
            failure=failure,
        )
        emit_progress("阶段三（6/7）校验收口", "完成自治审计并校验补救产物", "进入交付执行", "约 1 分钟内")
        emit_progress("阶段三（7/7）交付执行", "交付自治审计结果与可用方案包", "等待系统补库或用户执行反馈", "约 1 分钟内")

        if session_path and route_payload:
            print(
                build_delivery_summary(
                    session_path=session_path,
                    evidence_status=route_payload["evidence_status"],
                    route_confidence=route_payload["route_confidence"],
                    primary_strategies=route_payload["primary_strategies"],
                    resource_bundle=route_payload["resource_bundle"],
                    audit_path=audit_path,
                    delivery_mode="autonomous_synthesized_bootstrap",
                )
            )
        else:
            print("当前阶段：阶段三（自治补救）")
            print("当前动作：标准路由未命中，已只交付自治审计与阶段一补库动作")
            print(f"自治审计：{audit_path}")
            print("交付模式：stage1_replenishment_only")


if __name__ == "__main__":
    main()
