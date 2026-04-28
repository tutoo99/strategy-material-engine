---
type: method
primary_claim: 想让主题系统可扩展、可推荐、可演进，theme pack 应该拆成五层文件
claims:
  - 多主题系统需要把身份、设计 token、区块样式、推荐规则、预览样例拆开
  - 主题包分层后，渲染器和推荐器才能各读各的
tags: [主题系统, schema, theme pack, 可扩展性]
role: argument
strength: firsthand
channel_fit: [wechat, general]
source: .hermes/skills/wechat-factory/wechat-publisher/work/2026-04-19_qiaosan_theme_schema_v1_upgrade/final.md
date: 2026-04-20
quality_score: 4.3
source_reliability: 4.2
review_status: approved
---

如果主题系统未来不只是"多两个皮肤"，而是要支持自动推荐和长期扩展，那么最稳的做法不是继续往一个大文件里加字段，而是拆成一个 theme pack：

拆法：
1. `manifest.yaml` — 主题是谁、适合谁（身份层）
2. `tokens.yaml` — 颜色、字号、间距等设计 token（样式层）
3. `blocks.yaml` — 标题、引用、代码块、表格等区块样式（区块层）
4. `heuristics.yaml` — 推荐偏好和避让规则（推荐层）
5. `preview.md` — 最小预览和回归样例（校验层）

原理：五层不是"看起来更专业"，而是把原来混在一起的职责拆开。拆开后，渲染器、推荐器、人工维护三方各读各的，不会互相扯着走。
