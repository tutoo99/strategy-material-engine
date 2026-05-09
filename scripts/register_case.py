#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _index_state import mark_dirty
from _io_safety import file_lock
from _buildmate_lib import (
    assert_project_root,
    derive_case_id,
    derive_domain,
    derive_platform,
    normalize_whitespace,
    parse_case_body,
    read_markdown,
    today_iso,
    truncate,
    write_markdown,
)
from _dedupe_lib import normalize_title
from validate_case import validate_case


def first_heading(body: str) -> str:
    match = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
    return normalize_whitespace(match.group(1)) if match else ""


def load_source_uid(root: Path, source_path: str) -> str:
    if not source_path:
        return ""
    candidate = root / source_path
    if not candidate.exists() or not candidate.is_file():
        return ""
    meta, _body = read_markdown(candidate)
    return str(meta.get("source_uid", "") or "")


def find_existing_case_duplicate(root: Path, output_path: Path, merged_meta: dict) -> Path | None:
    cases_dir = root / "assets/cases"
    if not cases_dir.exists():
        return None
    target_path = output_path.resolve()
    target_case_id = str(merged_meta.get("case_id", "") or "")
    target_source_path = str(merged_meta.get("source_path", "") or "")
    target_source_uid = str(merged_meta.get("source_uid", "") or "")
    target_title = normalize_title(str(merged_meta.get("title", "") or ""))
    for path in sorted(cases_dir.rglob("*.md")):
        if not path.is_file() or path.name.startswith("_") or path.resolve() == target_path:
            continue
        meta, _body = read_markdown(path)
        if target_case_id and str(meta.get("case_id", "") or "") == target_case_id:
            return path
        if target_source_uid and str(meta.get("source_uid", "") or "") == target_source_uid:
            return path
        if target_source_path and str(meta.get("source_path", "") or "") == target_source_path:
            return path
        if target_title and normalize_title(str(meta.get("title", "") or "")) == target_title:
            return path
    return None


def register_case(
    input_path: Path,
    root: Path,
    output_path: Path | None = None,
    source_path: str = "",
    status: str = "approved",
    quality_score: float = 4.0,
    overwrite: bool = False,
    skip_preflight: bool = False,
    force_register_duplicate: bool = False,
) -> Path:
    if not skip_preflight:
        errors, _warnings = validate_case(input_path)
        if errors:
            rendered = "\n".join(f"- {error}" for error in errors)
            raise SystemExit(
                "Refusing to register a case that has not passed preflight validation.\n"
                "Please run `auto_repair_case.py` or `run_stage1_pipeline.py` first.\n"
                f"{rendered}"
            )

    meta, body = read_markdown(input_path)
    parsed = parse_case_body(body)
    sections = parsed["sections"]

    title = normalize_whitespace(str(meta.get("title") or first_heading(body) or input_path.stem))
    author_identity = normalize_whitespace(str(meta.get("author_identity") or sections.get("作者是谁", "待补充")))
    result_summary = normalize_whitespace(
        str(meta.get("result_summary") or truncate(sections.get("最终结果", "待补充"), 60))
    )

    resolved_output_path = output_path.resolve() if output_path else root / "assets/cases" / input_path.name
    existing_meta: dict = {}
    if resolved_output_path.exists():
        existing_meta, _ = read_markdown(resolved_output_path)
    if resolved_output_path.exists() and not overwrite:
        raise SystemExit(f"Case file already exists: {resolved_output_path}. Pass --overwrite to replace it.")

    if input_path.is_relative_to(root):
        default_source_path = str(input_path.relative_to(root))
    else:
        default_source_path = str(input_path)
    resolved_source_path = meta.get("source_path") or source_path or existing_meta.get("source_path") or default_source_path
    source_uid = str(meta.get("source_uid") or existing_meta.get("source_uid") or load_source_uid(root, str(resolved_source_path)))

    merged_meta = {
        "case_id": meta.get("case_id") or existing_meta.get("case_id") or derive_case_id(input_path),
        "title": meta.get("title") or existing_meta.get("title") or title,
        "author_identity": meta.get("author_identity") or existing_meta.get("author_identity") or author_identity,
        "domain": meta.get("domain") or existing_meta.get("domain") or derive_domain(meta, body),
        "platform": meta.get("platform") or existing_meta.get("platform") or derive_platform(meta, body),
        "stage": meta.get("stage") or existing_meta.get("stage") or "gene-library",
        "result_summary": meta.get("result_summary") or existing_meta.get("result_summary") or result_summary,
        "result_tags": meta.get("result_tags") or existing_meta.get("result_tags") or [],
        "symptoms": meta.get("symptoms") or existing_meta.get("symptoms") or [],
        "strategy_tags": meta.get("strategy_tags") or existing_meta.get("strategy_tags") or [],
        "resource_refs": meta.get("resource_refs") or existing_meta.get("resource_refs") or [],
        "causal_status": meta.get("causal_status") or existing_meta.get("causal_status") or "unknown",
        "cross_case_refs": meta.get("cross_case_refs") or existing_meta.get("cross_case_refs") or [],
        "counterfactual_notes": meta.get("counterfactual_notes") or existing_meta.get("counterfactual_notes") or [],
        "action_granularity_score": meta.get("action_granularity_score") or existing_meta.get("action_granularity_score") or "",
        "sequence_steps": meta.get("sequence_steps") or existing_meta.get("sequence_steps") or [],
        "platform_context": meta.get("platform_context") or existing_meta.get("platform_context") or "",
        "account_context": meta.get("account_context") or existing_meta.get("account_context") or "",
        "time_context": meta.get("time_context") or existing_meta.get("time_context") or "",
        "resource_links": meta.get("resource_links") or existing_meta.get("resource_links") or [],
        "resource_last_checked_at": meta.get("resource_last_checked_at") or existing_meta.get("resource_last_checked_at") or "",
        "source_path": resolved_source_path,
        "source_uid": source_uid,
        "quality_score": meta.get("quality_score") or existing_meta.get("quality_score") or quality_score,
        "status": meta.get("status") or existing_meta.get("status") or status,
        "content_source": meta.get("content_source") or existing_meta.get("content_source") or "human_provided",
        "body_lock": existing_meta.get("body_lock") if meta.get("body_lock") is None else meta.get("body_lock"),
        "approved_from": meta.get("approved_from")
        or existing_meta.get("approved_from")
        or (str(input_path.relative_to(root)) if input_path.is_relative_to(root) else str(input_path)),
        "last_human_reviewed_at": meta.get("last_human_reviewed_at") or existing_meta.get("last_human_reviewed_at") or today_iso(),
        "date": str(meta.get("date") or existing_meta.get("date") or today_iso()),
    }
    if merged_meta["body_lock"] is None:
        merged_meta["body_lock"] = True

    with file_lock(root, "ingest"):
        duplicate_path = find_existing_case_duplicate(root, resolved_output_path, merged_meta)
        if duplicate_path and not overwrite and not force_register_duplicate:
            raise SystemExit(
                f"Potential duplicate case already exists: {duplicate_path}. "
                "Pass --overwrite for the same output path or --force-register-duplicate to keep both."
            )

        write_markdown(resolved_output_path, merged_meta, body)
        mark_dirty(root, "cases", reason="register_case")
    return resolved_output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a human-approved case body without rewriting it.")
    parser.add_argument("input_file")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--source-path", default="")
    parser.add_argument("--status", default="approved")
    parser.add_argument("--quality-score", type=float, default=4.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--force-register-duplicate", action="store_true")
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    input_path = Path(args.input_file).resolve()
    output_path = Path(args.output).resolve() if args.output else None
    registered_path = register_case(
        input_path=input_path,
        root=root,
        output_path=output_path,
        source_path=args.source_path,
        status=args.status,
        quality_score=args.quality_score,
        overwrite=args.overwrite,
        skip_preflight=args.skip_preflight,
        force_register_duplicate=args.force_register_duplicate,
    )
    print(f"Registered approved case: {registered_path}")
    print(f"Index state updated: cases marked dirty. Run /opt/miniconda3/bin/python3 scripts/flush_indexes.py --root {root} --bucket cases")


if __name__ == "__main__":
    main()
