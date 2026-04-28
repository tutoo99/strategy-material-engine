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

# 【我的商业档案】待补充

## 资源画像

- **Q1：我目前可用于商业探索的月度现金流是多少？**
  - **A1：**
- **Q2：我每周能稳定投入的时间块有多少小时？**
  - **A2：**
- **Q3：我的核心技能是什么？**
  - **A3：**
- **Q4：我现有的启动资源有哪些？**
  - **A4：**

## 目标与偏好

- **Q1：我未来 12 个月的核心商业目标是什么？**
  - **A1：**
- **Q2：我的风险偏好如何？**
  - **A2：**
- **Q3：我更擅长 / 喜欢内容创作、流量运营还是产品交付？**
  - **A3：**
- **Q4：我希望系统以什么频率和方式与我互动？**
  - **A4：**

## 当前主战场

- 待补充

## 业务前线总表

- **前线：** 待补充 -> **看板：** `stage4_models/dashboards/example.md`

## 交互协议

- **互动频率：**
- **语气偏好：**
- **主动提醒规则：**

## 交互人格

- **人格原型：**
- **语气设定：**
- **重大挫折时的回应方式：**
- **幽默程度：**

## 主动关怀里程碑

- **连续作战30天：**

## 红色警报协议

- **触发条件：**
- **中断等级：**
- **触发动作：**
- **诊断入口：**

## 数据同步协议

- **同步频率：** daily
- **固定时间：** 17:00
- **预计耗时：** 10分钟
- **同步方式：** 手动同步
- **执行说明：** 每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。

## 档案维护

- **更新周期：** 每季度至少更新一次。
- **维护原则：** 系统对你的理解，完全基于这份档案的准确性。

## Structured Owner Profile

```yaml
owner_profile:
  owner_name: 待补充
  resource_profile:
    monthly_cashflow: 待补充
    weekly_hours: 待补充
    core_skills: []
    startup_resources: []
  goals_and_preferences:
    primary_goal_12m: 待补充
    risk_score: 5
    focus_area: 待补充
    interaction_preferences: []
  frontlines: []
  sync_protocol:
    frequency: daily
    time: '17:00'
    duration: 10分钟
    method: 手动同步
    instruction: 每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。
  interaction_persona:
    archetype: JARVIS
    tone: 简洁、直接、以数据为支撑，不做情绪化安慰。
    setback_response: 重大挫折时先指出事实和下一步诊断入口；如有相似案例，再引用案例给出可执行信心。
    humor_level: low
  milestone_rules:
  - id: M001
    name: 连续作战30天
    trigger_metric: 连续更新天数
    operator: '>='
    threshold: 30
    message: 老板，连续作战30天，达成习惯养成里程碑。
  red_alert_protocol:
    trigger: 任何核心业务指标连续3天下降超过30%
    threshold_days: 3
    drop_percent: 30
    interrupt_level: red_alert
    action: 立即打断常规周复盘，推送最相关的阶段二专家模型诊断入口，并冻结新增扩张动作。
    diagnosis_entry: 阶段二重新问诊入口：run_stage2 / stage2_diagnosis_update_needed
```
