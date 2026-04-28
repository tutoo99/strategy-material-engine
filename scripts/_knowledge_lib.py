#!/opt/miniconda3/bin/python3

from __future__ import annotations

from pathlib import Path
from typing import Any

from _material_lib import (  # noqa: F401
    DEFAULT_MODEL_NAME,
    DEFAULT_QUERY_PREFIX,
    DEFAULT_RERANKER_NAME,
    build_faiss_index,
    clamp_candidate_count,
    days_since,
    detect_device,
    encode_texts,
    ensure_float,
    ensure_int,
    ensure_string_list,
    lexical_overlap_ratio,
    list_markdown_files,
    parse_frontmatter,
    read_faiss_index,
    read_jsonl,
    rerank,
    write_faiss_index,
    write_jsonl,
)
from _buildmate_lib import parse_case_body, read_markdown


def normalize_preview(text: str, limit: int = 120) -> str:
    return str(text or "").replace("\n", " ").strip()[:limit]


def case_embed_payload(path: Path, root: Path) -> dict[str, Any]:
    meta, body = read_markdown(path)
    parsed = parse_case_body(body)
    sections = parsed.get("sections", {})
    decisions = parsed.get("decisions", [])
    tools = sorted(
        {
            str(tool).strip()
            for decision in decisions
            for tool in decision.get("tools", [])
            if str(tool).strip() and str(tool).strip() != "待补充"
        }
    )
    source_refs = ensure_string_list(meta.get("source_refs"))
    if not source_refs and meta.get("source_path"):
        source_refs = [str(meta.get("source_path"))]

    retrieval_tags = ensure_string_list(meta.get("retrieval_tags"))
    if not retrieval_tags:
        retrieval_tags = (
            ensure_string_list(meta.get("result_tags"))
            + ensure_string_list(meta.get("symptoms"))
            + ensure_string_list(meta.get("strategy_tags"))
            + tools
        )

    retrieval_summary = str(meta.get("retrieval_summary") or "").strip()
    if not retrieval_summary:
        retrieval_summary = " | ".join(
            [
                str(meta.get("title", "")).strip(),
                str(sections.get("一句话业务", "")).strip(),
                str(sections.get("核心目标", "")).strip(),
                str(sections.get("最终结果", "")).strip(),
                str(sections.get("最值钱忠告", "")).strip(),
            ]
        ).strip(" |")

    decision_lines: list[str] = []
    for decision in decisions[:8]:
        pieces = [
            str(decision.get("decision_point", "")).strip(),
            str(decision.get("choice", "")).strip(),
            str(decision.get("basis", "")).strip(),
        ]
        action_steps = [str(step).strip() for step in decision.get("action_steps", []) if str(step).strip()]
        if action_steps:
            pieces.append(" -> ".join(action_steps[:3]))
        line = " | ".join([p for p in pieces if p])
        if line:
            decision_lines.append(line)

    embed_text = "\n".join(
        [
            f"title: {meta.get('title', '')}",
            f"author_identity: {meta.get('author_identity', '')}",
            f"domain: {meta.get('domain', '')}",
            f"platform: {meta.get('platform', '')}",
            f"result_summary: {meta.get('result_summary', '')}",
            f"retrieval_summary: {retrieval_summary}",
            f"retrieval_tags: {' '.join(retrieval_tags)}",
            f"tools: {' '.join(tools)}",
            sections.get("一句话业务", ""),
            sections.get("核心目标", ""),
            sections.get("最终结果", ""),
            sections.get("最值钱忠告", ""),
            *decision_lines,
        ]
    )

    return {
        "id": str(path.relative_to(root)),
        "path": str(path.relative_to(root)),
        "asset_type": "case",
        "subtype": "case",
        "case_id": meta.get("case_id", ""),
        "title": meta.get("title", path.stem),
        "platform": meta.get("platform", ""),
        "domain": meta.get("domain", ""),
        "status": meta.get("status", ""),
        "result_summary": meta.get("result_summary", ""),
        "retrieval_summary": retrieval_summary,
        "retrieval_tags": retrieval_tags,
        "tools": tools,
        "source_refs": source_refs,
        "derived_material_refs": ensure_string_list(meta.get("derived_material_refs")),
        "body": body,
        "sections": sections,
        "embed_text": embed_text,
        "preview": normalize_preview(retrieval_summary or body),
    }
