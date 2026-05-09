# 工作流

## 1. 导入精华帖 / 实操帖

1. 先用 `scripts/import_source_and_route.py` 导入到 `sources/buildmate/`
2. 用 `scripts/extract_case.py` 生成案例草稿
3. 案例草稿默认写入 `assets/case_drafts/`
4. 人工修订后用 `scripts/register_case.py` 入 `assets/cases/`
5. 如需写作复用，再用 `scripts/derive_materials_from_case.py` 派生素材
6. 运行 `/opt/miniconda3/bin/python3 scripts/build_all_indexes.py --root .`

## 2. 导入公众号观点文 / 情感文 / 实操复盘 / 课程实录

1. 先用 `scripts/import_source_and_route.py` 导入到 `sources/materials/`
   - 如果是课程/实录/长访谈，优先直接连跑规划：`/opt/miniconda3/bin/python3 scripts/import_source_and_route.py input.md --root . --bucket materials --plan-materials`
2. 如需案例草稿，用 `scripts/extract_case.py` 生成到 `assets/case_drafts/`
3. 提取原子素材（二选一）：
   - **先做拆分规划**（多主题内容推荐）：`/opt/miniconda3/bin/python3 scripts/plan_source_materials.py sources/materials/xxx.md --root .`
     - 作用：自动识别 `single_theme_article / multi_theme_course / multi_theme_longform`
     - 输出：建议素材数量、类型、标题、来源章节、claims 草稿
     - 可加 `--write-plan work/plans/xxx.material-plan.md` 保存计划
     - 可加 `--create-drafts` 直接生成 draft 文件，再进入 validate / repair 流程
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

### 2.1 先判断内容形态，不要一律按“文章”处理

- **单主题文章**：通常围绕 1-2 个主张，适合按文章中心向下拆
- **多主题长文 / 长访谈**：先列主题域，再按域拆原子素材
- **系统课程 / 教学实录 / transcript**：默认视为“单源多主题”，先按模块、章节、能力域拆

如果是系统课程或教学实录，不要因为它“来自一个 source”就默认只提 1 条或少量几条。

### Shell 传路径的坑

中文文件名含引号（`""`）时，shell 会吃掉引号导致找不到文件。解决方案：

```bash
# 用 glob 模式避免引号问题
FILE=$(ls ~/Documents/大龄程序员*偷时间*/*.md)
/opt/miniconda3/bin/python3 scripts/import_source_and_route.py "$FILE" --root .

# 后续操作也用 $FILE 变量传递

# 或者用 find + xargs 绕过引号问题
find /tmp/extracted -name "*.md" | xargs -I{} head -500 "{}"
```

### YAML frontmatter 引号坑

素材 frontmatter 的字符串值（如 `primary_claim`）如果包含特殊字符（em-dash `——`、冒号 `:`、中文引号 `""` 等），用双引号包裹会导致 YAML 解析失败，flush_indexes 报 `ParserError`。

**错误写法**（会崩）：
```yaml
primary_claim: "无法开始，才是最大的问题"——新手做内容最大的障碍
```

**正确写法**：
```yaml
primary_claim: '无法开始，才是最大的问题——新手做内容最大的障碍'
```

规则：frontmatter 字符串值含中文标点时一律用单引号 `'...'`，或干脆不加引号（YAML 无特殊字符时裸字符串即可）。

### 批量入库流程（推荐）

当一篇长文需要提取多条素材时：

1. 优先用 `batch_import_sources.py` 一条命令导入 source、规划 source 原子素材、写 draft，并最后统一刷索引：

   ```bash
   /opt/miniconda3/bin/python3 scripts/batch_import_sources.py "$FILE" \
     --root . \
     --bucket buildmate \
     --source-type post \
     --author "作者名" \
     --origin "生财有术" \
     --tags "作者名,主题词1,主题词2" \
     --use-existing-source \
     --plan-source-materials \
     --plan-source-materials-llm \
     --create-source-material-drafts \
     --flush
   ```

2. 如果只想预检，不落素材文件，把 `--create-source-material-drafts` 换成 `--dry-run-source-material-drafts`。
3. 如果同一篇还需要商业案例，再追加 `--extract-case --llm --register-case --skip-case-preflight --derive-materials`；注意当前外部 Chat LLM 统一只接 DeepSeek，`--plan-source-materials-llm` 用于 source 拆素材，`--llm` 用于 case 提取，二者默认开启 `thinking=enabled, reasoning_effort=high`；`--derive-materials` 仍是从 registered case 机械派生素材。
4. 对多主题内容，按“每个主题域 1-3 条专精素材”估算工作量，不要预设 `6-10` 条上限。
5. 写完后跑 `/opt/miniconda3/bin/python3 scripts/validate_materials.py --root . <新素材路径...>`，检查元数据、`source_refs` 和类型纯度。
6. 如果问题是缺默认字段、裸文件名 `source_refs` 之类的机械问题，先跑 `/opt/miniconda3/bin/python3 scripts/repair_materials.py --root . <新素材路径...> --write`。
7. 修完后再跑一次 validator 确认清零。

### 反过度合并规则

- “不要贪多”是为了防止从短文里硬凑重复碎片，不是让你把多个主题压成一条大全素材
- 只要两个模块在未来检索或写作时可能被单独调用，就应该拆成两条
- 镜头语言、场面调度、声音设计、行业判断、学习方法这类模块默认分开提
- 只有 source 的核心价值本身就是“总框架”时，才额外保留一条总纲素材

### 新增质量闸门

写完素材后，至少做一次：

```bash
/opt/miniconda3/bin/python3 scripts/validate_materials.py --root . assets/materials/method/xxx.md
```

这个 validator 重点抓三类问题：
- frontmatter 缺字段或占位值没清掉
- `source_refs` 不是可解析的相对路径
- `data` 素材混入大段趋势/建议/方法，重新变成“大全条目”

对应的自动修工具：

```bash
/opt/miniconda3/bin/python3 scripts/repair_materials.py --root . assets/materials/method/xxx.md --write
```

这个 repair 脚本只做安全修复：
- 补默认字段（`ammo_type / role / strength / channel_fit / quality_score / review_status` 等）
- 把唯一可定位的裸文件名 `source_refs` 改成相对路径
- 在 `source` 为空时，尝试从 source 文件标题或首行回填

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
