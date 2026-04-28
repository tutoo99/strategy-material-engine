---
session_id: session_example
title: 【专家熔炉会话】待补充
furnace_ref: expert_models/furnace.md
training_ground_ref:
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
date: 2026-04-21
---

# 【专家熔炉会话】待补充

---

## 用户原始问题

- 待补充

## 澄清后的标准靶子

- **平台：**
- **症状：**
- **指标 / 现象：**
- **场景 / 环节：**
- **训练场引用：** `expert_models/training_grounds/...` / 无

## 熔炉内部召回记录

1. `cases/...`

## 证据状态

- **证据级别：** `formal / bootstrap`
- **正式病例数：** `1`
- **证据缺口：**

## 熔炉内部组装逻辑

### 检查站点 1
- **检查项：**
- **判断方法：**
- **行动指令：**
- **参数：**
- **资源引用：**
- **对应病例：**
  - `cases/...`

## 自修正动作

- **是否触发：** 是
- **触发原因：** 当前正式病例不足 `5` 个，不能把证据缺口伪装成成熟专家知识
- **修正动作：**
  1. 仅保留已有正式病例支撑的检查站点
  2. 删除无病例支撑的检查站点、步骤和资源
  3. 将本次会话标记为 `bootstrap`

## 阶段一补库动作

- **是否触发：** 是
- **执行方：** `system`
- **是否需要用户补充：** 否
- **目标病例数：** `5`
- **当前缺口：** `4`
- **补库检索简报：**
- **收录约束：**
  1. 只接收已商业化验证且明确赚到钱的案例
  2. 必须从阶段一入口按六步拆解后再入库

## 最终工单 / 治疗包

## Markdown工单

## 您的专属优化方案

**诊断结论：** 待补充

**✅ 请按顺序执行以下动作（预计总耗时：待补充）：**

### 任务一：待补充
- **动作：**
- **参数：**
- **参考病例：** `cases/...`
- **SOP / 资源：**
- **预计耗时：**

### 任务二：待补充
- **动作：**
- **参数：**
- **参考病例：** `cases/...`
- **SOP / 资源：**
- **预计耗时：**

### 任务三：待补充
- **动作：**
- **参数：**
- **参考病例：** `cases/...`
- **SOP / 资源：**
- **预计耗时：**

## Structured Work Order

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
      - 删除无病例支撑的检查站点、步骤和资源
      - 将本次会话标记为 bootstrap
  stage1_replenishment:
    required: true
    owner: system
    user_action_required: false
    target_case_count: 5
    gap_count: 4
    search_brief: 待补充
    intake_constraints:
      - 只接收已商业化验证且明确赚到钱的案例
      - 必须从阶段一入口按六步拆解后再入库
  tasks:
    - id: T1
      title: 待补充
      action: 待补充
      params: []
      case_refs:
        - cases/...
      resource_refs: []
      sop_refs: []
      estimated_time: 待补充
      priority: high
      success_check: 待补充
    - id: T2
      title: 待补充
      action: 待补充
      params: []
      case_refs:
        - cases/...
      resource_refs: []
      sop_refs: []
      estimated_time: 待补充
      priority: medium
      success_check: 待补充
  writeback_eligible: false
```

## 进度播报记录

### 进度播报 1
- **时间：** 2026-04-21 14:00
- **触发类型：** stage_start
- **当前阶段：** 阶段二（1/6）问题收集
- **当前步骤：** 问题收集
- **当前动作：** 收集用户当前最具体的痛点
- **下一步需要你提供：** 请用一句话描述你现在最具体的问题
- **预计剩余时间：** 约 1 分钟内

## 用户反馈

- 待补充

## 是否具备回写资格

- **结论：** 否 / 是
- **原因：**
