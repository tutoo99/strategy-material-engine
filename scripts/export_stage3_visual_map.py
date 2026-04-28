#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

import yaml


DEFAULT_GOAL_PROFILES_PATH = "strategy_models/routes/goal_profiles.yaml"
DEFAULT_STRATEGY_PROFILES_PATH = "strategy_models/routes/strategy_profiles.yaml"
DEFAULT_SITUATION_PROFILES_PATH = "strategy_models/routes/situation_profiles.yaml"
DEFAULT_OUTPUT_PATH = "strategy_models/productization/stage3_strategy_map.drawio"


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def slugify(text: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in text)


def add_vertex(cells: list[str], cell_id: str, x: int, y: int, width: int, height: int, value: str, style: str) -> None:
    cells.append(
        f'<mxCell id="{cell_id}" value="{escape(value)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry"/>'
        f"</mxCell>"
    )


def add_edge(cells: list[str], cell_id: str, source: str, target: str, value: str, style: str) -> None:
    cells.append(
        f'<mxCell id="{cell_id}" value="{escape(value)}" style="{style}" edge="1" parent="1" source="{source}" target="{target}">'
        '<mxGeometry relative="1" as="geometry"/>'
        "</mxCell>"
    )


def build_drawio_xml(situations: list[dict], goals: list[dict], strategies: list[dict]) -> str:
    cells: list[str] = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    node_ids: dict[str, str] = {}
    next_id = 2

    header_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#1f2937;fontColor=#ffffff;strokeColor=#111827;fontStyle=1;"
    situation_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dbeafe;strokeColor=#2563eb;"
    goal_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#fef3c7;strokeColor=#d97706;"
    strategy_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dcfce7;strokeColor=#16a34a;"
    legend_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#f3f4f6;strokeColor=#9ca3af;"
    primary_edge_style = "endArrow=block;endFill=1;strokeColor=#111827;strokeWidth=2;rounded=1;"
    secondary_edge_style = "endArrow=block;endFill=1;dashed=1;strokeColor=#6b7280;strokeWidth=1.5;rounded=1;"
    preferred_edge_style = "endArrow=block;endFill=1;strokeColor=#16a34a;strokeWidth=1.5;rounded=1;"
    blocked_edge_style = "endArrow=block;endFill=1;dashed=1;strokeColor=#dc2626;strokeWidth=1.5;rounded=1;"

    add_vertex(cells, str(next_id), 40, 20, 220, 40, "阶段三产品化图谱", header_style)
    next_id += 1
    add_vertex(cells, str(next_id), 40, 80, 220, 90, "蓝色：情境节点\n黄色：目标节点\n绿色：策略节点\n红色虚线：不适用禁区", legend_style)
    next_id += 1

    for index, situation in enumerate(situations):
        cell_id = str(next_id)
        next_id += 1
        value = f"{situation['situation_id']}\\n{situation['label']}"
        add_vertex(cells, cell_id, 40, 220 + index * 110, 220, 70, value, situation_style)
        node_ids[f"situation:{situation['label']}"] = cell_id

    for index, goal in enumerate(goals):
        cell_id = str(next_id)
        next_id += 1
        value = f"{goal['goal_id']}\\n{goal['label']}"
        add_vertex(cells, cell_id, 360, 220 + index * 140, 220, 80, value, goal_style)
        node_ids[f"goal:{goal['label']}"] = cell_id

    for index, strategy in enumerate(strategies):
        column = index // 9
        row = index % 9
        cell_id = str(next_id)
        next_id += 1
        value = f"{strategy['strategy_id']}\\n{strategy['label']}"
        add_vertex(cells, cell_id, 700 + column * 260, 220 + row * 95, 220, 70, value, strategy_style)
        node_ids[f"strategy:{strategy['label']}"] = cell_id

    for goal in goals:
        source = node_ids.get(f"goal:{goal['label']}")
        if not source:
            continue
        for label in goal.get("primary_strategies", []):
            target = node_ids.get(f"strategy:{label}")
            if target:
                add_edge(cells, str(next_id), source, target, "首选", primary_edge_style)
                next_id += 1
        for label in goal.get("secondary_strategies", []):
            target = node_ids.get(f"strategy:{label}")
            if target:
                add_edge(cells, str(next_id), source, target, "组合", secondary_edge_style)
                next_id += 1

    for situation in situations:
        source = node_ids.get(f"situation:{situation['label']}")
        if not source:
            continue
        for rule in situation.get("preferred_strategy_rules", []):
            label = str(rule.get("strategy_ref", "")).strip()
            target = node_ids.get(f"strategy:{label}")
            if target:
                add_edge(cells, str(next_id), source, target, "适用", preferred_edge_style)
                next_id += 1
        for rule in situation.get("not_suitable_strategy_rules", []):
            label = str(rule.get("strategy_ref", "")).strip()
            target = node_ids.get(f"strategy:{label}")
            if target:
                add_edge(cells, str(next_id), source, target, "禁区", blocked_edge_style)
                next_id += 1

    diagram = "".join(cells)
    return (
        '<mxfile host="app.diagrams.net" modified="2026-04-22T00:00:00.000Z" agent="Codex" version="24.7.17">'
        '<diagram id="stage3_strategy_map" name="阶段三策略图谱">'
        '<mxGraphModel dx="1800" dy="1200" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2200" pageHeight="1600" math="0" shadow="0">'
        f"<root>{diagram}</root>"
        "</mxGraphModel>"
        "</diagram>"
        "</mxfile>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the formal stage-3 visual strategy map as a draw.io file.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--goals-config", default=DEFAULT_GOAL_PROFILES_PATH)
    parser.add_argument("--strategies-config", default=DEFAULT_STRATEGY_PROFILES_PATH)
    parser.add_argument("--situations-config", default=DEFAULT_SITUATION_PROFILES_PATH)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    goals = [item for item in load_yaml(root / args.goals_config).get("goals", []) if isinstance(item, dict)]
    strategies = [item for item in load_yaml(root / args.strategies_config).get("strategies", []) if isinstance(item, dict)]
    situations = [item for item in load_yaml(root / args.situations_config).get("situations", []) if isinstance(item, dict)]

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_drawio_xml(situations, goals, strategies), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
