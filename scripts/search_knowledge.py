#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from _llm_client import DEFAULT_DEEPSEEK_BASE_URL, DEFAULT_DEEPSEEK_MODEL, call_deepseek_json, validate_deepseek_backend
from _knowledge_lib import (
    DEFAULT_MODEL_NAME,
    DEFAULT_QUERY_PREFIX,
    DEFAULT_RERANKER_NAME,
    encode_texts,
    normalize_preview,
    read_faiss_index,
    read_jsonl,
    rerank,
)

try:
    from _memory_guard import wait_for_memory_budget
except Exception:  # pragma: no cover - memory guard is best-effort on non-macOS hosts.
    wait_for_memory_budget = None  # type: ignore[assignment]

_LATIN_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._+-]*")
_CJK_BLOCK_RE = re.compile(r"[一-鿿]+")
_MULTI_INTENT_SPLIT_RE = re.compile(r"[？?；;]|(?:\s+and\s+)|(?:\s+or\s+)")
_QUOTED_TERM_RE = re.compile(r"[《“\"「](.+?)[》”\"」]")
_PERSON_NAME_RE = r"[\u4e00-\u9fffA-Za-z0-9·._-]{2,24}"
_PERSON_INTRO_PATTERNS = [
    re.compile(rf"^介绍(?:一下|下)?(?P<name>{_PERSON_NAME_RE})$"),
    re.compile(rf"^(?P<name>{_PERSON_NAME_RE})是谁$"),
    re.compile(rf"^(?P<name>{_PERSON_NAME_RE})(?:是什么人|什么背景|什么来头|什么经历)$"),
    re.compile(rf"^说说(?P<name>{_PERSON_NAME_RE})$"),
]
PERSON_FACET_CUES = {
    "background": ("自我介绍", "背景", "介绍", "作者", "是谁", "普通人", "来头"),
    "achievements": ("盈利", "收入", "流水", "利润", "副业", "经历", "做过", "七位数", "六位数", "十万", "40万"),
    "methodology": ("心法", "能力层", "认知层", "验证层", "方法", "方法论", "SOP", "流程", "标准化", "放大", "复制", "工具", "自动化", "公式"),
}

CONTEXTUAL_CUES = ("还有", "其他", "另外", "继续", "那", "这个", "那个", "上面", "刚才", "前面", "同样")
COMPARISON_CUES = ("哪个", "比较", "更", "区别", "对比", "vs", "VS", "还是")
REFERENTIAL_CUES = ("它", "他们", "她们", "这个", "那个", "这些", "那些", "都", "前者", "后者")
RHETORICAL_CUES = ("难道", "不会", "怎么可能", "凭什么", "不是", "岂不是")
SOURCE_MODE_CUES = ("原文", "出处", "原话", "谁说", "链接", "来源", "证据", "截图", "原帖", "怎么说")
WRITING_MODE_CUES = ("金句", "素材", "故事", "标题", "开头", "结尾", "文案", "写作", "类比", "观点", "情绪", "表达")
STRATEGY_MODE_CUES = ("打法", "方案", "怎么做", "流程", "复盘", "增长", "变现", "获客", "跑通", "SOP", "项目", "落地", "拆解")
PLATFORM_TERMS = (
    "小红书",
    "抖音",
    "快手",
    "视频号",
    "B站",
    "b站",
    "公众号",
    "Youtube",
    "youtube",
    "TikTok",
    "tiktok",
    "YPP",
)

QUERY_PLANNER_PROVIDER = os.getenv("KNOWLEDGE_QUERY_PLANNER_PROVIDER", "auto").strip().lower()
QUERY_PLANNER_LLM_BACKEND = os.getenv("KNOWLEDGE_QUERY_PLANNER_LLM_BACKEND", "auto").strip().lower()
QUERY_PLANNER_MODEL = os.getenv("KNOWLEDGE_QUERY_PLANNER_MODEL", os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL))
QUERY_PLANNER_BASE_URL = os.getenv("KNOWLEDGE_QUERY_PLANNER_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL))
QUERY_PLANNER_TIMEOUT = float(os.getenv("KNOWLEDGE_QUERY_PLANNER_TIMEOUT", "45"))
QUERY_PLANNER_THINKING = os.getenv("KNOWLEDGE_QUERY_PLANNER_THINKING", "disabled").strip().lower()
QUERY_PLANNER_REASONING_EFFORT = os.getenv("KNOWLEDGE_QUERY_PLANNER_REASONING_EFFORT", "").strip().lower()
SKILL_ROOT = Path(__file__).resolve().parents[1]
QUERY_PLANNER_RUNTIME_DIR = Path(os.getenv("KNOWLEDGE_QUERY_PLANNER_RUNTIME_DIR", str(SKILL_ROOT / "evals" / "query_planner")))
_LLM_QUERY_PLANNER_DISABLED_REASON = ""
_QUERY_PLANNER_CACHE_MEMO: dict[str, Any] | None = None


@dataclass(frozen=True)
class SearchProfile:
    name: str
    default_device: str = "auto"
    batch_size: int = 8
    reranker_batch_size: int = 16
    rerank_top_k: int = 10**6
    branch_max: int = 4
    branch_limit_cap: int = 12
    candidate_multiplier: int = 8
    candidate_min: int = 30
    use_local_lock: bool = False
    wait_for_memory: bool = False
    memory_wait_seconds: float = 0.0
    min_readily_available_mb: float = 2048.0
    max_compressed_mb: float = 2048.0


SEARCH_PROFILES: dict[str, SearchProfile] = {
    "legacy": SearchProfile(name="legacy"),
    "local_quality": SearchProfile(
        name="local_quality",
        default_device="cpu",
        batch_size=4,
        reranker_batch_size=4,
        rerank_top_k=32,
        branch_max=4,
        branch_limit_cap=12,
        candidate_multiplier=6,
        candidate_min=24,
        use_local_lock=True,
        wait_for_memory=True,
        memory_wait_seconds=20.0,
        min_readily_available_mb=2048.0,
        max_compressed_mb=2048.0,
    ),
    "local_fast": SearchProfile(
        name="local_fast",
        default_device="cpu",
        batch_size=4,
        reranker_batch_size=4,
        rerank_top_k=0,
        branch_max=2,
        branch_limit_cap=8,
        candidate_multiplier=4,
        candidate_min=16,
        use_local_lock=True,
        wait_for_memory=True,
        memory_wait_seconds=10.0,
    ),
    "local_deep": SearchProfile(
        name="local_deep",
        default_device="cpu",
        batch_size=4,
        reranker_batch_size=4,
        rerank_top_k=48,
        branch_max=4,
        branch_limit_cap=16,
        candidate_multiplier=8,
        candidate_min=32,
        use_local_lock=True,
        wait_for_memory=True,
        memory_wait_seconds=45.0,
        min_readily_available_mb=3072.0,
        max_compressed_mb=2048.0,
    ),
}


@dataclass
class SearchStats:
    profile: str
    started_at: float = field(default_factory=time.time)
    query_plan_seconds: float = 0.0
    index_load_seconds: float = 0.0
    encode_seconds: float = 0.0
    vector_search_seconds: float = 0.0
    field_match_seconds: float = 0.0
    reranker_seconds: float = 0.0
    memory_wait_seconds: float = 0.0
    branch_count: int = 0
    candidates_seen: int = 0
    reranked_count: int = 0
    memory_wait_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "total_seconds": round(time.time() - self.started_at, 3),
            "query_plan_seconds": round(self.query_plan_seconds, 3),
            "index_load_seconds": round(self.index_load_seconds, 3),
            "encode_seconds": round(self.encode_seconds, 3),
            "vector_search_seconds": round(self.vector_search_seconds, 3),
            "field_match_seconds": round(self.field_match_seconds, 3),
            "reranker_seconds": round(self.reranker_seconds, 3),
            "memory_wait_seconds": round(self.memory_wait_seconds, 3),
            "branch_count": self.branch_count,
            "candidates_seen": self.candidates_seen,
            "reranked_count": self.reranked_count,
            "memory_wait_reason": self.memory_wait_reason,
        }


def resolve_search_profile(name: str | None) -> SearchProfile:
    profile_name = str(name or os.getenv("KNOWLEDGE_SEARCH_PROFILE", "local_quality")).strip() or "local_quality"
    if profile_name not in SEARCH_PROFILES:
        raise ValueError(f"未知 search profile: {profile_name}")
    return SEARCH_PROFILES[profile_name]


@contextmanager
def local_search_lock(root: Path, enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    runtime_dir = root / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock_path = runtime_dir / "search_knowledge.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def compact_long_text(text: Any, limit: int) -> str:
    return compact_text(str(text or ""))[:limit]


def lightweight_item(raw_item: dict[str, Any], asset_type: str) -> dict[str, Any]:
    item = dict(raw_item)
    if "body" in item:
        body = str(item.get("body", ""))
        item.pop("body", None)
        if body:
            item["body_preview"] = compact_long_text(body, 900)
    if "chunk_text" in item:
        chunk_text = str(item.get("chunk_text", ""))
        item.pop("chunk_text", None)
        if chunk_text:
            item["chunk_text_preview"] = compact_long_text(chunk_text, 900)

    item["asset_type"] = asset_type
    if asset_type == "material":
        item["subtype"] = item.get("subtype") or item.get("type") or "material"
    elif asset_type == "source":
        item["subtype"] = item.get("chunk_role") or "source_chunk"
    elif asset_type == "entity":
        item["subtype"] = item.get("subtype") or "entity_profile"
    else:
        item["subtype"] = item.get("subtype") or "case"
    return item


class SearchContext:
    def __init__(self, root: Path, profile: SearchProfile, stats: SearchStats | None = None):
        self.root = root
        self.profile = profile
        self.stats = stats
        self._items: dict[str, list[dict[str, Any]]] = {}
        self._indexes: dict[str, Any] = {}

    def candidate_count(self, limit: int, item_count: int) -> int:
        raw_count = max(limit * self.profile.candidate_multiplier, self.profile.candidate_min)
        return min(raw_count, item_count)

    def load_items(self, key: str, relpath: str, asset_type: str) -> list[dict[str, Any]]:
        if key in self._items:
            return self._items[key]
        started = time.time()
        path = self.root / relpath
        rows = read_jsonl(path)
        items = [lightweight_item(row, asset_type) for row in rows]
        if asset_type == "material":
            items = [item for item in items if str(item.get("review_status", "") or "").strip() != "rejected"]
        self._items[key] = items
        if self.stats:
            self.stats.index_load_seconds += time.time() - started
        return items

    def load_index(self, key: str, relpath: str) -> Any | None:
        if key in self._indexes:
            return self._indexes[key]
        path = self.root / relpath
        if not path.exists():
            return None
        started = time.time()
        index = read_faiss_index(path)
        self._indexes[key] = index
        if self.stats:
            self.stats.index_load_seconds += time.time() - started
        return index

    @property
    def case_items(self) -> list[dict[str, Any]]:
        return self.load_items("cases", "index/cases/cases_vector_meta.jsonl", "case")

    @property
    def material_items(self) -> list[dict[str, Any]]:
        return self.load_items("materials", "index/materials/materials_meta.jsonl", "material")

    @property
    def entity_items(self) -> list[dict[str, Any]]:
        return self.load_items("entities", "index/entities/entities_meta.jsonl", "entity")

    @property
    def source_items(self) -> list[dict[str, Any]]:
        return self.load_items("sources", "index/sources/source_chunks_meta.jsonl", "source")


def normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high <= low:
        return [0.5 for _ in values]
    return [(value - low) / (high - low) for value in values]


def calibrate_reranker_score(score: float) -> float:
    return 1.0 / (1.0 + math.exp(-(score / 2.5)))


def calibrate_vector_score(score: float) -> float:
    return max(0.0, min(1.0, (float(score) - 0.35) / 0.35))


def extract_query_terms(text: str) -> list[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return []

    terms: list[str] = []
    seen: set[str] = set()

    def push(term: str) -> None:
        cleaned = term.strip().lower()
        if len(cleaned) < 2 or cleaned in seen:
            return
        seen.add(cleaned)
        terms.append(cleaned)

    for term in raw.split():
        push(term)

    for token in _LATIN_TOKEN_RE.findall(raw):
        push(token)

    for block in _CJK_BLOCK_RE.findall(raw):
        if len(block) <= 8:
            push(block)
        for size in (2, 3):
            if len(block) < size:
                continue
            for idx in range(len(block) - size + 1):
                push(block[idx : idx + size])

    return terms


def lexical_overlap(query: str, texts: list[str]) -> float:
    query_terms = extract_query_terms(query)
    if not query_terms:
        return 0.0
    haystack = " ".join(str(text or "") for text in texts).lower()
    hits = sum(1 for term in query_terms if term in haystack)
    return hits / len(query_terms)


def dedupe_keep_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def string_list(values: list[Any] | tuple[Any, ...] | None) -> list[str]:
    return dedupe_keep_order([str(value).strip() for value in list(values or []) if str(value).strip()])


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def clean_context_candidate(text: str) -> str:
    cleaned = compact_text(text)
    cleaned = re.sub(r"^(上一个案例是|这个案例是|案例是|我们刚在看|上面那个|刚才那个|前面那个)", "", cleaned)
    cleaned = re.sub(r"^(通过|围绕|关于)", "", cleaned)
    cleaned = cleaned.strip("：:，,。；; ")
    return cleaned


def normalize_query_text(query: str) -> str:
    text = compact_text(query)
    replacements = {
        "咋做": "怎么做",
        "咋搞": "怎么做",
        "怎么搞": "怎么做",
        "有啥": "有什么",
        "行不行": "是否可行",
        "靠谱吗": "是否靠谱",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[？?]+$", "", text)
    return compact_text(text)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def extract_json_from_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("模型返回为空")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError(f"未能从模型输出中提取 JSON：{raw[:200]}")
    return json.loads(match.group(0))


def resolve_query_planner_llm_config(
    backend: str = QUERY_PLANNER_LLM_BACKEND,
    *,
    override_model: str | None = None,
    override_base_url: str | None = None,
    override_api_key: str | None = None,
) -> dict[str, str]:
    resolved_backend = str(backend or "auto").strip().lower()
    validate_deepseek_backend(resolved_backend)
    api_key = str(override_api_key or os.getenv("KNOWLEDGE_QUERY_PLANNER_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("缺少可用的 Query Planner LLM 凭证，请设置 KNOWLEDGE_QUERY_PLANNER_API_KEY 或 DEEPSEEK_API_KEY。")
    return {
        "backend": "deepseek",
        "api_key": api_key,
        "base_url": str(override_base_url or QUERY_PLANNER_BASE_URL).strip(),
        "model": str(override_model or QUERY_PLANNER_MODEL).strip(),
    }


def expand_model_aliases(model: str, backend: str) -> list[str]:
    normalized = str(model or "").strip()
    if not normalized:
        return []
    return [normalized]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def resolve_query_planner_runtime_dir(root: Path | None = None) -> Path:
    if QUERY_PLANNER_RUNTIME_DIR.is_absolute():
        return QUERY_PLANNER_RUNTIME_DIR
    base_root = root or SKILL_ROOT
    return (base_root / QUERY_PLANNER_RUNTIME_DIR).resolve()


def query_planner_cache_path(root: Path | None = None) -> Path:
    return resolve_query_planner_runtime_dir(root) / "planner_cache.json"


def query_planner_log_path(root: Path | None = None) -> Path:
    return resolve_query_planner_runtime_dir(root) / "planner_events.jsonl"


def ensure_query_planner_runtime_dir(root: Path | None = None) -> Path:
    runtime_dir = resolve_query_planner_runtime_dir(root)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def load_query_planner_cache(root: Path | None = None) -> dict[str, Any]:
    global _QUERY_PLANNER_CACHE_MEMO
    if _QUERY_PLANNER_CACHE_MEMO is not None:
        return _QUERY_PLANNER_CACHE_MEMO
    cache_path = query_planner_cache_path(root)
    if cache_path.exists():
        try:
            _QUERY_PLANNER_CACHE_MEMO = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(_QUERY_PLANNER_CACHE_MEMO, dict):
                return _QUERY_PLANNER_CACHE_MEMO
        except Exception:
            pass
    _QUERY_PLANNER_CACHE_MEMO = {}
    return _QUERY_PLANNER_CACHE_MEMO


def save_query_planner_cache(root: Path | None = None) -> None:
    cache = load_query_planner_cache(root)
    ensure_query_planner_runtime_dir(root)
    query_planner_cache_path(root).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_query_planner_cache_key(
    query: str,
    *,
    mode: str,
    conversation_history: list[str] | None,
    context_info: str | None,
    rule_plan: dict[str, Any],
    model_name: str,
    base_url: str,
    thinking: str,
    reasoning_effort: str,
) -> str:
    payload = {
        "query": normalize_query_text(query),
        "mode": mode,
        "conversation_history": list(conversation_history or []),
        "context_info": compact_text(context_info or ""),
        "rule_plan": {
            "query_type": rule_plan.get("query_type"),
            "search_mode": rule_plan.get("search_mode"),
            "must_keep_terms": rule_plan.get("must_keep_terms", []),
            "rewrites": rule_plan.get("rewrites", []),
        },
        "model_name": model_name,
        "base_url": base_url,
        "thinking": thinking,
        "reasoning_effort": reasoning_effort,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def append_query_planner_event(event: dict[str, Any], root: Path | None = None) -> None:
    ensure_query_planner_runtime_dir(root)
    payload = {"ts": now_iso(), **event}
    with query_planner_log_path(root).open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def split_multi_intent_query(query: str) -> list[str]:
    raw_parts = _MULTI_INTENT_SPLIT_RE.split(str(query or ""))
    fragments: list[str] = []
    for part in raw_parts:
        cleaned = normalize_query_text(part)
        if len(cleaned) >= 2:
            fragments.append(cleaned)
    return dedupe_keep_order(fragments)


def guess_context_terms(conversation_history: list[str] | None, context_info: str | None) -> list[str]:
    candidates: list[str] = []
    sources = list(conversation_history or [])
    if context_info:
        sources.append(context_info)

    for source in sources[-3:]:
        text = str(source or "")
        for quoted in _QUOTED_TERM_RE.findall(text):
            cleaned = clean_context_candidate(quoted)
            if 1 < len(cleaned) <= 20:
                candidates.append(cleaned)
        for platform in PLATFORM_TERMS:
            if platform.lower() in text.lower():
                candidates.append(platform)
        for token in _LATIN_TOKEN_RE.findall(text):
            if len(token) >= 2:
                candidates.append(token)
        for block in _CJK_BLOCK_RE.findall(text):
            cleaned = clean_context_candidate(block)
            if 2 <= len(cleaned) <= 12 and cleaned not in {"我们", "你们", "他们", "这个", "那个", "还有", "其他"}:
                candidates.append(cleaned)
    return dedupe_keep_order(candidates)[:8]


def extract_must_keep_terms(query: str, conversation_history: list[str] | None = None, context_info: str | None = None) -> list[str]:
    terms: list[str] = []
    text = str(query or "")
    for quoted in _QUOTED_TERM_RE.findall(text):
        cleaned = compact_text(quoted)
        if 1 < len(cleaned) <= 24:
            terms.append(cleaned)
    for platform in PLATFORM_TERMS:
        if platform.lower() in text.lower():
            terms.append(platform)
    for token in _LATIN_TOKEN_RE.findall(text):
        if len(token) >= 2 and (any(ch.isdigit() for ch in token) or any(ch.isupper() for ch in token) or token.lower() in {"ypp", "seo", "sop"}):
            terms.append(token)
    for block in _CJK_BLOCK_RE.findall(text):
        cleaned = compact_text(block)
        if 2 <= len(cleaned) <= 10 and any(ch.isdigit() for ch in cleaned):
            terms.append(cleaned)
    terms.extend(guess_context_terms(conversation_history, context_info)[:3])
    return dedupe_keep_order(terms)[:8]


def detect_query_type(query: str, conversation_history: list[str] | None = None, context_info: str | None = None) -> tuple[str, list[str]]:
    normalized = normalize_query_text(query)
    signals: list[str] = []
    fragments = split_multi_intent_query(normalized)
    has_context = bool((conversation_history or []) or compact_text(context_info or ""))

    person_name, _requested_facets = detect_person_intro_query(normalized)
    if person_name:
        signals.append("人物介绍")
        return "person_intro", signals

    if len(fragments) > 1:
        signals.append("多意图")
        return "multi_intent", signals

    if any(cue in normalized for cue in REFERENTIAL_CUES) and has_context:
        signals.append("模糊指代")
        return "referential", signals

    if any(cue in normalized for cue in COMPARISON_CUES):
        signals.append("对比")
        return "comparison", signals

    if any(cue in normalized for cue in RHETORICAL_CUES):
        signals.append("反问")
        return "rhetorical", signals

    if any(cue in normalized for cue in CONTEXTUAL_CUES) and has_context:
        signals.append("上下文依赖")
        return "contextual", signals

    return "direct", signals


def detect_person_intro_query(query: str) -> tuple[str, list[str]]:
    normalized = normalize_query_text(query)
    for pattern in _PERSON_INTRO_PATTERNS:
        match = pattern.match(normalized)
        if match:
            name = compact_text(match.group("name"))
            if name:
                return name, ["background", "achievements"]

    suffix_to_facets = [
        ("是谁", ["background"]),
        ("什么背景", ["background"]),
        ("什么来头", ["background"]),
        ("什么人", ["background"]),
        ("做过什么", ["achievements"]),
        ("做了什么", ["achievements"]),
        ("有什么经历", ["achievements"]),
        ("什么经历", ["achievements"]),
        ("的方法论", ["methodology"]),
        ("方法论", ["methodology"]),
        ("的心法", ["methodology"]),
        ("心法", ["methodology"]),
        ("的原则", ["methodology"]),
        ("原则", ["methodology"]),
        ("的打法", ["methodology"]),
        ("打法", ["methodology"]),
    ]
    for suffix, facets in suffix_to_facets:
        if not normalized.endswith(suffix):
            continue
        name = compact_text(normalized[: -len(suffix)]).rstrip("的").strip()
        if 2 <= len(name) <= 24:
            return name, facets
    return "", []


def infer_search_mode(query: str) -> tuple[str, float, str]:
    normalized = normalize_query_text(query)
    person_name, _requested_facets = detect_person_intro_query(normalized)
    if person_name:
        return "source", 0.86, "命中人物介绍类问法，优先回到原始来源"
    lower = normalized.lower()
    source_hits = sum(1 for cue in SOURCE_MODE_CUES if cue.lower() in lower)
    writing_hits = sum(1 for cue in WRITING_MODE_CUES if cue.lower() in lower)
    strategy_hits = sum(1 for cue in STRATEGY_MODE_CUES if cue.lower() in lower)

    if source_hits >= max(writing_hits, strategy_hits) and source_hits > 0:
        return "source", min(0.72 + 0.08 * source_hits, 0.95), "命中出处/原文类词"
    if writing_hits >= max(source_hits, strategy_hits) and writing_hits > 0:
        return "writing", min(0.70 + 0.08 * writing_hits, 0.95), "命中写作/素材类词"
    if strategy_hits > 0:
        return "strategy", min(0.70 + 0.06 * strategy_hits, 0.92), "命中商业打法/落地类词"
    return "hybrid", 0.45, "未命中明显模式词，保守走混合检索"


def extract_comparison_targets(query: str) -> list[str]:
    normalized = normalize_query_text(query)
    targets: list[str] = []
    if "vs" in normalized.lower():
        parts = re.split(r"(?i)\bvs\b", normalized)
        targets.extend(compact_text(part) for part in parts)
    elif "和" in normalized:
        parts = normalized.split("和")
        targets.extend(compact_text(part) for part in parts)
    elif "跟" in normalized:
        parts = normalized.split("跟")
        targets.extend(compact_text(part) for part in parts)
    elif "还是" in normalized:
        parts = normalized.split("还是")
        targets.extend(compact_text(part) for part in parts)
    cleaned_targets: list[str] = []
    for target in targets:
        target = re.sub(r"(哪个更好|哪个更强|哪个更适合|哪个|比较|更)$", "", target).strip()
        if len(target) >= 2:
            cleaned_targets.append(target)
    return dedupe_keep_order(cleaned_targets)[:2]


def resolve_referential_query(query: str, context_terms: list[str]) -> str:
    normalized = normalize_query_text(query)
    if not context_terms:
        return normalized
    anchor = " ".join(context_terms[:2])
    resolved = normalized
    for cue in REFERENTIAL_CUES:
        resolved = resolved.replace(cue, anchor)
    return compact_text(resolved)


def build_rule_query_plan(
    query: str,
    *,
    mode: str = "hybrid",
    conversation_history: list[str] | None = None,
    context_info: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_query_text(query)
    query_type, query_signals = detect_query_type(normalized, conversation_history, context_info)
    inferred_mode, inferred_confidence, inferred_reason = infer_search_mode(normalized)
    context_terms = guess_context_terms(conversation_history, context_info)
    must_keep_terms = extract_must_keep_terms(normalized, conversation_history, context_info)
    need_context = query_type in {"contextual", "referential"} or any(cue in normalized for cue in CONTEXTUAL_CUES)
    entity_name = ""
    requested_facets: list[str] = []
    evidence_preference = "balanced"
    if query_type == "person_intro":
        entity_name, requested_facets = detect_person_intro_query(normalized)
        if entity_name:
            must_keep_terms = dedupe_keep_order([entity_name, *must_keep_terms])
        evidence_preference = "source_first"

    effective_mode = mode if mode != "hybrid" else inferred_mode
    rewrites: list[dict[str, Any]] = [
        {
            "query": normalized,
            "intent": "原始查询",
            "weight": 1.0,
            "source": "original",
            "reason": "保留用户原始表达，避免改写过头",
        }
    ]

    if query_type == "person_intro" and entity_name:
        rewrites.extend(
            [
                {
                    "query": entity_name,
                    "intent": "人物名直查",
                    "weight": 0.92,
                    "source": "rewrite",
                    "reason": "直接用人物名命中 author / 开头自我介绍 / 人物段落",
                },
                {
                    "query": compact_text(f"{entity_name} 是谁 背景 经历"),
                    "intent": "人物背景展开",
                    "weight": 0.88,
                    "source": "rewrite",
                    "reason": "把人物介绍问法展开成更稳定的背景/经历检索表达",
                },
                {
                    "query": compact_text(f"{entity_name} 自我介绍 做过什么"),
                    "intent": "人物经历展开",
                    "weight": 0.82,
                    "source": "rewrite",
                    "reason": "兼顾自述段落和经历枚举段落",
                },
            ]
        )
    elif query_type == "multi_intent":
        fragments = split_multi_intent_query(normalized)
        for fragment in fragments:
            fragment_query = fragment
            if need_context and context_terms:
                fragment_query = compact_text(f"{' '.join(context_terms[:2])} {fragment}")
            rewrites.append(
                {
                    "query": fragment_query,
                    "intent": "子问题拆分",
                    "weight": 0.76,
                    "source": "rewrite",
                    "reason": "将多意图查询拆成单一检索问题",
                }
            )
    elif query_type == "comparison":
        targets = extract_comparison_targets(normalized)
        if len(targets) == 2:
            rewrites.append(
                {
                    "query": f"{targets[0]} 和 {targets[1]} 的区别、优劣势、适用场景",
                    "intent": "对比分析",
                    "weight": 0.82,
                    "source": "rewrite",
                    "reason": "把对比口语改成结构化比较问题",
                }
            )
    elif query_type == "referential":
        resolved = resolve_referential_query(normalized, context_terms)
        if resolved != normalized:
            rewrites.append(
                {
                    "query": resolved,
                    "intent": "指代消解",
                    "weight": 0.84,
                    "source": "rewrite",
                    "reason": "用上下文实体替换指代词",
                }
            )
    elif query_type == "contextual" and context_terms:
        rewrites.append(
            {
                "query": compact_text(f"{' '.join(context_terms[:2])} {normalized}"),
                "intent": "补足上下文",
                "weight": 0.80,
                "source": "rewrite",
                "reason": "将上下文主题显式补进查询",
            }
        )
    elif query_type == "rhetorical":
        flattened = normalized
        for cue in RHETORICAL_CUES:
            flattened = flattened.replace(cue, "")
        flattened = compact_text(flattened.replace("吗", "").replace("么", ""))
        if flattened and flattened != normalized:
            rewrites.append(
                {
                    "query": flattened,
                    "intent": "去反问语气",
                    "weight": 0.74,
                    "source": "rewrite",
                    "reason": "去掉情绪语气，保留检索核心",
                }
            )

    allow_strategy_expand = effective_mode == "strategy" and (
        inferred_mode == "strategy" or query_type in {"contextual", "comparison", "multi_intent"}
    )
    allow_writing_expand = effective_mode == "writing" and (
        inferred_mode == "writing" or query_type in {"contextual", "comparison", "multi_intent"}
    )
    allow_source_expand = effective_mode == "source" and inferred_mode == "source"

    if allow_strategy_expand and len(normalized) <= 18:
        rewrites.append(
            {
                "query": compact_text(f"{normalized} 商业打法 流程 关键步骤 变现路径"),
                "intent": "策略展开",
                "weight": 0.70,
                "source": "rewrite",
                "reason": "把短 query 展开为可检索的商业执行表达",
            }
        )
    elif allow_writing_expand and len(normalized) <= 18:
        rewrites.append(
            {
                "query": compact_text(f"{normalized} 故事 金句 观点 素材"),
                "intent": "写作展开",
                "weight": 0.70,
                "source": "rewrite",
                "reason": "补足素材检索常用表达",
            }
        )
    elif allow_source_expand and not any(cue in normalized for cue in SOURCE_MODE_CUES):
        rewrites.append(
            {
                "query": compact_text(f"{normalized} 原文 出处 原话"),
                "intent": "证据展开",
                "weight": 0.72,
                "source": "rewrite",
                "reason": "补足出处型查询的证据词",
            }
        )

    deduped_rewrites: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    for rewrite in rewrites:
        rewritten_query = compact_text(rewrite.get("query", ""))
        if not rewritten_query or rewritten_query in seen_queries:
            continue
        seen_queries.add(rewritten_query)
        rewrite["query"] = rewritten_query
        deduped_rewrites.append(rewrite)

    confidence = 0.60
    if query_type != "direct":
        confidence += 0.12
    if need_context and context_terms:
        confidence += 0.10
    confidence = max(confidence, inferred_confidence)
    confidence = min(confidence, 0.96)

    return {
        "query_type": query_type,
        "query_signals": query_signals,
        "search_mode": effective_mode,
        "inferred_mode": inferred_mode,
        "inferred_mode_reason": inferred_reason,
        "need_context": need_context,
        "context_terms": context_terms,
        "must_keep_terms": must_keep_terms,
        "intent": query_type,
        "entity_name": entity_name,
        "requested_facets": requested_facets,
        "evidence_preference": evidence_preference,
        "rewrites": deduped_rewrites[:4],
        "confidence": round(confidence, 4),
    }


def should_try_llm_query_planner(
    rule_plan: dict[str, Any],
    *,
    provider: str,
    conversation_history: list[str] | None = None,
    context_info: str | None = None,
) -> bool:
    if _LLM_QUERY_PLANNER_DISABLED_REASON:
        return False
    if provider == "rule":
        return False
    if provider == "llm":
        return True
    query_type = str(rule_plan.get("query_type", "direct"))
    inferred_mode = str(rule_plan.get("inferred_mode", "hybrid"))
    confidence = float(rule_plan.get("confidence", 0.0) or 0.0)
    if query_type in {"contextual", "referential", "comparison", "multi_intent", "rhetorical", "person_intro"}:
        return True
    if inferred_mode == "hybrid" and confidence < 0.75:
        return True
    if conversation_history or compact_text(context_info or ""):
        return True
    return False


def build_query_planner_prompt(
    query: str,
    *,
    mode: str,
    conversation_history: list[str] | None,
    context_info: str | None,
    rule_plan: dict[str, Any],
) -> tuple[str, str]:
    system_prompt = (
        "你是一个 RAG 查询改写规划器。你的任务不是回答问题，而是生成检索计划。"
        "请严格输出 JSON，不要输出解释。"
        "你需要综合原始 query、对话历史、规则规划结果，生成更适合检索的 query plan。"
        "必须保留关键实体词，不允许臆造新项目、新平台、新作者。"
    )
    user_payload = {
        "task": "生成检索计划，供商业案例/素材/出处搜索使用",
        "requirements": {
            "language": "zh",
            "allowed_search_mode": ["strategy", "writing", "source", "hybrid"],
            "query_type_schema": ["direct", "contextual", "referential", "comparison", "multi_intent", "rhetorical", "person_intro"],
            "rewrite_rules": [
                "rewrites 最多 3 条，不含原始查询",
                "每条 rewrite 需要 query、intent、weight",
                "weight 取值 0-1",
                "不得删除 must_keep_terms 中的重要实体",
                "如不需要改写，可返回空 rewrites",
            ],
            "output_schema": {
                "query_type": "string",
                "search_mode": "string",
                "intent": "string",
                "entity_name": "string",
                "requested_facets": ["string"],
                "rewrites": [{"query": "string", "intent": "string", "weight": 0.8}],
                "must_keep_terms": ["string"],
                "need_context": True,
                "confidence": 0.8,
            },
        },
        "original_query": query,
        "requested_mode": mode,
        "conversation_history": list(conversation_history or []),
        "context_info": compact_text(context_info or ""),
        "rule_plan": rule_plan,
    }
    return system_prompt, json.dumps(user_payload, ensure_ascii=False)


def call_llm_query_planner(
    query: str,
    *,
    mode: str,
    conversation_history: list[str] | None,
    context_info: str | None,
    rule_plan: dict[str, Any],
    model_name: str = QUERY_PLANNER_MODEL,
    base_url: str = QUERY_PLANNER_BASE_URL,
    timeout: float = QUERY_PLANNER_TIMEOUT,
    root: Path | None = None,
) -> dict[str, Any]:
    llm_config = resolve_query_planner_llm_config(
        override_model=model_name,
        override_base_url=base_url,
    )
    resolved_api_key = llm_config["api_key"]
    resolved_base_url = llm_config["base_url"]
    primary_model = llm_config["model"]

    model_candidates = expand_model_aliases(primary_model, llm_config["backend"])
    cache_key = build_query_planner_cache_key(
        query,
        mode=mode,
        conversation_history=conversation_history,
        context_info=context_info,
        rule_plan=rule_plan,
        model_name="|".join(model_candidates),
        base_url=resolved_base_url,
        thinking=QUERY_PLANNER_THINKING,
        reasoning_effort=QUERY_PLANNER_REASONING_EFFORT,
    )
    cache = load_query_planner_cache(root)
    cache_entry = cache.get(cache_key)
    if isinstance(cache_entry, dict) and cache_entry.get("plan"):
        append_query_planner_event(
            {
                "event": "cache_hit",
                "query": query,
                "mode": mode,
                "backend": "llm_cache",
                "model": cache_entry.get("model", ""),
                "cache_key": cache_key,
            },
            root=root,
        )
        return dict(cache_entry["plan"])

    system_prompt, user_prompt = build_query_planner_prompt(
        query,
        mode=mode,
        conversation_history=conversation_history,
        context_info=context_info,
        rule_plan=rule_plan,
    )

    last_error: Exception | None = None
    for candidate_model in model_candidates:
        started_at = time.time()
        try:
            parsed = call_deepseek_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                model=candidate_model,
                timeout=timeout,
                temperature=0.1,
                thinking=QUERY_PLANNER_THINKING,
                reasoning_effort=QUERY_PLANNER_REASONING_EFFORT,
            )
            cache[cache_key] = {
                "cached_at": now_iso(),
                "model": candidate_model,
                "plan": parsed,
            }
            save_query_planner_cache(root)
            append_query_planner_event(
                {
                    "event": "llm_success",
                    "query": query,
                    "mode": mode,
                    "backend": "llm",
                    "provider": llm_config["backend"],
                    "model": candidate_model,
                    "thinking": QUERY_PLANNER_THINKING,
                    "reasoning_effort": QUERY_PLANNER_REASONING_EFFORT,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "cache_key": cache_key,
                },
                root=root,
            )
            return parsed
        except Exception as exc:
            last_error = exc
            append_query_planner_event(
                {
                    "event": "llm_error",
                    "query": query,
                    "mode": mode,
                    "backend": "llm",
                    "provider": llm_config["backend"],
                    "model": candidate_model,
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "error": str(exc),
                },
                root=root,
            )
            continue
    if last_error:
        raise last_error
    raise RuntimeError("LLM Query Planner 未执行")


def normalize_rewrite_entry(
    entry: dict[str, Any],
    *,
    must_keep_terms: list[str],
) -> dict[str, Any] | None:
    query = normalize_query_text(str(entry.get("query", "") or ""))
    if len(query) < 2:
        return None
    weight = clamp(float(entry.get("weight", 0.75) or 0.75), 0.0, 1.0)
    intent = compact_text(str(entry.get("intent", "") or "LLM改写")) or "LLM改写"
    query_lower = query.lower()
    preserved_terms = [term for term in must_keep_terms if term and term.lower() in query_lower]
    strong_terms = [term for term in must_keep_terms if len(term) >= 4 or any(ch.isdigit() for ch in term) or any("a" <= ch.lower() <= "z" for ch in term)]
    if strong_terms and not preserved_terms:
        return None
    return {
        "query": query,
        "intent": intent,
        "weight": weight,
        "source": "llm",
        "reason": "LLM Query Planner 改写",
    }


def sanitize_llm_query_plan(
    llm_plan: dict[str, Any],
    *,
    query: str,
    mode: str,
    rule_plan: dict[str, Any],
) -> dict[str, Any]:
    must_keep_terms = dedupe_keep_order(
        [str(term) for term in llm_plan.get("must_keep_terms", []) if str(term).strip()]
        + [str(term) for term in rule_plan.get("must_keep_terms", []) if str(term).strip()]
    )
    requested_mode = str(llm_plan.get("search_mode", "")).strip().lower()
    if requested_mode not in {"strategy", "writing", "source", "hybrid"}:
        requested_mode = str(rule_plan.get("search_mode", mode))
    if requested_mode == "hybrid" and str(rule_plan.get("search_mode", "hybrid")) in {"strategy", "writing", "source"}:
        if str(rule_plan.get("query_type", "")) in {"contextual", "comparison", "multi_intent"}:
            requested_mode = str(rule_plan.get("search_mode", mode))

    rewrites: list[dict[str, Any]] = []
    for raw_entry in llm_plan.get("rewrites", []) or []:
        if not isinstance(raw_entry, dict):
            continue
        normalized = normalize_rewrite_entry(raw_entry, must_keep_terms=must_keep_terms)
        if normalized:
            rewrites.append(normalized)
    rewrites = rewrites[:3]

    return {
        "query_type": str(llm_plan.get("query_type", "")).strip() or str(rule_plan.get("query_type", "direct")),
        "search_mode": requested_mode or str(rule_plan.get("search_mode", mode)),
        "intent": str(llm_plan.get("intent", "")).strip() or str(rule_plan.get("intent", rule_plan.get("query_type", "direct"))),
        "entity_name": compact_text(str(llm_plan.get("entity_name", "") or rule_plan.get("entity_name", ""))),
        "requested_facets": dedupe_keep_order([str(term) for term in llm_plan.get("requested_facets", []) if str(term).strip()] + [str(term) for term in rule_plan.get("requested_facets", []) if str(term).strip()]),
        "evidence_preference": str(llm_plan.get("evidence_preference", "")).strip() or str(rule_plan.get("evidence_preference", "balanced")),
        "need_context": bool(llm_plan.get("need_context", rule_plan.get("need_context", False))),
        "must_keep_terms": must_keep_terms,
        "rewrites": rewrites,
        "confidence": round(clamp(float(llm_plan.get("confidence", rule_plan.get("confidence", 0.7)) or 0.7), 0.0, 1.0), 4),
    }


def merge_query_plans(
    *,
    query: str,
    rule_plan: dict[str, Any],
    llm_plan: dict[str, Any] | None = None,
    planner_backend: str = "rule",
    fallback_reason: str = "",
) -> dict[str, Any]:
    merged = dict(rule_plan)
    merged["planner_backend"] = planner_backend
    if fallback_reason:
        merged["planner_fallback_reason"] = fallback_reason

    if not llm_plan:
        merged["rewrites"] = [
            {"query": normalize_query_text(query), "intent": "原始查询", "weight": 1.0, "source": "original", "reason": "保留用户原始表达，避免改写过头"},
            *[dict(entry) for entry in rule_plan.get("rewrites", [])[1:]],
        ][:4]
        return merged

    merged["query_type"] = str(llm_plan.get("query_type", merged.get("query_type", "direct")))
    merged["intent"] = str(llm_plan.get("intent", merged.get("intent", merged["query_type"])))
    merged["entity_name"] = compact_text(str(llm_plan.get("entity_name", "") or merged.get("entity_name", "")))
    merged["requested_facets"] = dedupe_keep_order(
        [str(term) for term in llm_plan.get("requested_facets", []) if str(term).strip()]
        + [str(term) for term in rule_plan.get("requested_facets", []) if str(term).strip()]
    )
    merged["evidence_preference"] = str(llm_plan.get("evidence_preference", "")).strip() or str(rule_plan.get("evidence_preference", "balanced"))
    merged["search_mode"] = str(llm_plan.get("search_mode", merged.get("search_mode", "hybrid")))
    merged["need_context"] = bool(llm_plan.get("need_context", merged.get("need_context", False)))
    merged["must_keep_terms"] = dedupe_keep_order(
        [str(term) for term in llm_plan.get("must_keep_terms", [])]
        + [str(term) for term in rule_plan.get("must_keep_terms", [])]
    )
    merged["confidence"] = round(
        clamp(max(float(rule_plan.get("confidence", 0.0) or 0.0), float(llm_plan.get("confidence", 0.0) or 0.0)), 0.0, 1.0),
        4,
    )

    combined_rewrites: list[dict[str, Any]] = [
        {"query": normalize_query_text(query), "intent": "原始查询", "weight": 1.0, "source": "original", "reason": "保留用户原始表达，避免改写过头"}
    ]
    combined_rewrites.extend(dict(entry) for entry in llm_plan.get("rewrites", []))
    combined_rewrites.extend(
        dict(entry)
        for entry in rule_plan.get("rewrites", [])[1:]
        if str(entry.get("query", "")).strip() not in {str(x.get("query", "")).strip() for x in combined_rewrites}
    )
    merged["rewrites"] = combined_rewrites[:4]
    return merged


def build_query_plan(
    query: str,
    *,
    mode: str = "hybrid",
    conversation_history: list[str] | None = None,
    context_info: str | None = None,
    planner_provider: str = QUERY_PLANNER_PROVIDER,
    root: Path | None = None,
) -> dict[str, Any]:
    global _LLM_QUERY_PLANNER_DISABLED_REASON
    rule_plan = build_rule_query_plan(
        query,
        mode=mode,
        conversation_history=conversation_history,
        context_info=context_info,
    )

    if not should_try_llm_query_planner(
        rule_plan,
        provider=planner_provider,
        conversation_history=conversation_history,
        context_info=context_info,
    ):
        fallback_reason = _LLM_QUERY_PLANNER_DISABLED_REASON if _LLM_QUERY_PLANNER_DISABLED_REASON else ""
        merged = merge_query_plans(query=query, rule_plan=rule_plan, planner_backend="rule", fallback_reason=fallback_reason)
        append_query_planner_event(
            {
                "event": "planner_rule_only",
                "query": query,
                "mode": mode,
                "backend": "rule",
                "fallback_reason": fallback_reason,
            },
            root=root,
        )
        return merged

    try:
        llm_raw_plan = call_llm_query_planner(
            query,
            mode=mode,
            conversation_history=conversation_history,
            context_info=context_info,
            rule_plan=rule_plan,
            root=root,
        )
        llm_plan = sanitize_llm_query_plan(llm_raw_plan, query=query, mode=mode, rule_plan=rule_plan)
        if not llm_plan.get("rewrites") and planner_provider == "llm":
            merged = merge_query_plans(query=query, rule_plan=rule_plan, planner_backend="rule", fallback_reason="LLM 未产出有效改写，回退规则规划")
            append_query_planner_event(
                {
                    "event": "planner_empty_llm_fallback",
                    "query": query,
                    "mode": mode,
                    "backend": "rule",
                },
                root=root,
            )
            return merged
        merged = merge_query_plans(query=query, rule_plan=rule_plan, llm_plan=llm_plan, planner_backend="llm")
        append_query_planner_event(
            {
                "event": "planner_merged",
                "query": query,
                "mode": mode,
                "backend": "llm",
                "rewrite_count": len(merged.get("rewrites", [])),
            },
            root=root,
        )
        return merged
    except Exception as exc:
        error_text = str(exc)
        if "SetLimitExceeded" in error_text or "429" in error_text or "TooManyRequests" in error_text:
            _LLM_QUERY_PLANNER_DISABLED_REASON = f"LLM Query Planner 已熔断回退：{error_text}"
        merged = merge_query_plans(
            query=query,
            rule_plan=rule_plan,
            planner_backend="rule",
            fallback_reason=f"LLM Query Planner 失败，已回退规则规划：{exc}",
        )
        append_query_planner_event(
            {
                "event": "planner_llm_fallback",
                "query": query,
                "mode": mode,
                "backend": "rule",
                "error": error_text,
                "circuit_open": bool(_LLM_QUERY_PLANNER_DISABLED_REASON),
            },
            root=root,
        )
        return merged


def default_min_score(mode: str) -> float:
    if mode == "source":
        return 0.67
    if mode == "writing":
        return 0.64
    if mode == "strategy":
        return 0.62
    return 0.63


def item_min_score(item: dict[str, Any], mode: str, base_threshold: float) -> float:
    asset_type = item.get("asset_type")
    subtype = item.get("subtype")

    if mode == "strategy":
        if asset_type == "case":
            return max(0.46, base_threshold - 0.14)
        if asset_type == "material" and subtype in {"playbook", "method", "data"}:
            return max(0.57, base_threshold - 0.02)
        if asset_type == "source":
            return max(0.73, base_threshold + 0.08)
        return max(0.66, base_threshold + 0.03)

    if mode == "writing":
        if asset_type == "entity":
            return max(0.70, base_threshold + 0.05)
        if asset_type == "material":
            return max(0.58, base_threshold - 0.03)
        if asset_type == "source":
            return max(0.66, base_threshold + 0.01)
        return max(0.68, base_threshold + 0.03)

    if mode == "source":
        if asset_type == "entity":
            return max(0.58, base_threshold - 0.06)
        if asset_type == "source":
            return max(0.64, base_threshold - 0.03)
        return max(0.72, base_threshold + 0.04)

    return base_threshold


def mode_bonus(item: dict[str, Any], mode: str) -> float:
    asset_type = item.get("asset_type")
    subtype = item.get("subtype")

    if mode == "strategy":
        if asset_type == "case":
            return 0.38
        if asset_type == "source":
            penalty = -0.18
            if subtype == "note":
                penalty -= 0.10
            elif subtype == "story":
                penalty -= 0.05
            return penalty
        if subtype == "playbook":
            return 0.16
        if subtype == "method":
            return 0.12
        if subtype == "data":
            return 0.08
        if subtype in {"story", "quote", "association", "insight"}:
            return -0.05

    if mode == "writing":
        if asset_type == "entity":
            return -0.06
        if asset_type == "source":
            return 0.03
        if asset_type == "case":
            return -0.08
        if subtype == "story":
            return 0.26
        if subtype == "data":
            return 0.18
        if subtype in {"quote", "insight", "association"}:
            return 0.24
        if subtype in {"method", "playbook"}:
            return 0.08

    if mode == "source":
        if asset_type == "entity":
            return 0.36
        if asset_type == "source":
            return 0.32
        if asset_type == "case":
            return -0.10
        if asset_type == "material":
            return -0.06

    return 0.0


def group_priority(item: dict[str, Any], mode: str) -> int:
    asset_type = item.get("asset_type")
    subtype = item.get("subtype")
    if mode == "strategy":
        if asset_type == "case":
            return 0
        if asset_type == "material" and subtype in {"playbook", "method", "data"}:
            return 1
        if asset_type == "material":
            return 2
        return 3
    if mode == "writing":
        if asset_type == "material" and subtype in {"quote", "story", "insight", "association", "data"}:
            return 0
        if asset_type == "material":
            return 1
        if asset_type == "source":
            return 2
        return 3
    if mode == "source":
        if asset_type == "entity":
            return 0
        return 1 if asset_type == "source" else 2
    return 0


def canonical_source_key(item: dict[str, Any]) -> str:
    asset_type = str(item.get("asset_type", "")).strip()
    path = str(item.get("path", "")).strip()
    source_refs = string_list(item.get("source_refs", []))

    if asset_type == "entity":
        return ""
    if asset_type == "source":
        return path
    if asset_type == "case":
        return source_refs[0] if len(source_refs) == 1 else path
    if asset_type == "material":
        return source_refs[0] if len(source_refs) == 1 else path
    return path


def source_diversity_caps(mode: str, item: dict[str, Any]) -> tuple[int, int]:
    asset_type = str(item.get("asset_type", "")).strip()
    if asset_type == "entity":
        return (10**6, 10**6)

    family_cap = 2
    asset_cap = 1

    if mode == "strategy":
        family_cap = 3
        if asset_type == "case":
            asset_cap = 2
    elif mode == "writing":
        if asset_type == "material":
            asset_cap = 2

    return family_cap, asset_cap


def apply_source_diversity(results: list[dict[str, Any]], *, mode: str, limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or not results:
        return []

    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    source_asset_counts: dict[tuple[str, str], int] = {}

    for item in results:
        source_key = canonical_source_key(item)
        if not source_key:
            selected.append(item)
            if len(selected) >= limit:
                return selected[:limit]
            continue

        family_cap, asset_cap = source_diversity_caps(mode, item)
        asset_type = str(item.get("asset_type", "")).strip()
        family_count = source_counts.get(source_key, 0)
        asset_count = source_asset_counts.get((source_key, asset_type), 0)

        if family_count >= family_cap or asset_count >= asset_cap:
            deferred.append(item)
            continue

        source_counts[source_key] = family_count + 1
        source_asset_counts[(source_key, asset_type)] = asset_count + 1
        selected.append(item)
        if len(selected) >= limit:
            return selected[:limit]

    if len(selected) < limit:
        for item in deferred:
            selected.append(item)
            if len(selected) >= limit:
                break

    return selected[:limit]


def is_writing_evidence_item(item: dict[str, Any]) -> bool:
    return str(item.get("asset_type", "")).strip() == "material" and str(item.get("subtype", "")).strip() in {"story", "data"}


def finalize_results(results: list[dict[str, Any]], *, mode: str, limit: int) -> list[dict[str, Any]]:
    selected = apply_source_diversity(results, mode=mode, limit=limit)
    if mode != "writing" or not selected:
        return selected
    if any(is_writing_evidence_item(item) for item in selected):
        return selected

    selected_keys = {str(item.get("id") or item.get("path")) for item in selected}
    candidate = next(
        (
            item
            for item in results
            if is_writing_evidence_item(item) and str(item.get("id") or item.get("path")) not in selected_keys
        ),
        None,
    )
    if candidate is None:
        return selected

    replace_index = next(
        (
            index
            for index in range(len(selected) - 1, -1, -1)
            if not is_writing_evidence_item(selected[index])
        ),
        None,
    )
    if replace_index is None:
        return selected

    promoted = list(selected)
    promoted[replace_index] = candidate
    promoted.sort(key=lambda item: (group_priority(item, mode), -float(item.get("_score", 0.0))))
    return promoted[:limit]


def material_doc(item: dict[str, Any]) -> str:
    parts = [str(item.get("primary_claim", "")), str(item.get("story_arc", ""))]
    parts.extend(str(x) for x in item.get("claims", []) if x)
    body = str(item.get("body_preview", "") or item.get("body", ""))
    if body:
        parts.append(body[:700])
    return compact_long_text(" ".join(parts), 900)


def entity_doc(item: dict[str, Any]) -> str:
    return compact_long_text(" ".join(
        [
            str(item.get("name", "")),
            str(item.get("title", "")),
            str(item.get("summary", "")),
            str(item.get("background_summary", "")),
            str(item.get("achievement_summary", "")),
            str(item.get("methodology_summary", "")),
            " ".join(str(x) for x in item.get("aliases", []) if x),
            str(item.get("body_preview", "") or item.get("body", ""))[:700],
        ]
    ), 900)


def source_doc(item: dict[str, Any]) -> str:
    return compact_long_text(" ".join(
        [
            str(item.get("title", "")),
            str(item.get("author", "")),
            str(item.get("origin", "")),
            str(item.get("summary", "")),
            str(item.get("chunk_summary", "")),
            str(item.get("chunk_text_preview", "") or item.get("chunk_text", ""))[:700],
        ]
    ), 900)


def source_field_bonus(item: dict[str, Any], query: str) -> float:
    field_text = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("author", "")),
            str(item.get("summary", "")),
            str(item.get("chunk_summary", "")),
        ]
    )
    overlap = lexical_overlap(query, [field_text])
    if overlap >= 0.30:
        return 0.08
    if overlap >= 0.12:
        return 0.04
    return 0.0


def material_field_bonus(item: dict[str, Any], query: str) -> float:
    field_text = " ".join(
        [
            str(item.get("primary_claim", "")),
            " ".join(str(x) for x in item.get("claims", []) if x),
            " ".join(str(x) for x in item.get("tags", []) if x),
            str(item.get("source", "")),
        ]
    )
    overlap = lexical_overlap(query, [field_text])
    if overlap >= 0.30:
        return 0.10
    if overlap >= 0.12:
        return 0.05
    return 0.0


def case_doc(item: dict[str, Any]) -> str:
    return compact_long_text(" ".join(
        [
            str(item.get("title", "")),
            str(item.get("retrieval_summary", "")),
            str(item.get("result_summary", "")),
            " ".join(str(x) for x in item.get("retrieval_tags", []) if x),
            " ".join(str(x) for x in item.get("source_refs", []) if x),
            str(item.get("body_preview", "") or item.get("body", ""))[:700],
        ]
    ), 900)


def lexical_bonus(item: dict[str, Any], mode: str, lexical_ratio: float) -> float:
    asset_type = item.get("asset_type")
    subtype = item.get("subtype")

    if mode == "strategy":
        if asset_type == "case":
            if lexical_ratio >= 0.30:
                return 0.12
            if lexical_ratio >= 0.16:
                return 0.08
            if lexical_ratio == 0.0:
                return -0.03
            return 0.03
        if asset_type == "material" and subtype in {"playbook", "method", "data"}:
            if lexical_ratio >= 0.24:
                return 0.08
            if lexical_ratio == 0.0:
                return -0.03
            return 0.02
        if asset_type == "source":
            if lexical_ratio >= 0.30:
                return 0.04
            if lexical_ratio == 0.0:
                return -0.12
            return -0.02

    if mode == "writing":
        if asset_type == "material":
            return 0.08 if lexical_ratio >= 0.24 else 0.04 if lexical_ratio >= 0.12 else 0.0
        if lexical_ratio == 0.0:
            return -0.03

    if mode == "source":
        if asset_type == "source":
            return 0.08 if lexical_ratio >= 0.24 else 0.04 if lexical_ratio >= 0.12 else 0.0
        if lexical_ratio == 0.0:
            return -0.04

    if lexical_ratio >= 0.24:
        return 0.05
    if lexical_ratio >= 0.12:
        return 0.02
    return 0.0


def is_low_confidence(item: dict[str, Any], mode: str) -> bool:
    lexical_ratio = float(item.get("_lexical_overlap", 0.0) or 0.0)
    reranker_abs = float(item.get("_reranker_abs", 0.0) or 0.0)
    vector_abs = float(item.get("_vector_abs", 0.0) or 0.0)
    asset_type = item.get("asset_type")

    if reranker_abs < 0.14 and lexical_ratio == 0.0 and vector_abs < 0.42:
        return True

    if mode == "strategy":
        if asset_type == "source" and lexical_ratio < 0.12 and reranker_abs < 0.32:
            return True
        if lexical_ratio == 0.0 and reranker_abs < 0.20 and vector_abs < 0.55:
            return True

    if mode == "writing" and asset_type != "material" and lexical_ratio == 0.0 and reranker_abs < 0.22:
        return True

    if mode == "source" and asset_type != "source" and lexical_ratio == 0.0 and reranker_abs < 0.22:
        return True

    return False


def collect_vector_candidates(
    context: SearchContext,
    *,
    index_key: str,
    index_relpath: str,
    items: list[dict[str, Any]],
    query_vector,
    limit: int,
    asset_type: str,
) -> list[dict[str, Any]]:
    if not items:
        return []
    index = context.load_index(index_key, index_relpath)
    if index is None:
        return []
    candidate_count = context.candidate_count(limit, len(items))
    started = time.time()
    scores, indices = index.search(query_vector, candidate_count)
    if context.stats:
        context.stats.vector_search_seconds += time.time() - started
    candidates = []
    for raw_score, idx in zip(scores[0].tolist(), indices[0].tolist()):
        if idx < 0 or idx >= len(items):
            continue
        item = dict(items[idx])
        item["asset_type"] = asset_type
        if asset_type == "material":
            item["subtype"] = item.get("subtype") or item.get("type") or "material"
        elif asset_type == "source":
            item["subtype"] = item.get("chunk_role") or "source_chunk"
        else:
            item["subtype"] = item.get("subtype") or "case"
        item["_vector_score"] = float(raw_score)
        candidates.append(item)
    return candidates


def collect_source_field_candidates(context: SearchContext, query: str, limit: int) -> list[dict[str, Any]]:
    items = context.source_items
    if not items:
        return []

    started = time.time()
    candidates: list[dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item)
        field_text = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("author", "")),
                str(item.get("summary", "")),
                str(item.get("chunk_summary", "")),
            ]
        )
        overlap = lexical_overlap(query, [field_text])
        author = str(item.get("author", "")).strip()
        author_hit = 1.0 if author and author in query else 0.0
        if overlap <= 0.0 and author_hit <= 0.0:
            continue
        item["asset_type"] = "source"
        item["subtype"] = item.get("chunk_role") or "source_chunk"
        item["_vector_score"] = 0.34 + overlap * 0.18 + author_hit * 0.16
        candidates.append(item)
    candidates.sort(key=lambda current: current["_vector_score"], reverse=True)
    if context.stats:
        context.stats.field_match_seconds += time.time() - started
    return candidates[: max(limit * 3, 12)]


def collect_material_field_candidates(context: SearchContext, query: str, limit: int) -> list[dict[str, Any]]:
    items = context.material_items
    if not items:
        return []

    started = time.time()
    candidates: list[dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item)
        field_text = " ".join(
            [
                str(item.get("primary_claim", "")),
                " ".join(str(x) for x in item.get("claims", []) if x),
                " ".join(str(x) for x in item.get("tags", []) if x),
                str(item.get("source", "")),
            ]
        )
        overlap = lexical_overlap(query, [field_text])
        primary_claim = str(item.get("primary_claim", "")).strip()
        primary_hit = 1.0 if primary_claim and primary_claim in query else 0.0
        if overlap <= 0.0 and primary_hit <= 0.0:
            continue
        item["asset_type"] = "material"
        item["subtype"] = item.get("subtype") or item.get("type") or "material"
        item["_vector_score"] = 0.36 + overlap * 0.22 + primary_hit * 0.18
        candidates.append(item)
    candidates.sort(key=lambda current: current["_vector_score"], reverse=True)
    if context.stats:
        context.stats.field_match_seconds += time.time() - started
    return candidates[: max(limit * 3, 12)]


def collect_entity_field_candidates(context: SearchContext, query: str, limit: int) -> list[dict[str, Any]]:
    items = context.entity_items
    if not items:
        return []

    started = time.time()
    candidates: list[dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item)
        field_text = " ".join(
            [
                str(item.get("name", "")),
                str(item.get("title", "")),
                str(item.get("summary", "")),
                str(item.get("background_summary", "")),
                str(item.get("achievement_summary", "")),
                str(item.get("methodology_summary", "")),
                " ".join(str(x) for x in item.get("aliases", []) if x),
            ]
        )
        overlap = lexical_overlap(query, [field_text])
        name = str(item.get("name", "")).strip()
        name_hit = 1.0 if name and name in query else 0.0
        if overlap <= 0.0 and name_hit <= 0.0:
            continue
        item["asset_type"] = "entity"
        item["subtype"] = item.get("subtype") or "entity_profile"
        item["_vector_score"] = 0.36 + overlap * 0.22 + name_hit * 0.18
        candidates.append(item)
    candidates.sort(key=lambda current: current["_vector_score"], reverse=True)
    if context.stats:
        context.stats.field_match_seconds += time.time() - started
    return candidates[: max(limit * 3, 12)]


def _search_knowledge_single(
    context: SearchContext,
    query: str,
    mode: str,
    limit: int,
    model: str,
    reranker_name: str | None,
    device: str,
    batch_size: int,
    min_score: float | None = None,
    query_vector: Any | None = None,
) -> list[dict[str, Any]]:
    if query_vector is None:
        started = time.time()
        query_vector = encode_texts(
            [query],
            model_name=model,
            device=device,
            batch_size=batch_size,
            query_prefix=DEFAULT_QUERY_PREFIX,
        )
        if context.stats:
            context.stats.encode_seconds += time.time() - started
    candidates: list[dict[str, Any]] = []
    candidates.extend(collect_vector_candidates(context, index_key="cases", index_relpath="index/cases/cases.faiss", items=context.case_items, query_vector=query_vector, limit=limit, asset_type="case"))
    candidates.extend(collect_vector_candidates(context, index_key="materials", index_relpath="index/materials/materials.faiss", items=context.material_items, query_vector=query_vector, limit=limit, asset_type="material"))
    candidates.extend(collect_vector_candidates(context, index_key="entities", index_relpath="index/entities/entities.faiss", items=context.entity_items, query_vector=query_vector, limit=limit, asset_type="entity"))
    candidates.extend(collect_vector_candidates(context, index_key="sources", index_relpath="index/sources/source_chunks.faiss", items=context.source_items, query_vector=query_vector, limit=limit, asset_type="source"))
    candidates.extend(collect_material_field_candidates(context, query, limit))
    candidates.extend(collect_entity_field_candidates(context, query, limit))
    candidates.extend(collect_source_field_candidates(context, query, limit))
    if not candidates:
        return []

    merged_candidates: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = str(item.get("id") or item.get("path"))
        if not key:
            continue
        existing = merged_candidates.get(key)
        if existing is None or float(item.get("_vector_score", 0.0)) > float(existing.get("_vector_score", 0.0)):
            merged_candidates[key] = item
    candidates = list(merged_candidates.values())
    if context.stats:
        context.stats.candidates_seen += len(candidates)

    vector_norms = normalize_scores([item["_vector_score"] for item in candidates])
    for item, norm in zip(candidates, vector_norms):
        item["_vector_norm"] = norm
        item["_vector_abs"] = calibrate_vector_score(item["_vector_score"])

    use_reranker = reranker_name is not None and len(candidates) > 1
    selected_for_rerank: list[dict[str, Any]] = []
    if use_reranker:
        rerank_top_k = context.profile.rerank_top_k
        selected_for_rerank = sorted(
            candidates,
            key=lambda item: (
                group_priority(item, mode),
                -float(item.get("_vector_norm", 0.0)),
                -float(item.get("_vector_score", 0.0)),
            ),
        )[:rerank_top_k] if rerank_top_k > 0 else []
        docs = []
        for item in selected_for_rerank:
            if item["asset_type"] == "case":
                docs.append(case_doc(item))
            elif item["asset_type"] == "entity":
                docs.append(entity_doc(item))
            elif item["asset_type"] == "material":
                docs.append(material_doc(item))
            else:
                docs.append(source_doc(item))
        started = time.time()
        selected_scores = rerank(
            query,
            docs,
            model_name=reranker_name,
            device=device,
            batch_size=context.profile.reranker_batch_size,
        ) if docs else []
        if context.stats:
            context.stats.reranker_seconds += time.time() - started
            context.stats.reranked_count += len(selected_scores)
        selected_norms = normalize_scores(selected_scores)
        selected_by_key = {
            str(item.get("id") or item.get("path")): (score, norm)
            for item, score, norm in zip(selected_for_rerank, selected_scores, selected_norms)
        }
        reranker_scores = []
        reranker_norms = []
        for item in candidates:
            score, norm = selected_by_key.get(str(item.get("id") or item.get("path")), (0.0, 0.0))
            reranker_scores.append(score)
            reranker_norms.append(norm)
    else:
        reranker_scores = [0.0 for _ in candidates]
        reranker_norms = [0.0 for _ in candidates]

    for item, rerank_score, rerank_norm in zip(candidates, reranker_scores, reranker_norms):
        item["_reranker_score"] = rerank_score
        item["_reranker_norm"] = rerank_norm
        item["_reranker_abs"] = calibrate_reranker_score(rerank_score)

        if item["asset_type"] == "case":
            doc_texts = [case_doc(item)]
        elif item["asset_type"] == "entity":
            doc_texts = [entity_doc(item)]
        elif item["asset_type"] == "material":
            doc_texts = [material_doc(item)]
        else:
            doc_texts = [source_doc(item)]

        lexical_ratio = lexical_overlap(query, doc_texts)
        item["_lexical_overlap"] = lexical_ratio
        bonus = mode_bonus(item, mode)
        item["_mode_bonus"] = bonus
        asset_prior = max(0.0, min(1.0, 0.5 + bonus))
        lex_bonus = lexical_bonus(item, mode, lexical_ratio)
        item["_lexical_bonus"] = lex_bonus
        field_bonus = 0.0
        if item["asset_type"] == "source":
            field_bonus = source_field_bonus(item, query)
        elif item["asset_type"] == "material":
            field_bonus = material_field_bonus(item, query)
        item["_field_bonus"] = field_bonus
        item["_score"] = (
            0.25 * item["_reranker_norm"]
            + 0.25 * item["_reranker_abs"]
            + 0.15 * item["_vector_norm"]
            + 0.15 * item["_vector_abs"]
            + 0.20 * asset_prior
            + lex_bonus
            + field_bonus
        )

        if item["asset_type"] == "case":
            item["preview"] = item.get("preview") or normalize_preview(item.get("retrieval_summary", "") or item.get("body_preview", "") or item.get("body", ""))
            item["why_matched"] = item.get("retrieval_summary") or item.get("result_summary", "")
            item["source_refs"] = item.get("source_refs", [])
        elif item["asset_type"] == "entity":
            item["preview"] = normalize_preview(item.get("summary", "") or item.get("body_preview", "") or item.get("body", ""))
            item["why_matched"] = item.get("summary", "") or item.get("name", "")
            item["source_refs"] = item.get("source_refs", [])
        elif item["asset_type"] == "material":
            item["preview"] = normalize_preview(item.get("body_preview", "") or item.get("body", ""))
            item["why_matched"] = item.get("primary_claim", "")
            item["source_refs"] = item.get("source_refs", [])
        else:
            item["preview"] = normalize_preview(item.get("chunk_text_preview", "") or item.get("chunk_text", ""))
            item["why_matched"] = item.get("chunk_summary", "")
            item["source_refs"] = [item.get("path", "")]

    candidates.sort(key=lambda item: (group_priority(item, mode), -item["_score"]))
    threshold = default_min_score(mode) if min_score is None else min_score
    filtered: list[dict[str, Any]] = []
    for item in candidates:
        if is_low_confidence(item, mode):
            continue
        if item["_score"] < item_min_score(item, mode, threshold):
            continue
        filtered.append(item)

    if mode == "strategy":
        strong_cases = [item for item in filtered if item.get("asset_type") == "case"]
        if strong_cases:
            preferred = strong_cases
            secondary = [
                item
                for item in filtered
                if item.get("asset_type") != "case" and not (item.get("asset_type") == "source" and item.get("_lexical_overlap", 0.0) < 0.12)
            ]
            filtered = preferred + secondary

    return finalize_results(filtered, mode=mode, limit=limit)


def merge_search_results(
    candidates: list[dict[str, Any]],
    *,
    mode: str,
    limit: int,
    query_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        key = str(candidate.get("id") or candidate.get("path"))
        if not key:
            continue
        current = grouped.get(key)
        if current is None or float(candidate.get("_score", 0.0)) > float(current.get("_score", 0.0)):
            merged = dict(candidate)
            grouped[key] = merged
            current = merged

        query_matches = list(current.get("_query_matches", []))
        query_matches.append(
            {
                "query": candidate.get("_matched_query"),
                "intent": candidate.get("_matched_intent"),
                "source": candidate.get("_matched_query_source"),
                "weight": candidate.get("_matched_query_weight"),
                "score": round(float(candidate.get("_branch_score", candidate.get("_score", 0.0))), 6),
            }
        )
        current["_query_matches"] = query_matches
        current["_coverage"] = len({entry["query"] for entry in query_matches if entry.get("query")})
        current["_query_plan"] = query_plan or current.get("_query_plan")

    source_query_coverage: dict[str, set[str]] = {}
    for item in grouped.values():
        source_key = canonical_source_key(item)
        if not source_key:
            continue
        query_set = source_query_coverage.setdefault(source_key, set())
        for entry in item.get("_query_matches", []):
            query = str(entry.get("query", "")).strip()
            if query:
                query_set.add(query)

    merged_results: list[dict[str, Any]] = []
    for item in grouped.values():
        source_key = canonical_source_key(item)
        source_coverage = len(source_query_coverage.get(source_key, set())) if source_key else int(item.get("_coverage", 1) or 1)
        item["_source_key"] = source_key
        item["_source_coverage"] = source_coverage
        coverage_basis = source_coverage if source_key else int(item.get("_coverage", 1) or 1)
        coverage_bonus = min(0.025 * max(coverage_basis - 1, 0), 0.06)
        original_bonus = 0.04 if any(match.get("source") == "original" for match in item.get("_query_matches", [])) else 0.0
        item["_score"] = float(item.get("_score", 0.0)) + coverage_bonus + original_bonus
        merged_results.append(item)

    merged_results.sort(key=lambda item: (group_priority(item, mode), -float(item.get("_score", 0.0))))

    if mode == "strategy":
        case_results = [item for item in merged_results if item.get("asset_type") == "case"]
        if case_results:
            non_case_results = [item for item in merged_results if item.get("asset_type") != "case"]
            merged_results = case_results + non_case_results

    return finalize_results(merged_results, mode=mode, limit=limit)


def aggregate_person_intro_results(
    results: list[dict[str, Any]],
    *,
    query_plan: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    source_groups: dict[str, list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []

    requested_facets = [str(facet).strip() for facet in query_plan.get("requested_facets", []) if str(facet).strip()]

    def source_facet_score(item: dict[str, Any]) -> float:
        if not requested_facets:
            return 0.0
        text = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("chunk_summary", "")),
                str(item.get("why_matched", "")),
                str(item.get("preview", "")),
                str(item.get("chunk_text", ""))[:400],
            ]
        )
        score = 0.0
        for facet in requested_facets:
            for cue in PERSON_FACET_CUES.get(facet, ()):
                if cue in text:
                    score += 1.0
        return score

    for item in results:
        if item.get("asset_type") == "entity":
            enriched = dict(item)
            facet_snippets: list[str] = []
            facet_map = {
                "background": str(enriched.get("background_summary", "")).strip(),
                "achievements": str(enriched.get("achievement_summary", "")).strip(),
                "methodology": str(enriched.get("methodology_summary", "")).strip(),
            }
            for facet in requested_facets:
                snippet = facet_map.get(facet, "")
                if snippet:
                    facet_snippets.append(snippet)
            if not facet_snippets:
                facet_snippets.append(str(enriched.get("summary", "")).strip())
            enriched["preview"] = " ".join([snippet for snippet in facet_snippets[:2] if snippet]).strip() or str(enriched.get("preview", "")).strip()
            enriched["why_matched"] = " | ".join([snippet for snippet in facet_snippets if snippet]).strip() or str(enriched.get("why_matched", "")).strip()
            entities.append(enriched)
            continue
        if item.get("asset_type") != "source":
            passthrough.append(item)
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            passthrough.append(item)
            continue
        source_groups.setdefault(path, []).append(item)

    aggregated: list[dict[str, Any]] = []
    for path, items in source_groups.items():
        ranked = sorted(items, key=lambda current: float(current.get("_score", 0.0)), reverse=True)
        facet_ranked = sorted(
            ranked,
            key=lambda current: (
                source_facet_score(current),
                float(current.get("_score", 0.0)),
            ),
            reverse=True,
        )
        best = dict(facet_ranked[0])
        author = str(best.get("author", "")).strip()
        title = str(best.get("title", "")).strip()
        summary_candidates = facet_ranked if requested_facets else ranked
        preview_candidates = facet_ranked if requested_facets else ranked
        summaries = dedupe_keep_order([str(item.get("why_matched", "")).strip() for item in summary_candidates if str(item.get("why_matched", "")).strip()])
        previews = dedupe_keep_order([str(item.get("preview", "")).strip() for item in preview_candidates if str(item.get("preview", "")).strip()])
        query_matches = []
        for item in ranked:
            query_matches.extend(item.get("_query_matches", []))
        best["_query_matches"] = query_matches
        best["_coverage"] = len({entry.get("query") for entry in query_matches if entry.get("query")})
        best["subtype"] = "source_profile"
        best["chunk_role"] = "profile"
        best["why_matched"] = " | ".join(summaries[:3]) if summaries else str(best.get("why_matched", "")).strip()
        preview_parts = []
        if author:
            preview_parts.append(f"作者：{author}")
        if previews:
            preview_parts.append(previews[0])
        if len(previews) > 1:
            preview_parts.append(previews[1])
        best["preview"] = " ".join(part for part in preview_parts if part).strip() or str(best.get("preview", "")).strip()
        best["source_refs"] = [path]
        best["evidence_snippets"] = previews[:3]
        path_coverage_bonus = min(0.02 * max(len(ranked) - 1, 0), 0.06)
        best["_score"] = float(best.get("_score", 0.0)) + path_coverage_bonus
        if title and author and author not in title:
            best["title"] = f"{author}｜{title}"
        aggregated.append(best)

    combined = entities + aggregated + passthrough
    combined.sort(key=lambda item: (group_priority(item, "source"), -float(item.get("_score", 0.0))))
    return combined[:limit]


def rerank_merged_results(
    *,
    query: str,
    results: list[dict[str, Any]],
    context: SearchContext,
    mode: str,
    reranker_name: str | None,
    device: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not reranker_name or len(results) <= 1 or context.profile.rerank_top_k <= 0:
        return finalize_results(results, mode=mode, limit=limit)

    selected = sorted(
        results,
        key=lambda item: (
            group_priority(item, mode),
            -float(item.get("_score", 0.0)),
            -float(item.get("_vector_score", 0.0)),
        ),
    )[: context.profile.rerank_top_k]
    docs: list[str] = []
    for item in selected:
        if item["asset_type"] == "case":
            docs.append(case_doc(item))
        elif item["asset_type"] == "entity":
            docs.append(entity_doc(item))
        elif item["asset_type"] == "material":
            docs.append(material_doc(item))
        else:
            docs.append(source_doc(item))
    if not docs:
        return finalize_results(results, mode=mode, limit=limit)

    started = time.time()
    scores = rerank(
        query,
        docs,
        model_name=reranker_name,
        device=device,
        batch_size=context.profile.reranker_batch_size,
    )
    if context.stats:
        context.stats.reranker_seconds += time.time() - started
        context.stats.reranked_count += len(scores)

    norms = normalize_scores(scores)
    by_key = {
        str(item.get("id") or item.get("path")): (score, norm)
        for item, score, norm in zip(selected, scores, norms)
    }
    for item in results:
        key = str(item.get("id") or item.get("path"))
        if key not in by_key:
            continue
        score, norm = by_key[key]
        old_abs = float(item.get("_reranker_abs", 0.0) or 0.0)
        old_norm = float(item.get("_reranker_norm", 0.0) or 0.0)
        new_abs = calibrate_reranker_score(score)
        item["_reranker_score"] = score
        item["_reranker_norm"] = norm
        item["_reranker_abs"] = new_abs
        item["_score"] = float(item.get("_score", 0.0)) - 0.25 * old_norm - 0.25 * old_abs + 0.25 * norm + 0.25 * new_abs

    results.sort(key=lambda item: (group_priority(item, mode), -float(item.get("_score", 0.0))))
    return finalize_results(results, mode=mode, limit=limit)


def search_knowledge(
    root: Path,
    query: str,
    mode: str,
    limit: int,
    model: str,
    reranker_name: str | None,
    device: str,
    batch_size: int,
    min_score: float | None = None,
    conversation_history: list[str] | None = None,
    context_info: str | None = None,
    enable_query_rewrite: bool = True,
    planner_provider: str = QUERY_PLANNER_PROVIDER,
    profile_name: str | None = None,
) -> list[dict[str, Any]]:
    profile = resolve_search_profile(profile_name)
    stats = SearchStats(profile=profile.name)
    resolved_device = device if device != "auto" else profile.default_device
    resolved_batch_size = batch_size if batch_size else profile.batch_size
    effective_reranker_name = reranker_name if profile.rerank_top_k > 0 else None

    with local_search_lock(root, profile.use_local_lock):
        if profile.wait_for_memory and wait_for_memory_budget is not None:
            ok, reason, waited = wait_for_memory_budget(
                timeout_seconds=profile.memory_wait_seconds,
                min_readily_available_mb=profile.min_readily_available_mb,
                max_compressed_mb=profile.max_compressed_mb,
            )
            stats.memory_wait_seconds += waited
            if not ok:
                stats.memory_wait_reason = reason

        context = SearchContext(root, profile, stats)
        started = time.time()
        query_plan = build_query_plan(
            query,
            mode=mode,
            conversation_history=conversation_history,
            context_info=context_info,
            planner_provider=planner_provider,
            root=root,
        )
        stats.query_plan_seconds += time.time() - started
        effective_mode = query_plan.get("search_mode", mode) if enable_query_rewrite else mode
        if not effective_mode:
            effective_mode = mode

        if not enable_query_rewrite:
            results = _search_knowledge_single(
                context,
                query,
                effective_mode,
                limit,
                model,
                effective_reranker_name,
                resolved_device,
                resolved_batch_size,
                min_score,
            )
            for item in results:
                item["_query_plan"] = query_plan
                item["_query_matches"] = [{"query": query, "intent": "原始查询", "source": "original", "weight": 1.0, "score": round(float(item.get("_score", 0.0)), 6)}]
                item["_search_stats"] = stats.as_dict()
            return results

        branch_specs = list(query_plan.get("rewrites", [])) or [
            {"query": normalize_query_text(query), "intent": "原始查询", "weight": 1.0, "source": "original", "reason": "fallback"}
        ]
        branch_specs = branch_specs[: profile.branch_max]
        stats.branch_count = len(branch_specs)

        branch_queries: list[str] = []
        filtered_branch_specs: list[dict[str, Any]] = []
        for branch in branch_specs:
            branch_query = str(branch.get("query", "")).strip()
            if not branch_query:
                continue
            branch_queries.append(branch_query)
            filtered_branch_specs.append(branch)

        if not branch_queries:
            return []

        started = time.time()
        branch_vectors = encode_texts(
            branch_queries,
            model_name=model,
            device=resolved_device,
            batch_size=resolved_batch_size,
            query_prefix=DEFAULT_QUERY_PREFIX,
        )
        stats.encode_seconds += time.time() - started

        merged_candidates: list[dict[str, Any]] = []
        branch_limit = min(max(limit * 2, limit + 2), profile.branch_limit_cap)
        for branch_index, branch in enumerate(filtered_branch_specs):
            branch_query = branch_queries[branch_index]
            branch_weight = float(branch.get("weight", 1.0) or 1.0)
            branch_results = _search_knowledge_single(
                context,
                branch_query,
                effective_mode,
                branch_limit,
                model,
                None,
                resolved_device,
                resolved_batch_size,
                min_score,
                query_vector=branch_vectors[branch_index : branch_index + 1],
            )
            for rank, item in enumerate(branch_results):
                enriched = dict(item)
                enriched["_branch_score"] = float(item.get("_score", 0.0))
                enriched["_matched_query"] = branch_query
                enriched["_matched_intent"] = branch.get("intent", "")
                enriched["_matched_query_source"] = branch.get("source", "rewrite")
                enriched["_matched_query_weight"] = branch_weight
                enriched["_score"] = (
                    float(item.get("_score", 0.0)) * (0.88 + 0.12 * branch_weight)
                    + (0.04 if branch.get("source") == "original" else 0.015)
                    - rank * 0.003
                )
                enriched["_query_plan"] = query_plan
                merged_candidates.append(enriched)

        if not merged_candidates:
            return []

        pre_rerank_limit = max(limit, profile.rerank_top_k if effective_reranker_name else limit)
        merged_results = merge_search_results(merged_candidates, mode=effective_mode, limit=pre_rerank_limit, query_plan=query_plan)
        merged_results = rerank_merged_results(
            query=query,
            results=merged_results,
            context=context,
            mode=effective_mode,
            reranker_name=effective_reranker_name,
            device=resolved_device,
            limit=limit,
        )
        if str(query_plan.get("intent", query_plan.get("query_type", ""))).strip() == "person_intro":
            merged_results = aggregate_person_intro_results(merged_results, query_plan=query_plan, limit=limit)
        stats_payload = stats.as_dict()
        for item in merged_results:
            item["_search_stats"] = stats_payload
        return merged_results


def main() -> None:
    parser = argparse.ArgumentParser(description="统一搜索商业案例、素材和来源")
    parser.add_argument("query")
    parser.add_argument("--root", default=".")
    parser.add_argument("--mode", choices=["strategy", "writing", "source", "hybrid"], default="hybrid")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--reranker", default=DEFAULT_RERANKER_NAME, help="'none' 可关闭 reranker")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=0, help="0 表示使用 profile 默认 batch size")
    parser.add_argument("--profile", choices=sorted(SEARCH_PROFILES), default=os.getenv("KNOWLEDGE_SEARCH_PROFILE", "local_quality"))
    parser.add_argument("--min-score", type=float)
    parser.add_argument("--history", action="append", default=[], help="追加一条对话历史，可多次传入")
    parser.add_argument("--context-info", default="", help="额外上下文信息")
    parser.add_argument("--disable-query-rewrite", action="store_true")
    parser.add_argument("--query-planner-provider", choices=["auto", "rule", "llm"], default=QUERY_PLANNER_PROVIDER)
    parser.add_argument("--show-query-plan", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    reranker_name = None if str(args.reranker).lower() in {"none", "false", "0"} else args.reranker
    results = search_knowledge(
        root,
        args.query,
        args.mode,
        args.limit,
        args.model,
        reranker_name,
        args.device,
        args.batch_size,
        args.min_score,
        conversation_history=list(args.history or []),
        context_info=args.context_info,
        enable_query_rewrite=not args.disable_query_rewrite,
        planner_provider=args.query_planner_provider,
        profile_name=args.profile,
    )
    query_plan = results[0].get("_query_plan", {}) if results else {}
    if args.show_query_plan:
        print(json.dumps({"query_plan": query_plan}, ensure_ascii=False))
    for item in results:
        payload = {
            "asset_type": item["asset_type"],
            "subtype": item.get("subtype"),
            "path": item.get("path"),
            "score": round(item["_score"], 6),
            "preview": item.get("preview"),
            "why_matched": item.get("why_matched"),
            "source_refs": item.get("source_refs", []),
        }
        if item["asset_type"] == "case":
            payload["title"] = item.get("title")
            payload["platform"] = item.get("platform")
            payload["domain"] = item.get("domain")
        elif item["asset_type"] == "material":
            payload["primary_claim"] = item.get("primary_claim")
            payload["type"] = item.get("type")
        else:
            payload["title"] = item.get("title")
            payload["chunk_role"] = item.get("chunk_role")
        if args.verbose:
            payload["rank_debug"] = {
                "vector_score": round(item.get("_vector_score", 0.0), 6),
                "vector_norm": round(item.get("_vector_norm", 0.0), 6),
                "vector_abs": round(item.get("_vector_abs", 0.0), 6),
                "reranker_score": round(item.get("_reranker_score", 0.0), 6),
                "reranker_norm": round(item.get("_reranker_norm", 0.0), 6),
                "reranker_abs": round(item.get("_reranker_abs", 0.0), 6),
                "mode_bonus": round(item.get("_mode_bonus", 0.0), 6),
                "lexical_overlap": round(item.get("_lexical_overlap", 0.0), 6),
                "lexical_bonus": round(item.get("_lexical_bonus", 0.0), 6),
                "matched_query": item.get("_matched_query"),
                "matched_query_weight": round(float(item.get("_matched_query_weight", 0.0) or 0.0), 6),
            }
            payload["query_matches"] = item.get("_query_matches", [])
            payload["query_plan"] = item.get("_query_plan", query_plan)
            payload["search_stats"] = item.get("_search_stats", {})
        else:
            payload["query_plan_backend"] = item.get("_query_plan", query_plan).get("planner_backend", query_plan.get("planner_backend"))
            if item.get("_search_stats"):
                payload["search_profile"] = item["_search_stats"].get("profile")
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
