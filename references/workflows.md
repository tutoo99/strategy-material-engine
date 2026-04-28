# 工作流

## 1. 导入精华帖 / 实操帖

1. 先用 `scripts/import_source_and_route.py` 导入到 `sources/buildmate/`
2. 用 `scripts/extract_case.py` 生成案例草稿
3. 案例草稿默认写入 `assets/case_drafts/`
4. 人工修订后用 `scripts/register_case.py` 入 `assets/cases/`
5. 如需写作复用，再用 `scripts/derive_materials_from_case.py` 派生素材
6. 运行 `/opt/miniconda3/bin/python3 scripts/build_all_indexes.py --root .`

## 2. 导入公众号观点文 / 情感文 / 实操复盘

1. 先用 `scripts/import_source_and_route.py` 导入到 `sources/materials/`
2. 如需案例草稿，用 `scripts/extract_case.py` 生成到 `assets/case_drafts/`
3. 提取原子素材（二选一）：
   - **自动提取**（需先建索引）：`scripts/extract_material.py <chunk_id> --root .`
     - 注意：参数是 chunk_id 不是文件路径，chunk_id 来自索引
     - 索引构建慢（~180s），不适合单次快速操作
   - **手动创建**（推荐）：用 `scripts/new_material.py <标题> --type method|insight|story|data --root .`
     - 默认写入 `assets/materials/<type>/`
     - 默认只创建文件，不自动重建索引
     - 如需让新素材立刻可搜索，追加 `--rebuild`
     - 创建后用 write_file 填充内容（frontmatter + 正文）
4. 最后统一重建索引：`/opt/miniconda3/bin/python3 scripts/build_all_indexes.py --root .`
5. 默认不建 case，除非它真的具备完整商业执行链

### Shell 传路径的坑

中文文件名含引号（`""`）时，shell 会吃掉引号导致找不到文件。解决方案：

```bash
# 用 glob 模式避免引号问题
FILE=$(ls ~/Documents/大龄程序员*偷时间*/*.md)
/opt/miniconda3/bin/python3 scripts/import_source_and_route.py "$FILE" --root .

# 后续操作也用 $FILE 变量传递
```

### 批量入库流程（推荐）

当一篇长文需要提取多条素材时：

1. `import_source_and_route.py` 导入原文
2. 通读全文，列出要提取的素材清单（标题+类型）
3. 逐个调用 `new_material.py` 创建素材文件（默认不重建索引）
4. 用 `write_file` 批量填充所有素材内容（execute_code 更高效）
5. 最后 `/opt/miniconda3/bin/python3 scripts/build_all_indexes.py --root .` 统一重建一次完整索引

## 3. 搜商业方案

```bash
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "小红书低成本获客" --mode strategy --root .
```

结果会优先返回：case / playbook / method

## 4. 搜写作素材

```bash
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "关于成长焦虑的故事和金句" --mode writing --root .
```

结果会优先返回：quote / story / insight / association

## 5. 追出处

```bash
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "这句话原文怎么说" --mode source --root .
```

结果会优先返回来源 chunk。

## 6. 带上下文搜

```bash
/opt/miniconda3/bin/python3 scripts/search_knowledge.py "它更适合做私域吗" \
  --mode hybrid \
  --history "上一个案例是图书垂直小店，通过抖音内容带货再承接到知识付费" \
  --query-planner-provider auto \
  --show-query-plan \
  --verbose
```

适用于模糊指代、承接上下文、多意图等用户自然语言 query。

## 7. 增量索引（推荐用于入库后刷新）

全量构建（`build_all_indexes.py`）耗时较长。入库后推荐走增量刷新：

```bash
# 刷新所有脏桶
/opt/miniconda3/bin/python3 scripts/flush_indexes.py --root .

# 只刷某个桶
/opt/miniconda3/bin/python3 scripts/flush_indexes.py --root . --bucket sources
```

原理：flush_indexes 按 manifest/cache 增量机制，只对新增/变更的资源做编码。

### `--root` 参数的 cwd 陷阱

所有脚本的 `--root` 参数是相对于**当前工作目录**解析的。Hermes terminal 默认 cwd 在 `scripts/` 目录下，所以：

```bash
# cwd 在 scripts/ 时（Hermes 默认）
flush_indexes.py --root ..

# cwd 在项目根目录时（手动操作）
scripts/flush_indexes.py --root .
```

**如果看到索引输出全是 0（如 `0 chunks, changed_docs=0`），大概率是 --root 指错了目录。** 先 `ls <root>/sources/` 确认路径是否正确。

### 构建链路隔离（faiss + torch 兼容性）

faiss 和 torch 2.9.1 同进程加载会导致随机 segfault，已通过两层隔离解决：

1. **懒加载**：`scripts/_material_lib.py` 不再模块导入时同时拉 torch 和 faiss
2. **进程隔离**：`scripts/_incremental_index.py` 在主进程做增量编码，将向量交给子进程 `scripts/_faiss_write_index.py` 单独写 faiss 索引

**注意**：搜索脚本（`search_knowledge.py`）仍在查询进程内同时用向量编码和 faiss 读索引。如观察到查询链路也有 segfault，需单独拆查询层。

**懒加载改动的已知副作用**：`_material_lib.py` 的 `rerank()` 函数在懒加载改造后，必须在 `torch.no_grad()` 之前先调用 `torch = _import_torch()`，否则会 NameError。如果新增了使用 torch/faiss 的函数，务必在函数体内做懒加载导入，不要放在模块顶层。

## 8. 测 Query Planner

```bash
/opt/miniconda3/bin/python3 scripts/evaluate_query_planner.py --root . --provider auto
```

会生成专项测试报告，并检查：

- query 类型识别
- search mode 路由
- LLM / 规则回退
- 低相关 query 空结果门控
