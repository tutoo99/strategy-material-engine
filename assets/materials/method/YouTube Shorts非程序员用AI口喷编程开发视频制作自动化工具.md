---
type: method
title: YouTube Shorts非程序员用AI口喷编程开发视频制作自动化工具
primary_claim: 非程序员通过AI编程工具Cursor搭载GLM4.7开发了几万行代码的YouTube Shorts视频制作自动化工具，覆盖从下载对标到批量生成的全流程
claims:
  - 非程序员一行代码没写过全靠口喷编程，用Cursor搭载Kimi和GLM4.7代替Claude
  - Claude号被封后改用Cursor方案，后来用Google Antigravity搭载Gemini 3 Pro和Claude Opus 4.5
  - 自动化工具支持7大功能：视频下载、分场景首帧提取、图片提示词反推、视频提示词反推、爆款脚本CSV存档、参考角色库、并行多模型多图多视频生成
  - 成本参考NanoBanana Pro约0.2元一张图，Veo 3.1约0.35元一个视频
  - 工具痛点是流程过于线性不够灵活，计划转向Comfy UI/N8N风格的工作流式流程
tags: 天才老师,YouTube,Shorts,AI编程,自动化,Cursor,GLM,生财有术
source: 大学老师初入油管21天2400万观看初级YPP审核失败复刻AI视频流水线
source_refs:
  - sources/materials/大学老师初入油管21天2400万观看初级YPP审核失败复刻AI视频流水线.md
date: 2025-12-31
---

## 自动化工具开发路径

天才老师不是程序员，在做好第一条视频梳理完工作流后立即开始开发自动化工具。第2条到后续所有视频全部通过自己的工具制作。

技术栈：
- 编程工具：Cursor（Claude被封后改用）
- AI模型：先用Kimi+GLM4.7，后用Google Antigravity搭载Gemini 3 Pro和Claude Opus 4.5
- API调用：云雾API并行多模型生成

功能模块：
1. 视频下载（需导出浏览器Cookies绕过机器人检测）
2. 分场景首帧提取
3. 场景帧图片提示词反推
4. 视频提示词反推
5. 爆款脚本输出CSV存档
6. 参考角色库（乞丐Rumi、圣诞节Mira等角色形象统一管理）
7. 并行多模型多图多视频生成

## 关键启示
- 先手动跑通完整流程，再自动化，这样知道每个环节的卡点和需求
- 工具开发的目标是解决手动切换工具、管理内容资产的痛点
- 流程线性是常见问题，工作流式架构是下一步方向
