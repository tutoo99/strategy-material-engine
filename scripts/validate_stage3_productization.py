#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


DEFAULT_QUESTIONNAIRE_PATH = "strategy_models/productization/stage3_questionnaire.yaml"
DEFAULT_VISUAL_MAP_PATH = "strategy_models/productization/stage3_strategy_map.drawio"
DEFAULT_GOAL_PROFILES_PATH = "strategy_models/routes/goal_profiles.yaml"
DEFAULT_SITUATION_PROFILES_PATH = "strategy_models/routes/situation_profiles.yaml"


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the formal stage-3 productization assets.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--questionnaire", default=DEFAULT_QUESTIONNAIRE_PATH)
    parser.add_argument("--visual-map", default=DEFAULT_VISUAL_MAP_PATH)
    parser.add_argument("--goals-config", default=DEFAULT_GOAL_PROFILES_PATH)
    parser.add_argument("--situations-config", default=DEFAULT_SITUATION_PROFILES_PATH)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    questionnaire_path = root / args.questionnaire
    visual_map_path = root / args.visual_map
    goals = {str(item.get("goal_id", "")).strip() for item in load_yaml(root / args.goals_config).get("goals", []) if isinstance(item, dict)}
    situations = {str(item.get("situation_id", "")).strip() for item in load_yaml(root / args.situations_config).get("situations", []) if isinstance(item, dict)}

    if not questionnaire_path.exists():
        raise SystemExit(f"ERROR: 缺少问答脚本文件：{questionnaire_path}")
    if not visual_map_path.exists():
        raise SystemExit(f"ERROR: 缺少可视化图谱文件：{visual_map_path}")

    questionnaire = load_yaml(questionnaire_path)
    question_ids = {str(item.get("id", "")).strip() for item in questionnaire.get("questions", []) if isinstance(item, dict)}
    expected = {"situation_id", "goal_id", "platform", "domain", "constraint_ids"}
    if expected - question_ids:
        raise SystemExit(f"ERROR: 问答脚本缺少必要问题：{', '.join(sorted(expected - question_ids))}")

    situation_options = {
        str(option.get("id", "")).strip()
        for question in questionnaire.get("questions", [])
        if str(question.get("id", "")).strip() == "situation_id"
        for option in question.get("options", [])
        if isinstance(option, dict)
    }
    if not situation_options.issubset(situations):
        raise SystemExit("ERROR: 问答脚本中的情境选项与正式情境节点不一致。")

    goal_options = {
        str(option.get("id", "")).strip()
        for question in questionnaire.get("questions", [])
        if str(question.get("id", "")).strip() == "goal_id"
        for option in question.get("options", [])
        if isinstance(option, dict)
    }
    if not goal_options.issubset(goals):
        raise SystemExit("ERROR: 问答脚本中的目标选项与正式目标族不一致。")

    visual_text = visual_map_path.read_text(encoding="utf-8")
    if "<mxfile" not in visual_text or "<diagram" not in visual_text:
        raise SystemExit("ERROR: 可视化图谱文件不是合法的 draw.io XML。")

    print("OK: stage3 productization assets passed validation.")


if __name__ == "__main__":
    main()
