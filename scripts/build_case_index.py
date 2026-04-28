#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from _buildmate_lib import ensure_list, extract_markdown_links, list_markdown_files, parse_case_body, read_jsonl, read_markdown, write_jsonl

SKIP_DIR_NAMES = {"imported", "case_drafts", "drafts"}


def build_case_index(root: Path, cases_dir_name: str = "assets/cases", output_dir_name: str = "index/cases") -> int:
    cases_dir = root / cases_dir_name
    output_dir = root / output_dir_name
    rows: list[dict] = []
    meta_rows: list[dict] = []
    resource_health_index = {
        str(item.get("case_ref", "")).strip(): item
        for item in read_jsonl(output_dir / "resource_health_summary.jsonl")
        if str(item.get("case_ref", "")).strip()
    }

    for path in list_markdown_files(cases_dir):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        meta, body = read_markdown(path)
        parsed = parse_case_body(body)
        sections = parsed["sections"]
        decisions = parsed["decisions"]
        tools = sorted(
            {
                tool
                for decision in decisions
                for tool in decision.get("tools", [])
                if str(tool).strip() and str(tool).strip() != "待补充"
            }
        )
        search_text_parts = [
            str(meta.get("title", "")),
            str(meta.get("author_identity", "")),
            str(meta.get("domain", "")),
            str(meta.get("platform", "")),
            str(meta.get("result_summary", "")),
            sections.get("一句话业务", ""),
            sections.get("核心目标", ""),
            sections.get("最终结果", ""),
            sections.get("最值钱忠告", ""),
        ]
        search_text_parts.extend(
            [
                decision.get("decision_point", "")
                for decision in decisions
            ]
        )
        search_text_parts.extend(
            [
                decision.get("choice", "")
                for decision in decisions
            ]
        )
        search_text_parts.extend(ensure_list(meta.get("cross_case_refs")))
        search_text_parts.extend(ensure_list(meta.get("counterfactual_notes")))
        search_text_parts.extend(ensure_list(meta.get("sequence_steps")))
        search_text_parts.extend(tools)
        search_text_parts.extend(extract_markdown_links(body))

        row = {
            "path": str(path.relative_to(root)),
            "meta": meta,
            "body": body,
            "sections": sections,
            "decisions": decisions,
            "tools": tools,
            "search_text": " ".join(part for part in search_text_parts if part),
        }
        rows.append(row)
        sequence_steps = ensure_list(meta.get("sequence_steps"))
        cross_case_refs = ensure_list(meta.get("cross_case_refs"))
        counterfactual_notes = ensure_list(meta.get("counterfactual_notes"))
        resource_links = ensure_list(meta.get("resource_links"))
        resource_health = resource_health_index.get(str(path.relative_to(root)), {})
        meta_rows.append(
            {
                "case_id": meta.get("case_id"),
                "title": meta.get("title"),
                "path": str(path.relative_to(root)),
                "platform": meta.get("platform"),
                "domain": meta.get("domain"),
                "status": meta.get("status"),
                "content_source": meta.get("content_source"),
                "body_lock": meta.get("body_lock"),
                "quality_score": meta.get("quality_score"),
                "result_summary": meta.get("result_summary"),
                "result_tags": meta.get("result_tags", []),
                "symptoms": meta.get("symptoms", []),
                "strategy_tags": meta.get("strategy_tags", []),
                "resource_refs": meta.get("resource_refs", []),
                "causal_status": meta.get("causal_status", ""),
                "cross_case_refs": cross_case_refs,
                "counterfactual_notes": counterfactual_notes,
                "action_granularity_score": meta.get("action_granularity_score", ""),
                "sequence_steps": sequence_steps,
                "sequence_length": len(sequence_steps),
                "platform_context": meta.get("platform_context", ""),
                "account_context": meta.get("account_context", ""),
                "time_context": meta.get("time_context", ""),
                "resource_links": resource_links,
                "resource_link_count": len(resource_links),
                "resource_last_checked_at": meta.get("resource_last_checked_at", ""),
                "resource_health_status": resource_health.get("resource_health_status", ""),
                "resource_health_checked_at": resource_health.get("checked_at", ""),
                "verification_status": meta.get("verification_status", ""),
                "trust_level": meta.get("trust_level", ""),
                "reproducibility_score": meta.get("reproducibility_score", ""),
                "proof_refs": meta.get("proof_refs", []),
                "context_constraints": meta.get("context_constraints", []),
                "tools": tools,
                "decision_count": len(decisions),
                "inferred_decision_count": sum(1 for item in decisions if item.get("is_inferred") == "是"),
                "search_text": row["search_text"],
            }
        )

    write_jsonl(output_dir / "cases.jsonl", rows)
    write_jsonl(output_dir / "cases_meta.jsonl", meta_rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build JSONL indexes for Buildmate cases.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--cases-dir", default="assets/cases")
    parser.add_argument("--output-dir", default="index/cases")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    count = build_case_index(root=root, cases_dir_name=args.cases_dir, output_dir_name=args.output_dir)
    print(f"Indexed {count} case files into {root / args.output_dir}")


if __name__ == "__main__":
    main()
