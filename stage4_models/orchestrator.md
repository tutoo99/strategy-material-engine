---
orchestrator_id: stage4_orchestrator
title: 【阶段四总控】个性化商业智能体编排器
scope: 阶段四
status: active
version: v1.0
date: 2026-04-22
---

# 【阶段四总控】个性化商业智能体编排器

## 目标

- 把阶段三的执行反馈变成用户级长期学习闭环。
- 先更新阶段四自己的状态层，再决定是否回流到阶段二或阶段一。
- 只有系统故障或输入严重缺失时，才允许人工接管。

## 正式入口

- `阶段四档案初始化`
- `阶段四数据同步`
- `阶段四执行反馈`
- `阶段四周复盘生成`

## 读取顺序

1. `stage4_models/profile/`
2. `stage4_models/dashboards/`
3. `strategy_models/sessions/`
4. `strategy_models/audits/`
5. `expert_models/sessions/`
6. `cases/` 与索引

## 写入顺序

1. 先写 `stage4_models/feedback/`
2. 再更新 `stage4_models/dashboards/`
3. 如触发红色警报，生成 `stage4_models/dispatches/`
4. 再生成 `stage4_models/change_requests/`
5. 再生成 `stage4_models/reviews/`
6. 最后输出学习动作与模型修正项，决定是否建议回流阶段二或阶段一

## 回流规则

- 如果当前问题主要是执行偏差，优先留在阶段四内处理。
- 如果阶段三路径命中但路由不稳，输出 `stage3_route_update_needed`。
- 如果执行后暴露的是症状识别错误，输出 `stage2_diagnosis_update_needed`。
- 如果当前平台没有正式证据，输出 `stage1_replenishment_needed`。
- 如果问题已经足够具体，优先同时生成 `change_request`，而不是只停留在自然语言回流建议。
- 阶段四 v2 会把反馈拆成 `修正图谱 / 修正专家模型 / 更新资源库` 三类模型修正项。
- 如果看板进入红色警报，必须显式生成自动派发记录，把 `阶段二自修正` 与 `阶段一补库` 写成正式工单链。
- 阶段四现在允许通过 `change_request` + 执行器完成最小安全写回；复杂变更仍可保留人工兜底。
- 生成周复盘时，必须同时输出 `执行阻力控制` 和 `决策留白`，避免任务包变成高复杂度工单堆积。
- 即使系统给出推荐路径，也必须保留至少一个“先修正判断”选项和一个“最小下一步”选项，维持人的判断训练。

## 风险边界

- 不能把“无改善”一律当成阶段三失败。
- 不能在没有平台证据时硬凑下一周任务包。
- 不能把需要人工理解的异常写成系统已经完成。
