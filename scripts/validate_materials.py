#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _buildmate_lib import assert_project_root, list_markdown_files, read_markdown
from _knowledge_lib import ensure_string_list
from _material_lib import parse_frontmatter as parse_material_frontmatter


ALLOWED_TYPES = {
    "association",
    "case",
    "data",
    "entity",
    "framework",
    "insight",
    "method",
    "pitfall",
    "playbook",
    "quote",
    "story",
}
ALLOWED_AMMO_TYPES = {"hook", "substance", "dual"}
ALLOWED_REVIEW_STATUS = {"draft", "reviewed", "approved"}
ALLOW_EMPTY_LIST_FIELDS = {"used_in_articles", "impact_log"}
REQUIRED_FIELDS = [
    "type",
    "primary_claim",
    "claims",
    "tags",
    "ammo_type",
    "role",
    "strength",
    "channel_fit",
    "source",
    "source_refs",
    "date",
    "quality_score",
    "use_count",
    "used_in_articles",
    "impact_log",
    "source_reliability",
    "review_status",
]
DATA_FOREIGN_SECTION_KEYWORDS = [
    "建议",
    "方法",
    "流程",
    "趋势",
    "判断",
    "洞察",
    "误区",
    "路径",
    "模式",
    "心法",
    "学习",
]
DATA_NUMERIC_HINTS = [
    "%",
    "万",
    "亿",
    "元",
    "分钟",
    "小时",
    "天",
    "周",
    "月",
    "年",
    "ROI",
    "GMV",
    "播放",
    "粉丝",
    "收入",
    "利润",
    "成本",
    "单价",
    "产能",
    "转化",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("paths", nargs="*")
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    targets = collect_targets(root, args.paths)
    if not targets:
        raise SystemExit("No material files found.")

    total_errors = 0
    total_warnings = 0

    for path in targets:
        errors, warnings = validate_material(path, root)
        rel = path.relative_to(root)
        if not errors and not warnings:
            print(f"OK {rel}")
            continue
        print(f"[{rel}]")
        for message in errors:
            print(f"  ERROR: {message}")
        for message in warnings:
            print(f"  WARN: {message}")
        total_errors += len(errors)
        total_warnings += len(warnings)

    print(
        f"Validated {len(targets)} material file(s): "
        f"errors={total_errors}, warnings={total_warnings}"
    )
    if total_errors > 0 or (args.strict_warnings and total_warnings > 0):
        raise SystemExit(1)


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


def validate_material(path: Path, root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        meta, body = read_markdown(path)
    except Exception:
        raw_text = path.read_text(encoding="utf-8")
        try:
            meta, body = parse_material_frontmatter(raw_text)
        except Exception as exc:
            errors.append(f"frontmatter 解析失败：{exc}")
            return errors, warnings

    for field in REQUIRED_FIELDS:
        value = meta.get(field)
        if value is None:
            errors.append(f"缺少 frontmatter 字段：{field}")
            continue
        if isinstance(value, str) and not value.strip():
            errors.append(f"frontmatter 字段为空：{field}")
            continue
        if isinstance(value, list) and not value and field not in ALLOW_EMPTY_LIST_FIELDS:
            errors.append(f"frontmatter 列表字段为空：{field}")

    material_type = str(meta.get("type", "") or "").strip()
    if material_type not in ALLOWED_TYPES:
        errors.append(f"`type` 不在允许范围内：{material_type or '(empty)'}")

    claims = ensure_string_list(meta.get("claims"))
    if not claims:
        errors.append("`claims` 至少需要 1 条。")

    tags = ensure_string_list(meta.get("tags"))
    if not tags:
        errors.append("`tags` 不能为空列表。")

    ammo_type = str(meta.get("ammo_type", "") or "").strip()
    if ammo_type not in ALLOWED_AMMO_TYPES:
        errors.append(f"`ammo_type` 不在允许范围内：{ammo_type or '(empty)'}")

    channel_fit = ensure_string_list(meta.get("channel_fit"))
    if not channel_fit:
        errors.append("`channel_fit` 至少需要 1 个渠道。")

    source = str(meta.get("source", "") or "").strip()
    if not source or source == "待补充":
        errors.append("`source` 不能为空，也不能保留为 `待补充`。")

    source_refs = ensure_string_list(meta.get("source_refs"))
    if not source_refs:
        errors.append("`source_refs` 至少需要 1 条可解析来源路径。")
    else:
        for ref in source_refs:
            resolved, suggestion = resolve_source_ref(root, ref)
            if resolved is None:
                if suggestion:
                    errors.append(f"`source_refs` 无法解析：{ref}；建议改为 `{suggestion}`")
                else:
                    errors.append(f"`source_refs` 无法解析：{ref}")

    parse_numeric_field(meta, "quality_score", errors, lower=1.0, upper=5.0)
    parse_numeric_field(meta, "source_reliability", errors, lower=1.0, upper=5.0)
    parse_int_field(meta, "use_count", errors, lower=0)

    review_status = str(meta.get("review_status", "") or "").strip()
    if review_status not in ALLOWED_REVIEW_STATUS:
        errors.append(f"`review_status` 不在允许范围内：{review_status or '(empty)'}")

    used_in_articles = meta.get("used_in_articles")
    if not isinstance(used_in_articles, list):
        errors.append("`used_in_articles` 必须是列表。")

    impact_log = meta.get("impact_log")
    if not isinstance(impact_log, list):
        errors.append("`impact_log` 必须是列表。")

    if len(body.strip()) < 20:
        warnings.append("正文过短，像占位稿。")

    if material_type == "data":
        warnings.extend(validate_data_purity(body, claims))

    return errors, warnings


def parse_numeric_field(meta: dict, field: str, errors: list[str], *, lower: float, upper: float) -> None:
    raw = meta.get(field)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        errors.append(f"`{field}` 必须是数值。")
        return
    if value < lower or value > upper:
        errors.append(f"`{field}` 必须在 {lower} 到 {upper} 之间。")


def parse_int_field(meta: dict, field: str, errors: list[str], *, lower: int) -> None:
    raw = meta.get(field)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        errors.append(f"`{field}` 必须是整数。")
        return
    if value < lower:
        errors.append(f"`{field}` 不能小于 {lower}。")


def resolve_source_ref(root: Path, ref: str) -> tuple[Path | None, str | None]:
    candidate = (root / ref).resolve()
    if candidate.exists() and candidate.is_file():
        return candidate, str(candidate.relative_to(root))

    basename = Path(ref).name
    matches: list[Path] = []
    for source_root in [root / "sources", root / "assets/sources"]:
        if not source_root.exists():
            continue
        for path in source_root.rglob(basename):
            if path.is_file():
                matches.append(path.resolve())
    deduped = sorted(set(matches))
    if len(deduped) == 1:
        return None, str(deduped[0].relative_to(root))
    return None, None


def validate_data_purity(body: str, claims: list[str]) -> list[str]:
    warnings: list[str] = []
    headings = [
        line.lstrip("#").strip()
        for line in body.splitlines()
        if line.strip().startswith("#")
    ]
    if headings:
        headings = headings[1:]
    foreign_sections = [
        heading
        for heading in headings
        if any(keyword in heading for keyword in DATA_FOREIGN_SECTION_KEYWORDS)
    ]
    if foreign_sections:
        warnings.append(
            "`data` 正文出现非数据导向区块，疑似混入 method/insight："
            + " / ".join(foreign_sections[:5])
        )

    numeric_claims = 0
    for claim in claims:
        if any(char.isdigit() for char in claim) or any(hint in claim for hint in DATA_NUMERIC_HINTS):
            numeric_claims += 1
    if claims and numeric_claims < max(1, len(claims) // 2):
        warnings.append("`data` 的 claims 中数据型表述占比偏低，像是混入了趋势判断或建议。")

    return warnings


if __name__ == "__main__":
    main()
