#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from _io_safety import atomic_write_text, file_lock
from _index_state import mark_dirty
from _buildmate_lib import (
    assert_project_root,
    clean_markup,
    derive_story_outline,
    extract_numeric_phrases,
    normalize_whitespace,
    read_markdown,
    slugify,
    split_sentences,
    today_iso,
    truncate,
)
from _dedupe_lib import normalize_content, normalize_title, sha256_text
from _knowledge_lib import ensure_string_list, parse_case_body


def write_material(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\n{yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()}\n---\n\n{body.strip()}\n"
    atomic_write_text(path, content, encoding="utf-8")


def find_existing_material_duplicate(
    root: Path,
    subtype: str,
    derived_from_case: str,
    primary_claim: str,
    body: str,
) -> Path | None:
    target_dir = root / "assets/materials" / subtype
    if not target_dir.exists():
        return None
    target_hash = sha256_text(normalize_content(body))
    target_claim = normalize_title(primary_claim)
    for path in sorted(target_dir.rglob("*.md")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        try:
            meta, existing_body = read_markdown(path)
        except Exception:
            continue
        same_case = str(meta.get("derived_from_case", "") or "") == str(derived_from_case or "")
        same_type = str(meta.get("type", "") or "") == subtype
        if not same_case or not same_type:
            continue
        existing_hash = str(meta.get("content_sha256") or sha256_text(normalize_content(existing_body)))
        existing_claim = normalize_title(str(meta.get("primary_claim", "") or ""))
        if existing_hash == target_hash or (target_claim and existing_claim == target_claim):
            return path
    return None


def load_source_text(root: Path, meta: dict) -> str:
    candidates = ensure_string_list(meta.get("source_refs"))
    source_path = str(meta.get("source_path", "") or "").strip()
    if source_path:
        candidates.append(source_path)
    for candidate in candidates:
        path = root / candidate
        if path.exists() and path.is_file():
            _source_meta, source_body = read_markdown(path)
            return source_body
    return ""


def pick_quote_lines(text: str, limit: int = 2) -> list[str]:
    cues = ("记住", "别", "不要", "一定", "先", "哈哈", "真的", "就是", "其实", "根本", "别怂")
    candidates: list[tuple[int, str]] = []
    for sentence in split_sentences(text):
        cleaned = normalize_whitespace(sentence.strip("“”\"'"))
        if len(cleaned) < 6 or len(cleaned) > 30:
            continue
        score = 0
        if any(cue in cleaned for cue in cues):
            score += 3
        if cleaned.endswith(("啊", "呀", "呢", "吧", "了")):
            score += 1
        if any(token in cleaned for token in ("不要", "别", "记住", "一定")):
            score += 2
        if "..." in cleaned or "——" in cleaned:
            score += 1
        if score <= 0:
            continue
        candidates.append((score, cleaned))
    deduped: list[str] = []
    seen: set[str] = set()
    for _score, candidate in sorted(candidates, key=lambda item: item[0], reverse=True):
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


def build_association_lines(case_title: str, insight_text: str, core_goal: str, one_line_business: str) -> list[str]:
    seed = normalize_whitespace(insight_text or core_goal or one_line_business or case_title)
    short_case = normalize_whitespace(case_title)[:24]
    short_business = normalize_whitespace(one_line_business or core_goal or "这套打法")[:24]
    lines = [
        f"{seed}，有点像先搭脚手架再盖楼，先把重复动作稳定下来。",
        f"{short_case}，可以类比成把一次性灵感改造成可复制的流水线。",
        f"{short_business}，本质上接近先跑通单点，再做规模化放大。",
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = normalize_whitespace(line)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped[:3]


def dedupe_texts(values: list[str], limit: int | None = None) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = normalize_whitespace(clean_markup(value))
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


def safe_claim(text: str, fallback: str, *, limit: int = 64) -> str:
    cleaned = normalize_whitespace(clean_markup(text))
    if not cleaned:
        cleaned = normalize_whitespace(clean_markup(fallback))
    return truncate(cleaned or "未命名素材", limit)


def material_output_stem(material_meta: dict) -> str:
    material_type = str(material_meta.get("type", "") or "").strip()
    source_title = safe_claim(str(material_meta.get("source", "") or ""), "来源", limit=28)
    story_arc = str(material_meta.get("story_arc", "") or "").strip()
    if material_type == "story" and story_arc:
        return slugify(f"{source_title}_{story_arc}")
    if material_type == "data":
        return slugify(f"{source_title}_data")
    return slugify(safe_claim(str(material_meta.get("primary_claim", "") or ""), source_title, limit=48))


def build_story_body(
    *,
    arc: str,
    actor_label: str,
    focal_text: str,
    support_texts: list[str],
    evidence_lines: list[str],
) -> str:
    labels = {
        "origin": "故事起点",
        "turn": "关键转折",
        "payoff": "结果兑现",
    }
    lead = labels.get(arc, "故事片段")
    if focal_text.startswith(("我", "他", "她", "作者", "一位", "某")):
        first_line = f"{lead}里，{focal_text}"
    else:
        first_line = f"{lead}里，{actor_label}，{focal_text}"
    lines = [first_line]
    for text in dedupe_texts(support_texts, limit=2):
        if text != focal_text:
            lines.append(text)
    if evidence_lines:
        lines.extend(["", "故事证据："])
        lines.extend([f"- {line}" for line in evidence_lines[:3]])
    return "\n".join(lines).strip()


def pick_numeric_evidence_lines(text: str, limit: int = 3) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for sentence in split_sentences(text):
        cleaned = normalize_whitespace(clean_markup(sentence))
        if not cleaned or not any(char.isdigit() for char in cleaned):
            continue
        score = 0
        score += 2 if any(token in cleaned for token in ["赚", "收入", "变现", "盈利", "播放", "粉丝", "增长", "成交", "开通"]) else 0
        score += 1 if any(token in cleaned for token in ["天", "周", "月", "年", "%", "万", "刀"]) else 0
        score += 1 if len(extract_numeric_phrases(cleaned)) >= 2 else 0
        candidates.append((score, cleaned))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return dedupe_texts([item[1] for item in candidates], limit=limit)


def build_case_material_specs(root: Path, case_path: Path, meta: dict, body: str) -> list[tuple[str, dict, str]]:
    parsed = parse_case_body(body)
    sections = parsed.get("sections", {})

    case_title = str(meta.get("title") or case_path.stem)
    source_ref = str(case_path.relative_to(root)) if case_path.is_relative_to(root) else str(case_path)
    original_source_ref = str(meta.get("source_path", "") or "").strip()
    source_refs = dedupe_texts([source_ref, original_source_ref])
    common = {
        "tags": ensure_string_list(meta.get("result_tags")) + ensure_string_list(meta.get("strategy_tags")),
        "channel_fit": ["general"],
        "source": case_title,
        "source_refs": source_refs,
        "derived_from_case": meta.get("case_id", ""),
        "date": str(meta.get("date") or today_iso()),
        "quality_score": 3.0,
        "use_count": 0,
        "last_used_at": None,
        "used_in_articles": [],
        "impact_log": [],
        "source_reliability": 4.0,
        "review_status": "draft",
    }

    insight_body = sections.get("最值钱忠告", "") or sections.get("作战三原则", "")
    source_text = load_source_text(root, meta)
    story_basis_text = source_text or "\n".join(
        [
            sections.get("一句话业务", ""),
            sections.get("作者是谁", ""),
            sections.get("启动资源", ""),
            sections.get("核心目标", ""),
            sections.get("最大一个坑", ""),
            sections.get("最终结果", ""),
        ]
    )
    quote_lines = pick_quote_lines(source_text or story_basis_text)
    association_lines = build_association_lines(
        case_title=case_title,
        insight_text=insight_body,
        core_goal=sections.get("核心目标", ""),
        one_line_business=sections.get("一句话业务", ""),
    )
    playbook_body = "\n".join(
        [f"{i + 1}. {step}" for i, step in enumerate(ensure_string_list(meta.get("sequence_steps")))]
    )
    if not playbook_body:
        playbook_body = sections.get("最值钱忠告", "") or sections.get("核心目标", "")

    actor_label = sections.get("作者是谁", "")
    actor_label = actor_label if actor_label and actor_label != "待补充" else "文中这个操盘者"
    story_outline = derive_story_outline(
        body=story_basis_text,
        title=case_title,
        author_identity=sections.get("作者是谁", ""),
        one_line_business=sections.get("一句话业务", ""),
        core_goal=sections.get("核心目标", ""),
        final_result=sections.get("最终结果", ""),
        pitfall_text=sections.get("最大一个坑", ""),
        existing_sections=sections,
    )
    evidence_lines = dedupe_texts(
        ensure_string_list(sections.get("故事证据")) + ensure_string_list(story_outline.get("evidence_blocks", [])),
        limit=3,
    )
    if not evidence_lines:
        evidence_lines = pick_numeric_evidence_lines(story_basis_text, limit=2)

    story_specs: list[tuple[str, dict, str]] = []
    story_definitions = [
        (
            "origin",
            "opening",
            sections.get("起点处境", "") or story_outline.get("start", ""),
            [
                sections.get("一句话业务", ""),
                sections.get("核心目标", ""),
                sections.get("启动资源", ""),
            ],
        ),
        (
            "turn",
            "turn",
            sections.get("关键转折", "") or story_outline.get("turn", ""),
            [
                sections.get("最大一个坑", ""),
                sections.get("核心目标", ""),
            ],
        ),
        (
            "payoff",
            "argument",
            sections.get("结果兑现", "") or story_outline.get("payoff", ""),
            [
                sections.get("最终结果", ""),
                sections.get("一句话业务", ""),
            ],
        ),
    ]
    for arc, role, focal_text, support_texts in story_definitions:
        focal = safe_claim(focal_text, case_title)
        if not focal or focal == "待补充":
            continue
        body_text = build_story_body(
            arc=arc,
            actor_label=actor_label,
            focal_text=focal,
            support_texts=support_texts,
            evidence_lines=evidence_lines,
        )
        story_specs.append(
            (
                "story",
                {
                    "type": "story",
                    "story_arc": arc,
                    "primary_claim": focal,
                    "claims": dedupe_texts([focal, *support_texts, *evidence_lines], limit=4),
                    "ammo_type": "dual",
                    "role": role,
                    "strength": "firsthand",
                    "content_sha256": sha256_text(normalize_content(body_text)),
                    **common,
                },
                body_text,
            )
        )

    numeric_lines = pick_numeric_evidence_lines(
        "\n".join(
            [
                sections.get("最终结果", ""),
                sections.get("结果兑现", ""),
                story_basis_text,
            ]
        ),
        limit=3,
    )
    materials: list[tuple[str, dict, str]] = [*story_specs]
    if numeric_lines:
        data_body_lines = ["这个案例里最硬的不是观点，而是几组已经发生的结果数字："]
        data_body_lines.extend([f"- {line}" for line in numeric_lines])
        payoff_line = normalize_whitespace(clean_markup(sections.get("结果兑现", "") or sections.get("最终结果", "")))
        if payoff_line:
            data_body_lines.extend(["", f"这些数字真正支撑的是这条结果兑现：{payoff_line}"])
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
                    "strength": "firsthand",
                    "content_sha256": sha256_text(normalize_content(data_body)),
                    **common,
                },
                data_body,
            )
        )

    materials.extend(
        [
            (
                "insight",
                {
                    "type": "insight",
                    "primary_claim": safe_claim(sections.get("最值钱忠告", ""), case_title),
                    "claims": [sections.get("核心目标", "")],
                    "ammo_type": "dual",
                    "role": "argument",
                    "strength": "observation",
                    "content_sha256": sha256_text(normalize_content(insight_body)),
                    **common,
                },
                insight_body,
            ),
            (
                "playbook",
                {
                    "type": "playbook",
                    "primary_claim": f"{case_title} 的可执行打法",
                    "claims": ensure_string_list(meta.get("sequence_steps"))[:3],
                    "ammo_type": "substance",
                    "role": "argument",
                    "strength": "firsthand",
                    "content_sha256": sha256_text(normalize_content(playbook_body)),
                    **common,
                },
                playbook_body,
            ),
            (
                "quote",
                {
                    "type": "quote",
                    "primary_claim": safe_claim(quote_lines[0] if quote_lines else "", case_title),
                    "claims": quote_lines[:2],
                    "ammo_type": "hook",
                    "role": "argument",
                    "strength": "firsthand",
                    "content_sha256": sha256_text(normalize_content("\n".join([f"- {line}" for line in quote_lines]).strip())),
                    **common,
                },
                "\n".join([f"- {line}" for line in quote_lines]).strip(),
            ),
            (
                "association",
                {
                    "type": "association",
                    "primary_claim": f"{case_title} 的跨领域联想",
                    "claims": association_lines[:3],
                    "ammo_type": "hook",
                    "role": "argument",
                    "strength": "observation",
                    "content_sha256": sha256_text(normalize_content("\n".join([f"- {line}" for line in association_lines]).strip())),
                    **common,
                },
                "\n".join([f"- {line}" for line in association_lines]).strip(),
            ),
        ]
    )
    return materials


def main() -> None:
    parser = argparse.ArgumentParser(description="从一个案例派生 story/insight/playbook 素材草稿")
    parser.add_argument("case_path")
    parser.add_argument("--root", default=".")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    case_path = Path(args.case_path).resolve()
    meta, body = read_markdown(case_path)
    materials = build_case_material_specs(root, case_path, meta, body)

    created = []
    with file_lock(root, "ingest"):
        for subtype, material_meta, material_body in materials:
            if not material_body.strip():
                continue
            duplicate_path = find_existing_material_duplicate(
                root,
                subtype,
                str(material_meta.get("derived_from_case", "") or ""),
                str(material_meta.get("primary_claim", "") or ""),
                material_body,
            )
            if duplicate_path and not args.overwrite:
                continue
            output_path = root / "assets/materials" / subtype / f"{material_output_stem(material_meta)}.md"
            if output_path.exists() and not args.overwrite:
                continue
            write_material(output_path, material_meta, material_body)
            created.append(str(output_path))

        if created:
            mark_dirty(root, "materials", reason="derive_materials_from_case")

    for item in created:
        print(f"Created material: {item}")
    if created:
        print(f"Index state updated: materials marked dirty. Run /opt/miniconda3/bin/python3 scripts/flush_indexes.py --root {root} --bucket materials")
    if not created:
        print("No new materials were created.")


if __name__ == "__main__":
    main()
