# Buildmate 阶段一 / 阶段二 / 阶段三数据结构

## 目录层级

```text
strategy-material-engine/
├── sources/          # 原始案例输入
├── assets/
│   ├── case_drafts/  # AI 自动整理草稿
│   └── cases/        # 结构化案例档案
├── expert_models/    # 阶段二专家熔炉
│   ├── furnace.md
│   └── sessions/
├── strategy_models/  # 阶段三策略路由与方案包
│   ├── router.md
│   ├── productization/
│   ├── routes/
│   ├── resources/
│   └── sessions/
├── index/cases/      # 阶段一案例搜索索引
└── index/stage3/     # 阶段三证据图谱索引
```

### `strategy_models/productization/`

- `stage3_strategy_map.drawio`：阶段三正式可视化图谱
- `stage3_questionnaire.yaml`：阶段三正式推演问答脚本
- `README.md`：产品化入口说明

## `sources/` 模板

```yaml
---
source_type: post
title: 来源标题
author: 作者身份或昵称
origin: 来源平台或社区
platform: 小红书
domain: 内容副业
link: https://example.com/post
date: 2026-04-20
tags: [副业, 内容, 案例]
summary: 一句话说明这个原始案例主要讲什么
---
```

正文可以放：

- 原文全文
- 关键摘录
- 你自己的初步备注
- 额外补充链接

## `assets/cases/` frontmatter

```yaml
---
case_id: case_xiaohongshu_ppt_templates
title: 【上班族】小红书卖 PPT 模板，3 个月变现 1.5 万
author_identity: 上班族 / 运营岗
domain: 内容副业
platform: 小红书
stage: gene-library
result_summary: 3 个月变现 1.5 万，积累 8000 粉
result_tags: [变现, 冷启动, 内容转化]
symptoms: []
strategy_tags: []
resource_refs: []
causal_status: unknown
cross_case_refs: []
counterfactual_notes: []
action_granularity_score:
sequence_steps: []
platform_context:
account_context:
time_context:
resource_links: []
resource_last_checked_at:
source_path: sources/小红书虚拟资料副业案例.md
quality_score: 2.5
status: draft
content_source: ai_generated
body_lock: false
approved_from:
last_human_reviewed_at:
date: 2026-04-20
---
```

### 字段说明

- `case_id`：稳定 ID，用于索引、连边和引用
- `title`：推荐格式为“作者身份 + 核心打法 + 结果”
- `author_identity`：谁在什么背景下做成了这件事
- `domain`：业务领域，如 `内容副业`、`知识付费`、`私域运营`
- `platform`：平台或主战场，如 `小红书`、`抖音`、`微信`
- `stage`：当前固定写 `gene-library`
- `result_summary`：最关键结果，用一句话压缩
- `result_tags`：便于按结果筛选，如 `涨粉`、`变现`、`低成本`
- `symptoms`：预留给阶段二的问题标签
- `strategy_tags`：预留给阶段三的策略标签
- `resource_refs`：预留给阶段三四的资源索引
- `causal_status`：当前案例的因果判断状态，建议使用 `unknown / single_case_hypothesis / cross_case_validated / counterfactual_checked / refuted`
- `cross_case_refs`：交叉验证时引用的同类案例
- `counterfactual_notes`：反事实追问记录，用于防止幸存者偏差和归因谬误
- `action_granularity_score`：动作颗粒度评分，`1 ~ 5`
- `sequence_steps`：作战序列，记录动作顺序与依赖
- `platform_context / account_context / time_context`：成功发生时的平台阶段、账号阶段与时间背景
- `resource_links`：案例中提取出的链接型资源，用于后续心跳巡检
- `resource_last_checked_at`：资源最近一次巡检时间
- `source_path`：回指原始来源文件
- `quality_score`：当前案例可复用质量，`1.0 ~ 5.0`
- `status`：`draft / reviewed / approved`
- `content_source`：`ai_generated / human_provided / human_approved`
- `body_lock`：正文是否冻结；人工确认版必须为 `true`
- `approved_from`：人工确认版来源路径，可指向原整理稿或通过审核的草稿
- `last_human_reviewed_at`：最近一次人工确认时间

## `assets/cases/` 正文模板

```md
# 【案例名称】作者身份——核心打法，结果

---

## 【案例身份证】

**帖子标题：**  
**原文链接：**  
**一句话业务：**  
**作者是谁：**

**启动资源：**
1) **花了多少钱？**
2) **投入了多少时间？**
3) **有没有合伙人？**
4) **用到了什么特殊技能或设备？**
5) **其他启动条件：**

**核心目标：**  
**最终结果：**

---

## 【决策地图】

**1. 决策点：待补充**
- **选择：**
- **依据：**
- **动作：**
  1. ...
- **工具：**
  - ...
- **参数：**
  - ...
- **是否推测：** 是/否
- **证据摘录：**

---

## 【核心心法】

### 作战三原则：
1. ...
2. ...
3. ...

### 最大一个坑：
- 坑点：
- 解决方案：

### 最值钱一句忠告：
...

---

## 【归因与边界】

- **成功归因判断：**
- **交叉验证案例：**
- **平台/时间上下文：**
- **账号/业务阶段：**
- **时效背景：**
- **适用边界：**
- **反事实追问：**
  - ...

---

## 【作战序列】

1. ...

---

## 【资源清单】

- **资源链接：**
- **资源状态：** unchecked / healthy / degraded / retired
- **最后检查：**

---

## 【待验证推测】
- ...
```

推荐在 `核心心法` 和 `待验证推测` 之间增加三块：

- `【归因与边界】`
- `【作战序列】`
- `【资源清单】`

## 设计原则

- frontmatter 放稳定、可检索、可索引字段
- 正文放人工认可的可读版本
- 决策地图必须能回到“操作”层
- 缺证据的地方必须显式标记推测
- 人工确认后的正文只能追加增强信息，不能删减

## 阶段二目录与模板

阶段二分成“建模资产”和“运行会话”两层：

- 高频靶子索引：`index/stage2/symptom_candidates.jsonl`
- 靶子选择报告：`index/stage2/target_selection_report.md`
- 专家模型训练场：`expert_models/training_grounds/<symptom-slug>.md`
- 会诊记录：`expert_models/consultations/<symptom-slug>.md`
- 诊断手册：`expert_models/manuals/<symptom-slug>.md`
- 问诊表单：`expert_models/forms/<symptom-slug>.md`
- 临床实习记录：`expert_models/practicums/<symptom-slug>.md`
- 一个固定的 `expert_models/furnace.md`
- 多个运行时会话：`expert_models/sessions/<date>_<platform>_<symptom-slug>.md`

建模资产负责沉淀“第一个靶子”和可复用诊断逻辑；运行会话负责处理用户当下输入。二者不能互相替代。

### `index/stage2/symptom_candidates.jsonl` 模板

```json
{"rank":1,"symptom":"小红书笔记阅读量卡在 200-300","normalized_symptom":"小红书阅读量低位卡住","frequency":6,"concreteness_score":5,"observable_metrics":["阅读量","小眼睛"],"platforms":["小红书"],"case_refs":["cases/C001.md"],"formal_case_count":5,"evidence_status":"formal","excluded_as_broad":false}
```

每行代表一个候选靶子，必须能回链到阶段一案例。

### `target_selection_report.md` 模板

```md
# 【阶段二靶子选择报告】

## 输入
- **案例基因库：** index/cases/cases_meta.jsonl
- **统计口径：** approved / reviewed 优先，draft 只作候选提示

## 高频症状候选表
| 排名 | 候选症状 | 出现频次 | 具体度 | 可观察指标 | 代表案例 | 是否入选 |
|---|---:|---:|---:|---|---|---|

## 排除的大问题
- 怎么赚钱
- 怎么引流
- 怎么做增长

## 第一靶子定义卡
- **靶子名称：** 小红书阅读量低位诊断
- **精准问题：** 小红书笔记小眼睛长期卡在 200-300，上不去，如何诊断？
- **入选理由：** 高频、具体、可观察、可从病例召回动作。
- **训练场路径：** expert_models/training_grounds/xiaohongshu_read_low.md
```

### `training_grounds/` 模板

```yaml
---
training_ground_id: stage2_tg_example
title: 【专家模型训练场：小红书阅读量诊断】
scope: 阶段二
target_symptom: 小红书笔记小眼睛长期卡在 200-300，上不去
normalized_symptom: 小红书阅读量低位卡住
platform: 小红书
scene: 内容冷启动
status: draft
evidence_status: bootstrap
symptom_frequency: 3
formal_case_count: 1
case_refs:
  - cases/...
created_from: index/stage2/target_selection_report.md
date: 2026-04-22
---
```

正文至少包含：

- `第一靶子定义`
- `排除项`
- `高频证据`
- `代表病例入口`
- `可观察指标`
- `会诊记录区`
- `诊断手册草稿区`
- `问诊表单草稿区`
- `治疗包草稿区`
- `临床实习反馈区`

### `manuals/` 模板

每个 `检查站点` 都必须带资源编号，推荐使用固定格式：

- `R-01`
- `R-02`
- `R-03`

推荐正文结构：

```md
## 第一站：检查“门面”（封面&标题）

- **检查项：** 封面是否属于高对比度、信息清晰的大字报风格？
- **判断方法：** 将封面缩放到手机信息流小图尺寸，能否一眼看清核心信息？
- **✅ 行动指令：**
  1. **动作：** 打开稿定设计，搜索“小红书封面模板”，选用“知识干货”分类。
  2. **参数：** 标题字体“思源黑体-Bold”，字号 `68`，主色 `#FF4D4D`。
  3. **资源编号：** `R-01`
  4. **资源内容：** 稿定设计知识干货模板第 3 款 + 高点击封面配色参数。
  5. **来源病例：** `cases/C001.md`、`cases/C003.md`
- **病例引用：**
  - `cases/C001.md`
  - `cases/C003.md`
```

如果检查站点没有 `资源编号`，该站点不能进入正式诊断手册。

### `forms/` 模板

问诊表单必须分成两部分：

- 前半部分：症状采集
- 后半部分：诊断报告 / 治疗包 / 工单输出

推荐正文结构：

```md
# 【问诊表单：小红书阅读量诊断】

## 症状采集

1. 【平台】是哪里？
2. 【卡住的环节】是什么？
3. 【可观察现象】是什么？
4. 【目标结果】是什么？

## 诊断报告输出格式

## 您的专属优化方案

**诊断结论**：封面在小图模式下信息模糊，导致点击率低。

**✅ 请按顺序执行以下动作（预计总耗时：20分钟）：**

### 任务一：更换封面模板
- **动作：** 点击此链接直达【稿定设计-小红书封面模板库】
- **参数：** 选用“知识干货”类模板，将标题字号调整为 `>=68`
- **参考案例：** `cases/C001.md`
- **SOP / 资源：** `R-01` / `SOP-01`
- **预计耗时：** 8 分钟

### 任务二：优化标题前 10 字
- **动作：** 在标题前加上“【效率翻倍】”或“打工人必备：”
- **参数：** 标题前 10 字至少出现 1 个强结果词
- **参考案例：** `cases/C004.md`
- **SOP / 资源：** `R-02` / `SOP-02`
- **预计耗时：** 5 分钟
```

如果表单只有症状收集，没有“任务化诊断报告”，不能算阶段二第四步正式交付。

### `practicums/` 模板

临床实习记录必须是单独正式文件，不能只在对话里口头说明“我找人测了”。

推荐 frontmatter：

```yaml
---
practicum_id: stage2_practicum_example
title: 【临床实习：小红书阅读量诊断】
training_ground_ref: expert_models/training_grounds/xiaohongshu_read_low.md
form_ref: expert_models/forms/xiaohongshu_read_low.md
manual_ref: expert_models/manuals/xiaohongshu_read_low.md
status: draft
required_test_count: 3
completed_test_count: 0
date: 2026-04-22
---
```

推荐正文结构：

```md
# 【临床实习：小红书阅读量诊断】

## 测试计划

- **目标测试数：** 3
- **当前已完成：** 0
- **固定三问：**
  1. 表单问题看得懂吗？
  2. 诊断结论你觉得说到点上了吗？
  3. 行动建议你觉得能直接操作吗？

## 测试对象 1

- **对象标签：**
- **测试前原始内容：**
- **测试前原始数据：**
- **执行任务：** T1, T2
- **三问反馈：**
  - 表单问题看得懂吗？
  - 诊断结论你觉得说到点上了吗？
  - 行动建议你觉得能直接操作吗？
- **1~2 天后结果变化：**
- **是否改善：** 是 / 否 / 部分
- **有效动作：**
- **无效动作：**
- **新暴露卡点：**

## 迭代决策

- **如果反馈看不懂：** 简化问题描述
- **如果反馈不准：** 回查病例库并补充手册
- **如果行动有效：** 生成阶段一回写候选
- **如果行动无效：** 判断是执行不到位还是建议有误

## 阶段一回写候选

- **是否生成：** 是 / 否
- **候选对象：**
- **候选原因：**
- **是否已经赚到钱：** 是 / 否
- **金额 / 结果：**
- **下一步：** 如果已赚到钱，按阶段一入口注册为新案例
```

如果没有 `3` 个测试对象，必须在文件里显式写出缺口。

### `furnace.md` 模板

```yaml
---
furnace_id: expert_furnace
title: 【专家熔炉】待补充
scope: 阶段二
status: active
version: v0.1
date: 2026-04-20
---
```

正文至少包含：

- `入口定义`
- `澄清规则`
- `病例召回规则`
- `SOP 组装规则`
- `工单输出规则`
- `反馈回流规则`

### `sessions/` 模板

```yaml
---
session_id: session_example
title: 【专家熔炉会话】待补充
furnace_ref: expert_models/furnace.md
input_symptom: 待补充
platform: 待补充
status: draft
evidence_status: bootstrap
evidence_case_count: 1
evidence_gap: 待补充
progress_protocol: hybrid-3min
progress_event_count: 0
last_progress_at:
retrieved_case_refs:
  - cases/...
date: 2026-04-20
---
```

正文至少包含：

- `用户原始问题`
- `澄清后的标准靶子`
- `熔炉内部召回记录`
- `证据状态`
- `熔炉内部组装逻辑`
- `自修正动作`
- `阶段一补库动作`
- `Markdown工单`
- `Structured Work Order`
- `进度播报记录`
- `用户反馈`
- `是否具备回写资格`

## `进度播报记录` 建议结构

会话文件里建议固定增加：

```md
## 进度播报记录

### 进度播报 1
- **时间：** 2026-04-21 14:00
- **触发类型：** stage_start / key_step_start / timeout
- **当前阶段：** 阶段二（1/6）问题收集
- **当前步骤：** 问题收集
- **当前动作：** 收集你当前最具体的痛点
- **下一步需要你提供：** 请用一句话描述问题
- **预计剩余时间：** 约 1 分钟内

### 进度播报 2
- **时间：** 2026-04-21 14:03
- **触发类型：** timeout
- **当前阶段：** 阶段二（3/6）病例召回
- **当前步骤：** 病例召回
- **当前动作：** 正在复核已召回病例是否满足商业化验证
- **下一步需要你提供：** 无需提供，等待召回完成
- **预计剩余时间：** 约 3 分钟内
- **当前已完成：** 已完成关键词召回与首轮筛选
- **仍在处理的原因：** 仍在排除未赚到钱样本
- **剩余缺口：** 还差最终正式病例清单确认
```

## 阶段二反馈建议结构

`用户反馈` 区块在试运行期建议固定写成：

```text
【反馈类型】阶段二执行反馈
【会话文件】expert_models/sessions/xxxx.md
【原始痛点】...
【执行任务】T1, T2
【未执行任务】T3
【结果变化】...
【是否改善】是 / 否 / 部分
【是否赚到钱】是 / 否
【金额】...
【新暴露出的卡点】...
【我建议修正的地方】...
【证据】...
```

系统识别到 `【反馈类型】阶段二执行反馈` 时，应自动视为：

- 需要把反馈落入当前会话
- 需要触发 `self_repair`
- 如有必要，触发 `stage1_replenishment`

## 阶段三目录与模板

阶段三采用：

- 一个固定的 `strategy_models/graph_center.md`
- 一个固定的 `strategy_models/router.md`
- 一组固定的 `goal_profiles / strategy_profiles`
- 一组正式资源资产 `AP / TR / TC`
- 多个运行时会话：`strategy_models/sessions/<date>_<platform>_<goal>.md`
- 多个自治审计文件：`strategy_models/audits/<date>_<platform>_<goal>.md`

### `router.md` 模板

```yaml
---
router_id: strategy_router
title: 【策略路由器】待补充
scope: 阶段三
status: active
version: v1.0
date: 2026-04-22
---
```

正文至少包含：

- `入口定义`
- `目标收敛规则`
- `图谱召回规则`
- `路由判断规则`
- `方案包输出规则`
- `证据分级规则`

### `strategy_models/resources/` 模板

每个资源文件建议固定使用 frontmatter：

```yaml
---
resource_id: AP001
title: 待补充
resource_type: action_pack / template_resource / tool_call
status: active
strategy_refs: []
goal_refs: []
platform_refs: []
case_refs: []
---
```

正文至少包含：

- `适用目标`
- `执行步骤` 或 `模板`
- `输出结果`
- `风险提示`

### `strategy_models/sessions/` 模板

```yaml
---
session_id: stage3_session_example
title: 【策略推演会话】待补充
router_ref: strategy_models/router.md
input_goal: 待补充
normalized_goal: 待补充
user_type: 待补充
platform: 待补充
domain: 待补充
constraints: []
status: draft
evidence_status: bootstrap
evidence_case_count: 1
route_confidence: low
progress_protocol: hybrid-3min
progress_event_count: 0
last_progress_at:
selected_strategy_refs: []
selected_case_refs: []
selected_resource_refs: []
autonomous_mode: false
generation_mode: standard / synthesized_bootstrap
gap_type:
audit_ref:
date: 2026-04-22
---
```

正文至少包含：

- `用户原始目标`
- `收敛后的标准目标`
- `用户情境卡`
- `图谱召回记录`
- `路由判断记录`
- `证据状态`
- `方案包组装逻辑`
- `Markdown 方案包`
- `Structured Solution Package`
- `风险提示`
- `7天执行反馈指标`
- `进度播报记录`

### `strategy_models/audits/` 模板

```yaml
---
audit_id: stage3_audit_example
title: 【阶段三自治审计】待补充
scope: stage3
status: ready
input_goal: 待补充
platform: 待补充
user_type: 待补充
domain: 待补充
constraints: []
failure_mode: unmatched_goal
gap_type: stage3_route_gap
decision: synthesized_bootstrap
manual_fallback_required: false
generated_session_ref:
date: 2026-04-22
---
```

正文至少包含：

- `触发背景`
- `失败诊断`
- `阶段二反问结果`
- `阶段一补库动作`
- `自治学习动作`
- `Structured Autonomous Audit`

### `Structured Solution Package` 最小字段

```yaml
solution_package:
  target_goal: 待补充
  normalized_goal: 待补充
  evidence_status: bootstrap
  evidence_case_count: 1
  route_confidence: low
  primary_strategy: 待补充
  secondary_strategies: []
  case_refs:
    - cases/...
  resource_bundle:
    action_refs:
      - AP001
    template_refs:
      - TR001
    tool_refs:
      - TC001
    platform_resource_refs:
      - B站
  tasks:
    - id: T1
      title: 待补充
      strategy_ref: 待补充
      action: 待补充
      resource_refs: []
      case_refs: []
      estimated_time: 待补充
      success_check: 待补充
  risks:
    - 待补充
  feedback_metrics:
    - 待补充
```

### `strategy_models/node_patches/` 模板

阶段二如果沉淀出新的可复用诊断逻辑，不应只停留在手册里，还应额外产出一个“节点化补丁”供阶段三直接消费。

推荐 frontmatter：

```yaml
---
artifact_type: strategy_node_patch
patch_id: strategy_node_patch_example
title: 【阶段二 -> 阶段三节点补丁】待补充
status: draft
source_stage2_ref: expert_models/manuals/example.md
target_node_id: N999
node_type: strategy
date: 2026-04-22
---
```

正文至少包含：

- `来源专家模型`
- `节点定义`
- `路由边补丁`
- `资源调用索引`
- `Structured Strategy Node Patch`

### `Structured Strategy Node Patch` 最小字段

```yaml
strategy_node_patch:
  patch_id: strategy_node_patch_example
  source_ref: expert_models/manuals/example.md
  source_type: manual
  target_layer: stage3
  node:
    node_id: N999
    node_name: 待补充
    node_type: strategy
    trigger_conditions: []
    applicable_params: []
    not_applicable_warning: 待补充
    action_refs: []
    template_refs: []
    tool_refs: []
    preferred_case_refs: []
    evidence_case_refs: []
  proposed_edges:
    - edge_type: goal_strategy
      from_ref: goal_example
      to_ref: N999
      trigger_conditions: []
      call_output: []
      reason: 待补充
```

## 阶段四目录与模板

阶段四采用：

- 一个固定的 `stage4_models/orchestrator.md`
- 一个用户档案：`stage4_models/profile/owner_profile.md`
- 多个前线看板：`stage4_models/dashboards/*.md`
- 多个执行反馈：`stage4_models/feedback/*.md`
- 多个系统变更请求：`stage4_models/change_requests/*.md`
- 多个每周复盘：`stage4_models/reviews/*.md`
- 多个自动派发记录：`stage4_models/dispatches/*.md`

### `owner_profile` 模板

```yaml
---
artifact_type: owner_profile
profile_id: owner_profile_example
title: 【我的商业档案】待补充
owner_name: 待补充
status: active
review_cycle: quarterly
primary_goal: 待补充
risk_score: 5
focus_area: 待补充
frontlines: []
date: 2026-04-22
---
```

正文至少包含：

- `资源画像`
- `目标与偏好`
- `当前主战场`
- `业务前线总表`
- `交互协议`
- `交互人格`
- `主动关怀里程碑`
- `红色警报协议`
- `人类判断协议`
- `数据同步协议`
- `档案维护`
- `Structured Owner Profile`

其中 `资源画像` 与 `目标与偏好` 建议按问答式落地，至少显式包含：

- `Q1 / A1`
- `Q2 / A2`
- `Q3 / A3`
- `Q4 / A4`

### `frontline_dashboard` 模板

```yaml
---
artifact_type: frontline_dashboard
dashboard_id: dashboard_example
title: 【数据看板】待补充
profile_ref: stage4_models/profile/owner_profile.md
frontline_name: 待补充
platform: 待补充
domain: 待补充
status: active
alert_level: normal
last_synced_at: 2026-04-22 10:00
latest_feedback_ref:
latest_review_ref:
date: 2026-04-22
---
```

正文至少包含：

- `前线概览`
- `核心指标`
- `内容表现`
- `内容表现采集口径`
- `待办事项`
- `主动关怀消息`
- `红色警报协议`
- `红色警报消息`
- `手动同步机制`
- `预警状态`
- `Structured Frontline Dashboard`

### `stage4_feedback_record` 模板

```yaml
---
artifact_type: stage4_feedback_record
feedback_id: stage4_feedback_example
title: 【阶段四执行反馈】待补充
status: ready
profile_ref: stage4_models/profile/owner_profile.md
dashboard_ref: stage4_models/dashboards/example.md
source_stage3_session: strategy_models/sessions/...
generated_review_ref:
improved: partial
date: 2026-04-22
---
```

正文至少包含：

- `反馈背景`
- `执行结果`
- `学习判断`
- `学习动作`
- `模型修正项`
- `Structured Stage4 Feedback`

### `weekly_strategy_review` 模板

```yaml
---
artifact_type: weekly_strategy_review
review_id: weekly_review_example
title: 【每周战略复盘会】待补充
status: ready
profile_ref: stage4_models/profile/owner_profile.md
dashboard_refs: []
feedback_refs: []
week_range: 2026-04-20 ~ 2026-04-26
date: 2026-04-22
---
```

正文至少包含：

- `生成依据`
- `本周核心判断`
- `决策留白`
- `交互人格输出`
- `主动关怀与警报`
- `本周任务包`
- `授权项`
- `老板确认`
- `学习动作`
- `Structured Weekly Review`

其中 `本周任务包` 不应只是抽象任务名，至少应体现：

- `诊断`
- `策略`
- `预计耗时`
- `执行步骤`
- `执行包`（动作包 / 模板资源 / 工具调用 / 关联案例）
- `成功检查`
- `执行阻力`（认知负荷 / 平台数 / 上下文切换 / 阻力评分 / 最小下一步）

其中 `决策留白` 至少应体现：

- `决策问题`
- `decision_options`
- `是否必须填写理由`
- `老板填写区`

### `Structured Stage4 Feedback` 最小字段

```yaml
stage4_feedback:
  source_stage3_session: strategy_models/sessions/...
  executed_tasks: []
  observed_metric_changes: []
  improved: partial
  new_bottlenecks: []
  observations: []
  authorization:
    update_dashboard: false
    generate_review: false
    reopen_stage2: false
    trigger_stage1_replenishment: false
  learning_actions: []
  model_corrections:
    effectiveness_score: 0
    effectiveness_note: 待补充
    correction_slots: []

### `monthly_model_review` 模板

```yaml
---
artifact_type: monthly_model_review
review_id: monthly_model_review_example
title: 【月度模型修正会】待补充
status: ready
profile_ref: stage4_models/profile/owner_profile.md
feedback_refs: []
month_range: 2026-04
date: 2026-04-22
---
```

正文至少包含：

- `生成依据`
- `本月反馈概览`
- `模型修正清单`
- `修正执行决议`
- `Structured Monthly Model Review`

### `Structured Monthly Model Review` 最小字段

```yaml
monthly_model_review:
  source_refs: []
  summary:
    feedback_count: 0
    average_effectiveness_score: 0
    top_bottlenecks: []
  correction_backlog: []
  execution_decisions: []
```

### `red_alert_dispatch` 模板

```yaml
---
artifact_type: red_alert_dispatch
dispatch_id: red_alert_dispatch_example
title: 【阶段四自动派发】待补充
status: ready
profile_ref: stage4_models/profile/owner_profile.md
dashboard_ref: stage4_models/dashboards/example.md
generated_stage2_session_ref: expert_models/sessions/...
trigger_type: red_alert
alert_level: critical
date: 2026-04-22
---
```

正文至少包含：

- `触发背景`
- `系统判断`
- `阶段二自修正派发`
- `阶段一补库派发`
- `跟进条件`
- `Structured Red Alert Dispatch`

### `Structured Red Alert Dispatch` 最小字段

```yaml
red_alert_dispatch:
  source_refs: []
  trigger_type: red_alert
  frontline_name: 待补充
  platform: 待补充
  alert_level: critical
  trigger_summary: 待补充
  decision_summary: 待补充
  dispatch_strategy: stage1_first_then_stage2
  manual_fallback_required: false
  stage2_dispatch:
    required: true
    session_ref: expert_models/sessions/...
    evidence_status: bootstrap
    evidence_case_count: 0
    self_repair_required: true
    result: 待补充
  stage1_replenishment:
    required: true
    owner: system
    user_action_required: false
    target_case_count: 5
    gap_count: 5
    search_brief: 待补充
    intake_constraints: []
    result: 待补充
  next_gate:
    wait_for: stage1_replenishment_complete
    reentry_rule: 待补充
    next_action: 待补充
```

### `change_request` 模板

阶段四如果判定需要回流修正，不应只给自然语言建议，而应产出一份正式 `change_request`，供执行器自动落盘。

推荐 frontmatter：

```yaml
---
artifact_type: change_request
change_request_id: change_request_example
title: 【系统变更请求】待补充
status: draft
source_ref: stage4_models/feedback/example.md
target_stage: stage3
change_type: stage3_route_patch
target_ref: strategy_models/routes/strategy_profiles.yaml
patch_mode: append
manual_fallback_required: false
date: 2026-04-22
---
```

正文至少包含：

- `触发来源`
- `变更目标`
- `执行补丁`
- `验证与重建`
- `Structured Change Request`

### `Structured Change Request` 最小字段

```yaml
change_request:
  request_id: change_request_example
  source_ref: stage4_models/feedback/example.md
  target_stage: stage3
  change_type: stage3_route_patch
  manual_fallback_required: false
  expected_effect: 待补充
  changes:
    - change_id: CR-001
      target_ref: strategy_models/routes/strategy_profiles.yaml
      patch_mode: append
      section_title: ''
      content: |
        # 待补充
      reason: 待补充
  validation_commands:
    - python3 scripts/validate_change_request.py stage4_models/change_requests/example.md
  rebuild_actions:
    - python3 scripts/build_stage3_seed_map.py --root /Users/naipan/.hermes/skills/strategy-material-engine
```

### `Structured Weekly Review` 最小字段

```yaml
weekly_review:
  source_refs: []
  core_judgment:
    primary_bottleneck: 待补充
    priority_goal: 待补充
    avoid_list: []
  decision_options: []
  decision_prompt: 待补充
  rationale_required: true
  owner_snapshot:
    primary_goal_12m: 待补充
    weekly_hours: 待补充
    risk_score: 5
    focus_area: 待补充
  dashboard_snapshot:
    frontline_name: 待补充
    metric_summary: []
  human_judgment_policy: {}
  route_summary: 待补充
  total_estimated_hours: 待补充
  task_package: []
  authorizations:
    update_dashboard: false
    reopen_stage2: false
    trigger_stage1_replenishment: false
  learning_actions: []
```

## 交互播报建议结构

试运行期间，系统每次与用户交互，建议固定带上：

```text
当前阶段：阶段一 / 阶段二 / 阶段二反馈
当前步骤：X/Y
当前动作：...
下一步需要你提供：...
预计剩余时间：约 N 分钟
```

## 阶段一默认交付结构

阶段一完成后，默认不要直接把完整拆解稿贴在对话里，建议固定输出：

```text
当前阶段：阶段一（完成）
当前动作：交付阶段一结果摘要，不默认展开完整拆解稿
交付方式：文件路径 + 简短摘要 + 校验/入库结果
草稿文件：...
案例文件：...
校验结果：通过 / 未通过
自动修复次数：N
索引结果：...
下一步：如需查看全文，再打开对应文件；默认不在对话里粘贴整稿
```

## 进度汇报频率约束

试运行期间，建议固定采用：

- **混合模式**
  - 每 `3` 分钟至少汇报一次
  - 每次阶段切换 / 关键步骤开始时立即汇报

如果单一步骤超过 `3` 分钟：

- 系统必须追加一次超时进度汇报
- 超时进度汇报建议补充：
  - `当前已完成：...`
  - `仍在处理的原因：...`

## 阶段二反馈最小触发条件

如果想让反馈真正落入系统并触发 `self_repair`，最小字段建议为：

- `【会话文件】`
- `【执行任务】`
- `【结果变化】`
- `【是否改善】`

满足最小条件：

- 可以触发阶段二自修正
- 可以更新会话中的 `用户反馈`

不满足最小条件：

- 系统应继续追问
- 不应直接开始 `self_repair`

## ETA 建议写法

试运行期间，`预计剩余时间` 建议固定使用粗粒度表达：

- `约 1 分钟内`
- `约 3 分钟内`
- `约 5 分钟内`
- `约 10 分钟内`
- `需要更久，原因是 ...`

## 阶段二接口原则

- 阶段二先区分 `建模模式` 和 `运行问诊模式`
- 建模模式必须先扫描阶段一基因库，输出高频症状候选表与第一靶子定义卡
- 建模模式必须创建 `【专家模型训练场：XXX诊断】`
- 运行问诊模式不预设默认靶子；靶子来自用户症状、授权案例提炼、红色警报或已存在训练场
- 阶段二运行时会话都应尽量回链到阶段一案例中的：
  - `symptoms`
  - `strategy_tags`
  - `resource_refs`
- 阶段二中的“病例引用”默认只允许引用阶段一 `assets/cases/` 中已商业化验证的病例
- 外部参考样本、公开 transcript、公开视频，只能作为 `external_refs` 性质的参考，不应当充当病例
- 当正式病例数 `<5` 时，会话必须标记为 `bootstrap / provisional`，不能伪装成正式成熟专家
- 当某个检查站点 / 任务拿不到病例支撑时，系统必须先删掉该站点 / 任务，再记录 `self_repair`
- 当正式病例数为 `0` 时，会话必须退化为 `replenishment-only`，由系统发起阶段一补库
- 阶段二的“行动指令”不是抽象建议，必须落到操作层
- 每条关键检查标准都应至少绑定一个可用资源引用
- 阶段二允许为高频靶子沉淀训练场、会诊记录、诊断手册和问诊表单；运行时仍使用同一个熔炉处理不同输入
- 阶段二的最终出口必须同时包含：
  - 人类可读的 Markdown 工单
  - 机器可读的 YAML `work_order`

### `Structured Work Order` 最小字段

```yaml
work_order:
  target_symptom: 待补充
  diagnosis: 待补充
  evidence_status: bootstrap
  evidence_case_count: 1
  evidence_gap: 待补充
  self_repair:
    required: true
    actions:
      - 仅保留已有正式病例支撑的检查站点
  stage1_replenishment:
    required: true
    owner: system
    user_action_required: false
    target_case_count: 5
    gap_count: 4
    search_brief: 待补充
    intake_constraints:
      - 只接收已商业化验证且明确赚到钱的案例
  tasks:
    - id: T1
      title: 待补充
      action: 待补充
      params: []
      case_refs: []
      resource_refs: []
      sop_refs: []
      estimated_time: 待补充
      priority: high
      success_check: 待补充
  writeback_eligible: false
```
