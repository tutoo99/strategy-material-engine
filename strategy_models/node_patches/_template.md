---
artifact_type: strategy_node_patch
patch_id: strategy_node_patch_example
title: 【阶段二 -> 阶段三节点补丁】待补充
status: draft
source_stage2_ref: expert_models/manuals/_template.md
target_node_id: N999
node_type: strategy
date: 2026-04-22
---

# 【阶段二 -> 阶段三节点补丁】待补充

## 来源专家模型

- **来源文件：** `expert_models/manuals/_template.md`
- **来源类型：** `manual / session / practicum`
- **补丁原因：** 待补充

## 节点定义

- **节点名称：** 待补充
- **节点类型：** `strategy / situation / goal / resource`
- **适用情境：** 待补充
- **禁区提醒：** 待补充

## 路由边补丁

- 待补充

## 资源调用索引

- **动作包：**
- **模板资源：**
- **工具调用：**
- **证据案例：**

## Structured Strategy Node Patch

```yaml
strategy_node_patch:
  patch_id: strategy_node_patch_example
  source_ref: expert_models/manuals/_template.md
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
