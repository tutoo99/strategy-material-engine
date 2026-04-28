# 阶段四操作说明：个性化商业智能体闭环

当前阶段四的目标是：

1. 建立用户级商业档案。
2. 维护每个业务前线的数据看板。
3. 把阶段三执行反馈转成学习动作。
4. 自动生成带执行包的每周战略复盘会。
5. 把学习动作沉淀成正式 `change_request`，供执行器自动写回前置阶段。

## 生成档案

```bash
python3 scripts/run_stage4_cycle.py \
  --mode init-profile \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --owner-name '星河' \
  --monthly-cashflow '5000元' \
  --weekly-hours '10小时' \
  --skill '写作' \
  --startup-resource 'B站账号1个' \
  --goal-12m '打造一个月入1万的知识产品业务' \
  --risk-score 3 \
  --focus-area '内容创作'
```

生成档案时会同时产出：

- `stage4_models/profile/owner_profile.md`：系统正式读取的结构化档案
- `【我的商业档案】.md`：系统根目录下的人类入口文档

正式档案正文应使用问答式结构填写 `资源画像` 和 `目标与偏好`，并保留 `Structured Owner Profile` 供脚本读取。档案更新周期默认为 `quarterly`，即每季度至少更新一次。

正式档案还应显式写出：

- 全部业务前线总表
- 每个前线对应的 `【数据看板】`
- 交互人格：人格原型、语气设定、重大挫折回应方式
- 主动关怀里程碑：例如连续更新 30 天触发里程碑消息
- 红色警报协议：例如核心指标连续 3 天下降超过 30% 时强制打断并推送诊断入口
- 人类判断协议：每次周复盘必须保留 2-3 个可选路径，并要求操作者填写选择理由
- 默认数据同步协议：每天下午 `17:00`，花 `10分钟` 手动同步一次

## 同步数据看板

```bash
python3 scripts/run_stage4_cycle.py \
  --mode sync-dashboard \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --frontline-name 'B站内容副业主号' \
  --platform 'B站' \
  --domain '内容副业' \
  --metric '粉丝数=3200' \
  --metric '近7日均阅读=950'
```

每个看板除 `核心指标 / 内容表现 / 待办事项` 外，还应包含：

- `内容表现采集口径`：标题、封面、核心数据、评论待回复
- `主动关怀消息`：已触发的里程碑消息
- `红色警报协议 / 红色警报消息`：核心指标异常时的强制打断规则与消息
- `手动同步机制`：默认沿 owner profile 中的每日 `17:00 / 10分钟` 协议

如果看板预警等级进入 `critical`，系统现在还会同步产出：

- `expert_models/sessions/..._red_alert.md`：自动触发的阶段二红色警报诊断
- `stage4_models/dispatches/..._red_alert.md`：阶段四正式自动派发记录

自动派发记录的作用不是重复报错，而是显式说明：

- 系统已经派发了哪个阶段二诊断入口
- 阶段一补库是否已经由系统挂起
- 当前在等待什么条件后自动重入下一轮诊断

## 处理执行反馈

```bash
python3 scripts/run_stage4_cycle.py \
  --mode process-feedback \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --source-stage3-session 'strategy_models/sessions/2026-04-22_B站_获取初始精准流量.md' \
  --executed-task 'T1' \
  --metric-change '首轮播放=300->920' \
  --improved partial \
  --new-bottleneck '承接入口还不够清晰' \
  --allow-dashboard-update \
  --allow-review-generation
```

执行反馈产物中，系统会额外生成：

- `有效性评分`
- `模型修正项`
  - `修正图谱`
  - `修正专家模型`
  - `更新资源库`
- `stage4_models/change_requests/*.md`
  - 当反馈已经足够具体时，应优先沉淀为正式变更请求，而不是只停留在文字建议。

## 生成每周复盘

```bash
python3 scripts/run_stage4_cycle.py \
  --mode generate-review \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --source-feedback 'stage4_models/feedback/xxxx.md' \
  --week-range '2026-04-20 ~ 2026-04-26'
```

生成出来的周复盘不应只是“下周做什么”的摘要，而应尽量具备：

- 档案摘要：目标、可投入时间、风险偏好、主偏好能力
- 数据摘要：最近核心指标的快照
- 图谱推演：当前目标对应的主策略和组合策略
- 交互人格输出：按 owner profile 里的语气设定输出
- 主动关怀与警报：里程碑消息或红色警报消息
- 任务级执行包：诊断、动作、预计耗时、执行步骤、资源入口、成功检查
- 执行阻力控制：每个任务必须给出认知负荷、上下文切换、阻力评分、最小下一步和聚合执行建议
- 决策留白：必须给出 2-3 个可选路径，标记推荐项，并要求操作者写下选择理由
- 老板确认项：阅读确认、授权看板更新、承诺回填反馈

阶段四生成周复盘时，不能把“给出任务包”当成结束。系统必须额外做两件事：

- 先压低执行断层：如果任务跨多个平台或步骤过多，要明确写出 `最小下一步`，并提示是否存在同步、复制、发布类聚合自动化空间。
- 再保留人的判断训练：即使系统有推荐路径，也必须保留至少一个修正优先路径和一个最小闭环路径，避免操作者退化为按钮操作员。

## 生成月度模型修正会

```bash
python3 scripts/run_stage4_cycle.py \
  --mode generate-model-review \
  --root '/Users/naipan/.hermes/skills/strategy-material-engine' \
  --source-feedback-ref 'stage4_models/feedback/xxxx.md' \
  --source-feedback-ref 'stage4_models/feedback/yyyy.md' \
  --month-range '2026-04'
```

这个产物的用途不是再讲一遍经验，而是把多条反馈合并成正式的模型修正清单，供阶段一 / 二 / 三回写使用。

## 执行系统变更请求

先校验：

```bash
python3 scripts/validate_change_request.py stage4_models/change_requests/<request-file>.md
```

再执行：

```bash
python3 scripts/apply_change_request.py stage4_models/change_requests/<request-file>.md
```

当前执行器是最小安全版：

- 支持 `append / append_section / create_file`
- 只允许写入正式系统目录
- 只允许执行白名单里的验证和重建命令
- 目标是先打通“反馈 -> 工单 -> 写回 -> 校验”的最小闭环

## 校验命令

```bash
python3 scripts/validate_stage4_artifact.py stage4_models/profile/owner_profile.md
python3 scripts/validate_stage4_artifact.py stage4_models/dashboards/<dashboard>.md
python3 scripts/validate_stage4_artifact.py stage4_models/feedback/<feedback>.md
python3 scripts/validate_stage4_artifact.py stage4_models/reviews/<review>.md
python3 scripts/validate_stage4_artifact.py stage4_models/dispatches/<dispatch>.md
python3 scripts/validate_change_request.py stage4_models/change_requests/<request>.md
```

## 当前阶段四 v1 能力边界

- 能生成正式档案、看板、反馈记录和周复盘。
- 能根据阶段三反馈自动判断是否建议回流阶段二或阶段一。
- 能把学习动作写成正式结构化记录。
- 现已支持最小版 `change_request` 执行器，可自动执行安全的追加类写回。
- 但阶段四现在会生成正式 `模型修正项` 与 `月度模型修正会`，把修正需求沉淀成稳定工单，而不是停留在口头总结。
- 当看板触发红色警报时，会自动生成阶段二诊断入口与阶段四自动派发记录；若证据不足，会在派发记录里显式转为阶段一补库优先。
