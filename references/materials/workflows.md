# Workflows

## Ingestion workflow

Use this flow when turning raw input into searchable sources and reusable materials:

1. Decide whether the input is raw source material or an already-formed reusable unit
2. Save raw source material into `sources/`
3. Run `/opt/miniconda3/bin/python3 scripts/build_sources_index.py --root . --device cpu --batch-size 2`
4. Search source chunks with `scripts/search_sources.py`
5. Promote the best chunk into a draft material with `scripts/extract_material.py`
6. Rewrite and finish the draft under `assets/materials/<type>/`
7. Run `/opt/miniconda3/bin/python3 scripts/build_materials_index.py --root . --device cpu --batch-size 2`

## 素材提取标准

### 入库原则：宽进严出

提取时不要纠结"这条素材好不好"，只问一个问题：**它有没有可能在未来某个场景的某篇文章里被直接用到？** 有，就入库。砍掉的只应该是明确无用的噪音（过时信息、错误事实、与所有内容方向都不相关的）。

### 提取时必做四件事

1. **改写，不搬运** — 用自己的话重新表述，不要复制粘贴原文
2. **脱敏隐私信息** — 入库时必须去掉或替换以下内容：
   - 具体人名 → 换成角色描述（"一位做知识付费的创业者"）
   - 具体公司/组织名 → 换成泛化描述（"一个社群产品""某大厂"）
   - 人名+公司/金额/职位的组合 → 去掉身份关联，保留数字和场景
   - 论证链、比喻、金句、方法论步骤 → **保留**，这些是素材核心价值
   - 脱敏只处理隐私，不处理内容质量
3. **标 ammo_type** — 凭直觉选 hook / substance / dual，不纠结：
   - 读完想转发 → hook
   - 读完学到东西 → substance
   - 两者都有 → dual
4. **标 channel_fit** — 想想这条素材最适合你的哪个号/赛道，标到最细粒度

### 提取时不要做的事

- 不要评估传播力或信任度（这是市场反馈，不是你能预判的）
- 不要用变现能力做筛选标准（素材的直接服务对象是文章，不是变现）
- 不要重复提取同一观点的不同表述
- 不要把原始来源直接当作成品素材存入
- 不要在素材正文里保留具体人名、公司名、或其他可直接识别来源身份的信息

## Writing workflow

Use this flow when drafting an article or other content asset:

1. Break the piece into section intents or claims
2. Search `assets/materials/` for each claim
3. Prefer precise materials with clear claim match and role fit
4. If recall is weak, search `sources/` as fallback
5. Turn useful fallback chunks into new materials after writing

## Feedback workflow（发布后回写）

文章发布后，回填素材的使用效果：

1. 在素材的 `used_in_articles` 里加上文章标识
2. 在 `impact_log` 里加一条记录：
   - `impact: traffic` — 贡献了流量（被评论、被转发、被引用）
   - `impact: trust` — 贡献了信任（读者说学到东西、专业认可）
   - `impact: both` — 两者兼具
   - `impact: none` — 没有明显效果
3. `quality_score` 根据积累的 impact_log 自然调整：
   - 出现多次 traffic 或 both → 上调
   - 出现多次 none → 下调
4. 这个反馈回路跑起来后，素材库会自然形成"哪些弹药好用、哪些粮仓硬"的数据

## Index build: offline mode required in sandboxed envs

The embedding model (BAAI/bge-large-zh-v1.5) IS cached locally in the sandbox, but `transformers` still tries to contact HuggingFace for metadata validation by default — which times out in sandboxed/network-restricted environments.

**Fix already applied:** `scripts/_material_lib.py` sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` at import time.

If index builds still fail with network timeouts, manually prefix the command:
```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /opt/miniconda3/bin/python3 scripts/build_materials_index.py --root . --device cpu --batch-size 2
```

**Do NOT remove these env vars.** The model cache exists; the issue is purely an unwanted network probe.

## Quality gate

Keep these rules active:

- Do not accept weak materials that still require inventing missing details
- Do not treat raw source text as finished material
- Do not skip material search during drafting
- Do not add `emotion` retrieval to the core loop until the main retrieval path is stable
