#!/usr/bin/env python3

from __future__ import annotations

import argparse
from types import SimpleNamespace
from pathlib import Path

import yaml

from run_stage3_strategy_session import (
    DEFAULT_AUDIT_DIR,
    DEFAULT_GOAL_PROFILES_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_ROUTER_PATH,
    DEFAULT_SITUATION_NODES_PATH,
    DEFAULT_SITUATION_STRATEGY_EDGES_PATH,
    DEFAULT_STRATEGY_PROFILES_PATH,
    DEFAULT_STRATEGY_SITUATION_EDGES_PATH,
    Stage3RoutingError,
    build_delivery_summary,
    build_route_payload,
    load_case_catalog,
    load_case_meta_catalog,
    load_edges_by_key,
    load_goal_profiles,
    load_resource_catalog,
    load_situation_nodes,
    load_strategy_nodes,
    load_strategy_profiles,
    run_autonomous_recovery,
    write_stage3_session,
)


DEFAULT_QUESTIONNAIRE_PATH = "strategy_models/productization/stage3_questionnaire.yaml"


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def load_questionnaire(path: Path) -> dict:
    return load_yaml(path)


def find_option(questionnaire: dict, question_id: str, option_id: str) -> dict:
    for question in questionnaire.get("questions", []):
        if str(question.get("id", "")).strip() != question_id:
            continue
        for option in question.get("options", []):
            if str(option.get("id", "")).strip() == option_id:
                return option
    raise SystemExit(f"ERROR: 未在问答脚本中找到 {question_id} 的选项：{option_id}")


def format_questionnaire_markdown(questionnaire: dict) -> str:
    lines = [
        f"# {questionnaire.get('title', '阶段三策略推演问答脚本')}",
        "",
        questionnaire.get("description", "").strip(),
        "",
    ]
    for question in sorted(questionnaire.get("questions", []), key=lambda item: int(item.get("order", 0) or 0)):
        lines.extend(
            [
                f"## {question.get('title', '问题')}：{question.get('prompt', '')}",
                f"- **回答方式：** {question.get('answer_type', 'single_choice')}",
                "",
            ]
        )
        for option in question.get("options", []):
            lines.append(f"- `{option.get('id', '')}` {option.get('label', '')}：{option.get('description', '')}")
        lines.append("")
    return "\n".join(lines).strip()


def resolve_answers(questionnaire: dict, args: argparse.Namespace, situation_nodes: dict[str, dict]) -> dict:
    situation_option = find_option(questionnaire, "situation_id", args.situation_id)
    goal_option = find_option(questionnaire, "goal_id", args.goal_id)
    platform_option = find_option(questionnaire, "platform", args.platform_id)
    domain_option = find_option(questionnaire, "domain", args.domain_id)

    constraints: list[str] = []
    if questionnaire.get("defaults", {}).get("include_situation_default_constraints", True):
        situation_node = situation_nodes.get(str(situation_option.get("maps_to", {}).get("user_type", "")).strip(), {})
        constraints.extend([str(item).strip() for item in situation_node.get("default_constraints", []) if str(item).strip()])

    for constraint_id in args.constraint_id:
        option = find_option(questionnaire, "constraint_ids", constraint_id)
        constraint = str(option.get("maps_to", {}).get("constraint", "")).strip()
        if constraint:
            constraints.append(constraint)

    merged_constraints: list[str] = []
    seen: set[str] = set()
    for item in constraints:
        if item and item not in seen:
            seen.add(item)
            merged_constraints.append(item)

    return {
        "goal": str(goal_option.get("maps_to", {}).get("goal", "")).strip(),
        "user_type": str(situation_option.get("maps_to", {}).get("user_type", "")).strip(),
        "platform": str(platform_option.get("maps_to", {}).get("platform", "")).strip(),
        "domain": str(domain_option.get("maps_to", {}).get("domain", "")).strip(),
        "constraints": merged_constraints,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run stage-3 strategy routing from the formal questionnaire asset.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--questionnaire", default=DEFAULT_QUESTIONNAIRE_PATH)
    parser.add_argument("--print-questionnaire", action="store_true")
    parser.add_argument("--situation-id")
    parser.add_argument("--goal-id")
    parser.add_argument("--platform-id")
    parser.add_argument("--domain-id")
    parser.add_argument("--constraint-id", action="append", default=[])
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-dir", default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--router-ref", default=DEFAULT_ROUTER_PATH)
    parser.add_argument("--goals-config", default=DEFAULT_GOAL_PROFILES_PATH)
    parser.add_argument("--strategies-config", default=DEFAULT_STRATEGY_PROFILES_PATH)
    parser.add_argument("--disable-autonomous-learning", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    questionnaire = load_questionnaire(root / args.questionnaire)
    if args.print_questionnaire:
        print(format_questionnaire_markdown(questionnaire))
        return

    required = {
        "--situation-id": args.situation_id,
        "--goal-id": args.goal_id,
        "--platform-id": args.platform_id,
        "--domain-id": args.domain_id,
    }
    missing = [flag for flag, value in required.items() if not value]
    if missing:
        raise SystemExit(f"ERROR: 缺少问答答案参数：{', '.join(missing)}")

    strategy_profiles = load_strategy_profiles(root / args.strategies_config)
    goal_profiles = load_goal_profiles(root / args.goals_config)
    resource_catalog = load_resource_catalog(root)
    case_catalog = load_case_catalog(root)
    case_meta_catalog = load_case_meta_catalog(root)
    strategy_nodes = load_strategy_nodes(root)
    situation_nodes = load_situation_nodes(root, DEFAULT_SITUATION_NODES_PATH)
    situation_strategy_edges = load_edges_by_key(root, DEFAULT_SITUATION_STRATEGY_EDGES_PATH, "from_situation")
    strategy_situation_edges = load_edges_by_key(root, DEFAULT_STRATEGY_SITUATION_EDGES_PATH, "from_strategy")

    answers = resolve_answers(questionnaire, args, situation_nodes)
    goal_profile = next(
        (item for item in goal_profiles if str(item.get("goal_id", "")).strip() == args.goal_id),
        None,
    )
    if goal_profile is None:
        raise SystemExit(f"ERROR: 未找到 goal_id={args.goal_id} 对应的正式目标族。")

    try:
        route_payload = build_route_payload(
            raw_goal=answers["goal"],
            goal_profile=goal_profile,
            strategy_profiles=strategy_profiles,
            strategy_nodes=strategy_nodes,
            situation_nodes=situation_nodes,
            situation_strategy_edges=situation_strategy_edges,
            strategy_situation_edges=strategy_situation_edges,
            case_catalog=case_catalog,
            resource_catalog=resource_catalog,
            user_type=answers["user_type"],
            platform=answers["platform"],
            domain=answers["domain"],
            constraints=answers["constraints"],
        )
        session_path = write_stage3_session(
            root=root,
            output_dir=args.output_dir,
            router_ref=args.router_ref,
            raw_goal=answers["goal"],
            route_payload=route_payload,
            user_type=answers["user_type"],
            platform=answers["platform"],
            domain=answers["domain"],
            constraints=answers["constraints"],
        )
        print(
            build_delivery_summary(
                session_path=session_path,
                evidence_status=route_payload["evidence_status"],
                route_confidence=route_payload["route_confidence"],
                primary_strategies=route_payload["primary_strategies"],
                resource_bundle=route_payload["resource_bundle"],
                delivery_mode="questionnaire",
            )
        )
    except Stage3RoutingError as failure:
        if args.disable_autonomous_learning:
            raise SystemExit(f"ERROR: {failure.detail}") from failure
        recovery_args = SimpleNamespace(
            goal=answers["goal"],
            user_type=answers["user_type"],
            platform=answers["platform"],
            domain=answers["domain"],
            constraint=answers["constraints"],
            output_dir=args.output_dir,
            audit_dir=args.audit_dir,
            router_ref=args.router_ref,
        )
        audit_path, session_path, route_payload = run_autonomous_recovery(
            root=root,
            args=recovery_args,
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
        if session_path and route_payload:
            print(
                build_delivery_summary(
                    session_path=session_path,
                    evidence_status=route_payload["evidence_status"],
                    route_confidence=route_payload["route_confidence"],
                    primary_strategies=route_payload["primary_strategies"],
                    resource_bundle=route_payload["resource_bundle"],
                    audit_path=audit_path,
                    delivery_mode="questionnaire_autonomous",
                )
            )
        else:
            print("当前阶段：阶段三（问答脚本自治补救）")
            print("当前动作：问答入口已触发自治审计，但当前仅能交付补库动作。")
            print(f"自治审计：{audit_path}")


if __name__ == "__main__":
    main()
