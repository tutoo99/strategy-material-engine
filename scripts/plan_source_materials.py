#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from _buildmate_lib import assert_project_root, clean_markup, read_markdown, slugify, split_sentences, write_markdown
from _io_safety import file_lock
from _index_state import mark_dirty
from _llm_client import call_deepseek_json, validate_deepseek_backend
from new_material import default_ammo_type, default_strength
from repair_materials import repair_material_meta
from validate_materials import validate_material_components


COURSE_HINTS = ["第一章", "第二章", "第三章", "课程", "课", "讲义", "教程", "基础概念", "入门"]
METHOD_HINTS = [
    "方法",
    "技巧",
    "规则",
    "运用",
    "构图",
    "景别",
    "角度",
    "运镜",
    "拍摄",
    "机位",
    "布光",
    "光色",
    "光的",
    "升格",
    "降格",
    "流程",
    "步骤",
    "选择",
    "控制",
    "分工",
    "定调",
]
DATA_HINTS = ["数据", "成本", "单价", "价格", "ROI", "GMV", "转化", "播放", "收入", "产能"]
INSIGHT_HINTS = ["本质", "判断", "洞察", "趋势", "误区", "陷阱", "认知", "底层逻辑"]
QUOTE_HINTS = ["金句", "语录", "一句话", "原话"]
GENERIC_TITLE_HINTS = ["概念", "原则", "基础", "总览", "框架", "总结", "导论", "入门"]
CLAIM_LABELS = ["知识点", "讲法", "应用", "原理", "重点", "定义", "作用", "特点", "适合", "目的"]
DATA_SIGNAL_HINTS = ["数据", "成本", "单价", "价格", "ROI", "GMV", "转化", "收入", "利润", "预算", "产能", "样本", "播放量"]
DATA_UNITS = ["元", "万", "%", "倍", "小时", "天", "月", "年", "fps", "帧", "人", "条", "篇", "单"]
ALLOWED_MATERIAL_TYPES = {"method", "insight", "data", "quote", "story", "association", "playbook"}
ALLOWED_SOURCE_SHAPES = {"single_theme_article", "multi_theme_longform", "multi_theme_course"}


@dataclass
class HeadingSection:
    level: int
    title: str
    parent_title: str
    content: str


@dataclass
class PlannedMaterial:
    material_type: str
    title: str
    source_heading: str
    parent_heading: str
    claims: list[str]
    primary_claim: str = ""
    tags: list[str] | None = None
    evidence_spans: list[str] | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []
        if self.evidence_spans is None:
            self.evidence_spans = []


@dataclass
class DraftWriteResult:
    total: int = 0
    would_create: int = 0
    would_overwrite: int = 0
    created: int = 0
    overwritten: int = 0
    repaired: int = 0
    rejected: int = 0
    skipped_existing: int = 0
    failed: int = 0
    paths: list[str] | None = None
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.paths is None:
            self.paths = []
        if self.errors is None:
            self.errors = []

    @property
    def changed(self) -> bool:
        return self.created > 0 or self.overwritten > 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "would_create": self.would_create,
            "would_overwrite": self.would_overwrite,
            "created": self.created,
            "overwritten": self.overwritten,
            "repaired": self.repaired,
            "rejected": self.rejected,
            "skipped_existing": self.skipped_existing,
            "failed": self.failed,
            "paths": self.paths or [],
            "errors": self.errors or [],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--write-plan")
    parser.add_argument("--create-drafts", action="store_true")
    parser.add_argument("--dry-run-drafts", action="store_true", help="Preview draft file writes without creating files.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--progress", action="store_true", help="Print per-file draft write progress.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately when a draft write fails.")
    parser.add_argument("--channel-fit", action="append", default=[])
    parser.add_argument("--quality-score", type=float, default=3.0)
    parser.add_argument("--source-reliability", type=float, default=3.0)
    parser.add_argument(
        "--llm",
        dest="llm",
        action="store_true",
        default=True,
        help="Use DeepSeek to plan source material splits, falling back to rules on failure. Enabled by default.",
    )
    parser.add_argument(
        "--no-llm",
        dest="llm",
        action="store_false",
        help="Disable DeepSeek and use the rule-based material planner only.",
    )
    parser.add_argument("--llm-backend", default="auto", choices=["auto", "deepseek"], help="Only auto/deepseek are supported.")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-api-key", default="")
    parser.add_argument("--llm-timeout", type=float, default=180.0)
    parser.add_argument("--llm-max-materials", type=int, default=20)
    parser.add_argument("--llm-thinking", default="enabled", choices=["enabled", "disabled"], help="DeepSeek thinking mode for material planning.")
    parser.add_argument("--llm-reasoning-effort", default="high", choices=["high", "max", "xhigh"], help="DeepSeek reasoning effort for material planning.")
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    source_path = resolve_source_path(root, args.source_path)
    meta, body = read_markdown(source_path)

    source_title = str(meta.get("title") or source_path.stem).strip()
    source_ref = relative_ref(root, source_path)
    source_shape = classify_source_shape(source_title, body)
    sections = extract_heading_sections(body)
    if args.llm:
        try:
            validate_deepseek_backend(args.llm_backend)
            source_shape, materials = plan_materials_with_llm(
                source_title=source_title,
                source_ref=source_ref,
                fallback_source_shape=source_shape,
                sections=sections,
                body=body,
                model=args.llm_model,
                base_url=args.llm_base_url,
                api_key=args.llm_api_key,
                timeout=args.llm_timeout,
                max_materials=args.llm_max_materials,
                thinking=args.llm_thinking,
                reasoning_effort=args.llm_reasoning_effort,
            )
        except Exception as exc:
            if args.fail_fast:
                raise SystemExit(f"DeepSeek material planning failed: {exc}") from exc
            print(f"Warning: DeepSeek material planning failed, falling back to rules. {exc}", file=sys.stderr)
            picked_sections = pick_theme_sections(sections, source_shape)
            materials = [plan_material(section) for section in picked_sections if section.content.strip()]
    else:
        picked_sections = pick_theme_sections(sections, source_shape)
        materials = [plan_material(section) for section in picked_sections if section.content.strip()]

    draft_result: DraftWriteResult | None = None
    should_process_drafts = args.create_drafts or args.dry_run_drafts
    if should_process_drafts and args.format == "json":
        draft_result = create_drafts(
            root=root,
            materials=materials,
            source_title=source_title,
            source_ref=source_ref,
            date_value=str(meta.get("date") or ""),
            channel_fit=args.channel_fit or ["general"],
            quality_score=args.quality_score,
            source_reliability=args.source_reliability,
            overwrite=args.overwrite,
            dry_run=args.dry_run_drafts,
            progress=args.progress or should_process_drafts,
            progress_stream=sys.stderr,
            fail_fast=args.fail_fast,
        )
        if draft_result.changed and not args.dry_run_drafts:
            mark_dirty(root, "materials", reason="plan_source_materials")

    output = render_output(
        source_title=source_title,
        source_ref=source_ref,
        source_shape=source_shape,
        materials=materials,
        output_format=args.format,
        draft_result=draft_result,
    )

    if args.write_plan:
        plan_path = Path(args.write_plan)
        if not plan_path.is_absolute():
            plan_path = root / plan_path
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(output, encoding="utf-8")
        print(f"已写入计划：{plan_path}")
    else:
        print(output)
    if draft_result is not None and draft_result.failed:
        raise SystemExit(1)

    if should_process_drafts and args.format != "json":
        draft_result = create_drafts(
            root=root,
            materials=materials,
            source_title=source_title,
            source_ref=source_ref,
            date_value=str(meta.get("date") or ""),
            channel_fit=args.channel_fit or ["general"],
            quality_score=args.quality_score,
            source_reliability=args.source_reliability,
            overwrite=args.overwrite,
            dry_run=args.dry_run_drafts,
            progress=args.progress or should_process_drafts,
            progress_stream=sys.stdout,
            fail_fast=args.fail_fast,
        )
        if draft_result.changed and not args.dry_run_drafts:
            mark_dirty(root, "materials", reason="plan_source_materials")
        print(render_draft_summary(draft_result, dry_run=args.dry_run_drafts))
        if draft_result.failed:
            raise SystemExit(1)


def resolve_source_path(root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise SystemExit(f"Source file not found: {raw_path}")
    return resolved


def relative_ref(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def classify_source_shape(source_title: str, body: str) -> str:
    h2_count = len(re.findall(r"^##\s+.+$", body, flags=re.MULTILINE))
    h3_count = len(re.findall(r"^###\s+.+$", body, flags=re.MULTILINE))
    hint_hits = sum(1 for token in COURSE_HINTS if token in source_title or token in body[:1200])
    if h3_count >= 4 or (h2_count >= 3 and hint_hits >= 1):
        return "multi_theme_course"
    if h2_count >= 3:
        return "multi_theme_longform"
    return "single_theme_article"


def extract_heading_sections(body: str) -> list[HeadingSection]:
    pattern = re.compile(r"^(##|###)\s+(.+)$", flags=re.MULTILINE)
    matches = list(pattern.finditer(body))
    sections: list[HeadingSection] = []
    current_h2 = ""
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = normalize_heading(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        if level == 2:
            current_h2 = title
        sections.append(
            HeadingSection(
                level=level,
                title=title,
                parent_title=current_h2 if level == 3 else "",
                content=content,
            )
        )
    return sections


def normalize_heading(value: str) -> str:
    cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", str(value).strip())
    cleaned = cleaned.replace("：", " ").replace(":", " ")
    cleaned = re.sub(r"^[.。．、·\s\-_]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -*_")
    return cleaned


def pick_theme_sections(sections: list[HeadingSection], source_shape: str) -> list[HeadingSection]:
    if source_shape == "multi_theme_course":
        level3 = [section for section in sections if section.level == 3]
        if level3:
            return level3
    level2 = [section for section in sections if section.level == 2]
    if level2:
        return level2
    return sections


def plan_material(section: HeadingSection) -> PlannedMaterial:
    material_type = infer_material_type(section.title, section.content)
    title = suggest_material_title(section, material_type)
    claims = derive_claims(section.content)
    return PlannedMaterial(
        material_type=material_type,
        title=title,
        source_heading=section.title,
        parent_heading=section.parent_title,
        claims=claims,
    )


def plan_materials_with_llm(
    *,
    source_title: str,
    source_ref: str,
    fallback_source_shape: str,
    sections: list[HeadingSection],
    body: str,
    model: str,
    base_url: str,
    api_key: str,
    timeout: float,
    max_materials: int,
    thinking: str,
    reasoning_effort: str,
) -> tuple[str, list[PlannedMaterial]]:
    system_prompt, user_prompt = build_llm_material_planner_prompt(
        source_title=source_title,
        source_ref=source_ref,
        fallback_source_shape=fallback_source_shape,
        sections=sections,
        body=body,
        max_materials=max_materials,
    )
    payload = call_deepseek_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        temperature=0.1,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
    )
    return sanitize_llm_material_plan(payload, fallback_source_shape=fallback_source_shape, max_materials=max_materials)


def build_llm_material_planner_prompt(
    *,
    source_title: str,
    source_ref: str,
    fallback_source_shape: str,
    sections: list[HeadingSection],
    body: str,
    max_materials: int,
) -> tuple[str, str]:
    system_prompt = (
        "你是中文商业素材库的入库编辑。你的任务是从原文规划原子素材拆分，不是写文章。"
        "请严格输出 JSON，不要输出解释。"
        "每条素材必须有原文依据，不能编造原文没有的信息。"
        "素材要原子化：一条素材只承载一个方法、洞察、数据事实、故事片段或打法。"
    )
    section_outline = [
        {
            "level": section.level,
            "title": section.title,
            "parent_title": section.parent_title,
            "preview": clean_markup(section.content)[:500],
        }
        for section in sections
    ]
    user_payload = {
        "task": "规划 source 到原子素材的拆分方案",
        "source_title": source_title,
        "source_ref": source_ref,
        "rule_inferred_source_shape": fallback_source_shape,
        "allowed_source_shape": sorted(ALLOWED_SOURCE_SHAPES),
        "allowed_material_type": sorted(ALLOWED_MATERIAL_TYPES),
        "max_materials": max(1, max_materials),
        "requirements": [
            "只返回 JSON 对象",
            "materials 最多 max_materials 条",
            "不要把完整文章压成一条素材",
            "不要为铺垫、寒暄、目录单独建素材",
            "method/playbook 要能指导行动，data 必须包含具体数字或事实，insight 必须是明确判断或本质归纳",
            "claims 必须短句化，每条 1 个意思，最多 5 条",
            "evidence_spans 必须摘录原文中的短片段，最多 3 条",
        ],
        "output_schema": {
            "source_shape": "single_theme_article | multi_theme_longform | multi_theme_course",
            "materials": [
                {
                    "material_type": "method | insight | data | quote | story | association | playbook",
                    "title": "短标题",
                    "source_heading": "来源小节标题，可为空",
                    "parent_heading": "上级主题，可为空",
                    "primary_claim": "最核心的一句话",
                    "claims": ["要点1", "要点2"],
                    "tags": ["标签1", "标签2"],
                    "evidence_spans": ["原文短片段1"],
                    "confidence": 0.8,
                }
            ],
        },
        "section_outline": section_outline,
        "source_body": body,
    }
    return system_prompt, json.dumps(user_payload, ensure_ascii=False)


def sanitize_llm_material_plan(payload: dict[str, Any], *, fallback_source_shape: str, max_materials: int) -> tuple[str, list[PlannedMaterial]]:
    raw_shape = str(payload.get("source_shape") or "").strip()
    source_shape = raw_shape if raw_shape in ALLOWED_SOURCE_SHAPES else fallback_source_shape
    raw_materials = payload.get("materials")
    if not isinstance(raw_materials, list):
        raise ValueError("DeepSeek material plan missing materials list")

    materials: list[PlannedMaterial] = []
    seen_titles: set[str] = set()
    for raw_item in raw_materials:
        if not isinstance(raw_item, dict):
            continue
        item = material_from_llm_entry(raw_item)
        if item is None:
            continue
        title_key = item.title.strip()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        materials.append(item)
        if len(materials) >= max(1, max_materials):
            break
    if not materials:
        raise ValueError("DeepSeek material plan produced no valid materials")
    return source_shape, materials


def material_from_llm_entry(entry: dict[str, Any]) -> PlannedMaterial | None:
    material_type = str(entry.get("material_type") or "method").strip().lower()
    if material_type not in ALLOWED_MATERIAL_TYPES:
        material_type = "method"
    title = normalize_heading(str(entry.get("title") or ""))
    if not title:
        return None
    claims = sanitize_string_list(entry.get("claims"), limit=5, item_limit=160)
    primary_claim = clean_claim(str(entry.get("primary_claim") or ""))
    if primary_claim and primary_claim not in claims:
        claims.insert(0, primary_claim)
    claims = dedupe([claim for claim in claims if is_usable_claim(claim)])[:5]
    if not claims:
        claims = [title]
    return PlannedMaterial(
        material_type=material_type,
        title=title,
        source_heading=normalize_heading(str(entry.get("source_heading") or "")),
        parent_heading=normalize_heading(str(entry.get("parent_heading") or "")),
        claims=claims,
        primary_claim=primary_claim or claims[0],
        tags=sanitize_string_list(entry.get("tags"), limit=8, item_limit=30),
        evidence_spans=sanitize_string_list(entry.get("evidence_spans"), limit=3, item_limit=180),
        confidence=safe_float(entry.get("confidence")),
    )


def sanitize_string_list(value: Any, *, limit: int, item_limit: int) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    elif value:
        raw_values = [value]
    else:
        raw_values = []
    result: list[str] = []
    for item in raw_values:
        cleaned = clean_markup(str(item))
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -*_")
        if cleaned and cleaned not in result:
            result.append(cleaned[:item_limit])
        if len(result) >= limit:
            break
    return result


def safe_float(value: Any) -> float:
    try:
        return max(0.0, min(float(value or 0.0), 1.0))
    except (TypeError, ValueError):
        return 0.0


def infer_material_type(title: str, content: str) -> str:
    title_text = clean_markup(title)
    content_text = clean_markup(content)
    combined = f"{title_text}\n{content_text}"
    if any(token in title_text for token in QUOTE_HINTS):
        return "quote"
    if any(token in title_text for token in METHOD_HINTS):
        return "method"
    if has_strong_data_signal(title_text, content_text):
        return "data"
    if any(token in title_text for token in INSIGHT_HINTS):
        return "insight"
    if any(token in combined for token in METHOD_HINTS):
        return "method"
    if any(token in combined for token in INSIGHT_HINTS):
        return "insight"
    return "method"


def suggest_material_title(section: HeadingSection, material_type: str) -> str:
    heading = normalize_heading(section.title)
    parent = normalize_heading(section.parent_title)
    title = heading
    if section.level == 3 and parent and should_prefix_parent(heading):
        title = f"{parent}-{heading}"
    if material_type == "method" and not any(token in title for token in ["法", "规则", "技巧", "流程", "步骤", "选择", "运用", "控制", "分工", "定调"]):
        if any(token in title for token in ["构图", "景别", "角度", "运镜", "机位", "布光", "光色", "画幅", "拍摄"]):
            title = f"{title}方法"
    return title


def derive_claims(content: str) -> list[str]:
    bullets = collect_bullet_claims(content)
    if bullets:
        return dedupe(bullets)[:5]

    sentences = [clean_claim(sentence) for sentence in split_sentences(content)]
    sentences = [sentence for sentence in sentences if is_usable_claim(sentence)]
    return dedupe(sentences)[:4]


def collect_bullet_claims(content: str) -> list[str]:
    raw_items: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*]\s+", stripped):
            candidate = re.sub(r"^[-*]\s+", "", stripped)
            if "PPT配图" in candidate:
                continue
            raw_items.append(candidate)
        elif re.match(r"^\d+\.\s+", stripped):
            candidate = re.sub(r"^\d+\.\s+", "", stripped)
            if "PPT配图" in candidate:
                continue
            raw_items.append(candidate)
        elif re.match(r"^[A-Z]\.\s*", stripped):
            candidate = re.sub(r"^[A-Z]\.\s*", "", stripped)
            if "PPT配图" in candidate:
                continue
            raw_items.append(candidate)

    cleaned_items = [clean_claim(item) for item in raw_items]
    cleaned_items = [item for item in cleaned_items if item]
    combined = merge_claim_fragments(cleaned_items)
    return [item for item in combined if is_usable_claim(item)]


def merge_claim_fragments(items: list[str]) -> list[str]:
    merged: list[str] = []
    pending = ""
    for item in items:
        if item.endswith("："):
            pending = item.rstrip("：")
            continue
        if pending:
            merged.append(f"{pending}：{item}")
            pending = ""
            continue
        merged.append(item)
    if pending:
        merged.append(pending)
    return merged


def clean_claim(text: str) -> str:
    cleaned = clean_markup(text)
    cleaned = re.sub(r"（[A-Za-z][A-Za-z/\-\s]+）", "", cleaned)
    cleaned = re.sub(r"\([A-Za-z][A-Za-z/\-\s]+\)", "", cleaned)
    cleaned = re.sub(r"\[\s*PPT配图\s*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\((?:\d+\s*)+\)", "", cleaned)
    cleaned = re.sub(r"\(\s*\d+\s*\)", "", cleaned)
    cleaned = re.sub(r"^(?:注|图示|示例)\s*[:：]\s*", "", cleaned)
    for label in CLAIM_LABELS:
        cleaned = re.sub(rf"^{label}\s*[:：]\s*", "", cleaned)
    cleaned = re.sub(r"^[\\/:：\-\s]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -*_")
    return cleaned[:160]


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


def has_strong_data_signal(title: str, content: str) -> bool:
    combined = f"{title}\n{content}"
    title_hit = any(token in title for token in DATA_SIGNAL_HINTS)
    unit_hits = sum(combined.count(unit) for unit in DATA_UNITS)
    number_hits = len(re.findall(r"\d+(?:\.\d+)?", combined))
    hint_hits = sum(1 for token in DATA_SIGNAL_HINTS if token in combined)
    return title_hit or (hint_hits >= 2 and number_hits >= 2) or (unit_hits >= 2 and number_hits >= 3)


def should_prefix_parent(heading: str) -> bool:
    if len(heading) <= 4:
        return True
    if any(token in heading for token in METHOD_HINTS + DATA_HINTS + INSIGHT_HINTS + QUOTE_HINTS):
        return False
    return any(token in heading for token in GENERIC_TITLE_HINTS)


def is_usable_claim(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(token in lowered for token in [".png", ".jpg", ".jpeg", ".gif", ".mp4"]):
        return False
    if any(token in text for token in ["PPT配图", "互动环节", "展示", "见下图", "如下图"]):
        return False
    if len(text) < 6:
        return False
    if text.endswith("：") and len(text) <= 10:
        return False
    return True


def render_output(
    *,
    source_title: str,
    source_ref: str,
    source_shape: str,
    materials: list[PlannedMaterial],
    output_format: str,
    draft_result: DraftWriteResult | None = None,
) -> str:
    payload = {
        "source_title": source_title,
        "source_ref": source_ref,
        "source_shape": source_shape,
        "material_count": len(materials),
        "materials": [asdict(item) for item in materials],
    }
    if draft_result is not None:
        payload["draft_write"] = draft_result.to_dict()
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)

    lines = [
        "# 素材拆分计划",
        "",
        f"- 来源标题：{source_title}",
        f"- 来源路径：{source_ref}",
        f"- 内容形态：{display_source_shape(source_shape)}",
        f"- 建议素材数：{len(materials)}",
        "",
        "| # | 类型 | 建议标题 | 来源小节 | 上级主题 |",
        "|---|------|----------|----------|----------|",
    ]
    for index, item in enumerate(materials, start=1):
        parent = item.parent_heading or "-"
        lines.append(f"| {index} | {display_material_type(item.material_type)} | {item.title} | {item.source_heading} | {parent} |")
    lines.append("")
    for index, item in enumerate(materials, start=1):
        lines.append(f"## {index}. {item.title}")
        lines.append(f"- 类型：{display_material_type(item.material_type)}")
        lines.append(f"- 来源小节：`{item.source_heading}`")
        if item.parent_heading:
            lines.append(f"- 上级主题：`{item.parent_heading}`")
        lines.append("- 建议要点：")
        for claim in item.claims:
            lines.append(f"  - {claim}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def create_drafts(
    *,
    root: Path,
    materials: list[PlannedMaterial],
    source_title: str,
    source_ref: str,
    date_value: str,
    channel_fit: list[str],
    quality_score: float,
    source_reliability: float,
    overwrite: bool,
    dry_run: bool,
    progress: bool,
    progress_stream,
    fail_fast: bool,
) -> DraftWriteResult:
    result = DraftWriteResult(total=len(materials))
    if progress:
        mode = "DRY-RUN" if dry_run else "WRITE"
        print(f"[drafts] {mode} source={source_title} total={len(materials)}", file=progress_stream, flush=True)

    if dry_run:
        return process_draft_items(
            root=root,
            materials=materials,
            source_title=source_title,
            source_ref=source_ref,
            date_value=date_value,
            channel_fit=channel_fit,
            quality_score=quality_score,
            source_reliability=source_reliability,
            overwrite=overwrite,
            dry_run=dry_run,
            progress=progress,
            progress_stream=progress_stream,
            fail_fast=fail_fast,
            result=result,
        )

    with file_lock(root, "ingest"):
        return process_draft_items(
            root=root,
            materials=materials,
            source_title=source_title,
            source_ref=source_ref,
            date_value=date_value,
            channel_fit=channel_fit,
            quality_score=quality_score,
            source_reliability=source_reliability,
            overwrite=overwrite,
            dry_run=dry_run,
            progress=progress,
            progress_stream=progress_stream,
            fail_fast=fail_fast,
            result=result,
        )


def process_draft_items(
    *,
    root: Path,
    materials: list[PlannedMaterial],
    source_title: str,
    source_ref: str,
    date_value: str,
    channel_fit: list[str],
    quality_score: float,
    source_reliability: float,
    overwrite: bool,
    dry_run: bool,
    progress: bool,
    progress_stream,
    fail_fast: bool,
    result: DraftWriteResult,
) -> DraftWriteResult:
    for index, item in enumerate(materials, start=1):
        output_path = root / "assets" / "materials" / item.material_type / f"{slugify(item.title)}.md"
        if output_path.exists() and not overwrite:
            result.skipped_existing += 1
            if progress:
                print(
                    f"[{index}/{len(materials)}] skipped_existing {relative_ref(root, output_path)}",
                    file=progress_stream,
                    flush=True,
                )
            continue

        existed_before = output_path.exists()
        try:
            body = build_draft_body(item)
            meta = build_draft_meta(
                item=item,
                source_title=source_title,
                source_ref=source_ref,
                date_value=date_value,
                channel_fit=channel_fit,
                quality_score=quality_score,
                source_reliability=source_reliability,
            )
            gated_meta, quality_errors, _quality_warnings, repair_changes = gate_draft_material(
                root=root,
                output_path=output_path,
                meta=meta,
                body=body,
            )
            if quality_errors:
                result.rejected += 1
                error = f"{relative_ref(root, output_path)}: quality gate rejected material: {'; '.join(quality_errors)}"
                result.errors.append(error)
                if progress:
                    print(f"[{index}/{len(materials)}] rejected {error}", file=progress_stream, flush=True)
                continue
            if repair_changes:
                result.repaired += 1

            if dry_run:
                action = "would_overwrite" if existed_before else "would_create"
                if existed_before:
                    result.would_overwrite += 1
                else:
                    result.would_create += 1
                result.paths.append(relative_ref(root, output_path))
            else:
                write_markdown(output_path, gated_meta or meta, body)
                action = "overwritten" if existed_before else "created"
                if existed_before:
                    result.overwritten += 1
                else:
                    result.created += 1
                result.paths.append(relative_ref(root, output_path))

            if progress:
                print(
                    f"[{index}/{len(materials)}] {action} {relative_ref(root, output_path)}",
                    file=progress_stream,
                    flush=True,
                )
        except Exception as exc:
            result.failed += 1
            error = f"{relative_ref(root, output_path)}: {exc}"
            result.errors.append(error)
            if progress:
                print(f"[{index}/{len(materials)}] failed {error}", file=progress_stream, flush=True)
            if fail_fast:
                raise SystemExit(f"Draft write failed after {index}/{len(materials)} items: {error}") from exc

    return result


def render_draft_summary(result: DraftWriteResult, *, dry_run: bool) -> str:
    label = "素材草稿预检" if dry_run else "素材草稿写入"
    if dry_run:
        return (
            f"{label}完成：total={result.total}, would_create={result.would_create}, "
            f"would_overwrite={result.would_overwrite}, skipped_existing={result.skipped_existing}, "
            f"repaired={result.repaired}, rejected={result.rejected}, failed={result.failed}"
        )
    return (
        f"{label}完成：total={result.total}, created={result.created}, overwritten={result.overwritten}, "
        f"repaired={result.repaired}, rejected={result.rejected}, skipped_existing={result.skipped_existing}, "
        f"failed={result.failed}"
    )


def build_draft_meta(
    *,
    item: PlannedMaterial,
    source_title: str,
    source_ref: str,
    date_value: str,
    channel_fit: list[str],
    quality_score: float,
    source_reliability: float,
) -> dict[str, Any]:
    primary_claim = item.primary_claim or (item.claims[0] if item.claims else item.title)
    return {
        "type": item.material_type,
        "title": item.title,
        "primary_claim": primary_claim,
        "claims": item.claims or [item.title],
        "tags": infer_tags(source_title, item),
        "ammo_type": default_ammo_type(item.material_type),
        "role": "argument",
        "strength": default_strength(item.material_type),
        "channel_fit": channel_fit,
        "source": source_title,
        "source_refs": [source_ref],
        "derived_from_case": "",
        "source_uid": "",
        "duplicate_of": "",
        "date": date_value,
        "quality_score": quality_score,
        "use_count": 0,
        "last_used_at": None,
        "used_in_articles": [],
        "impact_log": [],
        "source_reliability": source_reliability,
        "review_status": "draft",
    }


def gate_draft_material(
    *,
    root: Path,
    output_path: Path,
    meta: dict[str, Any],
    body: str,
) -> tuple[dict[str, Any] | None, list[str], list[str], list[str]]:
    errors, warnings, repairable_errors = validate_material_components(meta=meta, body=body, root=root)
    repair_changes: list[str] = []
    if errors and all(error in repairable_errors for error in errors):
        repaired_meta, repair_changes = repair_material_meta(path=output_path, root=root, meta=meta)
        errors, warnings, _repairable_errors = validate_material_components(meta=repaired_meta, body=body, root=root)
        meta = repaired_meta
    if errors:
        return None, errors, warnings, repair_changes
    gated_meta = dict(meta)
    if str(gated_meta.get("review_status", "") or "").strip() not in {"approved"}:
        gated_meta["review_status"] = "reviewed"
    return gated_meta, [], warnings, repair_changes


def build_draft_body(item: PlannedMaterial) -> str:
    evidence_spans = item.evidence_spans or []
    if item.material_type == "method":
        lines = []
        for index, claim in enumerate(item.claims, start=1):
            lines.append(f"{index}. {claim}")
        if evidence_spans:
            lines.extend(["", "## 原文依据", ""])
            lines.extend(f"- {span}" for span in evidence_spans)
        return "\n".join(lines)
    if item.material_type == "data":
        lines = ["## 数据要点", ""]
        for claim in item.claims:
            lines.append(f"- {claim}")
        if evidence_spans:
            lines.extend(["", "## 原文依据", ""])
            lines.extend(f"- {span}" for span in evidence_spans)
        return "\n".join(lines)
    lines = []
    for claim in item.claims:
        lines.append(f"- {claim}")
    if evidence_spans:
        lines.extend(["", "## 原文依据", ""])
        lines.extend(f"- {span}" for span in evidence_spans)
    return "\n".join(lines)


def infer_tags(source_title: str, item: PlannedMaterial) -> list[str]:
    tags = [token for token in [source_title, item.source_heading, item.parent_heading, *(item.tags or [])] if token]
    extracted = []
    for value in tags:
        for token in re.split(r"[\s,，、/]+", value):
            normalized = normalize_heading(token)
            if len(normalized) >= 2 and normalized not in extracted:
                extracted.append(normalized)
    return extracted[:8]


def display_source_shape(value: str) -> str:
    return {
        "single_theme_article": "单主题文章",
        "multi_theme_longform": "多主题长文",
        "multi_theme_course": "多主题课程",
    }.get(value, value)


def display_material_type(value: str) -> str:
    return {
        "method": "方法素材",
        "insight": "洞察素材",
        "data": "数据素材",
        "quote": "金句素材",
        "story": "故事素材",
        "association": "联想素材",
        "playbook": "打法素材",
    }.get(value, value)


if __name__ == "__main__":
    main()
