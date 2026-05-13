#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import re
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
ALLOWED_ROLES = {
    "action_card",
    "argument",
    "case_example",
    "ending",
    "evidence",
    "example",
    "framework",
    "hook",
    "opening",
    "reference",
    "thesis",
    "turn",
}
ALLOWED_STRENGTHS = {
    "analytical",
    "anecdote",
    "data",
    "experience",
    "expert",
    "fact",
    "firsthand",
    "framework",
    "hard_data",
    "historical",
    "method",
    "observation",
    "original",
    "practice",
    "principle",
    "quote",
    "secondhand",
    "synthesis",
}
ALLOWED_REVIEW_STATUS = {"draft", "queued_for_repair", "rejected", "reviewed", "approved"}
ALLOW_EMPTY_LIST_FIELDS = {"used_in_articles", "impact_log"}
REPAIRABLE_REQUIRED_FIELDS = {
    "ammo_type",
    "channel_fit",
    "date",
    "impact_log",
    "primary_claim",
    "quality_score",
    "role",
    "review_status",
    "source",
    "source_refs",
    "source_reliability",
    "strength",
    "title",
    "use_count",
    "used_in_articles",
}
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
PLACEHOLDER_HINTS = ("待补充", "这里写", "TODO", "TBD", "占位")
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
    total_repairable = 0

    for path in targets:
        errors, warnings, repairable_errors = analyze_material(path=path, root=root)
        rel = path.relative_to(root)
        if not errors and not warnings:
            print(f"OK {rel}")
            continue
        print(f"[{rel}]")
        for message in errors:
            print(f"  ERROR: {message}")
            if message in repairable_errors:
                print(f"  REPAIRABLE: {message}")
                total_repairable += 1
        for message in warnings:
            print(f"  WARN: {message}")
        total_errors += len(errors)
        total_warnings += len(warnings)

    print(
        f"Validated {len(targets)} material file(s): "
        f"errors={total_errors}, warnings={total_warnings}, repairable_errors={total_repairable}"
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
    errors, warnings, _repairable_errors = analyze_material(path=path, root=root)
    return errors, warnings


def analyze_material(path: Path, root: Path) -> tuple[list[str], list[str], list[str]]:
    try:
        meta, body = read_markdown(path)
    except Exception:
        raw_text = path.read_text(encoding="utf-8")
        try:
            meta, body = parse_material_frontmatter(raw_text)
        except Exception as exc:
            return [f"frontmatter 解析失败：{exc}"], [], []

    return validate_material_components(meta=meta, body=body, root=root)


def validate_material_components(meta: dict, body: str, root: Path) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    repairable_errors: list[str] = []

    def add_error(message: str, *, repairable: bool = False) -> None:
        errors.append(message)
        if repairable:
            repairable_errors.append(message)

    for field in REQUIRED_FIELDS:
        value = meta.get(field)
        if value is None:
            add_error(
                f"缺少 frontmatter 字段：{field}",
                repairable=field in REPAIRABLE_REQUIRED_FIELDS,
            )
            continue
        if isinstance(value, str) and not value.strip():
            add_error(
                f"frontmatter 字段为空：{field}",
                repairable=field in REPAIRABLE_REQUIRED_FIELDS,
            )
            continue
        if isinstance(value, list) and not value and field not in ALLOW_EMPTY_LIST_FIELDS:
            add_error(
                f"frontmatter 列表字段为空：{field}",
                repairable=field in REPAIRABLE_REQUIRED_FIELDS,
            )

    material_type = str(meta.get("type", "") or "").strip()
    if material_type not in ALLOWED_TYPES:
        add_error(f"`type` 不在允许范围内：{material_type or '(empty)'}")

    title = str(meta.get("title", "") or "").strip()
    if is_placeholder_text(title):
        add_error("`title` 不能为空，也不能保留为 `待补充`。", repairable=True)

    primary_claim = str(meta.get("primary_claim", "") or "").strip()
    if is_placeholder_text(primary_claim):
        add_error("`primary_claim` 不能为空，也不能保留为 `待补充`。", repairable=True)

    claims = ensure_string_list(meta.get("claims"))
    if not claims:
        add_error("`claims` 至少需要 1 条。")
    else:
        placeholder_claims = [claim for claim in claims if is_placeholder_text(claim)]
        if placeholder_claims:
            add_error("`claims` 不能只保留占位文本。")

    tags = ensure_string_list(meta.get("tags"))
    if not tags:
        add_error("`tags` 不能为空列表。")

    ammo_type = str(meta.get("ammo_type", "") or "").strip()
    if ammo_type not in ALLOWED_AMMO_TYPES:
        add_error(f"`ammo_type` 不在允许范围内：{ammo_type or '(empty)'}", repairable=True)

    role = str(meta.get("role", "") or "").strip()
    if role not in ALLOWED_ROLES:
        add_error(f"`role` 不在允许范围内：{role or '(empty)'}", repairable=True)

    strength = str(meta.get("strength", "") or "").strip()
    if strength not in ALLOWED_STRENGTHS:
        add_error(f"`strength` 不在允许范围内：{strength or '(empty)'}", repairable=True)

    channel_fit = ensure_string_list(meta.get("channel_fit"))
    if not channel_fit:
        add_error("`channel_fit` 至少需要 1 个渠道。", repairable=True)

    source = str(meta.get("source", "") or "").strip()
    if is_placeholder_text(source):
        add_error("`source` 不能为空，也不能保留为 `待补充`。", repairable=True)

    source_refs = ensure_string_list(meta.get("source_refs"))
    if not source_refs:
        add_error("`source_refs` 至少需要 1 条可解析来源路径。")
    else:
        for ref in source_refs:
            resolved, suggestion = resolve_source_ref(root, ref)
            if resolved is None:
                if suggestion:
                    add_error(f"`source_refs` 无法解析：{ref}；建议改为 `{suggestion}`", repairable=True)
                else:
                    add_error(f"`source_refs` 无法解析：{ref}")

    parse_numeric_field(meta, "quality_score", errors, lower=1.0, upper=5.0, repairable_errors=repairable_errors)
    parse_numeric_field(meta, "source_reliability", errors, lower=1.0, upper=5.0, repairable_errors=repairable_errors)
    parse_int_field(meta, "use_count", errors, lower=0, repairable_errors=repairable_errors)

    review_status = str(meta.get("review_status", "") or "").strip()
    if review_status not in ALLOWED_REVIEW_STATUS:
        add_error(f"`review_status` 不在允许范围内：{review_status or '(empty)'}", repairable=True)

    used_in_articles = meta.get("used_in_articles")
    if not isinstance(used_in_articles, list):
        add_error("`used_in_articles` 必须是列表。", repairable=True)

    impact_log = meta.get("impact_log")
    if not isinstance(impact_log, list):
        add_error("`impact_log` 必须是列表。", repairable=True)

    body_text = body.strip()
    if len(body_text) < 20:
        warnings.append("正文过短，像占位稿。")
    if contains_placeholder_text(body_text):
        add_error("正文仍包含占位文本，不可直接入库。")

    if material_type in {"method", "playbook"}:
        step_count = count_numbered_steps(body_text)
        if step_count < 2:
            add_error("`method/playbook` 正文至少需要 2 个可执行编号步骤。")
    if material_type == "data":
        numeric_signals = count_numeric_signals([primary_claim, *claims], body_text)
        if numeric_signals == 0:
            add_error("`data` 素材缺少可量化证据，无法通过门禁。")
        for message in validate_data_numeric_evidence_support(body, claims):
            add_error(message)
        warnings.extend(validate_data_purity(body, claims))
    if material_type in {"story", "insight"} and len(body_text) < 40:
        warnings.append("`story/insight` 正文偏短，建议补足原文依据后再入库。")

    return errors, warnings, repairable_errors


def parse_numeric_field(
    meta: dict,
    field: str,
    errors: list[str],
    *,
    lower: float,
    upper: float,
    repairable_errors: list[str] | None = None,
) -> None:
    raw = meta.get(field)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        message = f"`{field}` 必须是数值。"
        errors.append(message)
        if repairable_errors is not None:
            repairable_errors.append(message)
        return
    if value < lower or value > upper:
        message = f"`{field}` 必须在 {lower} 到 {upper} 之间。"
        errors.append(message)
        if repairable_errors is not None:
            repairable_errors.append(message)


def parse_int_field(
    meta: dict,
    field: str,
    errors: list[str],
    *,
    lower: int,
    repairable_errors: list[str] | None = None,
) -> None:
    raw = meta.get(field)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        message = f"`{field}` 必须是整数。"
        errors.append(message)
        if repairable_errors is not None:
            repairable_errors.append(message)
        return
    if value < lower:
        message = f"`{field}` 不能小于 {lower}。"
        errors.append(message)
        if repairable_errors is not None:
            repairable_errors.append(message)


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


def is_placeholder_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    return contains_placeholder_text(text)


def contains_placeholder_text(text: str) -> bool:
    return any(hint in text for hint in PLACEHOLDER_HINTS)


def count_numbered_steps(body: str) -> int:
    return sum(1 for line in body.splitlines() if re.match(r"^\s*\d+[.)、]\s+", line))


def count_numeric_signals(strings: list[str], body: str) -> int:
    haystack = " ".join(strings) + " " + body
    return sum(1 for char in haystack if char.isdigit()) + sum(1 for hint in DATA_NUMERIC_HINTS if hint in haystack)


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


def validate_data_numeric_evidence_support(body: str, claims: list[str]) -> list[str]:
    """Catch high-risk numeric unit drift between claims and quoted evidence.

    The gate is intentionally narrow: it only blocks claims that put a per-unit
    qualifier such as `每包` or `每月` near a number when no matching qualifier
    appears near the same number in the evidence section.
    """
    evidence = extract_evidence_section(body)
    if not evidence:
        return []

    errors: list[str] = []
    for claim in claims:
        claim_text = str(claim or "").strip()
        if not claim_text:
            continue
        for number_match in re.finditer(r"\d+(?:\.\d+)?", claim_text):
            qualifiers = numeric_context_qualifiers(claim_text, number_match.start(), number_match.end())
            if not qualifiers:
                continue
            number = number_match.group(0)
            if evidence_supports_number_qualifier(evidence, number, qualifiers):
                continue
            errors.append(
                "`data` claim 的数字单位/粒度缺少原文依据："
                f"{claim_text}（数字 {number} 附近的 {', '.join(sorted(qualifiers))} 未在原文依据中对应出现）"
            )
            break
    return errors


def extract_evidence_section(body: str) -> str:
    match = re.search(r"^##\s+原文依据\s*$", body, flags=re.MULTILINE)
    if not match:
        return ""
    evidence = body[match.end() :]
    next_heading = re.search(r"^##\s+", evidence, flags=re.MULTILINE)
    if next_heading:
        evidence = evidence[: next_heading.start()]
    return evidence


def numeric_context_qualifiers(text: str, number_start: int, number_end: int) -> set[str]:
    window = text[max(0, number_start - 8) : min(len(text), number_end + 8)]
    qualifiers: set[str] = set()
    for token in [
        "每包",
        "一包",
        "每条",
        "一条",
        "每月",
        "每年",
        "每天",
        "每日",
        "每周",
        "每个",
        "每人",
        "每户",
        "每棵",
    ]:
        if token in window:
            qualifiers.add(token)
    return qualifiers


def evidence_supports_number_qualifier(evidence: str, number: str, qualifiers: set[str]) -> bool:
    if not qualifiers:
        return True
    for match in re.finditer(re.escape(number), evidence):
        window = evidence[max(0, match.start() - 16) : min(len(evidence), match.end() + 16)]
        if any(token in window for token in qualifiers):
            return True
    return False


if __name__ == "__main__":
    main()
