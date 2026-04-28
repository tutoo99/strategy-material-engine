---
name: strategy-material-engine
description: 统一的商业方案检索与写作素材系统。用于导入原始来源、沉淀结构化商业案例、提取故事/金句/观点/方法等原子素材，并通过向量检索+rereanker统一搜索。适用于：搜索商业落地方案、搜索可执行打法、搜索写作素材、追溯原文出处、把精华帖拆成案例并派生素材、把公众号观点文或情感文沉淀成素材。
version: "0.1.0"
status: active
---

# Strategy Material Engine

这是统一后的唯一 skill。以后默认只用它，不再分别调用旧的拆案库或旧的素材库。

## 核心能力

- **方案模式**：搜索商业案例、项目打法、行动卡、方法路径
- **素材模式**：搜索故事、金句、洞察、联想发散、可写进文章的原子素材
- **证据模式**：追溯原始来源、原文片段、出处证据
- **入库模式**：导入来源、注册案例、从案例派生素材、构建统一索引

## 资产分层

- `sources/`：原始来源层，保留原文和证据
- `assets/cases/`：结构化商业案例层，服务方案检索与阶段推演
- `assets/materials/`：原子素材层，服务写作与表达复用

不要把所有内容都强行做成 case；也不要把完整 case 直接当作写作素材。

## 什么时候存成什么

- **精华帖 / 实操复盘 / 项目拆解** → `sources/` + `assets/cases/`，必要时再派生 `assets/materials/`
- **公众号观点文 / 情感文 / 感悟文** → `sources/` + `assets/materials/`，默认不建 case
- **想保留出处但暂时不加工** → 只进 `sources/`

## 推荐命令

注意：统一使用 conda base Python：

注意：Hermes 执行脚本时 cwd 在 `scripts/` 目录下，所以 `--root` 必须传 `..`（项目根目录），不能用 `.`（会解析为 scripts 目录本身）。

```bash
/opt/miniconda3/bin/python3 scripts/build_all_indexes.py --root ..
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "低成本获客" --mode strategy --root ..
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "成长焦虑金句" --mode writing --root ..
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "这句话原文出处" --mode source --root ..
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "它更适合做私域吗" --mode hybrid --history "上一个案例是图书垂直小店，通过抖音内容带货再承接到知识付费" --query-planner-provider auto --show-query-plan --verbose
/opt/miniconda3/bin/python3 scripts/evaluate_query_planner.py --root .. --provider auto
```

索引构建默认走稳定配置，而不是追求峰值吞吐：

- **入库后增量刷新（推荐）**：`cd scripts && /opt/miniconda3/bin/python3 flush_indexes.py --root ..`
- 全量重建：`cd scripts && /opt/miniconda3/bin/python3 build_all_indexes.py --root ..`
- 默认参数已经固定为 `--device cpu --batch-size 2`
- 如需单独跑某个索引脚本，也沿用同一组参数
- 构建链路已做 faiss + torch 进程隔离，不会再随机 segfault（详见 workflows.md）

### 入库相关

- 导入来源：`scripts/import_source_and_route.py`
- 从来源提取素材：`scripts/extract_material.py`
- 从来源提取案例草稿：`scripts/extract_case.py`
- 注册结构化案例：`scripts/register_case.py`
- 从案例派生素材：`scripts/derive_materials_from_case.py`

### 索引相关

- 构建来源索引：`scripts/build_sources_index.py --device cpu --batch-size 2`
- 构建素材索引：`scripts/build_materials_index.py --device cpu --batch-size 2`
- 构建案例元数据索引：`scripts/build_case_index.py`
- 构建案例向量索引：`scripts/build_cases_vector_index.py --device cpu --batch-size 2`
- 构建统一检索视图：`scripts/build_unified_index.py`
- 一键构建全部：`scripts/build_all_indexes.py`
## 手动入库流程

当 `import_source_and_route.py` 不适用时（如 Hermes 直接写文件），手动入库步骤：

1. 写 source 到 `sources/` 子目录
2. 按内容类型写 case draft（`assets/case_drafts/`）或 materials（`assets/materials/{insight,method,data,story,playbook,quote,association}/`）
3. 标记脏桶 + flush：`cd scripts && python3 -c "from _index_state import mark_dirty; from pathlib import Path; mark_dirty(Path('..').resolve(), 'sources', 'materials', reason='...')"` 然后 `python3 flush_indexes.py --root .. --all`
4. 搜索验证：`python3 search_knowledge.py "关键词" --mode writing --root ..`
- 单篇入库后增量更新（推荐）：`scripts/incremental_sources_index.py --root .`

## 搜索路径

- 写商业方案时：优先查 `cases`，再补 `playbook/method/source`
- 写文章时：优先查 `materials`，再用 `cases/source` 兜底
- 追证据时：优先查 `sources`

## 统一搜索模式

`scripts/search_knowledge.py` 提供 4 种模式：

- `strategy`：偏商业方案
- `writing`：偏写作素材
- `source`：偏原始来源
- `hybrid`：平衡返回

## Query Planner

统一搜索现在带有查询规划层：

- `rule`：只走规则改写
- `llm`：强制尝试 LLM 改写，失败时自动回退规则
- `auto`：默认模式，复杂 query 优先尝试 LLM，简单 query 直接走规则

常用参数：

- `--history`：传多轮对话历史
- `--context-info`：补额外上下文
- `--show-query-plan`：直接打印 query plan
- `--query-planner-provider auto|rule|llm`：切换规划后端

常用环境变量：

- `GLM_API_KEY`：GLM Query Planner 和 embedding 模型默认读取这个
- `GLM_BASE_URL`：默认 `https://open.bigmodel.cn/api/paas/v4`
- `GLM_TEXT_MODEL`：默认 `glm-4.7`
- `KNOWLEDGE_EMBEDDING_MODEL`：默认 `embedding-3`（智谱 GLM 系列）
- `ARK_API_KEY`：如果没配 GLM，会自动回到 ARK
- `KNOWLEDGE_QUERY_PLANNER_LLM_BACKEND=auto|glm|ark`：手动指定 Planner 的 LLM 后端

运行时产物：

- Query Planner 日志：`evals/query_planner/planner_events.jsonl`
- Query Planner 缓存：`evals/query_planner/planner_cache.json`

## 路径约定

- 案例正式存放在 `assets/cases/`
- 案例草稿存放在 `assets/case_drafts/`
- 写作素材存放在 `assets/materials/`
- 不再保留 `cases/`、`case_drafts/`、`materials/` 顶层兼容入口

## 搜索质量：已知问题与改进计划

### 同一 source 被重复召回（2026.4.25 诊断）

**现象**：多路观点搜索（如文章多小标题分别搜素材）时，同一篇原始来源的多个 chunk 或多个素材反复命中，挤占其他来源的坑位。

**根因诊断**（三层）：
1. **单次搜索内**：chunk 级去重已做（key=path），同一 chunk 不会重复——没问题
2. **多路合并（merge_search_results）**：coverage_bonus 按 chunk 级计算，同一 source 被多个 rewrite query 命中时 coverage 高 → score 更高 → 反而更挤占其他 source。这是主病灶
3. **跨多次调用**：Hermes 侧分多路独立调用 search_knowledge.py，没有全局去重。这是调用层问题

**改进方案**（优先级从高到低）：

方案A：merge_search_results 加 source-level MMR
- 在 merged_results[:limit] 截断前，按 resolve_source_key 聚合，同一原始来源最多占 max_per_source 个坑位（建议默认 2，写作场景可开 1）
- resolve_source_key：material/case 取 source_refs[0]，source chunk 取父路径，entity 不限
- 约 30 行代码，加在 1642 行之前

方案B：coverage_bonus 改为 source-level
- 当前 _coverage 是 chunk 级 query 命中数，改为按 source 聚合后再算
- 与方案 A 一起做，顺手的事

方案C：Hermes 调用层全局去重
- 在 article pipeline / framework_flow.py 里，汇总所有小标题的素材后做 source_refs 级去重
- 解决跨多次调用的问题

**执行建议**：先做 A+B（改 search_knowledge.py），再做 C（改 pipeline）

### faiss + torch 2.9.1 segfault（2026.4.26 诊断与修复）

**现象**：`build_sources_index.py` 等索引构建脚本随机 segfault（exit code 139）。

**根因**：faiss 1.13.2 和 torch 2.9.1 同时加载到同一 Python 进程会导致内存冲突。

**已实施解决方案（构建链路）**：
- `_material_lib.py`：懒加载，`_import_torch()` 和 `_import_faiss()` 藏在函数里，模块 import 时不会同时拉起
- `_faiss_write_index.py`：独立子进程，只负责从 .npy 建 faiss 索引（~26行）
- `_incremental_index.py`：主进程用 torch 编码 → 子进程写 faiss 索引，彻底隔离
- `flush_indexes.py`：增量刷新入口，依赖拓扑排序 + dirty tracking

**已知陷阱**：
- `rerank()` 函数在懒加载改造后漏了 `torch = _import_torch()`（已修复）。如果 `rerank` 报 `NameError: name 'torch' is not defined`，检查 `_material_lib.py` 里 rerank 函数开头是否有这行
- `_faiss_write_index.py` 里的 `from _material_lib import ...` 依赖 cwd 在 scripts 目录。如果子进程 cwd 不对会 ImportError，需加 `sys.path.insert(0, str(Path(__file__).resolve().parent))`

**查询链路（待观察）**：`search_knowledge.py` 运行时仍会在同一进程里同时用 torch（embedding）和 faiss（检索），查询时 faiss 只读风险较低但未完全隔离。如确认 segfault，下一步改为"两段式/三段式子进程查询"。

**已有增量脚本**：`scripts/flush_indexes.py --root .. --all`（推荐），不再需要 `incremental_sources_index.py`。

## 参考文档

- `references/layout.md`
- `references/schemas.md`
- `references/workflows.md`
- `references/buildmate/`（原 buildmate 参考）
- `references/materials/`（旧素材库参考）
