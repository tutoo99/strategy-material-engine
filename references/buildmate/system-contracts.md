# Buildmate 系统合同

这份文档只回答一件事：让四阶段系统真正闭环，还缺哪两份正式合同。

## 合同一：`strategy_node_patch`

作用：

- 把阶段二产出的新诊断逻辑，转成阶段三可消费的“节点化补丁”。
- 避免阶段二输出只能靠人读懂，再手工翻译到图谱。

正式位置：

- `strategy_models/node_patches/*.md`

核心字段：

- `source_ref`
- `source_type`
- `node.node_id`
- `node.node_name`
- `node.node_type`
- `trigger_conditions`
- `applicable_params`
- `not_applicable_warning`
- `action_refs`
- `template_refs`
- `tool_refs`
- `preferred_case_refs`
- `evidence_case_refs`
- `proposed_edges`

当前规则：

- 节点补丁本身不是正式图谱索引。
- 它是“可被阶段三和阶段四消费的标准中间件”。

## 合同二：`change_request`

作用：

- 把阶段四的学习结论转成可执行工单。
- 避免反馈只停留在“建议修正”而无法自动写回。

正式位置：

- `stage4_models/change_requests/*.md`

核心字段：

- `source_ref`
- `target_stage`
- `change_type`
- `target_ref`
- `patch_mode`
- `manual_fallback_required`
- `changes`
- `validation_commands`
- `rebuild_actions`

当前执行器：

- `scripts/apply_change_request.py`

当前能力边界：

- 支持 `append / append_section / create_file`
- 只允许写入正式系统目录
- 只允许执行白名单验证与重建命令

## 推荐最小闭环

1. 阶段二产出 `strategy_node_patch`
2. 阶段四基于反馈生成 `change_request`
3. 执行器应用 `change_request`
4. 自动运行验证命令
5. 自动运行重建动作
6. 下次阶段三 / 阶段四直接读取更新后的正式文件
