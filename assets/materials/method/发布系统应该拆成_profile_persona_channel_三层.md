---
type: method
primary_claim: 多账号内容系统要稳定，必须把 profile、persona、channel 三层拆开
claims:
  - 登录态、内容约束、业务入口不该混在一个对象里
  - 多账号系统要靠映射层降低维护脑力税
tags: [系统设计, 发布系统, channel, persona, profile]
role: argument
strength: firsthand
channel_fit: [wechat, general]
source: .hermes/skills/wechat-factory/wechat-publisher/work/2026-04-18_qiaosan_channel_upgrade/final.md
date: 2026-04-20
quality_score: 4.7
source_reliability: 4.4
review_status: approved
---

如果一套发布系统同时承载"登录后台""决定写作口吻""选择业务入口"三件事，短期能跑，长期一定乱。

拆法：
1. `profile` — 只保存哪个公众号的登录态（认证层）
2. `persona` — 只约束这类内容怎么写（风格层）
3. `channel` — 只做业务映射，告诉系统这篇内容该加载哪套 persona、走哪个 profile、归档到哪个目录（路由层）

使用方式：写文章时只需要回答一个问题——这篇内容发哪个 channel。后面的登录态、内容风格、归档规则都由系统顺着映射往下走。新增账号时也不需要再同时记四五个概念，维护成本明显下降。
