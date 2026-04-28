---
artifact_type: owner_profile
profile_id: owner_profile_星河
title: 【我的商业档案】星河
owner_name: 星河
status: active
review_cycle: quarterly
primary_goal: 打造一个月入1万的知识产品业务
risk_score: 3
focus_area: 内容创作
frontlines:
- B站内容副业主号
- B站好物测试前线
- 知乎冷启动测试前线
date: '2026-04-22'
---

# 【我的商业档案】星河

## 资源画像

- **Q1：我目前可用于商业探索的月度现金流是多少？**
  - **A1：** 5000元
- **Q2：我每周能稳定投入的时间块有多少小时？**
  - **A2：** 10小时
- **Q3：我的核心技能是什么？**
  - **A3：** 写作, 商业分析
- **Q4：我现有的启动资源有哪些？**
  - **A4：** B站账号1个, 个人案例库

## 目标与偏好

- **Q1：我未来 12 个月的核心商业目标是什么？**
  - **A1：** 打造一个月入1万的知识产品业务
- **Q2：我的风险偏好如何？**
  - **A2：** `3` / 10
- **Q3：我更擅长 / 喜欢内容创作、流量运营还是产品交付？**
  - **A3：** 内容创作
- **Q4：我希望系统以什么频率和方式与我互动？**
  - **A4：** 每周战略复盘, 重大风险预警

## 当前主战场

- B站内容副业主号

## 业务前线总表

- **前线：** B站内容副业主号 -> **看板：** `stage4_models/dashboards/B站内容副业主号.md`
- **前线：** B站好物测试前线 -> **看板：** `stage4_models/dashboards/B站好物测试前线.md`
- **前线：** 知乎冷启动测试前线 -> **看板：** `stage4_models/dashboards/知乎冷启动测试前线.md`

## 交互协议

- **互动频率：** 每周战略复盘, 重大风险预警
- **语气偏好：** 简洁、直接、以数据为支撑。
- **主动提醒规则：** 当核心指标连续恶化时，优先触发预警与复盘。

## 交互人格

- **人格原型：** JARVIS
- **语气设定：** 简洁、直接、以数据为支撑，不做情绪化安慰。
- **重大挫折时的回应方式：** 重大挫折时先指出事实和下一步诊断入口；如有相似案例，再引用案例给出可执行信心。
- **幽默程度：** low

## 主动关怀里程碑

- **连续作战30天：** 当 `连续更新天数` >= 30 时，自动生成消息：老板，连续作战30天，达成习惯养成里程碑。根据图谱，此阶段之后应优先检查稳定增长路径，而不是频繁换方向。

## 红色警报协议

- **触发条件：** 任何核心业务指标连续3天下降超过30%
- **中断等级：** red_alert
- **触发动作：** 立即打断常规周复盘，推送最相关的阶段二专家模型诊断入口，并冻结新增扩张动作。
- **诊断入口：** 阶段二重新问诊入口：run_stage2 / stage2_diagnosis_update_needed

## 人类判断协议

- **决策选项数量：** 3
- **是否强制填写选择理由：** 是
- **默认决策问题：** 本周只能押注一个主路径时，你选择哪一个？请写出选择理由。
- **防能力退化规则：** 每次周复盘必须保留 2-3 个可选路径，并要求操作者写下选择理由；每季度至少做一次不依赖自动推荐的手动推演。
- **季度手动推演：** 开启

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
  owner_name: 星河
  resource_profile:
    monthly_cashflow: 5000元
    weekly_hours: 10小时
    core_skills:
    - 写作
    - 商业分析
    startup_resources:
    - B站账号1个
    - 个人案例库
  goals_and_preferences:
    primary_goal_12m: 打造一个月入1万的知识产品业务
    risk_score: 3
    focus_area: 内容创作
    interaction_preferences:
    - 每周战略复盘
    - 重大风险预警
  frontlines:
  - B站内容副业主号
  - B站好物测试前线
  - 知乎冷启动测试前线
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
    message: 老板，连续作战30天，达成习惯养成里程碑。根据图谱，此阶段之后应优先检查稳定增长路径，而不是频繁换方向。
  red_alert_protocol:
    trigger: 任何核心业务指标连续3天下降超过30%
    threshold_days: 3
    drop_percent: 30
    interrupt_level: red_alert
    action: 立即打断常规周复盘，推送最相关的阶段二专家模型诊断入口，并冻结新增扩张动作。
    diagnosis_entry: 阶段二重新问诊入口：run_stage2 / stage2_diagnosis_update_needed
  human_judgment_policy:
    decision_options_required: 3
    rationale_required: true
    decision_prompt: 本周只能押注一个主路径时，你选择哪一个？请写出选择理由。
    anti_skill_decay_rule: 每次周复盘必须保留 2-3 个可选路径，并要求操作者写下选择理由；每季度至少做一次不依赖自动推荐的手动推演。
    quarterly_manual_drill: true
```
