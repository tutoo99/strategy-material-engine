# 阶段三产品化交付

这份目录就是阶段三第 6 步的正式交付物。

包含两类核心产物：

1. **可视化图谱**
   - 文件：`stage3_strategy_map.drawio`
   - 用途：在 draw.io 中直接打开，查看当前情境节点、目标节点、策略节点，以及“适用 / 禁区”关系。

2. **推演问答脚本**
   - 文件：`stage3_questionnaire.yaml`
   - 用途：作为阶段三问卷入口，收敛情境、目标、平台、领域和资源约束，再自动触发策略推演。

## 运行入口

### 1. 重新导出可视化图谱

```bash
/opt/miniconda3/bin/python3 scripts/export_stage3_visual_map.py --root '/Users/naipan/.hermes/skills/strategy-material-engine'
```

### 2. 查看正式问答脚本

```bash
/opt/miniconda3/bin/python3 scripts/run_stage3_questionnaire.py \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --print-questionnaire
```

### 3. 用问答脚本直接触发阶段三推演

```bash
/opt/miniconda3/bin/python3 scripts/run_stage3_questionnaire.py \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --situation-id S001 \
  --goal-id goal_initial_precise_traffic \
  --platform-id PLATFORM_BILIBILI \
  --domain-id DOMAIN_CONTENT_ECOM \
  --constraint-id C001 \
  --constraint-id C002
```

## 当前交付定位

- `stage3_strategy_map.drawio` 负责“看全局地图”
- `stage3_questionnaire.yaml` 负责“收答案”
- `run_stage3_questionnaire.py` 负责“把答案转成正式阶段三会话和方案包”

这三者共同组成阶段三的产品化交付，而不再只是底层索引和命令行参数。
