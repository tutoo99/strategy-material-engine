#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
from pathlib import Path

from _buildmate_lib import (
    assert_project_root,
    clean_markup,
    derive_story_outline,
    has_story_shape,
    normalize_whitespace,
    pick_story_evidence_blocks,
    read_markdown,
    today_iso,
    truncate,
)
from _index_state import mark_dirty
from _io_safety import file_lock
from _knowledge_lib import ensure_string_list
from derive_materials_from_case import (
    build_case_material_specs,
    build_story_body,
    dedupe_texts,
    find_existing_material_duplicate,
    material_output_stem,
    pick_numeric_evidence_lines,
    write_material,
)
from _dedupe_lib import normalize_content, sha256_text


STORYY_SOURCE_CUES = (
    "复盘",
    "实操",
    "项目",
    "起盘",
    "变现",
    "从0到1",
    "踩坑",
    "我是",
    "赚到",
    "做到",
    "航海",
)


def is_story_source_candidate(meta: dict, body: str, path: Path) -> bool:
    title = str(meta.get("title") or path.stem)
    summary = str(meta.get("summary") or "")
    haystack = f"{title}\n{summary}\n{body[:2000]}"
    if any(token in haystack for token in STORYY_SOURCE_CUES):
        return True
    evidence_blocks = pick_story_evidence_blocks(body, limit=1)
    return bool(evidence_blocks) or has_story_shape(haystack)


def build_source_story_data_specs(root: Path, source_path: Path, meta: dict, body: str) -> list[tuple[str, dict, str]]:
    relative_path = str(source_path.relative_to(root)) if source_path.is_relative_to(root) else str(source_path)
    title = str(meta.get("title") or source_path.stem)
    author = normalize_whitespace(str(meta.get("author", "") or ""))
    actor_label = author or "文中这个操盘者"
    outline = derive_story_outline(
        body=body,
        title=title,
        author_identity=author,
        one_line_business=str(meta.get("summary", "") or title),
    )
    evidence_lines = dedupe_texts(
        ensure_string_list(outline.get("evidence_blocks", [])) + pick_story_evidence_blocks(body, limit=3),
        limit=3,
    )
    common = {
        "tags": ensure_string_list(meta.get("tags")),
        "channel_fit": ["general"],
        "source": title,
        "source_refs": [relative_path],
        "derived_from_case": "",
        "source_uid": str(meta.get("source_uid", "") or ""),
        "date": str(meta.get("date") or today_iso()),
        "quality_score": 2.8,
        "use_count": 0,
        "last_used_at": None,
        "used_in_articles": [],
        "impact_log": [],
        "source_reliability": 3.8,
        "review_status": "draft",
    }

    materials: list[tuple[str, dict, str]] = []
    story_defs = [
        ("origin", "opening", str(outline.get("start", "") or ""), [title, str(meta.get("summary", "") or "")]),
        ("turn", "turn", str(outline.get("turn", "") or ""), [str(meta.get("summary", "") or "")]),
        ("payoff", "argument", str(outline.get("payoff", "") or ""), [str(meta.get("summary", "") or "")]),
    ]
    for arc, role, focal_text, support_texts in story_defs:
        focal = truncate(normalize_whitespace(clean_markup(focal_text)) or title, 64)
        if not focal or focal == "待补充":
            continue
        body_text = build_story_body(
            arc=arc,
            actor_label=actor_label,
            focal_text=focal,
            support_texts=support_texts,
            evidence_lines=evidence_lines,
        )
        materials.append(
            (
                "story",
                {
                    "type": "story",
                    "story_arc": arc,
                    "primary_claim": focal,
                    "claims": dedupe_texts([focal, *support_texts, *evidence_lines], limit=4),
                    "ammo_type": "dual",
                    "role": role,
                    "strength": "observation" if not author else "firsthand",
                    "content_sha256": sha256_text(normalize_content(body_text)),
                    **common,
                },
                body_text,
            )
        )

    numeric_lines = pick_numeric_evidence_lines(body, limit=3)
    if numeric_lines:
        data_body_lines = ["这篇材料里最值得留存的是几组可以直接拿来论证的结果数字："]
        data_body_lines.extend([f"- {line}" for line in numeric_lines])
        data_body = "\n".join(data_body_lines).strip()
        materials.append(
            (
                "data",
                {
                    "type": "data",
                    "primary_claim": numeric_lines[0],
                    "claims": numeric_lines[:3],
                    "ammo_type": "substance",
                    "role": "argument",
                    "strength": "observation" if not author else "firsthand",
                    "content_sha256": sha256_text(normalize_content(data_body)),
                    **common,
                },
                data_body,
            )
        )
    return materials
def write_material_specs(
    root: Path,
    materials: list[tuple[str, dict, str]],
    *,
    overwrite: bool,
    allowed_subtypes: set[str],
) -> list[str]:
    created: list[str] = []
    for subtype, material_meta, material_body in materials:
        if subtype not in allowed_subtypes or not material_body.strip():
            continue
        duplicate_path = find_existing_material_duplicate(
            root,
            subtype,
            str(material_meta.get("derived_from_case", "") or ""),
            str(material_meta.get("primary_claim", "") or ""),
            material_body,
        )
        if duplicate_path and not overwrite:
            continue
        output_path = root / "assets/materials" / subtype / f"{material_output_stem(material_meta)}.md"
        if output_path.exists() and not overwrite:
            continue
        write_material(output_path, material_meta, material_body)
        created.append(str(output_path))
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="为已有 case/source 增量回填 story/data 素材")
    parser.add_argument("--root", default=".")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--include-case-drafts", action="store_true")
    parser.add_argument("--include-buildmate-sources", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="最多处理多少个输入文件，0 表示不限")
    parser.add_argument("--type", action="append", choices=["story", "data"], default=[])
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    allowed_subtypes = set(args.type or ["story", "data"])

    case_paths = sorted((root / "assets/cases").rglob("*.md"))
    if args.include_case_drafts:
        case_paths.extend(sorted((root / "assets/case_drafts").rglob("*.md")))
    case_paths = [path for path in case_paths if path.is_file() and not path.name.startswith("_")]

    source_paths: list[Path] = []
    if args.include_buildmate_sources:
        source_paths = [
            path
            for path in sorted((root / "sources/buildmate").rglob("*.md"))
            if path.is_file() and not path.name.startswith("_")
        ]

    processed = 0
    created: list[str] = []
    with file_lock(root, "ingest"):
        for case_path in case_paths:
            if args.limit and processed >= args.limit:
                break
            meta, body = read_markdown(case_path)
            materials = build_case_material_specs(root, case_path.resolve(), meta, body)
            created.extend(write_material_specs(root, materials, overwrite=args.overwrite, allowed_subtypes=allowed_subtypes))
            processed += 1

        for source_path in source_paths:
            if args.limit and processed >= args.limit:
                break
            meta, body = read_markdown(source_path)
            if not is_story_source_candidate(meta, body, source_path):
                processed += 1
                continue
            materials = build_source_story_data_specs(root, source_path.resolve(), meta, body)
            created.extend(write_material_specs(root, materials, overwrite=args.overwrite, allowed_subtypes=allowed_subtypes))
            processed += 1

        if created:
            mark_dirty(root, "materials", reason="backfill_story_data")

    for item in created:
        print(f"Created material: {item}")
    print(f"Processed inputs: {processed}")
    print(f"Created materials: {len(created)}")
    if created:
        print(f"Index state updated: materials marked dirty. Run /opt/miniconda3/bin/python3 scripts/flush_indexes.py --root {root} --bucket materials")


if __name__ == "__main__":
    main()
