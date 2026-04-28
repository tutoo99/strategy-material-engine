#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from search_knowledge import build_query_plan, search_knowledge


DEFAULT_SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "上下文依赖",
        "query": "还有其他打法吗",
        "mode": "hybrid",
        "history": ["我们刚在看图书垂直小店的利润优先打法和抖音卖书案例"],
        "expect_backend": {"rule", "llm"},
        "expect_mode": "strategy",
    },
    {
        "name": "模糊指代",
        "query": "它更适合做私域吗",
        "mode": "hybrid",
        "history": ["上一个案例是图书垂直小店，通过抖音内容带货再承接到知识付费"],
        "expect_backend": {"rule", "llm"},
        "expect_type": "referential",
    },
    {
        "name": "多意图",
        "query": "YPP shorts 矩阵怎么做？变现靠什么？",
        "mode": "hybrid",
        "history": [],
        "expect_backend": {"rule", "llm"},
        "expect_type": "multi_intent",
    },
    {
        "name": "出处模式",
        "query": "B站悬赏带货原文怎么说",
        "mode": "hybrid",
        "history": [],
        "expect_backend": {"rule", "llm"},
        "expect_mode": "source",
    },
    {
        "name": "低相关噪音",
        "query": "火星奶茶裂变玄学",
        "mode": "strategy",
        "history": [],
        "expect_backend": {"rule", "llm"},
        "expect_empty": True,
    },
]


def record_result(name: str, status: str, detail: str, evidence: str = "") -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "evidence": evidence,
    }


def render_markdown_report(rows: list[dict[str, str]], root: Path, provider: str) -> str:
    pass_count = sum(1 for row in rows if row["status"] == "PASS")
    warn_count = sum(1 for row in rows if row["status"] == "WARN")
    fail_count = sum(1 for row in rows if row["status"] == "FAIL")

    lines = [
        "# Query Planner 测试报告",
        "",
        f"- 测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Skill 路径：`{root}`",
        f"- Planner Provider：`{provider}`",
        f"- 结果汇总：PASS {pass_count} / WARN {warn_count} / FAIL {fail_count}",
        "",
        "## 测试项明细",
        "",
        "| 测试项 | 结果 | 结论 |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['name']} | {row['status']} | {row['detail']} |")

    lines.extend(["", "## 关键证据", ""])
    for row in rows:
        if row["evidence"]:
            lines.extend([f"### {row['name']}", "", "```text", row["evidence"], "```", ""])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="评测 Query Planner 的规则/LLM/回退行为")
    parser.add_argument("--root", default=".")
    parser.add_argument("--provider", choices=["auto", "rule", "llm"], default="auto")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows: list[dict[str, str]] = []

    for scenario in DEFAULT_SCENARIOS:
        plan = build_query_plan(
            scenario["query"],
            mode=scenario["mode"],
            conversation_history=scenario["history"],
            planner_provider=args.provider,
            root=root,
        )
        results = search_knowledge(
            root,
            scenario["query"],
            scenario["mode"],
            3,
            "BAAI/bge-large-zh-v1.5",
            "BAAI/bge-reranker-v2-m3",
            "auto",
            8,
            conversation_history=scenario["history"],
            planner_provider=args.provider,
        )

        errors: list[str] = []
        backend = str(plan.get("planner_backend", ""))
        if backend not in scenario["expect_backend"]:
            errors.append(f"planner_backend={backend}")
        if scenario.get("expect_mode") and plan.get("search_mode") != scenario["expect_mode"]:
            errors.append(f"search_mode={plan.get('search_mode')}")
        if scenario.get("expect_type") and plan.get("query_type") != scenario["expect_type"]:
            errors.append(f"query_type={plan.get('query_type')}")
        if scenario.get("expect_empty") and results:
            errors.append("低相关 query 仍返回结果")

        status = "PASS" if not errors else "WARN"
        detail = "符合预期" if not errors else "；".join(errors)
        evidence = json.dumps(
            {
                "query": scenario["query"],
                "plan": plan,
                "top_results": [
                    {
                        "asset_type": item.get("asset_type"),
                        "path": item.get("path"),
                        "score": round(float(item.get("_score", 0.0) or 0.0), 6),
                    }
                    for item in results[:2]
                ],
            },
            ensure_ascii=False,
        )
        rows.append(record_result(scenario["name"], status, detail, evidence))

    markdown = render_markdown_report(rows, root, args.provider)
    output_path = Path(args.output).resolve() if args.output else root / "evals" / "reports" / f"query_planner_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
