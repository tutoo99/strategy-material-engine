#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

from _io_safety import atomic_write_text, file_lock
from _index_state import mark_dirty
from _buildmate_lib import assert_project_root, slugify, today_iso
from _dedupe_lib import (
    find_duplicate_matches,
    fingerprint_source,
    load_registry,
    make_registry_record,
    refresh_registry_match,
    registry_from_sources,
    strongest_match,
    upsert_registry_record,
    write_registry,
)
from _material_lib import parse_frontmatter
from plan_source_materials import classify_source_shape


def detect_bucket(text: str, title: str, source_type: str, bucket: str) -> str:
    if bucket in {"buildmate", "materials"}:
        return bucket
    combined = f"{title}\n{text}"
    buildmate_hits = sum(
        1
        for token in ["复盘", "变现", "获客", "转化", "项目", "打法", "实操", "引流", "利润", "成交"]
        if token in combined
    )
    material_hits = sum(
        1
        for token in ["感受", "关系", "情绪", "表达", "观点", "洞察", "金句", "联想"]
        if token in combined
    )
    if source_type in {"post", "case", "report"} or buildmate_hits >= material_hits + 1:
        return "buildmate"
    return "materials"


def main() -> None:
    parser = argparse.ArgumentParser(description="导入原始来源并自动路由到 buildmate/materials 来源池")
    parser.add_argument("input_path")
    parser.add_argument("--root", default=".")
    parser.add_argument("--bucket", default="auto", choices=["auto", "buildmate", "materials"])
    parser.add_argument("--source-type", default="article")
    parser.add_argument("--title", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--origin", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--link", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--output-name", default="")
    parser.add_argument(
        "--plan-materials",
        action="store_true",
        help="After importing a materials source, run plan_source_materials.py automatically. DeepSeek planning is enabled by default.",
    )
    parser.add_argument(
        "--no-plan-materials-llm",
        action="store_true",
        help="When --plan-materials is enabled, disable DeepSeek and use rule-based planning only.",
    )
    parser.add_argument(
        "--plan-format",
        default="markdown",
        choices=["markdown", "json"],
        help="Output format when --plan-materials is enabled.",
    )
    parser.add_argument(
        "--write-plan",
        default="",
        help="Optional output path for the generated material plan when --plan-materials is enabled.",
    )
    parser.add_argument(
        "--create-material-drafts",
        action="store_true",
        help="Create draft material files from the generated plan. Use with --plan-materials.",
    )
    parser.add_argument(
        "--overwrite-material-drafts",
        action="store_true",
        help="Overwrite existing draft files when --create-material-drafts is enabled.",
    )
    parser.add_argument(
        "--dedupe-mode",
        default="strict",
        choices=["strict", "review", "off"],
        help="strict/review will skip exact duplicates before writing; off disables duplicate checks.",
    )
    parser.add_argument("--force-import", action="store_true", help="Import even when duplicate candidates are found.")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="When an exact duplicate is found, refresh registry metadata instead of importing a new file.",
    )
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    input_path = Path(args.input_path).resolve()
    raw_text = input_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw_text)

    title = args.title or str(meta.get("title") or input_path.stem)
    author = args.author or str(meta.get("author", ""))
    origin = args.origin or str(meta.get("origin", ""))
    date_value = args.date or str(meta.get("date") or today_iso())
    link = args.link or str(meta.get("link", ""))
    summary = args.summary or str(meta.get("summary", ""))
    source_type = args.source_type or str(meta.get("source_type") or "article")
    if args.tags:
        tags = [item.strip() for item in args.tags.split(",") if item.strip()]
    else:
        tags = [str(item).strip() for item in meta.get("tags", []) if str(item).strip()]

    bucket = detect_bucket(body, title, source_type, args.bucket)
    output_name = args.output_name or f"{slugify(title)}.md"
    output_path = root / "sources" / bucket / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with file_lock(root, "ingest"):
        final_meta = {
            "source_type": source_type,
            "title": title,
            "author": author,
            "origin": origin,
            "date": date_value,
            "tags": tags,
            "link": link,
            "summary": summary,
        }
        fingerprint = fingerprint_source(final_meta, body, title=title)
        relative_output_path = str(output_path.relative_to(root))

        duplicate_of = ""
        duplicate_note = ""
        if args.dedupe_mode != "off":
            registry = load_registry(root)
            if not registry.get("sources"):
                registry = registry_from_sources(root, root / "sources")
                write_registry(root, registry)
            matches = find_duplicate_matches(registry, fingerprint, exclude_path=relative_output_path)
            strongest = strongest_match(matches)
            if strongest:
                duplicate_of = strongest.path
                duplicate_note = f"{strongest.match_type}: {strongest.reason}"
                if strongest.match_type in {"exact_url", "exact_content"} and not args.force_import:
                    if args.update_existing:
                        refresh_registry_match(root, strongest.path)
                        print(f"Duplicate source already exists, registry refreshed: {strongest.path}")
                    else:
                        print(f"Duplicate source already exists, skipped: {strongest.path}")
                    print(f"Existing source: {strongest.path}")
                    print(f"Matched title: {strongest.title}")
                    print(f"Reason: {duplicate_note}")
                    return
                if args.dedupe_mode in {"strict", "review"} and not args.force_import:
                    print("Potential duplicate source requires review; no file was written.")
                    print(f"Candidate: {strongest.path}")
                    print(f"Duplicate candidate: {strongest.path}")
                    print(f"Matched title: {strongest.title}")
                    if strongest.distance is not None:
                        print(f"Simhash distance: {strongest.distance}")
                    print(f"Reason: {duplicate_note}")
                    print("Pass --force-import to keep both copies, or --dedupe-mode off to bypass checks.")
                    return

        final_meta.update(
            {
                "source_uid": fingerprint.source_uid,
                "canonical_url": fingerprint.canonical_url,
                "content_sha256": fingerprint.content_sha256,
                "simhash64": fingerprint.simhash64,
                "imported_at": today_iso(),
            }
        )
        if duplicate_of:
            final_meta["duplicate_of"] = duplicate_of
            final_meta["dedupe_note"] = duplicate_note

        content = f"---\n{yaml.safe_dump(final_meta, allow_unicode=True, sort_keys=False).strip()}\n---\n\n{body.strip()}\n"
        atomic_write_text(output_path, content, encoding="utf-8")
        upsert_registry_record(
            root,
            make_registry_record(
                path=relative_output_path,
                title=title,
                author=author,
                origin=origin,
                fingerprint=fingerprint,
                status="duplicate" if duplicate_of else "active",
            ),
        )
        mark_dirty(root, "sources", reason="import_source_and_route")
    print(f"Imported source: {output_path}")
    print(f"Routed bucket: {bucket}")
    if duplicate_of:
        print(f"Duplicate kept intentionally: {duplicate_of}")
    print(f"Index state updated: sources marked dirty. Run /opt/miniconda3/bin/python3 scripts/flush_indexes.py --root {root}")

    source_shape = classify_source_shape(title, body)
    if bucket == "materials" and source_shape != "single_theme_article":
        suggested = [
            "/opt/miniconda3/bin/python3",
            "scripts/plan_source_materials.py",
            relative_output_path,
            "--root",
            str(root),
        ]
        print(f"Detected source shape: {source_shape}")
        print(f"Suggested next step: {' '.join(suggested)}")

    if args.plan_materials:
        if bucket != "materials":
            print("Skipped material planning: imported source was routed to buildmate bucket.")
            return
        run_material_planner(
            root=root,
            source_path=output_path,
            output_format=args.plan_format,
            write_plan=args.write_plan,
            create_material_drafts=args.create_material_drafts,
            overwrite_material_drafts=args.overwrite_material_drafts,
            use_llm=not args.no_plan_materials_llm,
        )

def run_material_planner(
    *,
    root: Path,
    source_path: Path,
    output_format: str,
    write_plan: str,
    create_material_drafts: bool,
    overwrite_material_drafts: bool,
    use_llm: bool,
) -> None:
    planner_script = Path(__file__).parent / "plan_source_materials.py"
    command = [
        sys.executable,
        str(planner_script),
        str(source_path),
        "--root",
        str(root),
        "--format",
        output_format,
    ]
    if write_plan:
        command.extend(["--write-plan", write_plan])
    if create_material_drafts:
        command.append("--create-drafts")
    if overwrite_material_drafts:
        command.append("--overwrite")
    if not use_llm:
        command.append("--no-llm")

    print("Material plan:")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "plan_source_materials.py failed")


if __name__ == "__main__":
    main()
