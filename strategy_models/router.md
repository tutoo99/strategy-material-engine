---
router_id: strategy_router
title: 【策略路由器】阶段三目标推演与方案包组装
scope: 阶段三
status: active
version: v1.1
date: 2026-04-22
---

# 【策略路由器】阶段三目标推演与方案包组装

## 入口定义

- 唯一入口是：用户给出一个明确目标，而不是抽象症状。
- 人类入口说明先看：`strategy_models/graph_center.md`，先理解“节点 / 边 / 属性”分别是什么，再进入正式路由。
- 当前正式支持的目标族以 `strategy_models/routes/goal_profiles.yaml` 为准。
- 当目标不在当前支持范围内时，不直接报错，而是自动进入 `strategy_models/audits/` 自治审计链路。
- 当阶段二沉淀出新能力时，可额外产出 `strategy_models/node_patches/*.md`，供阶段三后续注册为正式节点或路由补丁。

## 目标收敛规则

- 必须收敛出：
  - 目标
  - 用户类型
  - 平台
  - 业务领域
  - 资源约束
- 如果用户输入不完整，允许采用合理默认值，但必须写入会话的 `用户情境卡`。

## 图谱召回规则

- 策略证据只允许来自：
  - `index/stage3/strategy_nodes.jsonl`
  - `index/stage3/situation_nodes.jsonl`
  - `index/stage3/resource_nodes.jsonl`
  - `index/stage3/strategy_resource_edges.jsonl`
  - `index/stage3/case_strategy_edges.jsonl`
  - `index/stage3/case_resource_edges.jsonl`
  - `index/stage3/strategy_strategy_edges.jsonl`
  - `index/stage3/goal_strategy_edges.jsonl`
  - `index/stage3/situation_strategy_edges.jsonl`
  - `index/stage3/strategy_situation_edges.jsonl`
- 路由规则只允许来自：
  - `strategy_models/routes/goal_profiles.yaml`
  - `strategy_models/routes/strategy_profiles.yaml`
- 资源引用只允许来自：
  - `strategy_models/resources/`
- 节点补丁输入允许来自：
  - `strategy_models/node_patches/`
- 每个被选中的策略节点必须能直接暴露最小资源集装箱属性：
  - `action_refs`
  - `template_refs`
  - `tool_refs`
  - `preferred_case_refs`
- 路由边必须能直接暴露最小路由属性：
  - `trigger_conditions`
  - `applicable_params`
  - `not_applicable_warning`
  - `call_output`
  - `reason`

## 路由判断规则

- 先按目标族拿主策略和组合策略候选。
- 再按平台、领域、用户类型和资源约束过滤。
- 如果命中当前情境的 `not_suitable_for` 关系边，必须把该策略从正式方案中剔除，并在会话里显示为禁区路径。
- 优先使用 `approved` 证据支撑的策略。
- 统计共现边时，只把它当组合提示，不把它当因果结论。
- 如果关键策略只有 `draft` 证据，必须降级为 `bootstrap`，并在风险提示中写明。
- 如果标准目标族未命中但当前证据层仍能召回相关案例和策略，系统允许自动合成 `bootstrap` 路径。
- 如果没有可用证据，系统必须自动挂起阶段一补库动作，不能把补库责任转给用户。

## 方案包输出规则

- 最终只交付一份阶段三方案包。
- 方案包必须同时包含：
  - Markdown 方案包
  - YAML `solution_package`
- 当进入自治审计时，还必须同步产出一份 `strategy_models/audits/*.md`。
- 当阶段四已经给出明确修正工单时，允许消费 `stage4_models/change_requests/*.md` 作为图谱更新的执行入口。
- 每个任务必须绑定：
  - `strategy_ref`
  - `case_refs`
  - `resource_refs`
  - `success_check`
- 每个资源引用都必须能落到真实文件或标准资源词。

## 证据分级规则

- `formal`：
  - 主策略都有真实证据支撑
  - 且至少有 1 个 `approved` 案例在当前路径中
- `bootstrap`：
  - 存在仅由 `draft` 支撑的关键策略
  - 或主策略证据不足但仍可给出内测版路径
  - 或标准路由失败后由自治学习链路自动合成的临时路径

## 风险提示规则

- 不能把证据不足伪装成成熟路径。
- 不能把平台资源词当成动作包。
- 不能把“强共现”误写成“必然顺序”。
- 只有系统故障、服务不可用等灾害场景，才允许人工接管；正常覆盖扩展必须优先走自治审计与系统补库。
