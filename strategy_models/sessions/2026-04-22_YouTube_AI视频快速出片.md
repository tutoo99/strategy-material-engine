---
session_id: stage3_20260422_youtube_ai视频快速出片
title: 【策略推演会话】YouTube / AI视频快速出片
router_ref: strategy_models/router.md
input_goal: AI视频快速出片
normalized_goal: AI视频快速出片
user_type: AI内容创业者
platform: YouTube
domain: AI视频内容创业
constraints:
- 单人执行
- 7天内出首条视频
status: ready
evidence_status: formal
evidence_case_count: 1
route_confidence: medium
progress_protocol: hybrid-3min
progress_event_count: 7
last_progress_at: 2026-04-22 00:34
selected_strategy_refs:
- IP验证
- 脚本挖掘
- 分镜拆解
- AI视频生成
- 节奏剪辑
selected_case_refs:
- cases/youtube_seedance2真人爆款视频.md
selected_resource_refs:
- AP007
- AP008
- AP009
- AP010
- TR006
- TR007
- TC004
date: '2026-04-22'
---

# 【策略推演会话】YouTube / AI视频快速出片

## 用户原始目标

- AI视频快速出片

## 收敛后的标准目标

- **目标：** AI视频快速出片
- **目标族：** AI视频快速出片
- **平台：** YouTube
- **用户类型：** AI内容创业者

## 用户情境卡

- **平台：** YouTube
- **业务领域：** AI视频内容创业
- **资源约束：** 单人执行, 7天内出首条视频
- **不适合路径：** 没做 IP 验证就直接生成，极易白费生成成本。；AI 分镜和镜头草稿必须人工校对，不能直出。

## 图谱召回记录

1. `cases/youtube_seedance2真人爆款视频.md`

## 路由判断记录

### 路由节点 1：IP验证
- **策略摘要：** 先确认 IP 当前仍在爆，再决定是否投入脚本和生成成本。
- **命中原因：** 需要先判断热点 IP 当前是否仍有流量
- **不适用提醒：** 只凭印象判断 IP 热度时不适用
- **证据病例数：** `1`
- **其中 approved：** `1`

### 路由节点 2：脚本挖掘
- **策略摘要：** 从平台推荐和跨平台内容池里找可复爆脚本，不直接照搬。
- **命中原因：** 已确定可做 IP，需要找可复爆脚本
- **不适用提醒：** 只看单平台，容易同质化
- **证据病例数：** `1`
- **其中 approved：** `1`

### 路由节点 3：分镜拆解
- **策略摘要：** 用 AI 提供草稿，但必须逐镜校对，确保剧情和镜头不跑偏。
- **命中原因：** 已确定脚本，需要拆成可生成的分镜结构
- **不适用提醒：** 不做人工逐镜校对时不适用
- **证据病例数：** `1`
- **其中 approved：** `1`

### 路由节点 4：AI视频生成
- **策略摘要：** 按角色图、镜头约束和分段生成规则完成主流程出片。
- **命中原因：** 已有角色图和分镜表，可以进入分段生成
- **不适用提醒：** 角色图和镜头逻辑没锁定时，不适合直接生成
- **证据病例数：** `1`
- **其中 approved：** `1`

### 路由节点 5：节奏剪辑
- **策略摘要：** 用原片节奏和 BGM 做重剪，让 AI 画面重新成立。
- **命中原因：** 已有分段素材，需要重构节奏与情绪
- **不适用提醒：** 完全不复查节奏，只顺拼素材时不适用
- **证据病例数：** `1`
- **其中 approved：** `1`

## 证据状态

- **证据级别：** `formal`
- **证据病例数：** `1`
- **路由置信度：** `medium`

## 方案包组装逻辑

- 先按目标族拿主策略和组合策略，再按当前平台 / 用户类型 / 资源约束过滤。
- 资源包只调用已登记的 AP / TR / TC，不直接把平台资源词当动作包。
- 证据优先级：approved > reviewed > draft。

### 已组装资源
- **动作包：**
  - `AP007` 热门IP验证 SOP -> strategy_models/resources/actions/AP007.md
  - `AP008` 脚本源挖掘 SOP -> strategy_models/resources/actions/AP008.md
  - `AP009` AI分镜拆解 SOP -> strategy_models/resources/actions/AP009.md
  - `AP010` Seedance生成与节奏重剪 SOP -> strategy_models/resources/actions/AP010.md
- **模板资源：**
  - `TR006` IP与脚本验证记录表 -> strategy_models/resources/templates/TR006.md
  - `TR007` 分镜校对表 -> strategy_models/resources/templates/TR007.md
- **工具调用：**
  - `TC004` YouTube AI视频工具链检查清单 -> strategy_models/resources/tools/TC004.md
- **平台资源词：** Viewstats, YouTube无痕首页, 豆包, Gemini AI Studio, Seedance 2.0, Seedance 1.0, Gemini图片生成, 剪映, QQ音乐

## Markdown 方案包

## 为你动态组装的作战方案包

### 推荐路径
- **主策略：** IP验证, 脚本挖掘
- **组合策略：** 分镜拆解, AI视频生成, 节奏剪辑
- **证据案例：** `cases/youtube_seedance2真人爆款视频.md`

### 动作任务

### 任务 T1：完成一轮 IP 热度验证
- **动作：** 从无痕首页和 Viewstats 交叉确认 3 个候选 IP，只保留仍在爆发的那一个。
- **策略引用：** `IP验证`
- **资源引用：** `AP007`, `TR006`, `TC004`
- **参考案例：** `cases/youtube_seedance2真人爆款视频.md`
- **预计耗时：** 90 分钟
- **成功检查：** 完成 1 份 IP 验证记录表，并确定 1 个可做 IP。

### 任务 T2：建立脚本源清单
- **动作：** 从 YouTube 推荐和国内内容池各挖 3 个脚本源，并筛出最适合改写的 1 个。
- **策略引用：** `脚本挖掘`
- **资源引用：** `AP008`, `TR006`, `TC004`
- **参考案例：** `cases/youtube_seedance2真人爆款视频.md`
- **预计耗时：** 2 小时
- **成功检查：** 输出 1 份脚本源清单，并锁定 1 条待拆脚本。

### 任务 T3：完成一版可用分镜表
- **动作：** 用 Gemini 出分镜草稿，再按原视频逐镜删改，形成可生成分镜表。
- **策略引用：** `分镜拆解`
- **资源引用：** `AP009`, `TR007`, `TC004`
- **参考案例：** `cases/youtube_seedance2真人爆款视频.md`
- **预计耗时：** 2 小时
- **成功检查：** 输出 1 份逐镜校对后的分镜表。

### 任务 T4：跑通主流程生成
- **动作：** 先做角色图，再按 10 镜 / 15 秒分段生成主流程，缺镜头用补镜流程兜底。
- **策略引用：** `AI视频生成`
- **资源引用：** `AP010`, `TR007`, `TC004`
- **参考案例：** `cases/youtube_seedance2真人爆款视频.md`
- **预计耗时：** 3 小时
- **成功检查：** 产出 1 套可剪辑的分段视频素材。

### 任务 T5：完成一轮节奏重剪
- **动作：** 复用原片情绪结构与 BGM，按信息镜头和情绪镜头节奏重新剪出第一版成片。
- **策略引用：** `节奏剪辑`
- **资源引用：** `AP010`, `TR007`, `TC004`
- **参考案例：** `cases/youtube_seedance2真人爆款视频.md`
- **预计耗时：** 2 小时
- **成功检查：** 输出 1 条完成节奏重剪的成片。

## Structured Solution Package

```yaml
solution_package:
  target_goal: AI视频快速出片
  normalized_goal: AI视频快速出片
  evidence_status: formal
  evidence_case_count: 1
  route_confidence: medium
  primary_strategy: IP验证
  secondary_strategies:
  - 分镜拆解
  - AI视频生成
  - 节奏剪辑
  case_refs:
  - cases/youtube_seedance2真人爆款视频.md
  resource_bundle:
    action_refs:
    - AP007
    - AP008
    - AP009
    - AP010
    template_refs:
    - TR006
    - TR007
    tool_refs:
    - TC004
    platform_resource_refs:
    - Viewstats
    - YouTube无痕首页
    - 豆包
    - Gemini AI Studio
    - Seedance 2.0
    - Seedance 1.0
    - Gemini图片生成
    - 剪映
    - QQ音乐
  tasks:
  - id: T1
    title: 完成一轮 IP 热度验证
    strategy_ref: IP验证
    action: 从无痕首页和 Viewstats 交叉确认 3 个候选 IP，只保留仍在爆发的那一个。
    resource_refs:
    - AP007
    - TR006
    - TC004
    case_refs:
    - cases/youtube_seedance2真人爆款视频.md
    estimated_time: 90 分钟
    success_check: 完成 1 份 IP 验证记录表，并确定 1 个可做 IP。
  - id: T2
    title: 建立脚本源清单
    strategy_ref: 脚本挖掘
    action: 从 YouTube 推荐和国内内容池各挖 3 个脚本源，并筛出最适合改写的 1 个。
    resource_refs:
    - AP008
    - TR006
    - TC004
    case_refs:
    - cases/youtube_seedance2真人爆款视频.md
    estimated_time: 2 小时
    success_check: 输出 1 份脚本源清单，并锁定 1 条待拆脚本。
  - id: T3
    title: 完成一版可用分镜表
    strategy_ref: 分镜拆解
    action: 用 Gemini 出分镜草稿，再按原视频逐镜删改，形成可生成分镜表。
    resource_refs:
    - AP009
    - TR007
    - TC004
    case_refs:
    - cases/youtube_seedance2真人爆款视频.md
    estimated_time: 2 小时
    success_check: 输出 1 份逐镜校对后的分镜表。
  - id: T4
    title: 跑通主流程生成
    strategy_ref: AI视频生成
    action: 先做角色图，再按 10 镜 / 15 秒分段生成主流程，缺镜头用补镜流程兜底。
    resource_refs:
    - AP010
    - TR007
    - TC004
    case_refs:
    - cases/youtube_seedance2真人爆款视频.md
    estimated_time: 3 小时
    success_check: 产出 1 套可剪辑的分段视频素材。
  - id: T5
    title: 完成一轮节奏重剪
    strategy_ref: 节奏剪辑
    action: 复用原片情绪结构与 BGM，按信息镜头和情绪镜头节奏重新剪出第一版成片。
    resource_refs:
    - AP010
    - TR007
    - TC004
    case_refs:
    - cases/youtube_seedance2真人爆款视频.md
    estimated_time: 2 小时
    success_check: 输出 1 条完成节奏重剪的成片。
  risks:
  - 没做 IP 验证就直接生成，极易白费生成成本。
  - AI 分镜和镜头草稿必须人工校对，不能直出。
  feedback_metrics:
  - 已验证 IP 数
  - 已拆脚本数
  - 完成分镜数
  - 7 天出片数
```

## 风险提示

- 没做 IP 验证就直接生成，极易白费生成成本。
- AI 分镜和镜头草稿必须人工校对，不能直出。

## 7天执行反馈指标

- 已验证 IP 数
- 已拆脚本数
- 完成分镜数
- 7 天出片数

## 进度播报记录

### 进度播报 1
- **时间：** 2026-04-22 00:28
- **触发类型：** stage_start
- **当前阶段：** 阶段三（1/7）目标收集
- **当前步骤：** 目标收集
- **当前动作：** 收集用户本轮最明确的目标
- **下一步需要你提供：** 情境收敛
- **预计剩余时间：** 约 7 分钟内

### 进度播报 2
- **时间：** 2026-04-22 00:29
- **触发类型：** key_step_start
- **当前阶段：** 阶段三（2/7）情境收敛
- **当前步骤：** 情境收敛
- **当前动作：** 收敛平台、用户类型、领域和资源约束
- **下一步需要你提供：** 图谱召回
- **预计剩余时间：** 约 6 分钟内

### 进度播报 3
- **时间：** 2026-04-22 00:30
- **触发类型：** key_step_start
- **当前阶段：** 阶段三（3/7）图谱召回
- **当前步骤：** 图谱召回
- **当前动作：** 召回与目标最相关的策略节点、资源节点和证据案例
- **下一步需要你提供：** 路由判断
- **预计剩余时间：** 约 5 分钟内

### 进度播报 4
- **时间：** 2026-04-22 00:31
- **触发类型：** key_step_start
- **当前阶段：** 阶段三（4/7）路由判断
- **当前步骤：** 路由判断
- **当前动作：** 判断主策略、组合策略和不适用路径
- **下一步需要你提供：** 方案包组装
- **预计剩余时间：** 约 4 分钟内

### 进度播报 5
- **时间：** 2026-04-22 00:32
- **触发类型：** key_step_start
- **当前阶段：** 阶段三（5/7）方案包组装
- **当前步骤：** 方案包组装
- **当前动作：** 把动作包、模板和工具组装成可执行方案
- **下一步需要你提供：** 校验收口
- **预计剩余时间：** 约 3 分钟内

### 进度播报 6
- **时间：** 2026-04-22 00:33
- **触发类型：** key_step_start
- **当前阶段：** 阶段三（6/7）校验收口
- **当前步骤：** 校验收口
- **当前动作：** 校验证据等级、资源引用和会话结构
- **下一步需要你提供：** 交付执行
- **预计剩余时间：** 约 2 分钟内

### 进度播报 7
- **时间：** 2026-04-22 00:34
- **触发类型：** key_step_start
- **当前阶段：** 阶段三（7/7）交付执行
- **当前步骤：** 交付执行
- **当前动作：** 交付 Markdown 方案包与 YAML solution_package
- **下一步需要你提供：** 无需再提供，等待方案执行反馈
- **预计剩余时间：** 约 1 分钟内
