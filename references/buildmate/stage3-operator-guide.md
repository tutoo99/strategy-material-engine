# 阶段三操作说明：正式策略推演与方案包交付

当前阶段三已经进入正式可用状态，并具备自治补救能力。

当前阶段三的核心目标是：

1. 用标准词和证据边把案例、策略、资源连起来。
2. 用正式路由规则把目标映射成主策略和组合策略。
3. 输出一份可执行的阶段三会话和方案包。
4. 把图谱和推演产品化成“可视化图谱 + 推演问答脚本”。
5. 当标准路由失败时，自动生成自治审计，并判断该修阶段二还是补阶段一。
6. 把阶段二新增能力沉淀为 `strategy_models/node_patches/*.md`，作为正式节点化补丁。

## 第一入口：先看地图说明

在正式跑阶段三之前，先看：

- `strategy_models/graph_center.md`

这个文件不是执行器，而是阶段三第一步的人类入口。它负责把“图是什么”解释清楚：

- 节点是什么
- 边是什么
- 属性是什么
- 当前系统里的节点、边、属性分别落在哪些文件

如果你只想理解地图，不想立刻跑推演，先看这个文件；如果你已经理解地图，再继续看本说明和 `strategy_models/router.md`。

## 生成命令

```bash
python3 scripts/build_stage3_seed_map.py --root '/Users/naipan/.hermes/skills/strategy-material-engine'
```

默认开启标准词过滤，只保留 `references/stage3-tag-vocabulary.md` 里的 `strategy_tags` 和 `resource_refs`。

如需调试脏词来源，可以临时关闭过滤：

```bash
python3 scripts/build_stage3_seed_map.py --root '/Users/naipan/.hermes/skills/strategy-material-engine' --allow-nonstandard
```

## 输出文件

输出目录：`index/stage3/`

- `stage3_seed_report.md`：人读报告，用来检查当前图谱证据层是否健康。
- `strategy_nodes.jsonl`：策略节点，每行一个标准策略。
- `situation_nodes.jsonl`：情境节点卡，每行一个正式情境画像。
- `resource_nodes.jsonl`：资源节点，每行一个标准资源。
- `strategy_resource_edges.jsonl`：策略到资源的证据边。
- `case_strategy_edges.jsonl`：案例到策略的证据边。
- `case_resource_edges.jsonl`：案例到资源的证据边。
- `strategy_strategy_edges.jsonl`：策略之间的共现边，用于发现组合路径。
- `goal_strategy_edges.jsonl`：目标到策略的路由边，记录触发条件与调用产出。
- `situation_strategy_edges.jsonl`：情境到策略的路由边，既记录“特别适用”，也记录“禁区策略”。
- `strategy_situation_edges.jsonl`：策略到情境的显式关系边，便于直接检查“这个策略适合 / 不适合谁”。

产品化交付目录：`strategy_models/productization/`

- `stage3_strategy_map.drawio`：正式可视化图谱，建议用 draw.io 打开。
- `stage3_questionnaire.yaml`：正式推演问答脚本。
- `README.md`：阶段三产品化交付入口。
- `strategy_models/node_patches/`：阶段二 -> 阶段三的节点补丁目录。

## 正式运行命令

```bash
python3 scripts/run_stage3_strategy_session.py \
  --goal '获取初始精准流量' \
  --user-type '个人副业者' \
  --platform 'B站' \
  --domain '内容副业' \
  --constraint '启动资金<2000元' \
  --constraint '日均可用时间<3小时' \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine'
```

校验命令：

```bash
python3 scripts/validate_stage3_session.py strategy_models/sessions/<session-file>.md
python3 scripts/validate_stage3_audit.py strategy_models/audits/<audit-file>.md
python3 scripts/validate_strategy_node_patch.py strategy_models/node_patches/<patch-file>.md
python3 scripts/validate_stage3_productization.py --root '/Users/naipan/.hermes/skills/strategy-material-engine'
```

产品化命令：

```bash
python3 scripts/export_stage3_visual_map.py --root '/Users/naipan/.hermes/skills/strategy-material-engine'

python3 scripts/run_stage3_questionnaire.py \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --print-questionnaire

python3 scripts/run_stage3_questionnaire.py \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --situation-id S001 \
  --goal-id goal_initial_precise_traffic \
  --platform-id PLATFORM_BILIBILI \
  --domain-id DOMAIN_CONTENT_ECOM \
  --constraint-id C001 \
  --constraint-id C002
```

## 当前正式推演流程

### 1. 先定位目标

把用户目标翻译成 1 到 3 个标准策略词。

例：

- “想获取初始精准流量”可以先映射到 `冷启动验证`、`强结果选题`、`长尾流量`。
- “想做 B 站带货变现”可以先映射到 `选品策略`、`录屏内容`、`评论区转化`。
- “想做 AI 视频号”可以先映射到 `IP验证`、`脚本挖掘`、`AI视频生成`。

如果标准目标族没有命中：

- 不直接终止。
- 先做自治审计，判断是阶段二目标翻译问题、阶段三路由缺口，还是阶段一证据缺口。
- 只要当前证据还够，系统就自动合成一条 `bootstrap` 路径继续产出。
- 只有没有证据时，才只交付补库工单。

### 2. 找主策略节点

打开 `strategy_nodes.jsonl`，优先选择：

- `approved_case_count` 高的策略。
- `evidence_case_count` 高的策略。
- `max_quality_score` 高的策略。
- `platforms` / `domains` 与用户场景匹配的策略。

不要只看策略名字，要看它背后连接了哪些案例和资源。

现在的策略节点不应只被理解为“概念标签”，而应被理解为最小资源集装箱。至少要能直接看到：

- `action_refs`
- `template_refs`
- `tool_refs`
- `preferred_case_refs`

### 3. 路由判断

打开 `strategy_models/routes/goal_profiles.yaml` 和 `strategy_models/routes/strategy_profiles.yaml`：

- 先拿到目标族下的主策略和组合策略。
- 再按平台、用户类型、业务领域和资源约束判断适用性。
- 主策略证据不足时，必须降级为 `bootstrap`。

如果要检查“边”是不是已经不是普通连线，而是路由器，请继续看：

- `index/stage3/situation_nodes.jsonl`
- `index/stage3/goal_strategy_edges.jsonl`
- `index/stage3/situation_strategy_edges.jsonl`
- `index/stage3/strategy_situation_edges.jsonl`

这两类边至少应包含：

- `trigger_conditions`
- `applicable_params`
- `not_applicable_warning`
- `call_output`
- `reason`

同时要检查两件事：

- 当前用户类型是否命中了正式 `情境节点`，而不是只剩一个裸字符串。
- 当前主策略和组合策略里，是否已经剔除了命中 `not_suitable_for` 的禁区策略。

### 4. 组装资源包

优先使用 `strategy_models/resources/` 下的正式资源：

- 动作包：`AP`
- 模板资源：`TR`
- 工具调用：`TC`

这些资源索引现在应优先从策略节点本身读取；`strategy_profiles.yaml` 继续承担策略解释、适用规则和任务描述的补充角色。

平台资源词继续来自 `index/stage3/` 证据层。

输出时不要说“推荐某策略”就结束，必须写成：

- 执行动作。
- 调用资源。
- 关联案例。
- 风险提示。
- 下一轮反馈指标。
- 推演路径。
- 分组资源包，并且每个 `AP / TR / TC` 都要直接链接到真实文件。

### 5. 回看证据案例

打开 `case_strategy_edges.jsonl` 和 `case_resource_edges.jsonl`，确认推荐路径来自哪些案例。

如果证据案例都是 `draft`，方案必须降级为“待验证建议”。

如果至少有 1 个 `approved` 案例支撑，可以作为“优先尝试路径”，但仍要给出验证指标。

### 6. 接收阶段二节点补丁

如果阶段二新生成了一个正式 `strategy_node_patch`：

- 先校验补丁文件本身。
- 再检查里面的 `action_refs / template_refs / tool_refs / preferred_case_refs / evidence_case_refs` 是否都能落到现有系统资产。
- 补丁本身不直接替代正式图谱索引；它的作用是成为后续 route patch 或 seed map 重建的标准输入。
- 推荐与阶段四 `change_request` 配合：由阶段四生成正式写回工单，再触发执行器把补丁内容并入正式路由或资源层。

## 正式会话模板

```markdown
## 阶段三推演会话

### 用户情境
- 用户类型：
- 目标：
- 资源约束：
- 不适合路径：

### 推荐路径
- 主策略：
- 组合策略：
- 证据案例：
- 置信度：

### 动态方案包
- 动作包：
- 资源包：
- 工具入口：
- 案例快照：

### 7 天执行反馈指标
- 内容产出数：
- 点击 / 播放：
- 私域承接：
- 成交 / 留资：
- 需要二次诊断的问题：
```

## 当前正式支持目标

- 获取初始精准流量
- 种子用户付费验证
- 单入口私域承接
- B站带货转化
- AI视频快速出片

超出这个清单时，阶段三现在不会直接报错，而会进入自治审计链路。
