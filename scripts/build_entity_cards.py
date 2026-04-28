#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from _buildmate_lib import slugify, write_markdown
from _knowledge_lib import normalize_preview, parse_frontmatter


INTRO_CUES = ("自我介绍", "我是", "作者", "介绍", "普通人", "背景")
ACHIEVEMENT_CUES = ("盈利", "收入", "流水", "利润", "变现", "做到", "赚", "七位数", "六位数", "十万", "40万", "300+")
METHODOLOGY_CUES = ("心法", "方法", "原则", "SOP", "流程", "标准化", "自动化", "放大", "验证层", "能力层", "认知层", "跑通")
STRONG_METHODOLOGY_CUES = (
    "三点“放大”心法",
    "三点\"放大\"心法",
    "能力层",
    "认知层",
    "验证层",
    "标准化流程",
    "系统性拆解",
    "降低个人成本",
    "复制放大",
    "复刻放大",
    "规模化",
    "工具高度完成",
)
WEAK_METHOD_PREFIXES = ("但", "所以", "因此", "而且", "然后")
NUMBER_RE = re.compile(r"\d+(?:[.+万%]|个|位)?")


def chunk_body(body: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]


def clean_block(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", str(text or ""))
    cleaned = re.sub(r"^\s*#+\s*", "", cleaned)
    cleaned = re.sub(r"\s*>+\s*", " ", cleaned)
    cleaned = cleaned.replace("**", "")
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def score_intro_block(author: str, text: str) -> int:
    score = 0
    if author and author in text:
        score += 4
    if any(cue in text for cue in INTRO_CUES):
        score += 3
    if "年" in text or "毕业" in text or "辞职" in text:
        score += 2
    if 12 <= len(text) <= 120:
        score += 2
    if len(text) > 180:
        score -= 2
    if any(cue in text for cue in METHODOLOGY_CUES):
        score -= 1
    return score


def score_achievement_block(text: str) -> int:
    score = 0
    cue_hits = sum(1 for cue in ACHIEVEMENT_CUES if cue in text)
    score += cue_hits * 2
    score += len(NUMBER_RE.findall(text))
    if 16 <= len(text) <= 220:
        score += 2
    if "为什么" in text or "方法" in text or "心法" in text:
        score -= 2
    return score


def score_method_block(text: str) -> int:
    score = 0
    cue_hits = sum(1 for cue in METHODOLOGY_CUES if cue in text)
    score += cue_hits * 2
    strong_hits = sum(1 for cue in STRONG_METHODOLOGY_CUES if cue in text)
    score += strong_hits * 4
    if "：" in text or ":" in text:
        score += 1
    if any(token in text for token in ("怎么", "如何", "只要", "核心公式", "唯一标准")):
        score += 2
    if any(prefix == text[: len(prefix)] for prefix in WEAK_METHOD_PREFIXES):
        score -= 3
    if len(text) < 12:
        score -= 4
    elif 16 <= len(text) <= 180:
        score += 3
    elif len(text) > 240:
        score -= 2
    return score


def dedupe_lines(lines: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        normalized = clean_block(line)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def rank_lines(lines: list[str], scorer) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        score = scorer(line)
        if score <= 0:
            continue
        scored.append((score, -idx, line))
    scored.sort(reverse=True)
    return [line for _, _, line in scored]


def pick_intro_blocks(author: str, blocks: list[str]) -> list[str]:
    picked: list[str] = []
    for block in blocks[:16]:
        cleaned = clean_block(block)
        if not cleaned:
            continue
        if score_intro_block(author, cleaned) > 0:
            picked.append(cleaned)
    ranked = rank_lines(dedupe_lines(picked), lambda text: score_intro_block(author, text))
    return ranked[:3]


def pick_achievement_blocks(blocks: list[str]) -> list[str]:
    picked: list[str] = []
    for block in blocks[:40]:
        cleaned = clean_block(block)
        if not cleaned:
            continue
        if score_achievement_block(cleaned) > 0:
            picked.append(cleaned)
    ranked = rank_lines(dedupe_lines(picked), score_achievement_block)
    return ranked[:4]


def pick_method_blocks(blocks: list[str]) -> list[str]:
    picked: list[str] = []
    for block in blocks[:60]:
        cleaned = clean_block(block)
        if not cleaned:
            continue
        if score_method_block(cleaned) > 0:
            picked.append(cleaned)
    ranked = rank_lines(dedupe_lines(picked), score_method_block)
    return ranked[:4]


def build_card_body(
    name: str,
    intro_lines: list[str],
    achievement_lines: list[str],
    method_lines: list[str],
    source_refs: list[str],
) -> str:
    lines = [f"# {name}", "", "## 简介", ""]
    if intro_lines:
        for line in intro_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- 待补充：暂未自动抽出稳定的人物简介。")

    lines.extend(["", "## 代表经历", ""])
    if achievement_lines:
        for line in achievement_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- 待补充：暂未自动抽出稳定的结果/经历片段。")

    lines.extend(["", "## 方法论", ""])
    if method_lines:
        for line in method_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- 待补充：暂未自动抽出稳定的方法论片段。")

    lines.extend(["", "## 来源", ""])
    for ref in source_refs[:8]:
        lines.append(f"- {ref}")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="从 sources 自动派生人物实体卡")
    parser.add_argument("--root", default=".")
    parser.add_argument("--sources-dir", default="sources")
    parser.add_argument("--entities-dir", default="assets/entities/people")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sources_dir = root / args.sources_dir
    entities_dir = root / args.entities_dir
    entities_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(sources_dir.rglob("*.md")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        author = str(meta.get("author", "") or "").strip()
        if not author:
            continue
        grouped[author].append(
            {
                "path": str(path.relative_to(root)),
                "title": str(meta.get("title", path.stem) or path.stem).strip(),
                "origin": str(meta.get("origin", "") or "").strip(),
                "summary": str(meta.get("summary", "") or "").strip(),
                "date": str(meta.get("date", "") or "").strip(),
                "tags": [str(tag).strip() for tag in meta.get("tags", []) if str(tag).strip()],
                "blocks": chunk_body(body),
            }
        )

    count = 0
    for author, entries in grouped.items():
        intro_lines: list[str] = []
        achievement_lines: list[str] = []
        method_lines: list[str] = []
        origin_refs: list[str] = []
        source_refs: list[str] = []
        tags: list[str] = []
        for entry in entries:
            source_refs.append(entry["path"])
            if entry["origin"]:
                origin_refs.append(entry["origin"])
            tags.extend(entry["tags"])
            if entry["summary"]:
                intro_lines.append(entry["summary"])
            intro_lines.extend(pick_intro_blocks(author, entry["blocks"]))
            achievement_lines.extend(pick_achievement_blocks(entry["blocks"]))
            method_lines.extend(pick_method_blocks(entry["blocks"]))

        deduped_intro = dedupe_lines(intro_lines)
        deduped_achievements = dedupe_lines(achievement_lines)
        deduped_methods = dedupe_lines(method_lines)

        body = build_card_body(author, deduped_intro[:3], deduped_achievements[:4], deduped_methods[:4], source_refs)
        meta = {
            "entity_type": "person",
            "name": author,
            "aliases": [],
            "title": f"{author} 人物卡",
            "summary": normalize_preview("；".join(deduped_intro[:2]) or f"{author} 的人物简介卡", limit=180),
            "background_summary": normalize_preview(deduped_intro[0] if deduped_intro else "", limit=180),
            "achievement_summary": normalize_preview(deduped_achievements[0] if deduped_achievements else "", limit=180),
            "methodology_summary": normalize_preview(deduped_methods[0] if deduped_methods else "", limit=180),
            "source_count": len(source_refs),
            "source_refs": source_refs,
            "origin_refs": sorted(set(origin_refs)),
            "tags": sorted(set(tags)),
            "review_status": "draft",
        }
        output_path = entities_dir / f"{slugify(author)}.md"
        write_markdown(output_path, meta, body)
        count += 1

    print(f"Built {count} entity cards into {entities_dir}")


if __name__ == "__main__":
    main()
