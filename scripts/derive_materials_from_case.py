#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from _index_state import mark_dirty
from _buildmate_lib import assert_project_root, normalize_whitespace, read_markdown, slugify, split_sentences, today_iso
from _dedupe_lib import normalize_content, normalize_title, sha256_text
from _knowledge_lib import ensure_string_list, parse_case_body


def write_material(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\n{yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()}\n---\n\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8")


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
        meta, existing_body = read_markdown(path)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="从一个案例派生 story/insight/playbook 素材草稿")
    parser.add_argument("case_path")
    parser.add_argument("--root", default=".")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = assert_project_root(Path(args.root))
    case_path = Path(args.case_path).resolve()
    meta, body = read_markdown(case_path)
    parsed = parse_case_body(body)
    sections = parsed.get("sections", {})

    case_title = str(meta.get("title") or case_path.stem)
    source_ref = str(case_path.relative_to(root)) if case_path.is_relative_to(root) else str(case_path)
    common = {
        "tags": ensure_string_list(meta.get("result_tags")) + ensure_string_list(meta.get("strategy_tags")),
        "channel_fit": ["general"],
        "source": case_title,
        "source_refs": [source_ref],
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

    story_body = "\n".join(
        [
            sections.get("一句话业务", ""),
            sections.get("核心目标", ""),
            sections.get("最终结果", ""),
        ]
    ).strip()
    insight_body = sections.get("最值钱忠告", "") or sections.get("作战三原则", "")
    source_text = load_source_text(root, meta) or body
    quote_lines = pick_quote_lines(source_text)
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

    materials = [
        (
            "story",
            {
                "type": "story",
                "primary_claim": sections.get("一句话业务", "") or case_title,
                "claims": [sections.get("最终结果", "")],
                "ammo_type": "dual",
                "role": "opening",
                "strength": "firsthand",
                "content_sha256": sha256_text(normalize_content(story_body)),
                **common,
            },
            story_body,
        ),
        (
            "insight",
            {
                "type": "insight",
                "primary_claim": sections.get("最值钱忠告", "") or case_title,
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
                "primary_claim": quote_lines[0] if quote_lines else "",
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

    created = []
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
        output_path = root / "assets/materials" / subtype / f"{slugify(material_meta['primary_claim'])}.md"
        if output_path.exists() and not args.overwrite:
            continue
        write_material(output_path, material_meta, material_body)
        created.append(str(output_path))

    for item in created:
        print(f"Created material: {item}")
    if created:
        mark_dirty(root, "materials", reason="derive_materials_from_case")
        print(f"Index state updated: materials marked dirty. Run /opt/miniconda3/bin/python3 scripts/flush_indexes.py --root {root} --bucket materials")
    if not created:
        print("No new materials were created.")


if __name__ == "__main__":
    main()
