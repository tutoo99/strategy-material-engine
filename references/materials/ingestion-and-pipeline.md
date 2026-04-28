# Ingestion & Pipeline Reference

## Ingestion: ebooks and video transcripts

Both go into `sources/materials/` as raw source material.

### Ebooks

1. Extract text: PDF → magic-pdf (`~/Library/Python/3.9/bin/magic-pdf <file>`), EPUB → find txt/convert
2. If book is large (>50k chars), split by chapter — each chapter becomes a separate source file (e.g., `纳瓦尔宝典_第3章.md`)
3. Save the cleaned text as a markdown file with frontmatter
4. Use `scripts/import_source_and_route.py <file> --root . --bucket materials --source-type book`
5. Run `/opt/miniconda3/bin/python3 scripts/build_sources_index.py --root . --device cpu --batch-size 2`

### Video transcripts

1. Get subtitles: YouTube → youtube-content skill, B站 → browser/API extraction, audio → Whisper
2. If transcript > 10k chars, split by topic segments
3. Save the transcript as a markdown file with frontmatter
4. Use `scripts/import_source_and_route.py <file> --root . --bucket materials --source-type transcript`
5. Run `/opt/miniconda3/bin/python3 scripts/build_sources_index.py --root . --device cpu --batch-size 2`

### Duplicate gate

`scripts/import_source_and_route.py` now runs a cheap duplicate preflight before writing a new source:

- same normalized URL -> skip by default
- same normalized body hash -> skip by default
- near-same body fingerprint -> report candidate and skip unless explicitly forced

Useful commands:

```bash
/opt/miniconda3/bin/python3 scripts/import_source_and_route.py /path/to/source.md --root . --bucket materials
/opt/miniconda3/bin/python3 scripts/import_source_and_route.py /path/to/source.md --root . --bucket materials --force-import
/opt/miniconda3/bin/python3 scripts/audit_source_duplicates.py --root . --update-registry
```

When a duplicate really must be retained, use `--force-import`; the new source will be marked with `duplicate_of` and `dedupe_note`.

### Splitting principle

Split by retrieval granularity, not by source file. Each source should be 3000-8000 chars for optimal chunk matching. Overly large files produce imprecise retrieval because chunks lose context boundaries.

Write good metadata: tags (3-5 keywords), author, origin. These feed into embed_text and improve recall accuracy.

## Pipeline internals

For debugging and understanding how the system works:

```
入库: 文本 → BGE编码(1024维向量) → FAISS索引(.faiss) + 元数据(.jsonl)
搜索: 查询(+前缀) → BGE编码 → FAISS内积 → top-K → (可选reranker) → 返回
```

### BGE (bge-large-zh-v1.5)

Dual-tower encoder. Query and document encoded separately:
- Document: raw text → tokenizer → model → mean pooling → L2 normalize → 1024-dim vector
- Query: prefixed with `为这个句子生成表示以用于检索相关文章：` → same pipeline
- The prefix tells the model "this is the query side" for asymmetric retrieval
- Cached locally at `~/.cache/huggingface/hub/models--BAAI--bge-large-zh-v1.5` (~2.4 GB)

### FAISS (IndexFlatIP)

- Brute-force inner product search (equivalent to cosine similarity since vectors are L2-normalized)
- No compression, no partitioning — simple and accurate for <10k items
- Index saved as `.faiss` file, metadata as `.jsonl`, aligned by row index: `vector[i]` ↔ `meta[i]`
- Rebuild is full (not incremental) — scans all md files each time

### Current post-filter

`lexical_overlap_ratio()` in `_material_lib.py` checks token overlap between query and candidate texts. Catches semantic-only false positives where meaning is close but surface form doesn't match writing needs.

### Reranker (bge-reranker-v2-m3, 已实现)

Cross-encoder：query+document 作为输入对，输出相关性分数。比双塔编码器更准但慢约100倍，所以只对 FAISS 召回的 top-30~40 候选做 rerank。

**当前流水线**：`BGE → FAISS top-K(=limit*8) → type/role过滤 → reranker全量重排 → min-max归一化 → 60%reranker+40%heuristic混排 → 返回`

**模型细节**：
- BAAI/bge-reranker-v2-m3，本地缓存 `~/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3`
- 输出2类 logits，index 1 是正类（相关），用 `outputs.logits[:, 1]` 取分
- 进程级缓存（`_RERANKER_CACHE`），同进程内复用不重复加载

**混排公式**：
1. reranker 原始分数 min-max 归一化到 [0, 1]
2. 缩放到 heuristic 分数同量级：`reranker_scaled = 0.4 + norm * 0.3`（范围 0.4~0.7）
3. 最终分：`0.6 * reranker_scaled + 0.4 * heuristic_score`
4. heuristic_score 包含 vector_score + claim_bonus + quality_bonus + freshness 等（原有逻辑不变）

**关闭 reranker**：`--reranker none`（search_materials.py 和 search_sources.py 均支持）

**实现位置**：
- `_material_lib.py`：`load_reranker()` + `rerank()`
- `search_materials.py`：Phase 2 rerank → Phase 3 blend
- `search_sources.py`：同样的两阶段架构

**实测效果**：query "底层逻辑跨体量跨阶段通用的依据是什么" 无 reranker 时正确素材排第3（被不相关素材盖过），加 reranker 后正确素材排第1（reranker_score 4.8 vs 其他候选 2.1~2.8）。

**性能**：CLI 独立进程调用约 7-9 秒（含两个模型加载），同进程内调用（如 Hermes execute_code）reranker 加载一次后复用，推理本身仅几百毫秒。

## Upgrade path

```
素材 < 3000 条     → current: BGE + FAISS + bge-reranker-v2-m3
素材 > 3000       → migrate FAISS → Chroma (metadata filtering, incremental updates)
素材 > 10000      → incremental index build
```

### Reranker 已选型：bge-reranker-v2-m3

| Model | Size | License | Notes |
|---|---|---|---|
| **bge-reranker-v2-m3** | ~2.2 GB | MIT | **已部署**，Best accuracy, same family as BGE encoder |
| bge-reranker-v2-minicpm-layerwise | ~400 MB | MIT | 备选：更小更快，准确率略低 |

### FAISS → Chroma migration

Only 3 functions need changing in `_material_lib.py`:
- `build_faiss_index()` + `write_faiss_index()` → `collection.add(ids, embeddings, metadatas, documents)`
- `read_faiss_index()` + `faiss.search()` → `collection.query(query_embeddings, where={...})`
- jsonl metadata files become unnecessary (Chroma stores metadata natively)

Unchanged: `encode_texts()`, `parse_frontmatter()`, all parsing logic, all build/search script structure.

Estimated ~50-80 lines of code changes. Half day of work.

## Multi-project data isolation

Three approaches:

1. **Separate indexes per project** — current pattern, each .faiss file is one collection
2. **Single index + metadata filtering** — requires Chroma/Qdrant, not supported by raw FAISS
3. **Hybrid** — global shared index + per-project indexes (best balance of isolation and reuse)

Recommendation: stay with approach 1 until cross-project material reuse becomes a real need.
