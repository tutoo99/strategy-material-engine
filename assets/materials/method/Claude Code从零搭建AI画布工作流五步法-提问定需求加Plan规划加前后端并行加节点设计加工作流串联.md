---
type: method
primary_claim: 用Claude Code从零搭建AI画布工作流的五步法——提问定需求→Plan模式规划→前后端双线并行→节点设计→工作流串联
claims:
  - 工具：Claude Code + claude-opus-4-5-thinking模型（或claude-sonnet-4-5-thinking省钱）
  - 第一步：用AskUserQuestion工具让AI提16个高质量问题确保理解需求，回答总结存为claude.md
  - 第二步：Plan模式（Shift+Tab切换）规划架构，给API文档让AI自己读
  - 第三步：前后端双线并行，同时开2-3个终端分别处理不同模块
  - 第四步：前端节点UI设计，先参考现有产品截图给AI做UI草图，确定后再实现
  - 第五步：工作流串联，上游输出作为下游输入，逐个执行
  - 关键坑：数据转换最容易出错，不同模型（文生图/图生图/图生视频/视频理解/图片理解）参数不一样
  - 如果没有强设定每个模型之间的参数转换，AI编程会让你每天都在改bug的路上
  - 可以在Claude Code中同时使用GPT和Gemini，用各模型擅长的能力
  - 前端用React Flow做无限画布，后端用Go处理高并发
  - 本地存储用IndexedDB+LocalStorage
tags: [Claude Code, AI编程, 画布工作流, React Flow, AI漫剧, 从0到1, AI开发]
ammo_type: substance
role: argument
strength: firsthand
channel_fit: [general]
source: 生财有术-李澹归-用AI编程搭建AI漫剧工作流
date: 2026-01
quality_score: 3.0
use_count: 0
last_used_at:
used_in_articles: []
impact_log: []
source_reliability: 3.0
review_status: draft
---

Claude Code从零搭建AI画布工作流五步法（李澹归实战）

核心工具：
- Claude Code + claude-opus-4-5-thinking（迄今最聪明的模型）
- 中转API 35块1亿token（相当于400刀额度）
- 前端：React Flow（无限画布）
- 后端：Go（高并发）
- 存储：IndexedDB+LocalStorage（本地）

五步法：

第一步：提问定需求
- 用AskUserQuestion工具让AI提16个高质量问题
- 不知道怎么回答可以问GPT
- 回答完把总结存为claude.md（项目上下文文件）
- 核心认知：AI每次回答不一样，像分清萝卜还是纸巾的游戏

第二步：Plan模式规划
- Shift+Tab切换到Plan模式
- 直接给API文档URL让AI自己读
- Plan结束后跳对话框直接Enter继续
- CC只用两个内置工具：AskUserQuestion + Plan

第三步：前后端双线并行
- 同时开2-3个终端处理不同模块
- 一个终端跑后端API，一个跑前端页面
- 大规模重构了2次架构（前半个月不断踩坑）

第四步：前端节点UI设计
- 去TapNow等参考产品截图
- 截图+提示词一起发给AI做UI草图
- 先出草图确认方向→再实现→后续再美化
- "基本满足要求先实现后续再微调"

第五步：工作流串联
- 开始节点仅作为执行开关
- 上游输出作为下游输入按顺序执行
- 连接线逻辑和UI是难点需要反复调试

最大坑：数据转换
- 文生图、图生图、图生视频、视频理解、图片理解，每个模型参数都不一样
- 没有强设定参数转换=每天在改bug的路上

进阶技巧：
- 可以在Claude Code中同时调用GPT和Gemini
- 理解agent逻辑→像N8N/Coze一样创建工作流
- 理解skills逻辑→通过@功能实现画布全局记忆
- 节点有名字→所有提示词/图片/视频资产可复用

产品定价逻辑（三块成本）：
1. 网站使用成本（API+服务器+数据库）
2. 运营成本（分销+活动+拉新）
3. 市场竞争平衡（同质化时优势在哪）
订阅制=对冲，积分过期，用户量上来不可能所有人使用量一样，和保险逻辑类似