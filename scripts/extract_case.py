#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _buildmate_lib import (
    ADVICE_KEYWORDS,
    GOAL_KEYWORDS,
    PITFALL_KEYWORDS,
    RESULT_KEYWORDS,
    build_case_body,
    build_sequence_steps,
    build_case_title,
    build_pending_inferences,
    build_principles,
    derive_story_outline,
    build_startup_resources,
    compute_action_granularity_score,
    assert_project_root,
    decisions_from_payload,
    derive_case_id,
    derive_domain,
    derive_platform,
    extract_markdown_links,
    infer_decisions,
    llm_extract_case_payload,
    normalize_whitespace,
    pick_best_goal,
    pick_best_result,
    pick_first,
    read_markdown,
    split_sentences,
    today_iso,
    truncate,
    write_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a structured Buildmate case draft from a source file.")
    parser.add_argument("source")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--llm",
        dest="llm",
        action="store_true",
        default=True,
        help="Use one DeepSeek call to extract case structure, then fall back to rules for missing fields. Enabled by default.",
    )
    parser.add_argument(
        "--no-llm",
        dest="llm",
        action="store_false",
        help="Disable DeepSeek and use the rule-based case extractor only.",
    )
    parser.add_argument("--llm-backend", default="auto", choices=["auto", "deepseek"])
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-api-key", default="")
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--llm-thinking", default="enabled", choices=["enabled", "disabled"], help="DeepSeek thinking mode for case extraction.")
    parser.add_argument("--llm-reasoning-effort", default="high", choices=["high", "max", "xhigh"], help="DeepSeek reasoning effort for case extraction.")
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    source_path = Path(args.source).resolve()
    output_path = Path(args.output).resolve() if args.output else None
    created_path = extract_case(
        source_path=source_path,
        root=root,
        output_path=output_path,
        overwrite=args.overwrite,
        use_llm=args.llm,
        llm_backend=args.llm_backend,
        llm_model=args.llm_model,
        llm_base_url=args.llm_base_url,
        llm_api_key=args.llm_api_key,
        llm_timeout=args.llm_timeout,
        llm_thinking=args.llm_thinking,
        llm_reasoning_effort=args.llm_reasoning_effort,
    )
    print(f"Created case draft: {created_path}")


def extract_case(
    source_path: Path,
    root: Path,
    output_path: Path | None = None,
    overwrite: bool = False,
    use_llm: bool = True,
    llm_backend: str = "auto",
    llm_model: str = "",
    llm_base_url: str = "",
    llm_api_key: str = "",
    llm_timeout: float = 120.0,
    llm_thinking: str = "enabled",
    llm_reasoning_effort: str = "high",
) -> Path:
    meta, body = read_markdown(source_path)
    sentences = split_sentences(body)

    llm_payload: dict = {}
    if use_llm:
        try:
            llm_payload = llm_extract_case_payload(
                body=body,
                title=str(meta.get("title", "") or source_path.stem),
                author=str(meta.get("author", "") or ""),
                summary=str(meta.get("summary", "") or ""),
                backend=llm_backend,
                model=llm_model,
                base_url=llm_base_url,
                api_key=llm_api_key,
                timeout=llm_timeout,
                thinking=llm_thinking,
                reasoning_effort=llm_reasoning_effort,
            )
            print("LLM extraction succeeded.", file=sys.stderr)
        except Exception as exc:
            print(f"Warning: LLM extraction failed, falling back to rules. {exc}", file=sys.stderr)
            llm_payload = {}

    llm_resources = llm_payload.get("startup_resources") if isinstance(llm_payload.get("startup_resources"), dict) else {}

    one_line_business = llm_payload.get("one_line_business") or meta.get("summary") or (sentences[0] if sentences else "待补充")
    one_line_business = normalize_whitespace(str(one_line_business))

    author_identity = normalize_whitespace(str(llm_payload.get("author_identity") or meta.get("author") or "待补充"))
    startup_resources = build_startup_resources(sentences)
    startup_resources = {
        key: normalize_whitespace(str(llm_resources.get(key) or startup_resources.get(key) or "待补充"))
        for key in ["现金流", "时间", "技能", "团队/设备", "其他"]
    }
    core_goal = normalize_whitespace(str(llm_payload.get("core_goal") or pick_best_goal(sentences) or "待补充"))
    final_result = normalize_whitespace(str(llm_payload.get("final_result") or pick_best_result(sentences) or "待补充"))
    decisions = decisions_from_payload(llm_payload.get("decisions"), limit=5) or infer_decisions(sentences)
    principles = build_principles()

    pitfall_sentence = normalize_whitespace(str(llm_payload.get("pitfall_sentence") or pick_first(sentences, PITFALL_KEYWORDS) or "待补充：原文未明确给出最大一个坑。"))
    pitfall_solution = normalize_whitespace(str(llm_payload.get("pitfall_solution") or "待补充：需要回到原文，找到作者如何修正这个问题。"))
    advice = normalize_whitespace(str(llm_payload.get("advice") or pick_first(sentences, ADVICE_KEYWORDS) or "待补充：需要从原文提炼一句能直接改变动作的忠告。"))
    story_outline = derive_story_outline(
        body=body,
        title=str(meta.get("title", "") or source_path.stem),
        author_identity=author_identity,
        one_line_business=one_line_business,
        core_goal=core_goal,
        final_result=final_result,
        pitfall_text=pitfall_sentence,
        decisions=decisions,
    )
    story_start = normalize_whitespace(str(llm_payload.get("story_start") or story_outline.get("start") or "待补充"))
    story_turn = normalize_whitespace(str(llm_payload.get("story_turn") or story_outline.get("turn") or "待补充"))
    story_payoff = normalize_whitespace(str(llm_payload.get("story_payoff") or story_outline.get("payoff") or "待补充"))
    story_evidence_raw = llm_payload.get("story_evidence")
    if isinstance(story_evidence_raw, list):
        story_evidence = [normalize_whitespace(str(item)) for item in story_evidence_raw if normalize_whitespace(str(item))]
    else:
        story_evidence = []
    if not story_evidence:
        story_evidence = [normalize_whitespace(str(item)) for item in story_outline.get("evidence_blocks", []) if normalize_whitespace(str(item))]
    pending_inferences = build_pending_inferences(
        author_identity=author_identity,
        startup_resources=startup_resources,
        core_goal=core_goal,
        final_result=final_result,
        decisions=decisions,
    )
    sequence_steps = build_sequence_steps(decisions)
    action_granularity_score = compute_action_granularity_score(decisions)
    resource_links = extract_markdown_links(body)
    platform_context = derive_platform(meta, body)
    account_context = "待补充"
    time_context = str(meta.get("date") or today_iso())
    causal_status = "single_case_hypothesis"
    counterfactual_notes = [
        "当前仅完成单案例拆解，尚未确认这些动作是否构成稳定因果。",
    ]

    title = build_case_title(author_identity, one_line_business, final_result, source_title=str(meta.get("title") or ""))
    case_body = build_case_body(
        title=title,
        one_line_business=one_line_business,
        author_identity=author_identity,
        startup_resources=startup_resources,
        core_goal=core_goal,
        final_result=final_result,
        decisions=decisions,
        principles=principles,
        pitfall=(pitfall_sentence, pitfall_solution),
        advice=advice,
        pending_inferences=pending_inferences,
        causal_status=causal_status,
        cross_case_refs=[],
        counterfactual_notes=counterfactual_notes,
        sequence_steps=sequence_steps,
        platform_context=platform_context,
        account_context=account_context,
        time_context=time_context,
        resource_links=resource_links,
        story_start=story_start,
        story_turn=story_turn,
        story_payoff=story_payoff,
        story_evidence=story_evidence,
    )

    case_meta = {
        "case_id": derive_case_id(source_path),
        "title": title,
        "author_identity": author_identity,
        "domain": derive_domain(meta, body),
        "platform": derive_platform(meta, body),
        "stage": "gene-library",
        "result_summary": truncate(final_result, 60) if final_result != "待补充" else "待补充",
        "result_tags": [],
        "symptoms": [],
        "strategy_tags": [],
        "resource_refs": [],
        "causal_status": causal_status,
        "cross_case_refs": [],
        "counterfactual_notes": counterfactual_notes,
        "action_granularity_score": action_granularity_score,
        "sequence_steps": sequence_steps,
        "platform_context": platform_context,
        "account_context": account_context,
        "time_context": time_context,
        "resource_links": resource_links,
        "resource_last_checked_at": "",
        "source_path": str(source_path.relative_to(root)) if source_path.is_relative_to(root) else str(source_path),
        "quality_score": 2.0,
        "status": "draft",
        "content_source": "ai_generated",
        "body_lock": False,
        "approved_from": "",
        "last_human_reviewed_at": "",
        "date": str(meta.get("date") or today_iso()),
    }

    resolved_output_path = output_path.resolve() if output_path else root / "assets/case_drafts" / f"{source_path.stem}.md"
    if resolved_output_path.exists():
        existing_meta, _ = read_markdown(resolved_output_path)
        if existing_meta.get("body_lock") is True or existing_meta.get("status") == "approved":
            raise SystemExit(
                f"Refusing to overwrite locked approved case: {resolved_output_path}. "
                "Please write to a new draft path instead."
            )
    if resolved_output_path.exists() and not overwrite:
        raise SystemExit(f"Case file already exists: {resolved_output_path}. Pass --overwrite to replace it.")

    write_markdown(resolved_output_path, case_meta, case_body)
    return resolved_output_path


if __name__ == "__main__":
    main()
