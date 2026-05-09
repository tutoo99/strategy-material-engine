#!/opt/miniconda3/bin/python3

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import yaml

from _io_safety import atomic_write_jsonl


DEFAULT_MODEL_NAME = "BAAI/bge-large-zh-v1.5"
DEFAULT_RERANKER_NAME = "BAAI/bge-reranker-v2-m3"
DEFAULT_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
MODEL_MAX_LENGTH = 512

_MODEL_CACHE: dict[tuple[str, str], tuple[Any, Any]] = {}
_RERANKER_CACHE: dict[str, tuple[Any, Any]] = {}  # type: ignore[no-redef]


def _import_torch():
    import torch

    return torch


def _import_faiss():
    import faiss

    return faiss


def _sanitize_yaml_frontmatter(raw: str) -> str:
    """Sanitize common CJK patterns that break YAML safe_load.

    Handles:
    - CJK curly quotes \u201c\u201d\u2018\u2019 → corner brackets \u300c\u300d\u300e\u300f
      (these look like ASCII quotes to humans but are invalid YAML string delimiters)
    - Fullwidth parens \uff08\uff09 → halfwidth parens
    - Bare text after a double-quoted scalar on the same list line, e.g.
      - \"text\"note  →  - \"textnote\"
      This happens frequently with CJK annotations like - \"xxx\"（yyy）
    """
    out = raw.replace("\u201c", "\u300c").replace("\u201d", "\u300d")
    out = out.replace("\u2018", "\u300e").replace("\u2019", "\u300f")
    out = out.replace("\uff08", "(").replace("\uff09", ")")
    # Merge bare text after closing double-quote on list-item lines:
    #   - "quoted text"trailing  →  - "quoted texttrailing"
    out = re.sub(
        r'^(\s*- )\"([^\"]*)\"(\S.*)$',
        r'\1"\2\3"',
        out,
        flags=re.MULTILINE,
    )
    # Also merge bare text after closing double-quote on non-list scalar lines:
    #   key: "text"——trailing  →  key: "text——trailing"
    out = re.sub(
        r'^(?!\s*- )(\w[\w\s]*?):\s+\"([^\"]*)\"(\S.*)$',
        r'\1: "\2\3"',
        out,
        flags=re.MULTILINE,
    )
    return out


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text.strip()
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text.strip()
    raw_meta = _sanitize_yaml_frontmatter(parts[0][4:])
    body = parts[1].strip()
    meta = yaml.safe_load(raw_meta) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def list_markdown_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.md"))
        if path.is_file() and not path.name.startswith("_")
    ]


def ensure_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value).strip()]


def ensure_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def ensure_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_datetime_like(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    candidates = [normalized]
    if len(text) == 10:
        candidates.append(f"{text}T00:00:00+00:00")
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return None


def days_since(value: object) -> int | None:
    parsed = parse_datetime_like(value)
    if parsed is None:
        return None
    now = datetime.now(timezone.utc)
    return max((now - parsed).days, 0)


def detect_device(preferred: str | None = None) -> str:
    torch = _import_torch()
    if preferred and preferred != "auto":
        return preferred
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_encoder(model_name: str, device: str) -> tuple[Any, Any]:
    from transformers import AutoModel, AutoTokenizer

    cache_key = (model_name, device)
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        model = AutoModel.from_pretrained(model_name, local_files_only=True, use_safetensors=False)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name, use_safetensors=False)
    model.eval()
    model.to(device)
    _MODEL_CACHE[cache_key] = (tokenizer, model)
    return tokenizer, model


def mean_pool(last_hidden_state: Any, attention_mask: Any) -> Any:
    torch = _import_torch()
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    masked = last_hidden_state * mask
    summed = torch.sum(masked, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def encode_texts(
    texts: Iterable[str],
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    device: str = "auto",
    batch_size: int = 8,
    query_prefix: str | None = None,
) -> np.ndarray:
    torch = _import_torch()
    resolved_device = detect_device(device)
    tokenizer, model = load_encoder(model_name, resolved_device)
    text_list = [str(text).strip() for text in texts]
    if query_prefix:
        text_list = [f"{query_prefix}{text}" for text in text_list]
    if not text_list:
        return np.zeros((0, 1024), dtype=np.float32)

    batches: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(text_list), batch_size):
            batch = text_list[start : start + batch_size]
            tokens = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MODEL_MAX_LENGTH,
                return_tensors="pt",
            )
            tokens = {key: value.to(resolved_device) for key, value in tokens.items()}
            outputs = model(**tokens)
            pooled = mean_pool(outputs.last_hidden_state, tokens["attention_mask"])
            normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
            batches.append(normalized.detach().cpu().numpy().astype("float32"))
    return np.vstack(batches)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    atomic_write_jsonl(path, rows)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_faiss_index(vectors: np.ndarray):
    faiss = _import_faiss()
    if vectors.ndim != 2:
        raise ValueError("Vectors must be a 2D array")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return index


def write_faiss_index(path: Path, index: Any) -> None:
    faiss = _import_faiss()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
    try:
        faiss.write_index(index, str(temp_path))
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def read_faiss_index(path: Path):
    faiss = _import_faiss()
    return faiss.read_index(str(path))


def clamp_candidate_count(limit: int) -> int:
    return max(limit * 8, 30)


COMMON_CJK_TERMS = {
    "一个", "一种", "这个", "那个", "这些", "那些", "不是", "而是", "真正", "很多",
    "自己", "别人", "什么", "怎么", "为什么", "因为", "所以", "如果", "没有",
    "时候", "问题", "能力", "结果", "价值", "方法", "事情", "容易", "需要",
}


def lexical_terms(text: str) -> set[str]:
    """Extract lightweight lexical terms for mixed Chinese/English retrieval checks."""
    normalized = str(text or "").lower()
    terms = {
        match.group(0)
        for match in re.finditer(r"[a-z0-9][a-z0-9_+\-.]{1,}", normalized)
    }
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        if 2 <= len(segment) <= 8 and segment not in COMMON_CJK_TERMS:
            terms.add(segment)
        for size in (2, 3, 4):
            if len(segment) < size:
                continue
            for index in range(0, len(segment) - size + 1):
                gram = segment[index : index + size]
                if gram not in COMMON_CJK_TERMS:
                    terms.add(gram)
    return {term for term in terms if len(term) >= 2}


def lexical_overlap_ratio(query: str, texts: list[str]) -> float:
    query_terms = lexical_terms(query)
    if not query_terms:
        return 0.0
    haystack = str(" ".join(texts)).lower()
    hits = sum(1 for term in query_terms if term in haystack)
    return hits / len(query_terms)


def load_reranker(model_name: str = DEFAULT_RERANKER_NAME, device: str = "auto"):
    """Load a cross-encoder reranker model. Returns (tokenizer, model)."""
    if model_name in _RERANKER_CACHE:
        return _RERANKER_CACHE[model_name]
    from transformers import AutoModelForSequenceClassification
    from transformers import AutoTokenizer

    resolved_device = detect_device(device)
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(model_name, local_files_only=True)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    model.to(resolved_device)
    _RERANKER_CACHE[model_name] = (tokenizer, model)
    return tokenizer, model


def rerank(
    query: str,
    documents: list[str],
    *,
    model_name: str = DEFAULT_RERANKER_NAME,
    device: str = "auto",
    batch_size: int = 16,
) -> list[float]:
    """
    Re-rank documents against a query using a cross-encoder.
    Returns a list of scores, one per document, in the same order as input.
    """
    if not documents:
        return []
    torch = _import_torch()
    tokenizer, model = load_reranker(model_name, device)
    resolved_device = detect_device(device)
    pairs = [[query, doc] for doc in documents]
    all_scores: list[float] = []
    with torch.no_grad():
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start : start + batch_size]
            tokens = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            tokens = {key: value.to(resolved_device) for key, value in tokens.items()}
            outputs = model(**tokens)
            # bge-reranker-v2-m3 outputs logits; for relevance, use logit at index 1 (positive class)
            if outputs.logits.shape[-1] == 1:
                # Some reranker models output a single score
                batch_scores = outputs.logits.squeeze(-1).tolist()
            else:
                batch_scores = outputs.logits[:, 1].tolist()
            if isinstance(batch_scores, float):
                batch_scores = [batch_scores]
            all_scores.extend(batch_scores)
    return all_scores
