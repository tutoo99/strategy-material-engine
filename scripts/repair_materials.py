#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _buildmate_lib import assert_project_root, list_markdown_files, write_markdown
from _material_lib import parse_frontmatter as parse_material_frontmatter
from _material_lib import ensure_string_list
from new_material import default_ammo_type, default_strength


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("paths", nargs="*")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist repairs to disk. Without this flag, only print the planned changes.",
    )
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    targets = collect_targets(root, args.paths)
    if not targets:
        raise SystemExit("No material files found.")

    repaired = 0
    unchanged = 0

    for path in targets:
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_material_frontmatter(raw)
        new_meta, changes = repair_material_meta(path=path, root=root, meta=meta)
        rel = path.relative_to(root)
        if not changes:
            unchanged += 1
            print(f"UNCHANGED {rel}")
            continue
        repaired += 1
        print(f"REPAIR {rel}")
        for change in changes:
            print(f"  - {change}")
        if args.write:
            write_markdown(path, new_meta, body)

    mode = "write" if args.write else "dry-run"
    print(
        f"Repair scan complete ({mode}): targets={len(targets)}, "
        f"repaired={repaired}, unchanged={unchanged}"
    )


def collect_targets(root: Path, raw_paths: list[str]) -> list[Path]:
    if not raw_paths:
        return list_markdown_files(root / "assets/materials")

    targets: list[Path] = []
    seen: set[Path] = set()
    for raw in raw_paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        if candidate.is_dir():
            for child in list_markdown_files(candidate):
                if child not in seen:
                    seen.add(child)
                    targets.append(child)
            continue
        if candidate.is_file():
            if candidate not in seen:
                seen.add(candidate)
                targets.append(candidate)
            continue
        raise SystemExit(f"Path not found: {raw}")
    return sorted(targets)


def repair_material_meta(*, path: Path, root: Path, meta: dict) -> tuple[dict, list[str]]:
    updated = dict(meta)
    changes: list[str] = []

    material_type = str(updated.get("type", "") or "").strip()
    if material_type:
        changed = setdefault(updated, "ammo_type", default_ammo_type(material_type))
        if changed:
            changes.append(f"补 `ammo_type={updated['ammo_type']}`")
        changed = setdefault(updated, "strength", default_strength(material_type))
        if changed:
            changes.append(f"补 `strength={updated['strength']}`")

    if setdefault(updated, "role", "argument"):
        changes.append("补 `role=argument`")
    if setdefault_list(updated, "channel_fit", ["general"]):
        changes.append("补 `channel_fit=[general]`")
    if setdefault(updated, "quality_score", 3.0):
        changes.append("补 `quality_score=3.0`")
    if setdefault(updated, "source_reliability", 3.0):
        changes.append("补 `source_reliability=3.0`")
    if setdefault(updated, "review_status", "draft"):
        changes.append("补 `review_status=draft`")
    if setdefault(updated, "use_count", 0):
        changes.append("补 `use_count=0`")
    if setdefault_list(updated, "used_in_articles", []):
        changes.append("补 `used_in_articles=[]`")
    if setdefault_list(updated, "impact_log", []):
        changes.append("补 `impact_log=[]`")

    refs = ensure_string_list(updated.get("source_refs"))
    normalized_refs: list[str] = []
    ref_changed = False
    for ref in refs:
        resolved = resolve_source_ref(root, ref)
        if resolved and resolved != ref:
            normalized_refs.append(resolved)
            ref_changed = True
        else:
            normalized_refs.append(ref)
    if ref_changed:
        updated["source_refs"] = dedupe(normalized_refs)
        changes.append("规范化 `source_refs` 为可解析相对路径")

    if not ensure_string_list(updated.get("source_refs")) and refs:
        updated["source_refs"] = dedupe(refs)

    source_value = str(updated.get("source", "") or "").strip()
    if not source_value or source_value == "待补充":
        inferred = infer_source_label(root, ensure_string_list(updated.get("source_refs")), path)
        if inferred:
            updated["source"] = inferred
            changes.append(f"回填 `source={inferred}`")

    if not str(updated.get("title", "") or "").strip():
        updated["title"] = human_title_from_path(path)
        changes.append(f"回填 `title={updated['title']}`")

    if not str(updated.get("primary_claim", "") or "").strip():
        fallback = str(updated.get("title", "") or human_title_from_path(path))
        updated["primary_claim"] = fallback
        changes.append(f"回填 `primary_claim={fallback}`")

    return updated, changes


def setdefault(meta: dict, key: str, value: object) -> bool:
    current = meta.get(key)
    if current is None:
        meta[key] = value
        return True
    if isinstance(current, str) and not current.strip():
        meta[key] = value
        return True
    return False


def setdefault_list(meta: dict, key: str, value: list[str]) -> bool:
    current = meta.get(key)
    if current is None:
        meta[key] = list(value)
        return True
    if isinstance(current, list):
        return False
    if isinstance(current, str) and not current.strip():
        meta[key] = list(value)
        return True
    return False


def resolve_source_ref(root: Path, ref: str) -> str | None:
    candidate = (root / ref).resolve()
    if candidate.exists() and candidate.is_file():
        return str(candidate.relative_to(root))

    basename = Path(ref).name
    matches: list[Path] = []
    for source_root in [root / "sources", root / "assets/sources"]:
        if not source_root.exists():
            continue
        for path in source_root.rglob(basename):
            if path.is_file():
                matches.append(path.resolve())
    deduped_matches = sorted(set(matches))
    if len(deduped_matches) == 1:
        return str(deduped_matches[0].relative_to(root))
    return None


def infer_source_label(root: Path, source_refs: list[str], material_path: Path) -> str:
    for ref in source_refs:
        path = root / ref
        if not path.exists() or not path.is_file():
            continue
        if path.suffix.lower() == ".md":
            text = path.read_text(encoding="utf-8")
            source_meta, _body = parse_material_frontmatter(text)
            title = str(source_meta.get("title", "") or "").strip()
            if title:
                return title
        first_line = first_nonempty_line(path)
        if first_line:
            return first_line
        return path.stem
    author = str(material_path.stem)
    return author


def first_nonempty_line(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:120]
    return ""


def human_title_from_path(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"-原子拉片课$", "", stem)
    return stem.replace("-", " ")


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


if __name__ == "__main__":
    main()
