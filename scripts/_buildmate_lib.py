#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml

from _llm_client import call_deepseek_json, validate_deepseek_backend
from _io_safety import atomic_write_jsonl, atomic_write_text


REQUIRED_CASE_SECTIONS = [
    "一句话业务",
    "作者是谁",
    "启动资源",
    "核心目标",
    "最终结果",
    "决策地图",
    "作战三原则",
    "最大一个坑",
    "最值钱忠告",
    "待验证推测",
]

STORY_START_KEYWORDS = [
    "我是",
    "当时",
    "一开始",
    "最开始",
    "刚开始",
    "背景",
    "毕业",
    "失业",
    "辞职",
    "副业",
    "没有",
    "第一次",
]

STORY_TURN_KEYWORDS = [
    "后来",
    "但是",
    "但",
    "结果",
    "直到",
    "没想到",
    "于是",
    "卡住",
    "失败",
    "踩坑",
    "封号",
    "改成",
    "改为",
    "转向",
]

STORY_PAYOFF_KEYWORDS = [
    "最终",
    "最后",
    "后来",
    "赚",
    "收入",
    "变现",
    "增长",
    "盈利",
    "月入",
    "播放",
    "成交",
    "开通",
    "做到",
]

ACTION_VERBS = [
    "打开",
    "点击",
    "输入",
    "搜索",
    "选择",
    "复制",
    "粘贴",
    "导出",
    "创建",
    "填写",
    "设置",
    "发布",
    "私信",
    "回复",
    "测试",
    "对比",
    "筛选",
    "整理",
    "统计",
    "记录",
    "复盘",
    "上传",
    "下载",
    "截图",
    "建立",
    "调整",
    "拆解",
]

VAGUE_PRINCIPLE_TERMS = [
    "坚持",
    "专注",
    "别放弃",
    "持续学习",
    "努力",
    "执行力",
    "长期主义",
    "多尝试",
]

DECISION_KEYWORDS = [
    "决定",
    "选择",
    "改成",
    "改为",
    "放弃",
    "开始",
    "尝试",
    "测试",
    "优化",
    "定位",
    "定价",
    "发布",
    "上架",
    "引流",
    "转化",
]

GOAL_KEYWORDS = ["目标", "想", "希望", "为了", "打算", "计划", "先做", "想要"]
RESULT_KEYWORDS = ["赚", "收入", "变现", "成交", "粉丝", "阅读", "点赞", "复购", "增长", "新增"]
PITFALL_KEYWORDS = ["坑", "问题", "失败", "踩坑", "亏", "封号", "低", "卡住", "风险"]
ADVICE_KEYWORDS = ["建议", "一定要", "记住", "最好", "不要", "务必", "核心", "关键"]
RESOURCE_KEYWORDS = ["元", "万", "小时", "每天", "每周", "一个人", "自己", "电脑", "手机", "技能", "合伙"]
TOOL_HINTS = [
    "稿定设计",
    "Canva",
    "Figma",
    "飞书",
    "Notion",
    "Excel",
    "表格",
    "小红书",
    "抖音",
    "微信",
    "企微",
    "有赞",
    "知识星球",
    "小报童",
]

INFERENCE_HINTS = [
    "推测",
    "猜测",
    "原文未",
    "未说明",
    "未明确",
    "可能",
    "估计",
    "疑似",
    "大概",
]

ALLOWED_CAUSAL_STATUS = {
    "unknown",
    "single_case_hypothesis",
    "cross_case_validated",
    "counterfactual_checked",
    "refuted",
}


@dataclass
class Decision:
    decision_point: str
    choice: str
    basis: str
    action_steps: list[str]
    tools: list[str]
    params: list[str]
    inferred: bool
    evidence: str


def slugify(text: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", text).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "untitled"


def today_iso() -> str:
    return date.today().isoformat()


def assert_project_root(root: Path) -> Path:
    resolved = root.resolve()
    if not (resolved / "SKILL.md").exists():
        raise SystemExit(
            f"Error: {resolved} is not a valid project root (missing SKILL.md). "
            "Run the script from the skill root or pass --root with the project root."
        )
    return resolved


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text.strip()
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text.strip()
    raw_meta = parts[0][4:]
    body = parts[1].strip()
    meta = yaml.safe_load(raw_meta) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def dump_frontmatter(meta: dict) -> str:
    return yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()


def read_markdown(path: Path) -> tuple[dict, str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def write_markdown(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\n{dump_frontmatter(meta)}\n---\n\n{body.strip()}\n"
    atomic_write_text(path, content, encoding="utf-8")


def list_markdown_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.md"))
        if path.is_file() and not path.name.startswith("_")
    ]


def ensure_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value).strip()]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def clean_markup(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", cleaned)
    cleaned = cleaned.replace("**", " ")
    cleaned = cleaned.replace("__", " ")
    cleaned = cleaned.replace("```", " ")
    return normalize_whitespace(cleaned)


def split_sentences(text: str) -> list[str]:
    raw_parts = re.split(r"[。\n！？!?；;]+", clean_markup(text))
    results = []
    for part in raw_parts:
        normalized = normalize_whitespace(part)
        if len(normalized) >= 4:
            results.append(normalized)
    return results


def split_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    seen: set[str] = set()
    for raw_block in re.split(r"\n\s*\n", str(text or "")):
        cleaned = clean_markup(raw_block)
        if len(cleaned) < 8 or cleaned in seen:
            continue
        seen.add(cleaned)
        blocks.append(cleaned)
    return blocks


def pick_first(sentences: Iterable[str], keywords: list[str]) -> str | None:
    for sentence in sentences:
        if any(keyword in sentence for keyword in keywords):
            return sentence
    return None


def pick_many(sentences: Iterable[str], keywords: list[str], limit: int = 3) -> list[str]:
    hits: list[str] = []
    for sentence in sentences:
        if any(keyword in sentence for keyword in keywords):
            hits.append(sentence)
        if len(hits) >= limit:
            break
    return hits


def has_story_shape(text: str) -> bool:
    cleaned = clean_markup(text)
    if len(cleaned) < 16:
        return False
    score = 0
    if any(token in cleaned for token in ["我", "他", "她", "作者", "一位", "某", "这个人"]):
        score += 1
    if any(token in cleaned for token in STORY_START_KEYWORDS + STORY_TURN_KEYWORDS + STORY_PAYOFF_KEYWORDS):
        score += 1
    if any(token in cleaned for token in ACTION_VERBS):
        score += 1
    if any(char.isdigit() for char in cleaned):
        score += 1
    return score >= 2


def _score_story_text(
    text: str,
    *,
    keywords: list[str],
    prefer_numbers: bool = False,
    prefer_actions: bool = False,
) -> int:
    cleaned = clean_markup(text)
    if not cleaned:
        return -10
    score = 0
    score += sum(3 for keyword in keywords if keyword and keyword in cleaned)
    if any(token in cleaned for token in ["我", "他", "她", "作者", "一位", "某"]):
        score += 2
    if any(token in cleaned for token in ACTION_VERBS):
        score += 2 if prefer_actions else 1
    if any(char.isdigit() for char in cleaned):
        score += 2 if prefer_numbers else 1
    if len(cleaned) < 12:
        score -= 4
    elif 18 <= len(cleaned) <= 140:
        score += 2
    elif len(cleaned) > 220:
        score -= 2
    if not has_story_shape(cleaned):
        score -= 1
    return score


def pick_story_candidate(
    values: Iterable[str],
    *,
    keywords: list[str],
    prefer_numbers: bool = False,
    prefer_actions: bool = False,
    fallback: str = "",
) -> str:
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for value in values:
        cleaned = clean_markup(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ranked.append(
            (
                _score_story_text(
                    cleaned,
                    keywords=keywords,
                    prefer_numbers=prefer_numbers,
                    prefer_actions=prefer_actions,
                ),
                cleaned,
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    if ranked and ranked[0][0] > 0:
        return ranked[0][1]
    return clean_markup(fallback)


def pick_story_evidence_blocks(text: str, limit: int = 3) -> list[str]:
    ranked: list[tuple[int, str]] = []
    for block in split_blocks(text):
        score = _score_story_text(
            block,
            keywords=STORY_START_KEYWORDS + STORY_TURN_KEYWORDS + STORY_PAYOFF_KEYWORDS,
            prefer_numbers=True,
            prefer_actions=True,
        )
        if score <= 0:
            continue
        ranked.append((score, block))
    ranked.sort(key=lambda item: item[0], reverse=True)
    evidence: list[str] = []
    seen: set[str] = set()
    for _score, block in ranked:
        if block in seen:
            continue
        seen.add(block)
        evidence.append(block)
        if len(evidence) >= limit:
            break
    return evidence


def derive_story_outline(
    *,
    body: str,
    title: str = "",
    author_identity: str = "",
    one_line_business: str = "",
    core_goal: str = "",
    final_result: str = "",
    pitfall_text: str = "",
    decisions: list[Decision] | None = None,
    existing_sections: dict[str, str] | None = None,
) -> dict[str, Any]:
    sections = existing_sections or {}
    decision_texts: list[str] = []
    for decision in decisions or []:
        if decision.choice:
            decision_texts.append(decision.choice)
        if decision.basis:
            decision_texts.append(decision.basis)
        if decision.evidence:
            decision_texts.append(decision.evidence)
        decision_texts.extend(decision.action_steps[:2])

    source_sentences = split_sentences(body)
    evidence_blocks = pick_story_evidence_blocks(body, limit=3)

    start_candidates = [
        sections.get("起点处境", ""),
        sections.get("作者是谁", ""),
        sections.get("启动资源", ""),
        sections.get("一句话业务", ""),
        author_identity,
        one_line_business,
    ]
    start_candidates.extend(source_sentences[:10])
    start_candidates.extend(evidence_blocks[:2])

    turn_candidates = [
        sections.get("关键转折", ""),
        sections.get("最大一个坑", ""),
        pitfall_text,
    ]
    turn_candidates.extend(decision_texts[:8])
    turn_candidates.extend(source_sentences)
    turn_candidates.extend(evidence_blocks)

    payoff_candidates = [
        sections.get("结果兑现", ""),
        sections.get("最终结果", ""),
        final_result,
        core_goal,
    ]
    payoff_candidates.extend(decision_texts[:4])
    payoff_candidates.extend(source_sentences)
    payoff_candidates.extend(evidence_blocks)

    start = pick_story_candidate(
        start_candidates,
        keywords=STORY_START_KEYWORDS,
        prefer_actions=False,
        fallback=author_identity or one_line_business or title,
    )
    turn = pick_story_candidate(
        turn_candidates,
        keywords=STORY_TURN_KEYWORDS + PITFALL_KEYWORDS + DECISION_KEYWORDS,
        prefer_actions=True,
        fallback=pitfall_text,
    )
    payoff = pick_story_candidate(
        payoff_candidates,
        keywords=STORY_PAYOFF_KEYWORDS + RESULT_KEYWORDS,
        prefer_numbers=True,
        fallback=final_result or core_goal,
    )

    if not evidence_blocks:
        evidence_blocks = [item for item in [start, turn, payoff] if item]

    return {
        "start": start,
        "turn": turn,
        "payoff": payoff,
        "evidence_blocks": evidence_blocks[:3],
    }


def pick_best_goal(sentences: list[str]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for sentence in sentences:
        if not any(keyword in sentence for keyword in GOAL_KEYWORDS):
            continue
        score = 0
        score += 2 if any(token in sentence for token in ["目标", "想", "希望", "打算"]) else 0
        score += 1 if any(char.isdigit() for char in sentence) else 0
        score -= 1 if any(token in sentence for token in ["变现", "成交", "粉丝增长", "累计"]) else 0
        candidates.append((score, sentence))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def pick_best_result(sentences: list[str]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for sentence in sentences:
        if not any(keyword in sentence for keyword in RESULT_KEYWORDS):
            continue
        score = 0
        score += 2 if any(token in sentence for token in ["变现", "收入", "成交", "粉丝", "增长"]) else 0
        score += 2 if any(token in sentence for token in ["后来", "最终", "最后", "个月后", "天后", "累计"]) else 0
        score += 1 if any(char.isdigit() for char in sentence) else 0
        score -= 2 if any(token in sentence for token in ["目标", "想", "希望", "打算"]) else 0
        candidates.append((score, sentence))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def collect_tool_hints(text: str) -> list[str]:
    return [tool for tool in TOOL_HINTS if tool in text]


def extract_numeric_phrases(text: str) -> list[str]:
    matches = re.findall(r"[A-Za-z#\d\.]+(?:元|万|小时|篇|天|月|个|%|号字|粉|次)?", text)
    cleaned = []
    for match in matches:
        candidate = match.strip()
        if len(candidate) >= 2 and any(char.isdigit() for char in candidate):
            cleaned.append(candidate)
    return cleaned[:5]


def derive_domain(meta: dict, body: str) -> str:
    if meta.get("domain"):
        return str(meta["domain"]).strip()
    haystack = f"{meta.get('title', '')} {body}"
    if "小红书" in haystack or "抖音" in haystack:
        return "内容副业"
    if "私域" in haystack or "微信" in haystack:
        return "私域运营"
    if "知识星球" in haystack or "小报童" in haystack:
        return "知识付费"
    return "待补充"


def derive_platform(meta: dict, body: str) -> str:
    if meta.get("platform"):
        return str(meta["platform"]).strip()
    haystack = f"{meta.get('origin', '')} {meta.get('title', '')} {body}"
    for platform in ["小红书", "抖音", "微信", "知乎", "视频号", "B站"]:
        if platform in haystack:
            return platform
    return "待补充"


def derive_case_id(source_path: Path) -> str:
    return f"case_{slugify(source_path.stem).lower()}"


def _compact_text(text: str) -> str:
    return normalize_whitespace(str(text or ""))


def _build_extraction_prompt(title: str, author: str, summary: str, body: str) -> tuple[str, str]:
    """Build system and user prompts for case extraction."""
    system_prompt = (
        "你是一个把中文口语化经验分享文抽取成案例结构的编辑。"
        "你的目标是提炼作者的决策逻辑和可执行打法，而不是复述原文。"
        "口语化表达、段子、语气词需要还原成结构化的决策点和动作步骤。"
        "请只返回 JSON，不要输出解释。"
        "如果原文没有明确说出内容，就返回空字符串或空数组，不要编造。"
    )
    user_prompt = (
        "请从下面的原文中提取案例结构字段，返回 JSON 对象，字段如下：\n"
        "{\n"
        '  "one_line_business": "",\n'
        '  "author_identity": "",\n'
        '  "startup_resources": {"现金流": "", "时间": "", "技能": "", "团队/设备": "", "其他": ""},\n'
        '  "core_goal": "",\n'
        '  "final_result": "",\n'
        '  "story_start": "",\n'
        '  "story_turn": "",\n'
        '  "story_payoff": "",\n'
        '  "story_evidence": ["", ""],\n'
        '  "pitfall_sentence": "",\n'
        '  "pitfall_solution": "",\n'
        '  "advice": "",\n'
        '  "decisions": [\n'
        "    {\n"
        '      "decision_point": "",\n'
        '      "choice": "",\n'
        '      "basis": "",\n'
        '      "action_steps": ["", ""],\n'
        '      "tools": ["", ""],\n'
        '      "params": ["", ""],\n'
        '      "evidence": "",\n'
        '      "inferred": false\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "要求：\n"
        "1. decision_point 要写成真正的十字路口（面临什么选择），而不是空泛总结。\n"
        "2. action_steps 尽量写成带动作动词的可执行步骤，如\"准备5张不同主图→按错位原则排列→做10个链接\"。\n"
        "3. 最多返回 5 个 decisions，优先选择有具体操作步骤的决策点。\n"
        "4. 口语化表达要还原成结构化动作，例如\"前期不要烧钱\"→\"前期不投付费推广，先打满认证标+保持5A勋章\"。\n"
        "5. one_line_business 用一句话概括作者的核心业务或经验领域。\n"
        "6. core_goal 写作者想要达成的具体目标，不是文章主题。\n"
        "7. advice 提取最有实操价值的一句忠告。\n"
        "8. story_start / story_turn / story_payoff 要优先保留人物、处境、动作、结果，不要写成抽象洞察。\n\n"
        f"帖子标题：{title}\n"
        f"作者：{author}\n"
        f"摘要：{summary}\n"
        "原文：\n"
        f"{body}"
    )
    return system_prompt, user_prompt


def llm_extract_case_payload(
    *,
    body: str,
    title: str = "",
    author: str = "",
    summary: str = "",
    backend: str = "auto",
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    timeout: float = 120.0,
) -> dict[str, Any]:
    validate_deepseek_backend(backend)
    system_prompt, user_prompt = _build_extraction_prompt(title, author, summary, body)
    return call_deepseek_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        temperature=0.1,
    )


def decision_from_payload(item: dict[str, Any]) -> Decision | None:
    decision_point = _compact_text(str(item.get("decision_point", "") or ""))
    choice = _compact_text(str(item.get("choice", "") or ""))
    basis = _compact_text(str(item.get("basis", "") or ""))
    evidence = _compact_text(str(item.get("evidence", "") or choice or basis))
    action_steps = [_compact_text(str(step)) for step in ensure_list(item.get("action_steps")) if _compact_text(str(step))]
    tools = [_compact_text(str(tool)) for tool in ensure_list(item.get("tools")) if _compact_text(str(tool))]
    params = [_compact_text(str(param)) for param in ensure_list(item.get("params")) if _compact_text(str(param))]
    inferred = bool(item.get("inferred"))
    if not decision_point and choice:
        decision_point = f"围绕“{truncate(choice, 18)}”做出关键选择"
    if not choice and evidence:
        choice = evidence
    if not basis and evidence:
        basis = evidence
    if not action_steps and choice:
        action_steps = [f"根据原文执行该动作：{choice}"]
    if not choice and not decision_point:
        return None
    if not any(verb in " ".join(action_steps) for verb in ACTION_VERBS):
        inferred = True
    return Decision(
        decision_point=decision_point or "待补充",
        choice=choice or "待补充",
        basis=basis or "待补充",
        action_steps=action_steps[:5],
        tools=tools[:5],
        params=params[:5],
        inferred=inferred,
        evidence=evidence or choice or decision_point,
    )


def decisions_from_payload(items: Any, limit: int = 5) -> list[Decision]:
    if not isinstance(items, list):
        return []
    decisions: list[Decision] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        decision = decision_from_payload(item)
        if decision is None:
            continue
        decisions.append(decision)
        if len(decisions) >= limit:
            break
    return decisions


def build_case_title(author_identity: str, one_line_business: str, final_result: str, source_title: str = "") -> str:
    author_label = author_identity if author_identity and author_identity != "待补充" else ""
    business_label = truncate(one_line_business or "", 18)
    if not business_label or business_label == "核心打法待补充":
        return source_title[:50] if source_title else "案例标题待补充"
    result_label = truncate(final_result or "", 18)
    parts = [f"【{author_label}】" if author_label else "", business_label]
    if result_label and result_label != "结果待补充":
        parts.append(result_label)
    return "".join(parts)


def truncate(text: str, limit: int) -> str:
    normalized = normalize_whitespace(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip("，、；;,. ") + "…"


def build_startup_resources(sentences: list[str]) -> dict[str, str]:
    resource_sentences = pick_many(sentences, RESOURCE_KEYWORDS, limit=5)
    joined = "；".join(resource_sentences) if resource_sentences else "待补充"
    return {
        "现金流": pick_first(resource_sentences, ["元", "万"]) or "待补充",
        "时间": pick_first(resource_sentences, ["小时", "每天", "每周", "下班后"]) or "待补充",
        "技能": pick_first(resource_sentences, ["技能", "会", "擅长", "运营", "写作", "修图", "设计"]) or "待补充",
        "团队/设备": pick_first(resource_sentences, ["一个人", "合伙", "电脑", "手机", "设备"]) or "待补充",
        "其他": joined,
    }


def infer_decisions(sentences: list[str], limit: int = 5) -> list[Decision]:
    decisions: list[Decision] = []
    for index, sentence in enumerate(sentences):
        if not any(keyword in sentence for keyword in DECISION_KEYWORDS):
            continue
        basis = sentence
        if index + 1 < len(sentences) and any(token in sentences[index + 1] for token in ["因为", "所以", "发现", "考虑到", "于是"]):
            basis = f"{sentence}；{sentences[index + 1]}"
        tools = collect_tool_hints(sentence)
        params = extract_numeric_phrases(sentence)
        action_steps = [f"根据原文执行该动作：{sentence}"]
        inferred = not any(verb in sentence for verb in ACTION_VERBS)
        if inferred:
            action_steps = [
                f"【推测】先在原文中定位这条动作对应的具体操作：{sentence}",
                "【推测】将动作补写成按钮级步骤，例如“打开工具 → 选择模板 → 修改标题 → 导出发布”",
            ]
        decisions.append(
            Decision(
                decision_point=f"围绕“{truncate(sentence, 18)}”做出关键选择",
                choice=sentence,
                basis=basis,
                action_steps=action_steps,
                tools=tools,
                params=params,
                inferred=inferred,
                evidence=sentence,
            )
        )
        if len(decisions) >= limit:
            break

    if decisions:
        return decisions

    fallback = pick_first(sentences, GOAL_KEYWORDS + RESULT_KEYWORDS) or "原文未明确写出关键决策"
    return [
        Decision(
            decision_point="原文未明显出现决策句，需要人工补写决策十字路口",
            choice=fallback,
            basis="待人工补充：需要回到原文定位作者真正做选择的地方",
            action_steps=[
                "【推测】通读原文，标出作者从“想法”转向“执行”的地方",
                "【推测】至少补写 1 个带具体动作动词的操作步骤",
            ],
            tools=[],
            params=[],
            inferred=True,
            evidence=fallback,
        )
    ]


def build_principles() -> list[str]:
    return [
        "每次复用这个案例前，先补全“作者是谁 / 启动资源 / 核心目标 / 最终结果”四项前提。",
        "每个关键决策必须同时写出“依据”和至少一条带动作动词的操作步骤。",
        "每次发现原文缺步骤，立即把该项标记为【推测】并追加到“待验证推测”列表。",
    ]


def build_pending_inferences(
    author_identity: str,
    startup_resources: dict[str, str],
    core_goal: str,
    final_result: str,
    decisions: list[Decision],
) -> list[str]:
    pending: list[str] = []
    if author_identity == "待补充":
        pending.append("【推测】需要补出作者身份、背景和起点条件。")
    if all(value == "待补充" for value in startup_resources.values()):
        pending.append("【推测】需要补出启动资源，包括时间、现金流、技能和团队条件。")
    if core_goal == "待补充":
        pending.append("【推测】需要从原文中确认作者最初目标，而不是只记录结果。")
    if final_result == "待补充":
        pending.append("【推测】需要补出量化结果，例如收入、粉丝、阅读量或周期。")
    if any(decision.inferred for decision in decisions):
        pending.append("【推测】至少一个决策点仍未写到按钮级动作，需要人工补足。")
    return pending or ["暂无。"]


def build_sequence_steps(decisions: list[Decision]) -> list[str]:
    steps: list[str] = []
    for index, decision in enumerate(decisions, start=1):
        label = normalize_whitespace(decision.choice or decision.decision_point)
        if not label:
            continue
        steps.append(f"{index}. {label}")
    return steps[:8]


def compute_action_granularity_score(decisions: list[Decision]) -> int:
    if not decisions:
        return 1
    total_steps = 0
    specific_steps = 0
    for decision in decisions:
        for step in decision.action_steps:
            total_steps += 1
            if has_action_specificity(step):
                specific_steps += 1
    if total_steps <= 0:
        return 1
    ratio = specific_steps / total_steps
    if ratio >= 0.9:
        return 5
    if ratio >= 0.7:
        return 4
    if ratio >= 0.45:
        return 3
    if ratio >= 0.2:
        return 2
    return 1


def extract_sections_by_heading(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^##\s+(.+)$", body, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        sections[title] = content
    return sections


def clean_heading_title(title: str) -> str:
    normalized = normalize_whitespace(title)
    if normalized.startswith("【") and normalized.endswith("】"):
        normalized = normalized[1:-1].strip()
    return normalized


def parse_bold_labeled_block(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pattern = re.compile(r"^\*\*(.+?)：\*\*\s*(.*)$", flags=re.MULTILINE)
    matches = list(pattern.finditer(text))
    for index, match in enumerate(matches):
        label = normalize_whitespace(match.group(1))
        inline_value = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        tail = text[start:end].strip()
        value_parts = [part for part in [inline_value, tail] if part]
        fields[label] = "\n".join(value_parts).strip()
    return fields


def extract_level3_section(text: str, title: str) -> str:
    pattern = re.compile(rf"^###\s+{re.escape(title)}：?\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^###\s+.+$", text[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def parse_identity_section(text: str) -> dict[str, str]:
    fields = parse_bold_labeled_block(text)
    return {
        "帖子标题": fields.get("帖子标题", ""),
        "原文链接": fields.get("原文链接", ""),
        "一句话业务": fields.get("一句话业务", ""),
        "作者是谁": fields.get("作者是谁", ""),
        "启动资源": fields.get("启动资源", ""),
        "核心目标": fields.get("核心目标", ""),
        "最终结果": fields.get("最终结果", ""),
    }


def parse_core_section(text: str) -> tuple[list[str], dict[str, str], str]:
    principles_text = extract_level3_section(text, "作战三原则")
    pitfall_text = extract_level3_section(text, "最大一个坑")
    advice_text = extract_level3_section(text, "最值钱一句忠告")
    principles = parse_numbered_lines(principles_text)
    pitfall = parse_key_value_lines(pitfall_text)
    if "坑" in pitfall and "坑点" not in pitfall:
        pitfall["坑点"] = pitfall["坑"]
    advice = advice_text.strip()
    return principles, pitfall, advice


def parse_story_section(text: str) -> dict[str, str]:
    return {
        "起点处境": extract_level3_section(text, "起点处境"),
        "关键转折": extract_level3_section(text, "关键转折"),
        "结果兑现": extract_level3_section(text, "结果兑现"),
        "故事证据": extract_level3_section(text, "故事证据"),
    }


def parse_case_body(body: str) -> dict:
    raw_sections = extract_sections_by_heading(body)
    sections = {clean_heading_title(title): content for title, content in raw_sections.items()}

    identity = parse_identity_section(sections.get("案例身份证", ""))
    if identity["一句话业务"]:
        sections["一句话业务"] = identity["一句话业务"]
    if identity["作者是谁"]:
        sections["作者是谁"] = identity["作者是谁"]
    if identity["启动资源"]:
        sections["启动资源"] = identity["启动资源"]
    if identity["核心目标"]:
        sections["核心目标"] = identity["核心目标"]
    if identity["最终结果"]:
        sections["最终结果"] = identity["最终结果"]

    core_principles, core_pitfall, core_advice = parse_core_section(sections.get("核心心法", ""))
    if core_principles:
        sections["作战三原则"] = "\n".join(f"{index}. {item}" for index, item in enumerate(core_principles, start=1))
    if core_pitfall:
        sections["最大一个坑"] = "\n".join(f"- {key}：{value}" for key, value in core_pitfall.items())
    if core_advice:
        sections["最值钱忠告"] = core_advice

    story_fields = parse_story_section(sections.get("故事线", ""))
    for key, value in story_fields.items():
        if value:
            sections[key] = value

    decisions = parse_decision_section(sections.get("决策地图", ""))
    principles = parse_numbered_lines(sections.get("作战三原则", ""))
    pitfall = parse_key_value_lines(sections.get("最大一个坑", ""))
    return {
        "sections": sections,
        "decisions": decisions,
        "principles": principles,
        "pitfall": pitfall,
    }


def parse_numbered_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        normalized = re.sub(r"^\d+\.\s*", "", stripped)
        if normalized:
            lines.append(normalized)
    return lines


def extract_markdown_links(text: str) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = normalize_whitespace(match.group(1))
        if target and target not in links:
            links.append(target)
    return links


def classify_link_target(target: str) -> str:
    parsed = urlparse(str(target).strip())
    if parsed.scheme in {"http", "https"}:
        return "remote"
    if parsed.scheme in {"mailto", "tel"}:
        return "ignored"
    if str(target).startswith("/"):
        return "local"
    if re.match(r"^[A-Za-z]:[\\/]", str(target)):
        return "local"
    if str(target).startswith(("./", "../")) or "/" in str(target):
        return "local"
    return "unknown"


def parse_key_value_lines(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        normalized = stripped
        if normalized.startswith("- "):
            normalized = normalized[2:].strip()
        if normalized.startswith("**") and normalized.endswith("**") and "：" in normalized:
            normalized = normalized[2:-2].strip()
        match = re.match(r"^\*\*(.+?)：\*\*\s*(.*)$", normalized)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
        else:
            if "：" not in normalized:
                continue
            key, value = normalized.split("：", 1)
        data[key.strip()] = value.strip()
    return data


def parse_decision_section(text: str) -> list[dict]:
    if not text.strip():
        return []
    if re.search(r"^\*\*\d+\.\s*决策点：", text, flags=re.MULTILINE):
        return parse_pretty_decision_section(text)
    blocks = re.split(r"^###\s+决策点\s+\d+\s*$", text, flags=re.MULTILINE)
    decisions: list[dict] = []
    for block in blocks[1:]:
        decision = {
            "decision_point": "",
            "choice": "",
            "basis": "",
            "action_steps": [],
            "tools": [],
            "params": [],
            "is_inferred": "",
            "evidence": "",
        }
        current_list: str | None = None
        for raw_line in block.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- 决策点："):
                decision["decision_point"] = stripped.split("：", 1)[1].strip()
                current_list = None
            elif stripped.startswith("- 选择："):
                decision["choice"] = stripped.split("：", 1)[1].strip()
                current_list = None
            elif stripped.startswith("- 依据："):
                decision["basis"] = stripped.split("：", 1)[1].strip()
                current_list = None
            elif stripped.startswith("- 动作步骤："):
                current_list = "action_steps"
            elif stripped.startswith("- 工具："):
                current_list = "tools"
            elif stripped.startswith("- 参数："):
                current_list = "params"
            elif stripped.startswith("- 是否推测："):
                decision["is_inferred"] = stripped.split("：", 1)[1].strip()
                current_list = None
            elif stripped.startswith("- 证据摘录："):
                decision["evidence"] = stripped.split("：", 1)[1].strip()
                current_list = None
            elif current_list and re.match(r"^(\d+\.\s+|- )", stripped):
                value = re.sub(r"^(\d+\.\s+|- )", "", stripped).strip()
                if value:
                    decision[current_list].append(value)
        decisions.append(decision)
    return decisions


def parse_pretty_decision_section(text: str) -> list[dict]:
    blocks = re.split(r"^\*\*\d+\.\s*决策点：", text, flags=re.MULTILINE)
    titles = re.findall(r"^\*\*(\d+\.\s*决策点：.+?)\*\*\s*$", text, flags=re.MULTILINE)
    decisions: list[dict] = []
    for index, block in enumerate(blocks[1:]):
        title_line = titles[index] if index < len(titles) else ""
        decision_point = title_line.split("：", 1)[1].strip() if "：" in title_line else ""
        decision = {
            "decision_point": decision_point,
            "choice": "",
            "basis": "",
            "action_steps": [],
            "tools": [],
            "params": [],
            "is_inferred": "",
            "evidence": "",
        }
        field_pattern = re.compile(r"^\s*-\s*\*\*(.+?)：\*\*\s*(.*)$", flags=re.MULTILINE)
        matches = list(field_pattern.finditer(block))
        fields: dict[str, str] = {}
        for match_index, match in enumerate(matches):
            label = normalize_whitespace(match.group(1))
            inline_value = match.group(2).strip()
            start = match.end()
            end = matches[match_index + 1].start() if match_index + 1 < len(matches) else len(block)
            tail = block[start:end].strip()
            value_parts = [part for part in [inline_value, tail] if part]
            fields[label] = "\n".join(value_parts).strip()

        decision["choice"] = fields.get("选择", "")
        decision["basis"] = fields.get("依据", "")
        action_text = fields.get("动作", "") or fields.get("动作步骤", "")
        if action_text:
            decision["action_steps"] = [
                re.sub(r"^(\d+\)\s*|\d+\.\s*|- )", "", line.strip())
                for line in action_text.splitlines()
                if re.sub(r"^(\d+\)\s*|\d+\.\s*|- )", "", line.strip())
            ]
        tools_text = fields.get("工具", "")
        if tools_text:
            decision["tools"] = [
                re.sub(r"^(\d+\)\s*|\d+\.\s*|- )", "", line.strip())
                for line in tools_text.splitlines()
                if re.sub(r"^(\d+\)\s*|\d+\.\s*|- )", "", line.strip())
            ]
        params_text = fields.get("参数", "")
        if params_text:
            decision["params"] = [
                re.sub(r"^(\d+\)\s*|\d+\.\s*|- )", "", line.strip())
                for line in params_text.splitlines()
                if re.sub(r"^(\d+\)\s*|\d+\.\s*|- )", "", line.strip())
            ]
        decision["is_inferred"] = fields.get("是否推测", "")
        if not decision["is_inferred"]:
            haystack = " ".join([decision["decision_point"], decision["choice"], decision["basis"], *decision["action_steps"]])
            decision["is_inferred"] = "是" if "推测" in haystack else "否"
        decision["evidence"] = fields.get("证据摘录", "") or decision["basis"] or decision["choice"]
        decisions.append(decision)
    return decisions


def build_case_body(
    title: str,
    one_line_business: str,
    author_identity: str,
    startup_resources: dict[str, str],
    core_goal: str,
    final_result: str,
    decisions: list[Decision],
    principles: list[str],
    pitfall: tuple[str, str],
    advice: str,
    pending_inferences: list[str],
    causal_status: str = "single_case_hypothesis",
    cross_case_refs: list[str] | None = None,
    counterfactual_notes: list[str] | None = None,
    sequence_steps: list[str] | None = None,
    platform_context: str = "待补充",
    account_context: str = "待补充",
    time_context: str = "待补充",
    resource_links: list[str] | None = None,
    story_start: str = "",
    story_turn: str = "",
    story_payoff: str = "",
    story_evidence: list[str] | None = None,
) -> str:
    cross_case_refs = cross_case_refs or []
    counterfactual_notes = counterfactual_notes or []
    sequence_steps = sequence_steps or []
    resource_links = resource_links or []
    story_evidence = story_evidence or []
    lines = [f"# {title}", "", "---", "", "## 【案例身份证】", ""]
    lines.extend(
        [
            f"**帖子标题：** {title}",
            "**原文链接：** 待补充",
            f"**一句话业务：** {one_line_business}",
            f"**作者是谁：** {author_identity}",
            "",
            "**启动资源：**",
            f"1) **花了多少钱？** {startup_resources['现金流']}",
            f"2) **投入了多少时间？** {startup_resources['时间']}",
            f"3) **有没有合伙人？** {startup_resources['团队/设备']}",
            f"4) **用到了什么特殊技能或设备？** {startup_resources['技能']}",
            f"5) **其他启动条件：** {startup_resources['其他']}",
            "",
            f"**核心目标：** {core_goal}",
            f"**最终结果：** {final_result}",
            "",
            "---",
            "",
            "## 【决策地图】",
            "",
        ]
    )
    for index, decision in enumerate(decisions, start=1):
        lines.extend(
            [
                f"**{index}. 决策点：{decision.decision_point}**",
                f"- **选择：** {decision.choice}",
                f"- **依据：** {decision.basis}",
                "- **动作：**",
            ]
        )
        for step_index, step in enumerate(decision.action_steps, start=1):
            lines.append(f"  {step_index}. {step}")
        lines.append("- **工具：**")
        if decision.tools:
            for tool in decision.tools:
                lines.append(f"  - {tool}")
        else:
            lines.append("  - 待补充")
        lines.append("- **参数：**")
        if decision.params:
            for param in decision.params:
                lines.append(f"  - {param}")
        else:
            lines.append("  - 待补充")
        lines.extend(
            [
                f"- **是否推测：** {'是' if decision.inferred else '否'}",
                f"- **证据摘录：** {decision.evidence}",
                "",
            ]
        )
    lines.extend(["---", "", "## 【核心心法】", "", "### 作战三原则："])
    for index, principle in enumerate(principles, start=1):
        lines.append(f"{index}. {principle}")
    lines.extend(
        [
            "",
            "### 最大一个坑：",
            f"- 坑点：{pitfall[0]}",
            f"- 解决方案：{pitfall[1]}",
            "",
            "### 最值钱一句忠告：",
            advice,
            "",
            "---",
            "",
            "## 【故事线】",
            "",
            "### 起点处境：",
            story_start or "待补充：作者起点、限制条件和开始动机尚未抽清。",
            "",
            "### 关键转折：",
            story_turn or "待补充：原文里的关键变化点、踩坑与修正动作尚未抽清。",
            "",
            "### 结果兑现：",
            story_payoff or "待补充：结果变化、数字兑现和阶段性收获尚未抽清。",
            "",
            "### 故事证据：",
        ]
    )
    if story_evidence:
        for item in story_evidence:
            lines.append(f"- {item}")
    else:
        lines.append("- 待补充：需要回到原文摘出最有画面感的经历段落。")
    lines.extend(
        [
            "",
            "---",
            "",
            "## 【归因与边界】",
            "",
            f"- **成功归因判断：** {causal_status}",
            f"- **交叉验证案例：** {', '.join(cross_case_refs) if cross_case_refs else '待补充'}",
            f"- **平台/时间上下文：** {platform_context}",
            f"- **账号/业务阶段：** {account_context}",
            f"- **时效背景：** {time_context}",
            "- **适用边界：** 待补充",
            "- **反事实追问：**",
        ]
    )
    if counterfactual_notes:
        for item in counterfactual_notes:
            lines.append(f"  - {item}")
    else:
        lines.append("  - 如果不做这些动作，结果是否仍可能成立？待补充。")
        lines.append("  - 这些动作更像必要条件、充分条件还是相关性线索？待补充。")
    lines.extend(
        [
            "",
            "---",
            "",
            "## 【作战序列】",
            "",
        ]
    )
    if sequence_steps:
        lines.extend(sequence_steps)
    else:
        lines.append("1. 待补充")
    lines.extend(
        [
            "",
            "---",
            "",
            "## 【资源清单】",
            "",
        ]
    )
    if resource_links:
        for item in resource_links:
            lines.extend(
                [
                    f"- **资源链接：** {item}",
                    "- **资源状态：** unchecked",
                    "- **最后检查：** 待补充",
                ]
            )
    else:
        lines.extend(
            [
                "- **资源链接：** 待补充",
                "- **资源状态：** unchecked",
                "- **最后检查：** 待补充",
            ]
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "## 【待验证推测】",
        ]
    )
    for item in pending_inferences:
        lines.append(f"- {item}")
    return "\n".join(lines).strip()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    atomic_write_jsonl(path, rows)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def has_action_specificity(text: str) -> bool:
    normalized = normalize_whitespace(text)
    return any(verb in normalized for verb in ACTION_VERBS) or bool(re.search(r"\d", normalized))


def principle_is_vague(text: str) -> bool:
    normalized = normalize_whitespace(text)
    if not normalized:
        return True
    if any(term == normalized for term in VAGUE_PRINCIPLE_TERMS):
        return True
    if len(normalized) <= 6 and any(term in normalized for term in VAGUE_PRINCIPLE_TERMS):
        return True
    return not has_action_specificity(normalized) and not any(token in normalized for token in ["必须", "先", "每次", "发布前", "完成后", "不要", "至少"])


def normalize_inferred_marker(raw_value: str, fallback_text: str = "") -> str:
    normalized = normalize_whitespace(raw_value)
    if normalized in {"是", "否"}:
        return normalized

    haystack = normalize_whitespace(f"{normalized} {fallback_text}")
    if not haystack:
        return ""
    if any(token in haystack for token in INFERENCE_HINTS):
        return "是"
    return "否"


def has_case_structure(body: str) -> bool:
    parsed = parse_case_body(body)
    sections = parsed["sections"]
    return all(section in sections for section in ["案例身份证", "决策地图", "核心心法"])


def lexical_score(query: str, texts: list[str]) -> float:
    query_terms = [term for term in re.split(r"\s+", query.strip()) if term]
    haystack = " ".join(texts)
    if not query_terms or not haystack:
        return 0.0
    score = 0.0
    lowered_haystack = haystack.lower()
    for term in query_terms:
        lowered_term = term.lower()
        if lowered_term in lowered_haystack:
            score += 1.0
    return score / len(query_terms)
