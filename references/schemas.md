# 统一 Schema

## 一、Source

所有原始内容先进入 `sources/`。

```yaml
---
source_type: article
title: 标题
author: 作者
origin: 公众号
date: 2026-04-24
tags: [内容, 观点]
link: https://example.com
summary: 一句话摘要
---
```

## 二、Case

只有满足“可复用商业执行链”的内容才进入 `assets/cases/`。

case frontmatter 在兼容原 buildmate 的基础上，新增推荐字段：

```yaml
retrieval_tags: [获客, 小红书, 低成本]
retrieval_summary: 这是一条适合低成本获客检索的案例摘要
derived_material_refs: []
source_refs:
  - sources/buildmate/xxx.md
```

### 建 case 的最低判断标准

至少满足以下 3 项：

- 有明确目标
- 有执行动作
- 有路径选择
- 有结果/反馈
- 有可迁移做法

纯观点文、纯情感文默认不建 case。

## 三、Material

material 是原子化可复用单元，放在 `assets/materials/`。

```yaml
---
type: insight
primary_claim: 高估选择价值，低估打出来的价值
claims:
  - 真正决定成败的是能不能做出来并拿反馈
tags: [决策, 行动力]
ammo_type: dual
role: argument
strength: observation
channel_fit: [general]
source: 某篇文章标题
source_refs:
  - sources/materials/某篇文章.md
derived_from_case:
date: 2026-04-24
quality_score: 3.0
use_count: 0
last_used_at:
used_in_articles: []
impact_log: []
source_reliability: 3.0
review_status: draft
---
```

### type 受控词表

- `story`：故事
- `insight`：洞察
- `data`：数据点
- `method`：方法/SOP
- `quote`：金句
- `association`：联想/发散
- `playbook`：行动卡/打法卡

## 四、统一检索结果字段

所有统一搜索结果最终投影成：

```json
{
  "asset_type": "case | material | source",
  "subtype": "case / story / quote / source_chunk / ...",
  "path": "相对路径",
  "score": 0.0,
  "preview": "摘要",
  "why_matched": "为什么命中",
  "source_refs": []
}
```
