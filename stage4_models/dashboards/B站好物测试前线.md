---
artifact_type: frontline_dashboard
dashboard_id: dashboard_b站好物测试前线
title: 【数据看板】B站好物测试前线
profile_ref: stage4_models/profile/owner_profile.md
frontline_name: B站好物测试前线
platform: B站
domain: 内容电商
status: active
alert_level: warning
last_synced_at: 2026-04-22 02:49
latest_feedback_ref: stage4_models/feedback/2026-04-22_B站好物测试前线.md
latest_review_ref: stage4_models/reviews/2026-04-22_B站好物测试前线.md
date: '2026-04-22'
---

# 【数据看板】B站好物测试前线

## 前线概览

- **前线名称：** B站好物测试前线
- **平台：** B站
- **业务领域：** 内容电商
- **当前状态：** active

## 核心指标

- **粉丝数：** 180
- **近7日均播放：** 680
- **商品点击：** 21
- **成交单数：** 2
- **视频播放：** 680
- **连续更新天数：** 30

## 内容表现

- 首条录屏好物视频：标题=录屏好物首条；封面=单品利益点封面；数据=播放680，点击21，成交2；评论待回复=5条

## 内容表现采集口径

- 标题
- 封面
- 核心数据
- 评论待回复

## 待办事项

- 有点击和出单，但评论区承接还不稳定
- 选品还不够聚焦，内容和商品人群匹配度一般

## 主动关怀消息

- 老板，连续作战30天，达成习惯养成里程碑。根据图谱，此阶段之后应优先检查稳定增长路径，而不是频繁换方向。

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
  frontline_name: B站好物测试前线
  platform: B站
  domain: 内容电商
  status: active
  alert_level: warning
  alert_reason: 收到新的执行反馈，需要回看当前前线状态。
  metrics:
  - label: 粉丝数
    value: '180'
  - label: 近7日均播放
    value: '680'
  - label: 商品点击
    value: '21'
  - label: 成交单数
    value: '2'
  - label: 视频播放
    value: '680'
  - label: 连续更新天数
    value: '30'
  content_items:
  - 首条录屏好物视频：标题=录屏好物首条；封面=单品利益点封面；数据=播放680，点击21，成交2；评论待回复=5条
  todos:
  - 有点击和出单，但评论区承接还不稳定
  - 选品还不够聚焦，内容和商品人群匹配度一般
  notes:
  - 本次状态已按阶段四反馈刷新。
  source_refs:
  - stage4_models/feedback/2026-04-22_B站好物测试前线.md
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
  milestone_messages:
  - 老板，连续作战30天，达成习惯养成里程碑。根据图谱，此阶段之后应优先检查稳定增长路径，而不是频繁换方向。
  red_alert_messages: []
```
