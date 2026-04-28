# Schemas

## Material template

```yaml
---
type: story
primary_claim: 这里写主论点
claims:
  - 这里写可复用的次级论点
tags: [标签1, 标签2]
ammo_type: hook
role: argument
strength: anecdote
channel_fit: [general]
source: 原始来源
source_uid: url/content/meta 指纹ID，入库脚本自动生成
canonical_url: 规范化后的原始链接，入库脚本自动生成
content_sha256: 规范正文哈希，入库脚本自动生成
simhash64: 近似正文指纹，入库脚本自动生成
date: 2026-04-23
quality_score: 3.0
use_count: 0
last_used_at:
used_in_articles: []
impact_log: []
source_reliability: 4.0
review_status: draft
---
```

```md
这里写加工后的可直接使用素材正文。
```

### Material metadata fields

#### 核心字段

- `type`: 素材类型 — `story`（故事）、`insight`（洞察）、`data`（数据）、`method`（方法）
- `primary_claim`: 主要检索意图，一句话概括核心观点
- `claims`: 辅助声明，可选
- `tags`: 自由标签，用于辅助检索
- `source`: 来源标识
- `source_uid`: 来源唯一标识，优先由规范 URL 生成，其次由正文哈希生成
- `canonical_url`: 去掉 utm/分享参数后的来源 URL，用于检测同链接重复入库
- `content_sha256`: 去 frontmatter/空白/排版噪声后的正文哈希，用于检测强重复
- `simhash64`: 近似文本指纹，用于检测改标题、改排版、少量删改后的重复来源
- `duplicate_of`: 仅在强制保留重复副本时填写，指向已有来源路径
- `date`: 素材日期

#### 弹药分类字段

- `ammo_type`: **受控词表**，只能取三个值：
  - `hook`（弹药型）— 读完让人想转发的：金句、故事、反常识观点、情绪共鸣点
  - `substance`（粮仓型）— 读完让人觉得学到东西的：方法论、数据、SOP、实操复盘
  - `dual`（双栖型）— 两者兼具的
  - 提取时凭直觉标，不纠结；发布后用 impact_log 反馈纠偏

#### 渠道适配字段

- `channel_fit`: 适配的发布渠道和赛道，建议粒度示例：
  - `general` — 通用，任何渠道都能用
  - `流量号-情感` — 情感类流量号
  - `流量号-成长` — 成长类流量号
  - `流量号-职场` — 职场类流量号
  - `技术号-AI` — 技术号AI方向
  - `技术号-测试` — 技术号测试方向
  - `video` — 视频号口播
  - `xiaohongshu` — 小红书
  - 多选：`[流量号-情感, 流量号-成长]`

#### 文章角色字段

- `role`: 在文章中的角色 — `hook`（钩子）、`opening`（开头）、`argument`（论证）、`turn`（转折）、`ending`（结尾）
- `strength`: 说服力来源 — `anecdote`（轶事）、`observation`（观察）、`data`（数据）、`firsthand`（亲历）

#### 质量追踪字段

- `quality_score`: `1.0 ~ 5.0`，初始为 3.0，靠反馈数据自然跑分，不手动拍
- `use_count`: 已被引用次数
- `last_used_at`: 最近一次使用时间，ISO 日期或日期时间
- `used_in_articles`: 用过这条素材的文章标识列表
- `source_reliability`: 来源可靠度，`1.0 ~ 5.0`
- `review_status`: `draft / reviewed / approved`
- `impact_log`: 使用效果回写记录，每条格式：
  ```yaml
  - article: 文章标识
    date: 2026-04-23
    impact: traffic    # traffic / trust / both / none
    note: 评论区多次引用，转发效果明显
  ```

### 隐私脱敏规则（入库必须执行）

素材正文**必须脱敏**后才能存入 materials/，具体规则：

| 内容类型 | 处理方式 | 示例 |
|---------|---------|------|
| 具体人名 | 替换为角色描述 | 亦仁 → "一位做知识付费的创业者" |
| 具体公司/组织名 | 替换为泛化描述 | 生财有术 → "一个社群产品" |
| 人名+公司+职位组合 | 去掉身份关联 | "亦仁在生财有术有60位同事" → "某创业者团队有几十人" |
| 具体金额/数字 | 保留 | 15%年化、60人 → 直接保留 |
| 论证链结构 | 保留 | 怎么论证的，是写文章要学的 |
| 比喻/金句 | 保留 | 好表达，LLM会重新表述 |
| 方法论步骤 | 保留 | 框架和SOP是核心价值 |

**保留的内容**（论证链、比喻、金句、方法论步骤）是素材库的核心价值，不要因为脱敏而删掉。脱敏只处理隐私信息，不处理内容表达。

#### 各类型素材正文格式要求

不同类型的素材正文必须用对应的结构，不能统一写成散文：

- **story**（故事）：保留场景、人物、动作、转折、结论。段落式，像在讲一个事。
- **insight**（洞察）：先抛观点，再给论据。可以用列表，但重点是观点清晰、论据有力。
- **method**（方法）：**必须写成步骤格式**，编号列出操作步骤，确保别人拿去就能照着做。关键步骤不能埋在段落里，必须独立成行。
- **data**（数据）：先给数据/事实，再说明它支撑什么结论。数据要具体，结论要明确。

## Source template

```yaml
---
source_type: transcript
title: 来源标题
author: 作者
origin: 来源平台或场景
date: 2026-04-23
tags: [标签1, 标签2]
source_uid: 入库脚本自动生成
canonical_url: 入库脚本自动生成
content_sha256: 入库脚本自动生成
simhash64: 入库脚本自动生成
---
```

```md
这里写原始文本、摘录或转写内容。
```
