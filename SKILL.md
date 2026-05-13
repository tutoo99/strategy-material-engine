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
- **系统课程 / 教学实录 / 长访谈 / 多模块 transcript** → 先进 `sources/`，再按主题域拆成 `assets/materials/`；只有当它同时围绕一条完整商业执行链时才额外建 case
- **想保留出处但暂时不加工** → 只进 `sources/`

## 入库路径选择

当用户对本地文档下发“入库”命令时，默认优先走自动路径：

1. 先用 `scripts/import_source_and_route.py` 或 `scripts/batch_import_sources.py`
2. source / material 拆分默认先尝试 DeepSeek
3. 只有在以下情况才退回手动流程：
   - 自动规划脚本失败
   - 用户显式要求规则模式
   - 需要人工先查重、改 source 结构或补字段

**禁止把“手动入库流程”当成默认入口。**
手动流程只用于自动路径失败后的兜底，不是第一选择。

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
/opt/miniconda3/bin/python3 scripts/validate_materials.py --root .. assets/materials/method/xxx.md
/opt/miniconda3/bin/python3 scripts/repair_materials.py --root .. assets/materials/method/xxx.md --write
/opt/miniconda3/bin/python3 scripts/plan_source_materials.py sources/materials/xxx.md --root ..
```

索引构建默认走稳定配置，而不是追求峰值吞吐：

- **入库后增量刷新（推荐）**：`cd scripts && /opt/miniconda3/bin/python3 flush_indexes.py --root ..`
- 全量重建：`cd scripts && /opt/miniconda3/bin/python3 build_all_indexes.py --root ..`
- 默认参数已经固定为 `--device cpu --batch-size 2`
- 如需单独跑某个索引脚本，也沿用同一组参数
- 构建链路已做 faiss + torch 进程隔离，不会再随机 segfault（详见 workflows.md）

### 入库相关

- 导入来源：`scripts/import_source_and_route.py`
- 批量导入来源并最后统一刷索引：`scripts/batch_import_sources.py`
- 从 source 自动规划素材拆分：`scripts/plan_source_materials.py`
- 从来源提取素材：`scripts/extract_material.py`
- 从来源提取案例草稿：`scripts/extract_case.py`
- 注册结构化案例：`scripts/register_case.py`
- 从案例派生素材：`scripts/derive_materials_from_case.py`

批量导入时优先用：

```bash
/opt/miniconda3/bin/python3 scripts/batch_import_sources.py input1.md input2.md --root . --bucket auto --flush
```

精华帖 / 长文需要优先沉淀原子素材时：

```bash
/opt/miniconda3/bin/python3 scripts/batch_import_sources.py input1.md input2.md --root . --bucket buildmate --use-existing-source --plan-source-materials --plan-source-materials-llm --create-source-material-drafts --flush
```

精华帖还需要补充 case 链路时：

```bash
/opt/miniconda3/bin/python3 scripts/batch_import_sources.py input1.md input2.md --root . --bucket buildmate --extract-case --llm --register-case --derive-materials --skip-case-preflight --flush
```

注意：现在 source 材料拆分和 case 提取都默认先尝试 DeepSeek。`--plan-source-materials-llm` 和 `--llm` 主要用于显式声明意图；如果要强制规则模式，分别用 `--no-plan-source-materials-llm` 和 `--no-llm`。

**注意：DeepSeek API Key 必须在 shell 环境中可用。** `DEEPSEEK_API_KEY` 存在 `~/.hermes/.env` 里，但不会自动加载到 shell。如果 key 缺失，脚本会**静默回退到规则模式**，产出的素材标题是原文截断、claims 是照搬段落，质量极差。**每次运行需要 DeepSeek 的脚本前，必须先 `source ~/.hermes/.env`**。回退后需手动清理垃圾素材再重跑。

注意：批量脚本会逐篇安全落库，但只在最后执行一次 `flush_indexes.py`。不要为同一批文章给每篇单独跑索引刷新。

注意：`--flush` 只刷新脚本本次写入时标记过的 dirty buckets。如果 batch 后又手动 patch 了 `sources/`、`assets/cases/` 或 `assets/materials/` 文件，需要先手动标记脏桶再 flush，或直接用 `flush_indexes.py --bucket sources` / `--bucket cases` / `--bucket materials` 指定桶刷新。

注意：当前外部 Chat LLM 统一只接 DeepSeek。`--llm` 用于 case 草稿提取；`--plan-source-materials-llm` 用于 source 到原子素材的语义拆分规划。DeepSeek 只生成结构化 JSON 计划，写文件、查重、校验、索引仍由脚本完成。`--derive-materials` 仍是从已注册 case 里机械派生素材，不是 LLM 从原文拆素材。

注意：素材自动提取链路现在有质量门禁。结构性问题先自动修一次，内容门禁不过就直接拒收；通过门禁的自动素材会标成 `reviewed`，`rejected` 不进入正式检索。

DeepSeek 思考模式按任务分层：source 拆素材和 case 抽取默认 `thinking=enabled, reasoning_effort=high`；搜索 Query Planner 默认 `thinking=disabled`，避免日常检索被深度思考拖慢。只有未来做多步 Agent 化自修复时，才考虑把对应链路单独调到 `max`。

多主题课程 / 长访谈入库时，推荐直接连跑规划：

```bash
/opt/miniconda3/bin/python3 scripts/import_source_and_route.py input.md --root . --bucket materials --plan-materials
```

如果只想看拆分计划、不立刻写 draft，也可以单独执行：

```bash
/opt/miniconda3/bin/python3 scripts/plan_source_materials.py sources/materials/xxx.md --root . --llm --write-plan work/plans/xxx.material-plan.md
```

### 索引相关

- 构建来源索引：`scripts/build_sources_index.py --device cpu --batch-size 2`
- 构建素材索引：`scripts/build_materials_index.py --device cpu --batch-size 2`
- 构建案例元数据索引：`scripts/build_case_index.py`
- 构建案例向量索引：`scripts/build_cases_vector_index.py --device cpu --batch-size 2`
- 构建统一检索视图：`scripts/build_unified_index.py`
- 一键构建全部：`scripts/build_all_indexes.py`
## 输入文件格式预处理

入库前经常需要从各种格式提取纯文本。以下是常用方法：

### HTML → 纯文本
```bash
python3 -c "
from html.parser import HTMLParser
class T(HTMLParser):
    def __init__(s):
        super().__init__()
        s.text = []
    def handle_data(s, d):
        s.text.append(d)
t = T()
with open('input.html', 'r') as f:
    t.feed(f.read())
print(''.join(t.text))
"
```

### PDF → 纯文本
优先用 skill `pdf-extraction` 或 `pdf-extraction-mineru`（带OCR）。简单场景：
```bash
pdftotext input.pdf - 2>/dev/null | head -500
```

### Excel/CSV → 纯文本
```bash
python3 -c "
import openpyxl
wb = openpyxl.load_workbook('input.xlsx', read_only=True)
for ws in wb:
    for row in ws.iter_rows(values_only=True):
        print('\t'.join(str(c) if c else '' for c in row))
"
```

### 注意事项
- 提取前先用 `wc -c` 检查文件大小，大于100KB注意截断
- HTML 用 `HTMLParser` 而不是正则，避免漏标签或误匹配
- PDF 如果 `pdftotext` 输出乱码，说明是扫描件，走 MinerU 或视觉模型 OCR
- 提取后的文本用于 source 原文归档和 LLM 分析，不要手动编辑内容

## 手动入库流程（Hermes 直接操作时）

这个流程是兜底流程。只有自动导入 / 自动规划失败，或用户明确要求不用 DeepSeek 时才走这里。

当 `import_source_and_route.py` 不适用时（如 Hermes 直接写文件），完整步骤：

### Step 0：格式预处理
如果输入是 HTML/PDF/Excel，先用「输入文件格式预处理」章节的方法提取纯文本。

### Step 1：查重
```bash
find ~/.hermes/skills/strategy-material-engine -path "*/sources/*" -name "*关键词*" 2>/dev/null
find ~/.hermes/skills/strategy-material-engine -path "*/materials/*" -name "*关键词*" 2>/dev/null
```
如果 source 和对应 materials 都已存在，跳过入库。部分存在时只补缺的。

### Step 2：写 source / Step 3：写素材时的 YAML frontmatter 避坑

写 frontmatter 时最常踩的坑是**中文标点导致 YAML 解析失败**（`ParserError`）。

**好消息**：`_material_lib.py` 里的 `_sanitize_yaml_frontmatter()` 已自动处理三种高频问题：
1. 中文引号「""」「''」→ 直角引号「「」」「『』」
2. 全角括号「（）」→ 半角「()」
3. 双引号字符串后紧跟裸文本：`- "xxx"注释` → `- "xxx注释"`

所以大部分中文内容可以直接写，不用手动转义。

**仍需手动避免的情况**：
- 嵌套双引号：`primary_claim: "现金红包"比"返现"更有诱惑力` ← YAML 不支持
- 嵌套单引号：`primary_claim: '现金红包'比'返现'更有诱惑力`
- 裸中文破折号——（YAML 不认）
- 冒号后没空格：`key:value` ← 必须写 `key: value`
- 双引号闭合后紧跟非空格字符：`key: "xxx"——yyy` ← YAML 会把——解析为新标量开头

**推荐写法**（安全优先）：
- 纯中文不加引号：`primary_claim: 现金红包比返现更有诱惑力，用户觉得踏实`
- 强调用书名号或方括号：`primary_claim: 现金红包比返现更有诱惑力`
- 整行双引号包裹（内部无双引号）：`primary_claim: "现金红包比返现更有诱惑力"`
- 整行单引号包裹（内部无单引号，可含——）：`primary_claim: '无法开始，才是最大的问题——新手内容创业最大障碍'`

**路径解析和中文文件名注意事项**：
`plan_source_materials.py` 的 source 路径现在会先按当前 cwd 解析，再按 `--root` 解析；但在 Hermes、shell、脚本 cwd 不确定，或文件名含中文/空格/特殊符号时，仍优先传绝对路径，`--root` 也传项目根绝对路径。

如果 zsh 传中文路径给 Python 脚本时字符被截断或丢失，导致 `Source file not found`，用 Python `sys.argv` 直接注入参数，绕过 shell 层：
```bash
cd scripts && /opt/miniconda3/bin/python3 -c "
import sys
sys.argv = ['plan_source_materials.py', '/absolute/path/to/中文文件名.md', '--root', '/absolute/path/to/strategy-material-engine', '--llm']
from plan_source_materials import main
main()
" 2>&1
```

**如果 flush 还是报 ParserError**，在 source 写完后、flush 前跑验证定位问题文件：
```bash
cd ~/.hermes/skills/strategy-material-engine && python3 -c "
import yaml, glob
files = glob.glob('assets/materials/**/*.md', recursive=True) + glob.glob('assets/case_drafts/**/*.md', recursive=True)
for f in sorted(files):
    try:
        with open(f) as fh:
            c = fh.read()
        if c.startswith('---'):
            yaml.safe_load(c.split('---',2)[1])
    except Exception as e:
        print(f'ERROR: {f}: {e}')
" && echo 'All OK'
```

### Step 2：写 source
写完整原文到 `sources/buildmate/` 或 `sources/materials/`，frontmatter 按 schema 填写（title/author/origin/date/tags/link/summary）。保留原文不做删改。

### Step 3：提取素材
先判断**内容形态**，再决定提取什么：

- **单主题文章**：通常围绕 1-2 个核心观点展开，按文章主论点往下拆
- **多主题长文 / 长访谈**：先列主题域，再按域拆
- **系统课程 / 教学实录 / transcript**：默认视为“刻意设计的知识体系”，先按模块/章节/能力域拆，不要把整课压成一条

如果是多主题 source，先跑一遍规划器，再决定最终入库标题：

```bash
cd scripts && python3 plan_source_materials.py ../sources/materials/xxx.md --root .. --write-plan ../work/plans/xxx.material-plan.md
```

规划器会先做三件事：
- 判断 source 形态是 `single_theme_article` 还是 `multi_theme_course / multi_theme_longform`
- 按 `## / ###` 章节生成主题域拆分草案
- 给出建议素材类型、标题和 claims 草稿，减少手工“先列主题域”的负担

再按内容类型决定提取什么：

**观点文/方法论文**（如 V先生轻创业锦囊）：不建 case，直接提取 materials。常见类型分布：
- `method`：框架、流程、SOP、清单（最常见，干货密度高的文章通常 1-3 条）
- `insight`：反常识洞察、认知翻转、本质归纳
- `quote`：金句（有传播力的一句话）
- `data`：具体数字、对比数据、产出规划
- `playbook`：可执行打法（比 method 更具体，带条件判断）

**精华帖/实操复盘**：source + case draft + 必要时派生 materials。

**命名规范**：用中文概括核心主张，如 `垂直领域四种写作模板-维基百科法知乎法豆瓣法芒格法.md`。避免和已有文件重名。

**提取密度参考**：
- 单主题 3000-5000 字干货文通常提取 `4-8` 条
- 单主题 15000 字以上长文通常提取 `6-12` 条
- **系统课程 / 教学实录 / 多主题 transcript 不按字数硬限条数**，而是按“独立主题域数 × 每域可复用单元数”决定
- 一个独立主题域，通常至少应拆出 `1-3` 条专精素材；如果原文覆盖 6 个主题域，最终常见会落在 `6-18` 条，必要时更多

**单源多主题拆分规则**：
1. 先给 source 列一个 `3-10` 项的主题域清单，再开始写素材
2. 每个独立主题域至少检查一次：是否应该单独成条，而不是并入“大全”
3. 同一主题域里如果同时存在 `method / insight / data / quote` 等不同复用单元，应优先拆成多条，不要强行糊成一条
4. 只有当几个部分共享同一个不可分的核心主张时，才允许合并
5. **禁止把镜头语言、场面调度、声音设计、行业判断、学习方法这类可独立复用的模块合成一条总括素材**

**“不要贪多”的正确含义**：
- 它只用于防止从短文里硬凑重复碎片
- 它**不**意味着把多个独立主题硬并成一条“更完整”的大全素材
- 对系统课程，宁可拆成多条专精素材，也不要提成一条包罗万象但检索价值很低的总结

### Step 4：标记脏桶 + 刷新索引
如果素材/source/case 是脚本自动写入的，脚本通常会自动 `mark_dirty`；如果是手动 patch 文件，Hermes 不会触发 dirty tracking。手动改完后有两种刷新方式：

1. 直接指定桶刷新：`cd scripts && python3 flush_indexes.py --root .. --bucket materials`
2. 先 `mark_dirty`，再无参 flush：

```bash
cd scripts && python3 validate_materials.py --root .. ../assets/materials/method/xxx.md
cd scripts && python3 repair_materials.py --root .. ../assets/materials/method/xxx.md --write
cd scripts && python3 validate_materials.py --root .. ../assets/materials/method/xxx.md
cd scripts && python3 -c "
from _index_state import mark_dirty; from pathlib import Path
root = Path('..').resolve()
mark_dirty(root, 'sources', reason='...')
mark_dirty(root, 'materials', reason='...')
" && python3 flush_indexes.py --root .. --all
```

只改 `assets/materials` 时优先刷 `--bucket materials`；只改 `sources` 时刷 `--bucket sources`；只改 `assets/cases` 时刷 `--bucket cases`。`flush_indexes.py --root ..` 无参数时只看 dirty state，手动 patch 后没标脏会输出 `No dirty index buckets to flush.`。

### 注意：entity 卡片会被 flush 重建（反复踩坑确认）

`build_entity_cards.py` 会从 source 内容自动生成/重建 `assets/entities/people/*.md`。**手写或修改过的 entity 全部内容（包括手写的简介、方法论、金句列表）会在 `flush_indexes.py --all` 时被完全覆盖。** 这不是增量更新，是整文件重建。

**正确的操作顺序：**

1. 写 source / case / materials（正常流程）
2. 标记脏桶 + 刷新索引（`flush_indexes.py --all`）
3. **flush 完成后再写/更新 entity 卡片**（不要在 flush 前）

如果你在 flush 前写了 entity，flush 会覆盖它，你需要重写一遍。不要犯这个错误——已经反复踩了3轮。

entity 的 `source_count` 和 `source_refs` 字段会被自动维护，不需要手动更新。但自动生成的内容质量远不如手写（会直接截取 source 原文而非提炼摘要），所以重要人物（如条形马、亦仁等）的 entity 建议始终手动维护，flush 后重写。

### Step 5：搜索验证
```bash
cd scripts && python3 search_knowledge.py "关键词" --mode writing --root .. --disable-query-rewrite
```
确认新素材能被检索命中，score > 0.8 为佳。

## 内容入库实操 Playbook（Hermes 对话内入库）

这个 Playbook 不是默认入口，只是自动路径失败后的手动补救流程。

当用户发文件说"入库"时，按以下流程执行：

### Step 0：读取全文
- **先查 sources/ 是否已有存档**：`find ~/.hermes/skills/strategy-material-engine -path "*/sources/*" -name "*关键词*"`，有就从 sources/ 读原文，不要依赖用户原始路径（用户原始文件可能已删除/移动/重命名）
- 如果 sources/ 没有，再从用户提供的路径读取
- 先 `read_file` 看全文结构和长度
- 如果文件超过 2000 行，分批读取（offset 500/1000/1500...）
- 如果是 HTML/PDF，先预处理提取纯文本（参考「输入文件格式预处理」）
- **先判断内容形态**：这是单主题文章、多主题长文、系统课程、教学实录、还是长访谈；后续提取密度和拆分策略依赖这个判断
- **如果是课程/实录/长访谈**：先列出模块或主题域清单，再进入提取

### Step 1：导入 source
```bash
/opt/miniconda3/bin/python3 /path/to/scripts/import_source_and_route.py \
  "/path/to/input.md" \
  --root /path/to/strategy-material-engine \
  --bucket materials \
  --source-type article \
  --title "文章标题" \
  --author "作者" \
  --origin "来源平台/社群" \
  --date "YYYY-MM-DD" \
  --tags "标签1,标签2,标签3" \
  --link "" \
  --summary "一句话概括文章核心内容和价值" \
  2>&1
```

关键参数：
- `--bucket materials`：观点文/方法论文走 materials，实操复盘走 buildmate
- `--tags`：必须包含作者名、主题关键词、来源平台（生财有术等）
- `--summary`：写清楚文章的实操验证数据（如"2个月257万销售额"）

### Step 2：分析并提取素材

**提取什么**：只提取真正有复用价值的原子单元，不是概括全文。

默认先尝试 DeepSeek 规划；只有显式要求规则模式，才直接按人工规则拆。
如果自动提取后仍有结构问题，先用 `repair_materials.py` 做机械修补，再跑 `validate_materials.py` 复检；内容门禁不过就标记为 `rejected`，不要硬塞进正式素材库。

**先做形态判断**：
- **单主题文章**：围绕主论点拆，避免同义重复
- **多主题长文**：先拆主题域，再在域内拆原子单元
- **系统课程 / 教学实录 / transcript**：按模块、章节、能力域、知识域拆；默认视为“单源多主题”

**提取密度**：
- 3000-5000 字单主题干货文通常 `4-8` 条
- 15000 字以上单主题长文通常 `6-12` 条
- **系统课程 / 教学实录 / 多主题 transcript 没有固定上限**
- 对这类内容，先数清有多少独立主题域；**每个域至少考虑 1 条，常见是 1-3 条**
- 如果原文是超长系统课，最终条数明显高于 `6-10` 是正常的，不要因为“看起来已经很多了”而提前停

**素材类型判断**：
| 类型 | 何时用 | 特征 |
|------|--------|------|
| `method` | 框架/SOP/流程/清单 | 有步骤、有标准、可照做（最常见） |
| `insight` | 反常识洞察/本质归纳 | 颠覆认知的一句话+论证 |
| `playbook` | 可执行打法 | 比 method 更具体，带条件判断 |
| `quote` | 金句 | 有传播力的一句话 |
| `data` | 具体数字/对比数据 | 可引用的硬数据 |
| `story` | 真实案例故事 | 有人物有情节有结果 |

**单源多主题的执行规则**：
1. 先写主题域清单，例如：镜头语言 / 场面调度 / 声音设计 / 行业数据 / 学习路径 / 常见误区
2. 每个主题域单独判断是否能生成 `method`、`insight`、`data` 等不同素材
3. 只要两个模块在未来写作或检索时可能被单独调用，就应该拆成两条
4. **默认反对“总括型大全素材”**；只有 source 本身的价值就在于“跨模块总框架”时，才额外保留一条总纲
5. 如果一条素材标题里开始出现“完整方法论 / 全景 / 一网打尽 / 所有核心都在这里”这类倾向，先反查是否过度合并

**写素材的黄金规则**：
1. `primary_claim`：一句话说清这个素材的核心价值，读完就知道要不要用
2. `claims`：3-7 条关键论点，用列表格式，每条是一个可独立引用的原子观点
3. `tags`：必须包含作者名 + 主题关键词，方便后续按作者或主题搜索
4. 正文部分：提炼核心步骤或核心观点，不要照搬原文大段文字，要用自己的话重新组织
5. 命名：用中文概括核心主张，如 `四路搜索法竞品差评分析.md`

**什么时候停**：
- 不是看到 `6-10` 条就停
- 而是当每个主题域都已经覆盖到可复用的主张，并且再往下拆只会得到同义重复或证据不足的碎片时再停

**YAML frontmatter 避坑**（踩过多次坑，现已自动修复大部分）：
- `_sanitize_yaml_frontmatter()` 会自动处理中文引号、全角括号、双引号后裸文本
- 仍需手动避免：嵌套引号、裸破折号——、冒号后没空格
- 具体见「Step 2：YAML frontmatter 避坑」章节

### Step 3：写素材文件
每条素材写入对应类型目录：
```
assets/materials/method/xxx.md
assets/materials/insight/xxx.md
assets/materials/playbook/xxx.md
...
```

### Step 4：flush 索引
```bash
/opt/miniconda3/bin/python3 scripts/flush_indexes.py \
  --root /path/to/strategy-material-engine \
  --bucket materials 2>&1
```

### Step 5：汇报结果
给用户一个表格，列清楚：
- 素材库总数变化（如 275条 +6）
- 每条素材的类型、标题、核心要点（一句话）

### 连续多帖渐进式入库（同一人物多帖）

当用户连续发同一人物的多个帖子/短帖要求入库时（如刘智行系列帖），会出现数据拼图效应和校正需求。处理要点：

1. **每帖独立提取素材**：不要因为"之前已入库"就跳过。不同帖子往往有新数据点、新方法、新金句。
2. **主动做数据校正**：当新帖数据与已有素材矛盾时，建一条 `data` 类型素材做校正记录，格式用对比表（旧值|校正值）。例：`刘智行广告合作数据校正飞猪42575元10月互选单条10万合作品牌宝马飞猪银行.md`
3. **建数据全景素材**：当积累了3+帖数据后，建一条 `data` 类型素材做全矩阵数据交叉验证，把多源数据按时间线排列。这比散落在多条素材里的数据更有检索价值。
4. **命名时含数据关键词**：如 `刘智行单号9月收入81527元流量主1.5万广告4.2万橱窗9千陪跑1.5万.md`，方便后续按金额/月份/收入类型搜索。
5. **source_refs 统一指向同一 source 文件**：如果多篇帖子来自同一精华帖合集（如"生财5年差生逆袭.md"），都指向同一个 source。

### 常见来源的处理经验

**生财有术精华帖**（如条形马、袁锐钦、银河等）：
- source 放 `sources/materials/`
- 标签必含作者名+生财有术
- 作者如果重要人物，记忆里记录

**公众号文章**：
- 先确认是否已入库（查重）
- 标签含作者名+公众号矩阵相关标签

**HTML 文件**：
- 先用 Python 提取纯文本，注意处理 `<br>` → `\\n`、HTML entities
- 提取模板（execute_code 中用正则）：
  ```python
  import re
  text = re.sub(r'<br\s*/?>', '\n', html)
  text = re.sub(r'<[^>]+>', '', text)
  text = re.sub(r'&nbsp;', ' ', text)
  text = re.sub(r'&lt;', '<', text)
  text = re.sub(r'&gt;', '>', text)
  text = re.sub(r'&amp;', '&', text)
  lines = [l.strip() for l in text.split('\n') if l.strip()]
  clean = '\n\n'.join(lines)
  ```
- 超过 6000 字的 HTML 建议分批读取（clean[:6000] 先看前半段判断结构）

**纯文本粘贴**（用户直接在对话中粘贴文章）：
- 先用 write_file 保存到 /tmp/ 下
- 再用 import_source_and_route.py 导入
- 路径用 /tmp/xxx.md

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

- `DEEPSEEK_API_KEY`：DeepSeek Chat LLM 默认读取这个
- `DEEPSEEK_BASE_URL`：默认 `https://api.deepseek.com`
- `DEEPSEEK_MODEL`：默认 `deepseek-v4-pro`
- `DEEPSEEK_THINKING`：全局覆盖 DeepSeek 思考模式；未设置时由调用场景决定
- `DEEPSEEK_REASONING_EFFORT`：全局覆盖 DeepSeek 思考强度；思考模式下 `low/medium` 会按 DeepSeek 兼容规则映射为 `high`，`xhigh` 映射为 `max`
- `KNOWLEDGE_QUERY_PLANNER_API_KEY`：Query Planner 专用覆盖 key；未设置时读取 `DEEPSEEK_API_KEY`
- `KNOWLEDGE_QUERY_PLANNER_MODEL`：Query Planner 专用覆盖模型；未设置时读取 `DEEPSEEK_MODEL`
- `KNOWLEDGE_QUERY_PLANNER_LLM_BACKEND=auto|deepseek`：手动指定 Planner 的 LLM 后端
- `KNOWLEDGE_QUERY_PLANNER_THINKING`：Query Planner 思考模式，默认 `disabled`
- `KNOWLEDGE_QUERY_PLANNER_REASONING_EFFORT`：Query Planner 思考强度，默认不传；只在显式开启 planner 思考时使用

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
