---
type: method
primary_claim: 多主题系统里，preview.md 不只是展示文件，还应该承担回归校验样例的职责
claims:
  - 预览样例能把随机肉眼抽查变成稳定回归检查
  - 改渲染器时必须有固定的区块覆盖样本
tags: [测试, 主题系统, 回归校验, 预览]
role: argument
strength: observation
channel_fit: [wechat, general]
source: .hermes/skills/wechat-factory/wechat-publisher/work/2026-04-19_qiaosan_theme_schema_v1_upgrade/final.md
date: 2026-04-20
quality_score: 3.6
source_reliability: 3.8
review_status: reviewed
---

一旦主题从一套变成多套，每次改渲染器都靠随机抽几篇文章肉眼看，是很容易漏问题的。

做法：
1. 在 `preview.md` 里固定一组最小回归样例
2. 样例必须覆盖所有容易出错的区块：标题、列表、引用、代码块、表格、分割线
3. 每次主题或渲染器有变动时，用同一批样例做对照检查
4. 发现偏差立即修，不要"先放着回头再看"

原理：preview.md 表面上是预览文件，本质上承担的是质量守门员的职责。把随机肉眼抽查变成固定回归检查，多主题系统才能稳定迭代。
