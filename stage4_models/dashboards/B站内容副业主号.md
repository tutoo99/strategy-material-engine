---
artifact_type: frontline_dashboard
dashboard_id: dashboard_b站内容副业主号
title: 【数据看板】B站内容副业主号
profile_ref: stage4_models/profile/owner_profile.md
frontline_name: B站内容副业主号
platform: B站
domain: 内容副业
status: active
alert_level: warning
last_synced_at: 2026-04-22 02:49
latest_feedback_ref: stage4_models/feedback/2026-04-22_B站内容副业主号.md
latest_review_ref: stage4_models/reviews/2026-04-22_B站.md
date: '2026-04-22'
---

# 【数据看板】B站内容副业主号

## 前线概览

- **前线名称：** B站内容副业主号
- **平台：** B站
- **业务领域：** 内容副业
- **当前状态：** active

## 核心指标

- **粉丝数：** 3200
- **近7日均阅读：** 950
- **高意图私信：** 9
- **首轮播放：** 920

## 内容表现

- 获取初始精准流量：标题=获取初始精准流量；封面=强结果封面A；数据=阅读1200，点赞85；评论待回复=3条
- 细分场景选题：标题=细分场景选题；封面=场景封面B；数据=阅读760，点赞41；评论待回复=2条

## 内容表现采集口径

- 标题
- 封面
- 核心数据
- 评论待回复

## 待办事项

- 评论和私信有增长，但承接入口还不够清晰
- 长尾内容节奏还不稳定

## 主动关怀消息

- 当前未触发新的里程碑消息。

## 红色警报协议

- **触发条件：** 任何核心业务指标连续3天下降超过30%
- **触发动作：** 立即打断常规周复盘，推送最相关的阶段二专家模型诊断入口，并冻结新增扩张动作。
- **诊断入口：** 阶段二重新问诊入口：run_stage2 / stage2_diagnosis_update_needed

## 红色警报消息

- 当前未触发红色警报。

## 手动同步机制

- **同步频率：** daily
- **固定时间：** 17:00
- **预计耗时：** 10分钟
- **执行方式：** 手动同步
- **同步说明：** 每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。


## 预警状态

- **等级：** `warning`
- **原因：** 收到新的执行反馈，需要回看当前前线状态。

## Structured Frontline Dashboard

```yaml
dashboard:
  frontline_name: B站内容副业主号
  platform: B站
  domain: 内容副业
  status: active
  alert_level: warning
  alert_reason: 收到新的执行反馈，需要回看当前前线状态。
  metrics:
  - label: 粉丝数
    value: '3200'
  - label: 近7日均阅读
    value: '950'
  - label: 高意图私信
    value: '9'
  - label: 首轮播放
    value: '920'
  content_items:
  - 获取初始精准流量：标题=获取初始精准流量；封面=强结果封面A；数据=阅读1200，点赞85；评论待回复=3条
  - 细分场景选题：标题=细分场景选题；封面=场景封面B；数据=阅读760，点赞41；评论待回复=2条
  todos:
  - 评论和私信有增长，但承接入口还不够清晰
  - 长尾内容节奏还不稳定
  notes:
  - 本次状态已按阶段四反馈刷新。
  source_refs:
  - stage4_models/feedback/2026-04-22_B站内容副业主号.md
  sync_protocol:
    frequency: daily
    time: '17:00'
    duration: 10分钟
    method: 手动同步
    instruction: 每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。
  content_capture_fields:
  - 标题
  - 封面
  - 核心数据
  - 评论待回复
  red_alert_protocol:
    trigger: 任何核心业务指标连续3天下降超过30%
    threshold_days: 3
    drop_percent: 30
    interrupt_level: red_alert
    action: 立即打断常规周复盘，推送最相关的阶段二专家模型诊断入口，并冻结新增扩张动作。
    diagnosis_entry: 阶段二重新问诊入口：run_stage2 / stage2_diagnosis_update_needed
  milestone_messages: []
  red_alert_messages: []
```
