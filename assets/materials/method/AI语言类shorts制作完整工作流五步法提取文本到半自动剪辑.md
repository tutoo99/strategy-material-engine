---
title: AI语言类shorts制作完整工作流五步法
type: method
primary_claim: 语言类shorts制作五步工作流：GAS提取字幕+角色替换→批量TTS生成音频→参考图批量生图→Veo3/Sora2图转视频→半自动剪映剪辑
claims:
  - 第一步提取文本：把链接和要求发给GAS提取字幕，更换角色（儿童→成人），修改不合情节内容，导出JSON
  - 第二步生成音频：用aihotvideos网站批量生成TTS音频，或用veo3.1直接生成音画同步
  - 第三步生成图片：按小黄教练故事板提示词修改角色后导出CSV，用aihotvideos批量生图（参考图模式）
  - 第四步生成视频：用CineDream提示词模板让AI生成视频提示词，Veo3/Sora2图转视频
  - 第五步半自动剪辑：用capcut auto脚本自动对齐音频和视频，自动剪气息，视频部分仍需手动剪辑
  - 配音工具对比：veo3.1直接生成效果最好感情最丰富，elevenlabs V3多标签次之，单标签最差
  - 联署营销：前期随便带，找到高点击率链接后把商品P到视频里ALLIN
tags: 四水年华,AI语言类,YouTube,Shorts,工作流,GAS,elevenlabs,Veo3,Sora2,剪映
source: 月入5000美金的AI语言类Shorts实战复盘
source_refs:
  - 月入5000美金的AI语言类Shorts实战复盘.md
date: 2025-12
---

# AI语言类shorts制作完整工作流五步法

## Step 1：提取文本+角色替换
- 链接发给GAS提取字幕（也可用哼哼猫等下载软件）
- 更换角色：儿童→成人（Sakura→Rumi, Naruto→Abby, Mom→Mira, Dad→Jinu）
- 检查修改后内容有无情节不符，人工纠错
- 导出JSON供TTS使用

## Step 2：批量生成音频
- 工具：aihotvideos批量TTS
- 或用veo3.1/海螺V3.1直接生成音画同步（省去配音步骤）
- ElevenLabs V3情绪标签提示词：三阶段协议（提取→格式化注入情绪标签→生成JSON）

## Step 3：批量生成图片
- 用小黄教练故事板提示词模板修改角色
- 导出CSV → aihotvideos批量生图（参考图模式）

## Step 4：图转视频
- 用CineDream Architect提示词模板生成视频提示词
- Veo3/Sora2图转视频

## Step 5：半自动剪辑
- capcut auto脚本：自动对齐音频视频、自动剪气息
- 视频部分仍需手动剪辑
- 配置config.json修改素材根目录和剪映草稿路径

## 配音质量对比
veo3.1直接生成 > elevenlabs V3多标签 > elevenlabs V3单标签
