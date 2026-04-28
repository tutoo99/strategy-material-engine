#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import yaml

from _buildmate_lib import read_markdown, slugify, write_markdown
from validate_session import validate_session
from validate_stage4_artifact import validate_stage4_artifact


DEFAULT_PROFILE_REF = "stage4_models/profile/owner_profile.md"
PROFILE_ENTRY_REF = "【我的商业档案】.md"
PLATFORM_MARKERS = [
    "B站",
    "小红书",
    "抖音",
    "知乎",
    "微信",
    "企微",
    "知识星球",
    "小报童",
    "飞书",
    "稿定设计",
    "Notion",
    "Draw.io",
    "Miro",
    "Zapier",
    "IFTTT",
]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def default_sync_protocol() -> dict:
    return {
        "frequency": "daily",
        "time": "17:00",
        "duration": "10分钟",
        "method": "手动同步",
        "instruction": "每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。",
    }


def default_content_capture_fields() -> list[str]:
    return ["标题", "封面", "核心数据", "评论待回复"]


def default_interaction_persona() -> dict:
    return {
        "archetype": "JARVIS",
        "tone": "简洁、直接、以数据为支撑，不做情绪化安慰。",
        "setback_response": "重大挫折时先指出事实和下一步诊断入口；如有相似案例，再引用案例给出可执行信心。",
        "humor_level": "low",
    }


def default_milestone_rules() -> list[dict]:
    return [
        {
            "id": "M001",
            "name": "连续作战30天",
            "trigger_metric": "连续更新天数",
            "operator": ">=",
            "threshold": 30,
            "message": "老板，连续作战30天，达成习惯养成里程碑。根据图谱，此阶段之后应优先检查稳定增长路径，而不是频繁换方向。",
        }
    ]


def default_red_alert_protocol() -> dict:
    return {
        "trigger": "任何核心业务指标连续3天下降超过30%",
        "threshold_days": 3,
        "drop_percent": 30,
        "interrupt_level": "red_alert",
        "action": "立即打断常规周复盘，推送最相关的阶段二专家模型诊断入口，并冻结新增扩张动作。",
        "diagnosis_entry": "阶段二重新问诊入口：run_stage2 / stage2_diagnosis_update_needed",
    }


def default_human_judgment_policy() -> dict:
    return {
        "decision_options_required": 3,
        "rationale_required": True,
        "decision_prompt": "本周只能押注一个主路径时，你选择哪一个？请写出选择理由。",
        "anti_skill_decay_rule": "每次周复盘必须保留 2-3 个可选路径，并要求操作者写下选择理由；每季度至少做一次不依赖自动推荐的手动推演。",
        "quarterly_manual_drill": True,
    }


def extract_yaml_block(body: str, heading: str) -> dict:
    match = re.search(
        rf"##\s+{re.escape(heading)}\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1).strip()) or {}
    return payload if isinstance(payload, dict) else {}


def extract_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^##\s+(.+)$", body, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[title] = body[start:end].strip()
    return sections


def normalize_bool(value: object) -> bool:
    return bool(value)


def parse_key_value(text: str) -> tuple[str, str]:
    if "=" not in text:
        return text.strip(), ""
    key, value = text.split("=", 1)
    return key.strip(), value.strip()


def parse_metric_changes(values: list[str]) -> list[dict]:
    changes: list[dict] = []
    for item in values:
        label, value = parse_key_value(item)
        before = ""
        after = value
        if "->" in value:
            before, after = [part.strip() for part in value.split("->", 1)]
        changes.append({"label": label, "before": before, "after": after})
    return changes


def build_owner_profile_body(payload: dict) -> str:
    resource_profile = payload["resource_profile"]
    goals = payload["goals_and_preferences"]
    interaction_preferences = ", ".join(goals["interaction_preferences"]) or "每周战略复盘"
    sync_protocol = payload.get("sync_protocol", default_sync_protocol())
    frontlines = payload.get("frontlines", [])
    interaction_persona = payload.get("interaction_persona", default_interaction_persona())
    milestone_rules = payload.get("milestone_rules", default_milestone_rules())
    red_alert_protocol = payload.get("red_alert_protocol", default_red_alert_protocol())
    human_judgment_policy = payload.get("human_judgment_policy", default_human_judgment_policy())
    lines = [
        f"# 【我的商业档案】{payload['owner_name']}",
        "",
        "## 资源画像",
        "",
        "- **Q1：我目前可用于商业探索的月度现金流是多少？**",
        f"  - **A1：** {resource_profile['monthly_cashflow']}",
        "- **Q2：我每周能稳定投入的时间块有多少小时？**",
        f"  - **A2：** {resource_profile['weekly_hours']}",
        "- **Q3：我的核心技能是什么？**",
        f"  - **A3：** {', '.join(resource_profile['core_skills']) or '待补充'}",
        "- **Q4：我现有的启动资源有哪些？**",
        f"  - **A4：** {', '.join(resource_profile['startup_resources']) or '待补充'}",
        "",
        "## 目标与偏好",
        "",
        "- **Q1：我未来 12 个月的核心商业目标是什么？**",
        f"  - **A1：** {goals['primary_goal_12m']}",
        "- **Q2：我的风险偏好如何？**",
        f"  - **A2：** `{goals['risk_score']}` / 10",
        "- **Q3：我更擅长 / 喜欢内容创作、流量运营还是产品交付？**",
        f"  - **A3：** {goals['focus_area']}",
        "- **Q4：我希望系统以什么频率和方式与我互动？**",
        f"  - **A4：** {interaction_preferences}",
        "",
        "## 当前主战场",
        "",
    ]
    for item in frontlines[:1]:
        lines.append(f"- {item}")
    lines.extend(["", "## 业务前线总表", ""])
    if frontlines:
        for item in frontlines:
            lines.append(f"- **前线：** {item} -> **看板：** `{infer_dashboard_ref(item)}`")
    else:
        lines.append("- 待补充")
    lines.extend(
        [
            "",
            "## 交互协议",
            "",
            f"- **互动频率：** {interaction_preferences}",
            "- **语气偏好：** 简洁、直接、以数据为支撑。",
            "- **主动提醒规则：** 当核心指标连续恶化时，优先触发预警与复盘。",
            "",
            "## 交互人格",
            "",
            f"- **人格原型：** {interaction_persona.get('archetype', 'JARVIS')}",
            f"- **语气设定：** {interaction_persona.get('tone', '简洁、直接、以数据为支撑，不做情绪化安慰。')}",
            f"- **重大挫折时的回应方式：** {interaction_persona.get('setback_response', '先指出事实和下一步诊断入口。')}",
            f"- **幽默程度：** {interaction_persona.get('humor_level', 'low')}",
            "",
            "## 主动关怀里程碑",
            "",
        ]
    )
    for item in milestone_rules:
        lines.append(
            f"- **{item.get('name', '待补充')}：** 当 `{item.get('trigger_metric', '待补充')}` {item.get('operator', '>=')} {item.get('threshold', '待补充')} 时，自动生成消息：{item.get('message', '待补充')}"
        )
    lines.extend(
        [
            "",
            "## 红色警报协议",
            "",
            f"- **触发条件：** {red_alert_protocol.get('trigger', '待补充')}",
            f"- **中断等级：** {red_alert_protocol.get('interrupt_level', 'red_alert')}",
            f"- **触发动作：** {red_alert_protocol.get('action', '待补充')}",
            f"- **诊断入口：** {red_alert_protocol.get('diagnosis_entry', '待补充')}",
            "",
            "## 人类判断协议",
            "",
            f"- **决策选项数量：** {human_judgment_policy.get('decision_options_required', 3)}",
            f"- **是否强制填写选择理由：** {'是' if human_judgment_policy.get('rationale_required', True) else '否'}",
            f"- **默认决策问题：** {human_judgment_policy.get('decision_prompt', '本周只能押注一个主路径时，你选择哪一个？请写出选择理由。')}",
            f"- **防能力退化规则：** {human_judgment_policy.get('anti_skill_decay_rule', '每次周复盘必须保留可选路径，并要求操作者写下选择理由。')}",
            f"- **季度手动推演：** {'开启' if human_judgment_policy.get('quarterly_manual_drill', True) else '关闭'}",
            "",
            "## 数据同步协议",
            "",
            f"- **同步频率：** {sync_protocol.get('frequency', 'daily')}",
            f"- **固定时间：** {sync_protocol.get('time', '17:00')}",
            f"- **预计耗时：** {sync_protocol.get('duration', '10分钟')}",
            f"- **同步方式：** {sync_protocol.get('method', '手动同步')}",
            f"- **执行说明：** {sync_protocol.get('instruction', '每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。')}",
            "",
            "## 档案维护",
            "",
            "- **更新周期：** 每季度至少更新一次。",
            "- **维护原则：** 系统对你的理解，完全基于这份档案的准确性。",
            "",
            "## Structured Owner Profile",
            "",
            "```yaml",
            yaml.safe_dump({"owner_profile": payload}, allow_unicode=True, sort_keys=False).strip(),
            "```",
        ]
    )
    return "\n".join(lines).strip()


def write_artifact(path: Path, meta: dict, body: str) -> None:
    write_markdown(path, meta, body)
    errors, warnings = validate_stage4_artifact(path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    for warning in warnings:
        print(f"WARNING: {warning}")


def build_profile_entry_body(profile_ref: str) -> str:
    profile_path = re.sub(r"^//+", "/", str((Path.cwd() / profile_ref).resolve()))
    return "\n".join(
        [
            "# 【我的商业档案】",
            "",
            "这是阶段四的人类入口文档。",
            "",
            f"- **正式档案位置：** `{profile_ref}`",
            "- **用途：** 记录资源画像、目标与偏好、当前主战场、业务前线总表、交互人格、主动关怀里程碑、红色警报协议、数据同步协议和交互协议。",
            "- **更新要求：** 每季度至少更新一次；发生资源、目标或偏好变化时应立即更新。",
            "",
            "## 使用说明",
            "",
            "- 你平时查看和维护时，从这份文档进入。",
            "- 系统运行时，读取正式档案而不是这份入口说明。",
            "",
            "## 正式档案入口",
            "",
            f"- [打开正式档案]({profile_path})",
        ]
    ).strip()


def load_profile(root: Path, ref: str) -> tuple[dict, dict]:
    path = root / ref
    if not path.exists():
        raise SystemExit(f"ERROR: 未找到 owner profile：{ref}")
    meta, body = read_markdown(path)
    payload = extract_yaml_block(body, "Structured Owner Profile").get("owner_profile", {})
    if not isinstance(payload, dict):
        raise SystemExit("ERROR: owner profile 缺少有效的 structured payload。")
    return meta, payload


def infer_dashboard_ref(frontline_name: str) -> str:
    return f"stage4_models/dashboards/{slugify(frontline_name)}.md"


def detect_milestone_messages(dashboard_payload: dict, milestone_rules: list[dict]) -> list[str]:
    metrics = dashboard_payload.get("metrics", []) if isinstance(dashboard_payload, dict) else []
    metric_map = {str(item.get("label", "")).strip(): str(item.get("value", "")).strip() for item in metrics}
    messages: list[str] = []
    for rule in milestone_rules:
        trigger_metric = str(rule.get("trigger_metric", "")).strip()
        raw_value = metric_map.get(trigger_metric, "")
        if not raw_value:
            continue
        match = re.search(r"-?\d+(?:\.\d+)?", raw_value)
        if not match:
            continue
        current_value = float(match.group(0))
        threshold = float(rule.get("threshold", 0) or 0)
        operator = str(rule.get("operator", ">=")).strip()
        passed = operator == ">=" and current_value >= threshold
        if passed:
            messages.append(str(rule.get("message", "")).strip())
    return list(dict.fromkeys(message for message in messages if message))


def detect_red_alert_messages(dashboard_payload: dict, red_alert_protocol: dict) -> list[str]:
    alert_level = str(dashboard_payload.get("alert_level", "")).strip()
    messages: list[str] = []
    if alert_level == "critical":
        messages.append(
            f"红色警报：{red_alert_protocol.get('trigger', '触发条件待补充')}。{red_alert_protocol.get('action', '请立即进入诊断。')} 诊断入口：{red_alert_protocol.get('diagnosis_entry', '待补充')}"
        )
    return messages


def select_stage2_case_refs(platform: str) -> list[str]:
    normalized = str(platform).strip()
    if "B站" in normalized:
        return [
            "cases/在B站教年轻人赚钱月入三万，从0成为数字游民，全流程底层逻辑分享.md",
            "cases/bilibili_case_approved.md",
            "cases/B站悬赏带货实战手册.md",
        ]
    if "YouTube" in normalized or "youtube" in normalized.lower():
        return ["cases/youtube_seedance2真人爆款视频.md"]
    return []


def build_stage2_red_alert_session_body(
    input_symptom: str,
    platform: str,
    frontline_name: str,
    dashboard_ref: str,
    case_refs: list[str],
    evidence_gap: str,
    diagnosis_hint: str,
) -> str:
    evidence_status = "bootstrap" if case_refs else "bootstrap"
    evidence_count = len(case_refs)
    retrieval_lines: list[str] = []
    if case_refs:
        for idx, ref in enumerate(case_refs, start=1):
            retrieval_lines.append(f"{idx}. `{ref}`")
    else:
        retrieval_lines.append("- 当前平台暂无正式病例，自动切换为阶段一补库模式。")

    checkpoint_lines: list[str] = []
    markdown_task_lines: list[str] = []
    yaml_tasks: list[dict] = []
    if case_refs:
        checkpoint_lines.extend(
            [
                "### 检查站点 1：确认红色警报是否来自症状识别错误",
                "- **检查项：** 当前指标下滑更像是内容问题、承接问题还是平台证据缺口？",
                "- **判断方法：** 先对照最近 3 天关键指标、内容变化和承接动作，确认主瓶颈归属。",
                "- **行动指令：** 把最近 3 天的异常动作按“内容 / 承接 / 平台证据”三类归档，再判断是否需要重开阶段二问诊。",
                "- **参数：** 最近 3 天；至少 3 个核心指标；至少 1 条异常内容记录。",
                "- **资源引用：** 红色警报协议 / 数据看板 / 已召回病例",
                "- **对应病例：**",
            ]
        )
        for ref in case_refs[:2]:
            checkpoint_lines.append(f"  - `{ref}`")
        checkpoint_lines.extend(
            [
                "",
                "### 检查站点 2：用最小修复动作先止损",
                "- **检查项：** 当前是否应该停止扩张并先执行最小诊断动作？",
                "- **判断方法：** 如果核心指标连续恶化且原因未明确，先冻结扩张动作，只保留诊断和止损动作。",
                "- **行动指令：** 先停止新增投放 / 新选题 / 新承接动作，再完成红警诊断工单。",
                "- **参数：** 冻结周期 24 小时；保留 1 次最小数据同步。",
                "- **资源引用：** 红色警报协议 / 数据看板",
                "- **对应病例：**",
            ]
        )
        checkpoint_lines.append(f"  - `{case_refs[0]}`")

        markdown_task_lines.extend(
            [
                "### 任务一：完成红警症状复核",
                "- **动作：** 以红色警报为入口，复核最近 3 天关键指标、内容变化和承接动作，确认真正主瓶颈。",
                "- **参数：** 最近 3 天；3 个核心指标；1 条异常内容记录。",
                f"- **参考病例：** `{case_refs[0]}`",
                "- **SOP / 资源：** 数据看板 / 红色警报协议",
                "",
                "### 任务二：冻结新增扩张动作并保留最小观测",
                "- **动作：** 在诊断结论明确前，暂停新增扩张动作，只保留最小数据同步与异常记录。",
                "- **参数：** 冻结 24 小时；仅保留 1 次看板同步。",
                f"- **参考病例：** `{case_refs[0]}`",
                "- **SOP / 资源：** 数据看板 / 红色警报协议",
            ]
        )
        yaml_tasks = [
            {
                "id": "T1",
                "title": "完成红警症状复核",
                "action": "复核最近3天关键指标、内容变化和承接动作，确认真正主瓶颈。",
                "params": ["最近3天", "3个核心指标", "1条异常内容记录"],
                "case_refs": case_refs[:1],
                "resource_refs": [dashboard_ref],
                "sop_refs": [],
                "estimated_time": "1 小时",
                "priority": "high",
                "success_check": "明确写出当前红警真正对应的单一主瓶颈。",
            },
            {
                "id": "T2",
                "title": "冻结新增扩张动作并保留最小观测",
                "action": "暂停新增扩张动作，只保留最小数据同步与异常记录。",
                "params": ["冻结24小时", "1次看板同步"],
                "case_refs": case_refs[:1],
                "resource_refs": [dashboard_ref],
                "sop_refs": [],
                "estimated_time": "0.5 小时",
                "priority": "high",
                "success_check": "在诊断完成前没有继续扩张动作，并保留关键异常记录。",
            },
        ]

    work_order = {
        "target_symptom": input_symptom,
        "diagnosis": diagnosis_hint,
        "evidence_status": evidence_status,
        "evidence_case_count": evidence_count,
        "evidence_gap": evidence_gap,
        "self_repair": {
            "required": evidence_count < 5,
            "actions": [
                "仅保留已有正式病例支撑的检查站点" if evidence_count else "切换为阶段一补库模式",
                "将本次会话标记为 bootstrap",
            ],
        },
        "stage1_replenishment": {
            "required": evidence_count < 5,
            "owner": "system",
            "user_action_required": False,
            "target_case_count": 5,
            "gap_count": max(0, 5 - evidence_count),
            "search_brief": f"{platform} / 红色警报 / 核心指标连续下滑 / 已商业化验证 / 阶段二补库",
            "intake_constraints": [
                "只接收已商业化验证且明确赚到钱的案例",
                "必须从阶段一入口按六步拆解后再入库",
            ],
        },
        "tasks": yaml_tasks,
        "writeback_eligible": False,
    }

    lines = [
        f"# 【专家熔炉会话】{frontline_name} 红色警报诊断",
        "",
        "---",
        "",
        "## 用户原始问题",
        "",
        f"- 阶段四红色警报自动触发：{input_symptom}",
        "",
        "## 澄清后的标准靶子",
        "",
        f"- **平台：** {platform}",
        f"- **症状：** {input_symptom}",
        "- **指标 / 现象：** 核心指标连续下滑，已触发红色警报。",
        f"- **场景 / 环节：** {frontline_name} / 看板异常诊断",
        "",
        "## 熔炉内部召回记录",
        "",
        *retrieval_lines,
        "",
        "## 证据状态",
        "",
        f"- **证据级别：** `{evidence_status}`",
        f"- **正式病例数：** `{evidence_count}`",
        f"- **证据缺口：** {evidence_gap}",
        "",
        "## 熔炉内部组装逻辑",
        "",
    ]
    if checkpoint_lines:
        lines.extend(checkpoint_lines)
    else:
        lines.append("- 当前平台暂无正式病例，红色警报诊断先退化为阶段一补库模式。")
    lines.extend(
        [
            "",
            "## 自修正动作",
            "",
            f"- **是否触发：** {'是' if evidence_count < 5 else '否'}",
            f"- **触发原因：** {evidence_gap}",
            "- **修正动作：**",
            "  1. 将本次会话标记为 bootstrap。",
            "  2. 优先保留红色警报止损动作。",
            "  3. 如正式病例不足，继续触发阶段一补库。",
            "",
            "## 阶段一补库动作",
            "",
            f"- **是否触发：** {'是' if evidence_count < 5 else '否'}",
            "- **执行方：** `system`",
            "- **是否需要用户补充：** 否",
            "- **目标病例数：** `5`",
            f"- **当前缺口：** `{max(0, 5 - evidence_count)}`",
            f"- **补库检索简报：** {work_order['stage1_replenishment']['search_brief']}",
            "- **收录约束：**",
            "  1. 只接收已商业化验证且明确赚到钱的案例",
            "  2. 必须从阶段一入口按六步拆解后再入库",
            "",
            "## Markdown工单",
            "",
            "## 您的专属优化方案",
            "",
            f"**诊断结论**：{diagnosis_hint}",
            "",
            "**✅ 请按顺序执行以下动作（预计总耗时：1.5 小时）：**",
            "",
        ]
    )
    if markdown_task_lines:
        lines.extend(markdown_task_lines)
    else:
        lines.append("**当前不交付业务执行任务。请先完成系统补库，再重新进入阶段二会话。**")
    lines.extend(
        [
            "",
            "## Structured Work Order",
            "",
            "```yaml",
            yaml.safe_dump({"work_order": work_order}, allow_unicode=True, sort_keys=False).strip(),
            "```",
            "",
            "## 进度播报记录",
            "",
        ]
    )
    progress_stages = [
        ("阶段二（1/6）问题收集", "问题收集", "记录红色警报自动触发的原始症状"),
        ("阶段二（2/6）靶子澄清", "靶子澄清", "把红色警报收敛为可诊断的单一靶子"),
        ("阶段二（3/6）病例召回", "病例召回", "召回与当前红色警报最相关的正式病例"),
        ("阶段二（4/6）工单组装", "工单组装", "生成止损优先的阶段二诊断工单"),
        ("阶段二（5/6）校验收口", "校验收口", "完成阶段二会话校验与收口"),
        ("阶段二（6/6）交付执行", "交付执行", "把红色警报对应的诊断工单交付到会话"),
    ]
    now = now_text()
    for idx, (stage, step, action) in enumerate(progress_stages, start=1):
        lines.extend(
            [
                f"### 进度播报 {idx}",
                f"- **时间：** {now}",
                f"- **触发类型：** {'stage_start' if idx == 1 else 'key_step_start'}",
                f"- **当前阶段：** {stage}",
                f"- **当前步骤：** {step}",
                f"- **当前动作：** {action}",
                "- **下一步需要你提供：** 无需提供，系统已按红色警报自动触发。",
                "- **预计剩余时间：** 约 1 分钟内",
                "",
            ]
        )
    lines.extend(
        [
            "## 用户反馈",
            "",
            "- 待补充",
            "",
            "## 是否具备回写资格",
            "",
            "- **结论：** 否",
            "- **原因：** 当前为红色警报自动触发的阶段二诊断入口，会话尚未完成商业化闭环验证。",
        ]
    )
    return "\n".join(lines).strip()


def maybe_generate_stage2_red_alert_session(
    root: Path,
    profile_ref: str,
    dashboard_ref: str,
    dashboard_payload: dict,
) -> str | None:
    red_alert_messages = dashboard_payload.get("red_alert_messages", [])
    if not isinstance(red_alert_messages, list) or not red_alert_messages:
        return None

    frontline_name = str(dashboard_payload.get("frontline_name", "")).strip() or "red_alert"
    platform = str(dashboard_payload.get("platform", "")).strip() or "待补充"
    input_symptom = f"{frontline_name} 出现红色警报，核心指标异常下滑，需要立即进入阶段二诊断。"
    case_refs = select_stage2_case_refs(platform)
    evidence_count = len(case_refs)
    evidence_gap = (
        f"当前只有 {evidence_count} 个已商业化验证正式病例，尚未达到成熟会诊标准。"
        if evidence_count
        else "当前平台暂无正式病例，需先切换为阶段一补库模式。"
    )
    diagnosis_hint = (
        "当前应先止损并复核症状归属，再决定是回流阶段二重诊，还是阶段一补库。"
        if evidence_count
        else "当前平台暂无正式证据，红色警报已自动转为阶段一补库优先。"
    )
    session_ref = f"expert_models/sessions/{datetime.now().date()}_{slugify(frontline_name)}_red_alert.md"
    meta = {
        "session_id": f"session_{datetime.now().strftime('%Y_%m_%d')}_{slugify(frontline_name)}_red_alert".lower(),
        "title": f"【专家熔炉会话】{frontline_name} 红色警报诊断",
        "furnace_ref": "expert_models/furnace.md",
        "input_symptom": input_symptom,
        "platform": platform,
        "status": "ready",
        "evidence_status": "bootstrap",
        "evidence_case_count": evidence_count,
        "evidence_gap": evidence_gap,
        "progress_protocol": "hybrid-3min",
        "progress_event_count": 6,
        "last_progress_at": now_text(),
        "retrieved_case_refs": case_refs,
        "date": datetime.now().date().isoformat(),
    }
    body = build_stage2_red_alert_session_body(
        input_symptom=input_symptom,
        platform=platform,
        frontline_name=frontline_name,
        dashboard_ref=dashboard_ref,
        case_refs=case_refs,
        evidence_gap=evidence_gap,
        diagnosis_hint=diagnosis_hint,
    )
    write_markdown(root / session_ref, meta, body)
    errors, _warnings, _repairs = validate_session(root / session_ref)
    if errors:
        raise SystemExit("ERROR: 自动触发的阶段二红色警报会话未通过校验。")
    return session_ref


def build_red_alert_dispatch_body(payload: dict) -> str:
    stage2_dispatch = payload["stage2_dispatch"]
    stage1_replenishment = payload["stage1_replenishment"]
    next_gate = payload["next_gate"]
    lines = [
        f"# 【阶段四自动派发】{payload['frontline_name']} 红色警报",
        "",
        "## 触发背景",
        "",
        f"- **前线：** {payload['frontline_name']}",
        f"- **平台：** {payload['platform']}",
        f"- **看板：** `{payload['dashboard_ref']}`",
        f"- **警报等级：** `{payload['alert_level']}`",
        f"- **触发类型：** `{payload['trigger_type']}`",
        f"- **触发摘要：** {payload['trigger_summary']}",
        "",
        "## 系统判断",
        "",
        f"- **核心结论：** {payload['decision_summary']}",
        f"- **调度策略：** {payload['dispatch_strategy']}",
        f"- **是否需要人工：** {'是' if payload['manual_fallback_required'] else '否'}",
        "",
        "## 阶段二自修正派发",
        "",
        f"- **是否触发：** {'是' if stage2_dispatch['required'] else '否'}",
        f"- **会话引用：** `{stage2_dispatch['session_ref']}`",
        f"- **证据级别：** `{stage2_dispatch['evidence_status']}`",
        f"- **正式病例数：** `{stage2_dispatch['evidence_case_count']}`",
        f"- **是否需要自修正：** {'是' if stage2_dispatch['self_repair_required'] else '否'}",
        f"- **执行结果：** {stage2_dispatch['result']}",
        "",
        "## 阶段一补库派发",
        "",
        f"- **是否触发：** {'是' if stage1_replenishment['required'] else '否'}",
        f"- **执行方：** `{stage1_replenishment['owner']}`",
        f"- **是否需要用户补充：** {'是' if stage1_replenishment['user_action_required'] else '否'}",
        f"- **目标病例数：** `{stage1_replenishment['target_case_count']}`",
        f"- **当前缺口：** `{stage1_replenishment['gap_count']}`",
        f"- **补库检索简报：** {stage1_replenishment['search_brief']}",
    ]
    intake_constraints = stage1_replenishment.get("intake_constraints", [])
    if intake_constraints:
        lines.append("- **收录约束：**")
        for item in intake_constraints:
            lines.append(f"  - {item}")
    lines.extend(
        [
            f"- **执行结果：** {stage1_replenishment['result']}",
            "",
            "## 跟进条件",
            "",
            f"- **等待信号：** `{next_gate['wait_for']}`",
            f"- **重入规则：** {next_gate['reentry_rule']}",
            f"- **下一跳：** {next_gate['next_action']}",
            "",
            "## Structured Red Alert Dispatch",
            "",
            "```yaml",
            yaml.safe_dump({"red_alert_dispatch": payload["structured_payload"]}, allow_unicode=True, sort_keys=False).strip(),
            "```",
        ]
    )
    return "\n".join(lines).strip()


def generate_red_alert_dispatch(
    root: Path,
    profile_ref: str,
    dashboard_ref: str,
    dashboard_payload: dict,
    generated_stage2_session_ref: str,
) -> str | None:
    session_ref = str(generated_stage2_session_ref).strip()
    if not session_ref:
        return None
    red_alert_messages = dashboard_payload.get("red_alert_messages", [])
    if not isinstance(red_alert_messages, list) or not red_alert_messages:
        return None

    session_meta, work_order = load_stage2_work_order(root, session_ref)
    frontline_name = str(dashboard_payload.get("frontline_name", "")).strip() or "red_alert"
    platform = str(dashboard_payload.get("platform", "")).strip() or "待补充"
    alert_level = str(dashboard_payload.get("alert_level", "critical")).strip() or "critical"
    trigger_summary = (
        str(red_alert_messages[0]).strip()
        if isinstance(red_alert_messages, list) and red_alert_messages and str(red_alert_messages[0]).strip()
        else "红色警报触发后，系统自动进入阶段二诊断编排。"
    )

    evidence_status = str(session_meta.get("evidence_status", work_order.get("evidence_status", "bootstrap"))).strip() or "bootstrap"
    evidence_case_count = int(session_meta.get("evidence_case_count", work_order.get("evidence_case_count", 0)) or 0)
    self_repair = work_order.get("self_repair", {}) if isinstance(work_order.get("self_repair"), dict) else {}
    stage1_replenishment = work_order.get("stage1_replenishment", {}) if isinstance(work_order.get("stage1_replenishment"), dict) else {}
    stage1_required = bool(stage1_replenishment.get("required"))
    gap_count = int(stage1_replenishment.get("gap_count", max(0, 5 - evidence_case_count)) or 0)
    target_case_count = int(stage1_replenishment.get("target_case_count", 5) or 5)

    if evidence_case_count == 0:
        decision_summary = "当前平台暂无正式证据，系统已将红色警报转为阶段一补库优先，并保留阶段二红警入口作为重入锚点。"
        dispatch_strategy = "stage1_first_then_stage2"
        wait_for = "stage1_replenishment_complete"
        reentry_rule = "补库完成并新增正式病例后，自动重开同主题阶段二问诊，再决定是否恢复阶段三输出。"
        next_action = "等待系统补齐病例后，重新生成红警阶段二会话。"
        stage2_result = "已生成红色警报阶段二会话，但当前仅保留 bootstrap 诊断入口，不继续下发业务执行任务。"
        stage1_result = "已正式挂起系统补库动作，补库完成前不把当前问题当成可稳定回答的问题。"
    elif stage1_required:
        decision_summary = "当前已有少量正式证据，系统已自动触发阶段二红警诊断，并并行挂起阶段一补库以补齐成熟证据。"
        dispatch_strategy = "stage2_with_parallel_stage1"
        wait_for = "stage2_feedback_and_stage1_parallel_replenishment"
        reentry_rule = "先执行红警阶段二止损动作；如果阶段二反馈仍暴露证据缺口，则继续沿当前补库工单补齐。"
        next_action = "等待阶段二反馈回写，同时保持补库工单开启。"
        stage2_result = "已生成红色警报阶段二会话，先做止损和症状复核，再根据反馈继续自修正。"
        stage1_result = "已并行挂起系统补库动作，避免低证据路径被误当成成熟打法。"
    else:
        decision_summary = "当前证据足够支撑红警自修正，系统已直接派发阶段二诊断，会暂不新增补库动作。"
        dispatch_strategy = "stage2_only"
        wait_for = "stage2_feedback"
        reentry_rule = "等待阶段二反馈；如反馈继续暴露证据不足，再升级为阶段一补库。"
        next_action = "等待阶段二反馈回写。"
        stage2_result = "已生成红色警报阶段二会话，可直接进入自修正和止损执行。"
        stage1_result = "当前不需要新增阶段一补库动作。"

    structured_payload = {
        "source_refs": [profile_ref, dashboard_ref, session_ref],
        "trigger_type": "red_alert",
        "frontline_name": frontline_name,
        "platform": platform,
        "alert_level": alert_level,
        "trigger_summary": trigger_summary,
        "decision_summary": decision_summary,
        "dispatch_strategy": dispatch_strategy,
        "manual_fallback_required": False,
        "stage2_dispatch": {
            "required": True,
            "session_ref": session_ref,
            "evidence_status": evidence_status,
            "evidence_case_count": evidence_case_count,
            "self_repair_required": bool(self_repair.get("required")),
            "result": stage2_result,
        },
        "stage1_replenishment": {
            "required": stage1_required,
            "owner": str(stage1_replenishment.get("owner", "system")).strip() or "system",
            "user_action_required": bool(stage1_replenishment.get("user_action_required", False)),
            "target_case_count": target_case_count,
            "gap_count": gap_count,
            "search_brief": str(stage1_replenishment.get("search_brief", "")).strip() or f"{platform} / 红色警报 / 补库待补充",
            "intake_constraints": stage1_replenishment.get("intake_constraints", []),
            "result": stage1_result,
        },
        "next_gate": {
            "wait_for": wait_for,
            "reentry_rule": reentry_rule,
            "next_action": next_action,
        },
    }

    dispatch_ref = f"stage4_models/dispatches/{datetime.now().date()}_{slugify(frontline_name)}_red_alert.md"
    meta = {
        "artifact_type": "red_alert_dispatch",
        "dispatch_id": f"red_alert_dispatch_{datetime.now().strftime('%Y%m%d')}_{slugify(frontline_name)}".lower(),
        "title": f"【阶段四自动派发】{frontline_name} 红色警报",
        "status": "ready",
        "profile_ref": profile_ref,
        "dashboard_ref": dashboard_ref,
        "generated_stage2_session_ref": session_ref,
        "trigger_type": "red_alert",
        "alert_level": alert_level,
        "date": datetime.now().date().isoformat(),
    }
    payload = {
        "frontline_name": frontline_name,
        "platform": platform,
        "dashboard_ref": dashboard_ref,
        "alert_level": alert_level,
        "trigger_type": "red_alert",
        "trigger_summary": trigger_summary,
        "decision_summary": decision_summary,
        "dispatch_strategy": dispatch_strategy,
        "manual_fallback_required": False,
        "stage2_dispatch": structured_payload["stage2_dispatch"],
        "stage1_replenishment": structured_payload["stage1_replenishment"],
        "next_gate": structured_payload["next_gate"],
        "structured_payload": structured_payload,
    }
    write_artifact(root / dispatch_ref, meta, build_red_alert_dispatch_body(payload))
    return dispatch_ref


def build_dashboard_body(payload: dict) -> str:
    sync_protocol = payload.get("sync_protocol", default_sync_protocol())
    content_capture_fields = payload.get("content_capture_fields", default_content_capture_fields())
    milestone_messages = payload.get("milestone_messages", [])
    red_alert_messages = payload.get("red_alert_messages", [])
    red_alert_protocol = payload.get("red_alert_protocol", default_red_alert_protocol())
    generated_stage2_session_ref = str(payload.get("generated_stage2_session_ref", "")).strip()
    generated_red_alert_dispatch_ref = str(payload.get("generated_red_alert_dispatch_ref", "")).strip()
    lines = [
        f"# 【数据看板】{payload['frontline_name']}",
        "",
        "## 前线概览",
        "",
        f"- **前线名称：** {payload['frontline_name']}",
        f"- **平台：** {payload['platform']}",
        f"- **业务领域：** {payload['domain']}",
        f"- **当前状态：** {payload['status']}",
        "",
        "## 核心指标",
        "",
    ]
    for item in payload["metrics"]:
        lines.append(f"- **{item['label']}：** {item['value']}")
    lines.extend(["", "## 内容表现", ""])
    for item in payload["content_items"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 内容表现采集口径", ""])
    for item in content_capture_fields:
        lines.append(f"- {item}")
    lines.extend(["", "## 待办事项", ""])
    for item in payload["todos"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 主动关怀消息", ""])
    if milestone_messages:
        for item in milestone_messages:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前未触发新的里程碑消息。")
    lines.extend(["", "## 红色警报协议", ""])
    lines.append(f"- **触发条件：** {red_alert_protocol.get('trigger', '待补充')}")
    lines.append(f"- **触发动作：** {red_alert_protocol.get('action', '待补充')}")
    lines.append(f"- **诊断入口：** {red_alert_protocol.get('diagnosis_entry', '待补充')}")
    lines.extend(["", "## 红色警报消息", ""])
    if red_alert_messages:
        for item in red_alert_messages:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前未触发红色警报。")
    if generated_stage2_session_ref:
        lines.append(f"- **自动触发的阶段二诊断：** `{generated_stage2_session_ref}`")
    if generated_red_alert_dispatch_ref:
        lines.append(f"- **自动派发记录：** `{generated_red_alert_dispatch_ref}`")
    lines.extend(
        [
            "",
            "## 手动同步机制",
            "",
            f"- **同步频率：** {sync_protocol.get('frequency', 'daily')}",
            f"- **固定时间：** {sync_protocol.get('time', '17:00')}",
            f"- **预计耗时：** {sync_protocol.get('duration', '10分钟')}",
            f"- **执行方式：** {sync_protocol.get('method', '手动同步')}",
            f"- **同步说明：** {sync_protocol.get('instruction', '每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。')}",
            "",
            "",
            "## 预警状态",
            "",
            f"- **等级：** `{payload['alert_level']}`",
            f"- **原因：** {payload['alert_reason']}",
            "",
            "## Structured Frontline Dashboard",
            "",
            "```yaml",
            yaml.safe_dump({"dashboard": payload}, allow_unicode=True, sort_keys=False).strip(),
            "```",
        ]
    )
    return "\n".join(lines).strip()


def merge_metrics(existing: list[dict], updates: list[dict]) -> list[dict]:
    ordered: list[dict] = []
    index: dict[str, dict] = {}
    for item in existing:
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        clean = {"label": label, "value": str(item.get("value", "")).strip()}
        ordered.append(clean)
        index[label] = clean
    for item in updates:
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        value = str(item.get("value", "")).strip()
        if label in index:
            index[label]["value"] = value
        else:
            clean = {"label": label, "value": value}
            ordered.append(clean)
            index[label] = clean
    return ordered


def load_dashboard(root: Path, ref: str) -> tuple[dict | None, dict | None]:
    path = root / ref
    if not path.exists():
        return None, None
    meta, body = read_markdown(path)
    payload = extract_yaml_block(body, "Structured Frontline Dashboard").get("dashboard", {})
    return meta, payload if isinstance(payload, dict) else {}


def load_stage2_work_order(root: Path, ref: str) -> tuple[dict, dict]:
    path = root / ref
    if not path.exists():
        raise SystemExit(f"ERROR: 未找到阶段二会话：{ref}")
    meta, body = read_markdown(path)
    payload = extract_yaml_block(body, "Structured Work Order").get("work_order", {})
    if not isinstance(payload, dict):
        raise SystemExit("ERROR: 阶段二会话缺少有效的 Structured Work Order。")
    return meta, payload


def infer_alert_level(improved: str) -> str:
    if improved == "no":
        return "critical"
    if improved == "partial":
        return "warning"
    return "normal"


def load_stage3_session(root: Path, ref: str) -> tuple[dict, dict]:
    path = root / ref
    if not path.exists():
        raise SystemExit(f"ERROR: 未找到阶段三会话：{ref}")
    meta, body = read_markdown(path)
    payload = extract_yaml_block(body, "Structured Solution Package").get("solution_package", {})
    if not isinstance(payload, dict):
        raise SystemExit("ERROR: 阶段三会话缺少有效的 solution_package。")
    return meta, payload


def load_stage3_audit(root: Path, ref: str) -> tuple[dict, dict] | tuple[None, None]:
    normalized = str(ref).strip()
    if not normalized:
        return None, None
    path = root / normalized
    if not path.exists():
        return None, None
    meta, body = read_markdown(path)
    payload = extract_yaml_block(body, "Structured Autonomous Audit").get("autonomous_audit", {})
    return meta, payload if isinstance(payload, dict) else {}


def infer_resource_ref(resource_ref: str) -> str:
    normalized = str(resource_ref).strip()
    if normalized.startswith("strategy_models/"):
        return normalized
    if normalized.startswith("AP"):
        return f"strategy_models/resources/actions/{normalized}.md"
    if normalized.startswith("TR"):
        return f"strategy_models/resources/templates/{normalized}.md"
    if normalized.startswith("TC"):
        return f"strategy_models/resources/tools/{normalized}.md"
    return normalized


def extract_numbered_list(section_text: str) -> list[str]:
    items: list[str] = []
    for line in section_text.splitlines():
        match = re.match(r"^\s*\d+\.\s+(.*)$", line.strip())
        if match:
            items.append(match.group(1).strip())
    return items


def extract_bullet_list(section_text: str) -> list[str]:
    items: list[str] = []
    for line in section_text.splitlines():
        match = re.match(r"^\s*-\s+(.*)$", line.strip())
        if match:
            items.append(match.group(1).strip())
    return items


def load_resource_item(root: Path, resource_ref: str) -> dict:
    normalized_ref = infer_resource_ref(resource_ref)
    path = root / normalized_ref
    fallback = {
        "resource_id": str(resource_ref).strip(),
        "title": str(resource_ref).strip(),
        "resource_type": "unknown",
        "ref": normalized_ref,
        "steps": [],
        "fields": [],
        "checklist": [],
        "risks": [],
    }
    if not path.exists():
        return fallback

    meta, body = read_markdown(path)
    sections = extract_sections(body)
    apply_targets = extract_bullet_list(sections.get("适用目标", ""))
    steps = extract_numbered_list(sections.get("执行步骤", ""))
    checklist = extract_numbered_list(sections.get("清单", ""))
    fields = extract_bullet_list(sections.get("字段", ""))
    risks = extract_bullet_list(sections.get("风险提示", ""))
    return {
        "resource_id": str(meta.get("resource_id", resource_ref)).strip(),
        "title": str(meta.get("title", resource_ref)).strip(),
        "resource_type": str(meta.get("resource_type", "unknown")).strip(),
        "ref": normalized_ref,
        "apply_targets": apply_targets,
        "steps": steps,
        "fields": fields,
        "checklist": checklist,
        "risks": risks,
    }


def parse_hour_value(text: str) -> int:
    match = re.search(r"(\d+)", str(text))
    return int(match.group(1)) if match else 0


def summarize_dashboard_metrics(dashboard_payload: dict) -> list[str]:
    metrics = dashboard_payload.get("metrics", []) if isinstance(dashboard_payload, dict) else []
    summary: list[str] = []
    for item in metrics[:5]:
        label = str(item.get("label", "")).strip()
        value = str(item.get("value", "")).strip()
        if label and value:
            summary.append(f"{label}={value}")
    return summary


def detect_platforms_in_text(*parts: object) -> list[str]:
    text = " ".join(str(part).strip() for part in parts if str(part).strip())
    detected: list[str] = []
    for marker in PLATFORM_MARKERS:
        if marker in text and marker not in detected:
            detected.append(marker)
    return detected


def classify_cognitive_load(weight: int) -> str:
    if weight >= 10:
        return "high"
    if weight >= 6:
        return "medium"
    return "low"


def estimate_execution_friction(task: dict) -> dict:
    execution_steps = [str(item).strip() for item in task.get("execution_steps", []) if str(item).strip()]
    template_fields = [str(item).strip() for item in task.get("template_fields", []) if str(item).strip()]
    tool_checks = [str(item).strip() for item in task.get("tool_checks", []) if str(item).strip()]
    risk_notes = [str(item).strip() for item in task.get("risk_notes", []) if str(item).strip()]
    platforms = detect_platforms_in_text(
        task.get("title", ""),
        task.get("diagnosis", ""),
        task.get("action", ""),
        task.get("source_ref", ""),
        " ".join(execution_steps),
        " ".join(template_fields),
        " ".join(tool_checks),
    )
    platform_count = max(1, len(platforms))
    context_switch_count = max(0, platform_count - 1)
    estimated_hours = parse_hour_value(task.get("estimated_time", ""))
    complexity_weight = (
        min(len(execution_steps), 6)
        + min(len(template_fields), 4)
        + min(len(tool_checks), 4)
        + min(len(risk_notes), 3)
        + min(estimated_hours, 4)
        + context_switch_count
    )
    minimum_next_step = execution_steps[0] if execution_steps else str(task.get("action", "")).strip() or "先回看当前任务并补充第一步动作。"
    friction_score = min(10, max(1, 1 + estimated_hours + context_switch_count + (complexity_weight // 2)))
    automation_candidate = platform_count >= 2 or any(
        token in " ".join(execution_steps + [str(task.get("action", "")).strip()]) for token in ["同步", "更新", "复制", "发布"]
    )
    consolidation_tip = "先只完成最小下一步，再决定是否继续展开。"
    if automation_candidate:
        consolidation_tip = "这类任务存在聚合执行空间，优先合并重复同步或跨平台操作。"
    return {
        "platforms": platforms,
        "platform_count": platform_count,
        "context_switch_count": context_switch_count,
        "cognitive_load": classify_cognitive_load(complexity_weight),
        "estimated_friction_score": friction_score,
        "minimum_next_step": minimum_next_step,
        "automation_candidate": automation_candidate,
        "consolidation_tip": consolidation_tip,
    }


def enrich_task_with_execution_friction(task: dict) -> dict:
    clean = dict(task)
    clean["execution_friction"] = estimate_execution_friction(clean)
    return clean


def pick_matching_resource(resources: list[dict], prefixes: tuple[str, ...]) -> list[dict]:
    matched: list[dict] = []
    for item in resources:
        resource_id = str(item.get("resource_id", "")).strip()
        if resource_id.startswith(prefixes):
            matched.append(item)
    return matched


def build_resource_bundle_summary(resources: list[dict], case_refs: list[str]) -> dict:
    return {
        "action_packs": [
            {
                "resource_id": item["resource_id"],
                "title": item["title"],
                "ref": item["ref"],
            }
            for item in pick_matching_resource(resources, ("AP",))
        ],
        "template_resources": [
            {
                "resource_id": item["resource_id"],
                "title": item["title"],
                "ref": item["ref"],
            }
            for item in pick_matching_resource(resources, ("TR",))
        ],
        "tool_calls": [
            {
                "resource_id": item["resource_id"],
                "title": item["title"],
                "ref": item["ref"],
            }
            for item in pick_matching_resource(resources, ("TC",))
        ],
        "case_refs": case_refs,
    }


def flatten_execution_steps(task: dict, resources: list[dict], bottleneck: str) -> list[str]:
    steps: list[str] = []
    task_action = str(task.get("action", "")).strip()
    if task_action:
        steps.append(task_action)
    for item in pick_matching_resource(resources, ("AP",)):
        steps.extend(item.get("steps", [])[:4])
    if not steps:
        for item in pick_matching_resource(resources, ("TC",)):
            steps.extend(item.get("checklist", [])[:4])
    deduped = list(dict.fromkeys(step for step in steps if step))
    if bottleneck and bottleneck not in "".join(deduped):
        deduped.append(f"执行时重点观察：{bottleneck}")
    return deduped[:6]


def build_task_from_stage3_task(task: dict, resources: list[dict], primary_bottleneck: str) -> dict:
    bundle = build_resource_bundle_summary(resources, [str(item).strip() for item in task.get("case_refs", []) if str(item).strip()])
    template_fields: list[str] = []
    for item in pick_matching_resource(resources, ("TR",)):
        template_fields.extend(item.get("fields", [])[:6])
    tool_checks: list[str] = []
    for item in pick_matching_resource(resources, ("TC",)):
        tool_checks.extend(item.get("checklist", [])[:5])
    risk_notes: list[str] = []
    for item in resources:
        risk_notes.extend(item.get("risks", [])[:2])
    return {
        "title": str(task.get("title", "")).strip() or "延续阶段三任务",
        "diagnosis": primary_bottleneck or "当前需要继续验证阶段三路径命中质量。",
        "strategy_ref": str(task.get("strategy_ref", "")).strip() or "沿用阶段三主路径",
        "action": str(task.get("action", "")).strip() or "继续执行当前动作。",
        "estimated_time": str(task.get("estimated_time", "")).strip() or "1 小时",
        "source_ref": "strategy_models/sessions/来源任务",
        "success_check": str(task.get("success_check", "")).strip() or "完成本轮执行并回写数据。",
        "execution_steps": flatten_execution_steps(task, resources, primary_bottleneck),
        "template_fields": list(dict.fromkeys(field for field in template_fields if field))[:6],
        "tool_checks": list(dict.fromkeys(check for check in tool_checks if check))[:6],
        "risk_notes": list(dict.fromkeys(note for note in risk_notes if note))[:4],
        "execution_bundle": bundle,
    }


def build_partial_gap_tasks(
    bottlenecks: list[str],
    available_resources: list[dict],
    dashboard_ref: str,
) -> list[dict]:
    tasks: list[dict] = []
    joined = " ".join(bottlenecks)

    if "评论区" in joined or "承接" in joined:
        comment_resources = [item for item in available_resources if str(item.get("resource_id", "")).startswith(("TC001", "TC003"))]
        tasks.append(
            {
                "title": "补评论区承接脚本",
                "diagnosis": "已有点击和出单，但评论区承接不稳定，说明 CTA 和回复脚本没有闭环。",
                "strategy_ref": "评论区转化",
                "action": "把视频口播、简介和评论区回复统一成单一 CTA，只保留一个承接动作。",
                "estimated_time": "1 小时",
                "source_ref": dashboard_ref,
                "success_check": "形成 3 条标准评论区回复脚本，并在下一条视频中完成一次完整承接测试。",
                "execution_steps": [
                    "从最近 1 条已有点击的视频里，提取 5 个高频评论或私信问题。",
                    "写出 3 条固定回复脚本：问题重述 + 利益点 + 唯一 CTA。",
                    "检查口播、标题简介、评论区蓝链回复是否只指向 1 个动作。",
                    "发布后记录评论回复率、商品点击和成交单数三项变化。",
                ],
                "template_fields": ["高频问题", "回复脚本", "唯一 CTA", "蓝链利益点"],
                "tool_checks": [
                    "CTA 是否只有一个",
                    "发布后是否记录评论 / 私信高频问题",
                    "复查评论区蓝链回复是否与节点利益点一致",
                ],
                "risk_notes": ["不要同时给两个以上承接入口。"],
                "execution_bundle": build_resource_bundle_summary(comment_resources, []),
            }
        )

    if "选品" in joined or "品类" in joined or "人群匹配" in joined:
        product_resources = [item for item in available_resources if str(item.get("resource_id", "")).startswith(("AP004", "TR004", "TC003"))]
        tasks.append(
            {
                "title": "聚焦单一品类做首发验证",
                "diagnosis": "选品还不够聚焦，内容与商品人群匹配度一般，说明当前题材和商品没有形成单点击穿。",
                "strategy_ref": "选品策略",
                "action": "只保留 1 个品类方向，重做候选品评分并确定 1 个首发验证品。",
                "estimated_time": "2 小时",
                "source_ref": dashboard_ref,
                "success_check": "完成 10 个候选品评分表，并明确 1 个首发验证品和对应人群场景。",
                "execution_steps": [
                    "打开 B 站搜索与选品中心，围绕 1 个细分人群列出 10 个候选品。",
                    "按搜索结果质量、竞争度、佣金空间、出单概率四项打分。",
                    "把泛品剔除，只保留最容易讲清利益点的 1 个首发验证品。",
                    "为这个商品补 1 个单一场景的视频脚本，不再混合多个卖点。",
                ],
                "template_fields": ["关键词", "特定人群 / 场景", "竞争度", "佣金空间", "出单概率", "是否首发验证"],
                "tool_checks": [
                    "在选品中心记录候选品与节点活动",
                    "复查佣金空间",
                    "复盘评论、点击和成交，不只看播放",
                ],
                "risk_notes": ["不要只看热度，不看搜索意图和佣金空间。"],
                "execution_bundle": build_resource_bundle_summary(product_resources, []),
            }
        )

    return tasks


def build_learning_actions(
    improved: str,
    session_meta: dict,
    audit_ref: str,
    audit_payload: dict | None,
    dashboard_ref: str,
    feedback_ref: str,
    allow_dashboard_update: bool,
    allow_review_generation: bool,
    allow_reopen_stage2: bool,
    allow_stage1_replenishment: bool,
    new_bottlenecks: list[str],
) -> list[dict]:
    actions: list[dict] = []
    stage1_gap_required = False
    if allow_dashboard_update:
        actions.append(
            {
                "type": "dashboard_update",
                "target_ref": dashboard_ref,
                "reason": "已收到新的执行结果与指标变化，需要同步前线状态。",
                "proposed_change": "更新核心指标、待办事项和预警等级。",
            }
        )

    if any(token in " ".join(new_bottlenecks) for token in ["时间", "预算", "现金流", "精力"]):
        actions.append(
            {
                "type": "profile_update",
                "target_ref": DEFAULT_PROFILE_REF,
                "reason": "反馈暴露出资源约束变化。",
                "proposed_change": "回看 owner profile 中的时间、风险或资源参数。",
            }
        )

    if audit_payload and isinstance(audit_payload.get("stage1_replenishment"), dict):
        stage1_replenishment = audit_payload["stage1_replenishment"]
        if stage1_replenishment.get("required") is True and (allow_stage1_replenishment or improved != "yes"):
            stage1_gap_required = True
            actions.append(
                {
                    "type": "stage1_replenishment_needed",
                    "target_ref": audit_ref or feedback_ref,
                    "reason": "源阶段三自治审计已标记阶段一证据缺口。",
                    "proposed_change": stage1_replenishment.get("search_brief", "沿当前审计简报补充正式案例。"),
                }
            )

    if improved == "no":
        if normalize_bool(session_meta.get("autonomous_mode")) and not stage1_gap_required:
            actions.append(
                {
                    "type": "stage3_route_update_needed",
                    "target_ref": audit_ref or feedback_ref,
                    "reason": "自治路由执行后仍无改善，优先复核阶段三路径。",
                    "proposed_change": "重看目标族、主策略和资源包组合，必要时重新跑阶段三。",
                }
            )
        if not stage1_gap_required and (allow_reopen_stage2 or not normalize_bool(session_meta.get("autonomous_mode"))):
            actions.append(
                {
                    "type": "stage2_diagnosis_update_needed",
                    "target_ref": feedback_ref,
                    "reason": "当前路径未带来改善，可能命中了错误瓶颈。",
                    "proposed_change": "回流阶段二重新确认最具体症状，再决定是否保留当前阶段三目标。",
                }
            )
    elif improved == "partial":
        if not stage1_gap_required:
            target_ref = audit_ref or feedback_ref
            action_type = "stage3_route_update_needed" if normalize_bool(session_meta.get("autonomous_mode")) else "stage2_diagnosis_update_needed"
            actions.append(
                {
                    "type": action_type,
                    "target_ref": target_ref,
                    "reason": "已有部分改善，说明方向可能对，但路径粒度仍不够。",
                    "proposed_change": "保留有效动作，同时细化瓶颈并重组下周任务包。",
                }
            )

    if allow_review_generation:
        actions.append(
            {
                "type": "next_week_task_package",
                "target_ref": feedback_ref,
                "reason": "已授权系统生成下周任务包。",
                "proposed_change": "基于本次反馈和最新看板生成每周战略复盘会。",
            }
        )

    return actions


def derive_effectiveness_score(improved: str, new_bottlenecks: list[str], learning_actions: list[dict]) -> tuple[int, str]:
    if improved == "yes":
        base = 9
    elif improved == "partial":
        base = 7
    else:
        base = 3
    base -= max(0, len(new_bottlenecks) - 1)
    if any(item["type"] == "stage1_replenishment_needed" for item in learning_actions):
        base -= 1
    score = max(1, min(10, base))
    if improved == "yes":
        note = "当前动作有效，可继续放大，但仍需保留关键观测。"
    elif improved == "partial":
        note = "当前动作部分有效，但还未穿透主瓶颈，需要把有效动作沉淀为模型修正。"
    else:
        note = "当前动作未带来改善，应优先修正底层判断，而不是继续加码执行。"
    return score, note


def build_model_correction_slots(
    learning_actions: list[dict],
    primary_bottleneck: str,
    source_session_ref: str,
    feedback_ref: str,
) -> list[dict]:
    slot_defaults = [
        {
            "slot": "修正图谱",
            "status": "not_needed",
            "target_ref": source_session_ref,
            "proposed_change": "当前未触发图谱修正。",
        },
        {
            "slot": "修正专家模型",
            "status": "not_needed",
            "target_ref": feedback_ref,
            "proposed_change": "当前未触发专家模型修正。",
        },
        {
            "slot": "更新资源库",
            "status": "not_needed",
            "target_ref": feedback_ref,
            "proposed_change": "当前未触发资源库更新。",
        },
    ]
    slots = {item["slot"]: item for item in slot_defaults}

    for action in learning_actions:
        action_type = str(action.get("type", "")).strip()
        target_ref = str(action.get("target_ref", "")).strip() or feedback_ref
        proposed_change = str(action.get("proposed_change", "")).strip()
        if action_type == "stage3_route_update_needed":
            slots["修正图谱"] = {
                "slot": "修正图谱",
                "status": "required",
                "target_ref": target_ref,
                "proposed_change": f"在阶段三图谱或路由节点中补充围绕“{primary_bottleneck}”的检查与资源索引；{proposed_change}",
            }
        elif action_type == "stage2_diagnosis_update_needed":
            slots["修正专家模型"] = {
                "slot": "修正专家模型",
                "status": "required",
                "target_ref": target_ref,
                "proposed_change": f"在阶段二诊断手册中新增针对“{primary_bottleneck}”的检查项，并重写问诊口径；{proposed_change}",
            }
        elif action_type == "stage1_replenishment_needed":
            slots["更新资源库"] = {
                "slot": "更新资源库",
                "status": "required",
                "target_ref": target_ref,
                "proposed_change": f"把这次围绕“{primary_bottleneck}”的缺口结构化为补库案例或资源条目；{proposed_change}",
            }

    return [slots["修正图谱"], slots["修正专家模型"], slots["更新资源库"]]


def build_feedback_body(payload: dict) -> str:
    lines = [
        f"# 【阶段四执行反馈】{payload['frontline_name']} / {payload['target_goal']}",
        "",
        "## 反馈背景",
        "",
        f"- **来源阶段三会话：** `{payload['source_stage3_session']}`",
        f"- **执行任务：** {', '.join(payload['executed_tasks']) if payload['executed_tasks'] else '待补充'}",
        f"- **是否改善：** `{payload['improved']}`",
        "",
        "## 执行结果",
        "",
        "- **指标变化：**",
    ]
    for item in payload["observed_metric_changes"]:
        if item.get("before"):
            lines.append(f"  - {item['label']}：{item['before']} -> {item['after']}")
        else:
            lines.append(f"  - {item['label']}：{item['after']}")
    lines.extend(["- **新暴露问题：**"])
    if payload["new_bottlenecks"]:
        for item in payload["new_bottlenecks"]:
            lines.append(f"  - {item}")
    else:
        lines.append("  - 无")
    lines.extend(["- **补充观察：**"])
    if payload["observations"]:
        for item in payload["observations"]:
            lines.append(f"  - {item}")
    else:
        lines.append("  - 无")
    lines.extend(
        [
            "",
            "## 学习判断",
            "",
            f"- **当前主判断：** {payload['summary_judgment']}",
            f"- **是否需要回流阶段二：** {'是' if payload['needs_stage2'] else '否'}",
            f"- **是否需要回流阶段一：** {'是' if payload['needs_stage1'] else '否'}",
            "",
            "## 学习动作",
            "",
        ]
    )
    for item in payload["learning_actions"]:
        lines.append(f"- `{item['type']}` -> `{item['target_ref']}`：{item['proposed_change']}")
    lines.extend(
        [
            "",
            "## 模型修正项",
            "",
            f"- **有效性评分：** {payload['effectiveness_score']} 分（{payload['effectiveness_note']}）",
            "- **模型修正行动：**",
        ]
    )
    for item in payload["model_correction_slots"]:
        status_text = "需要执行" if item["status"] == "required" else "暂不执行"
        lines.append(f"  - **{item['slot']}：** [{status_text}] `{item['target_ref']}` -> {item['proposed_change']}")
    lines.extend(
        [
            "",
            "## Structured Stage4 Feedback",
            "",
            "```yaml",
            yaml.safe_dump({"stage4_feedback": payload["structured_payload"]}, allow_unicode=True, sort_keys=False).strip(),
            "```",
        ]
    )
    return "\n".join(lines).strip()


def derive_summary_judgment(improved: str, learning_actions: list[dict]) -> str:
    if improved == "yes":
        return "当前路径有效，可以进入节奏放大与下周任务延续。"
    if any(item["type"] == "stage1_replenishment_needed" for item in learning_actions):
        return "当前更像证据层不足，继续硬跑意义有限，应优先补库。"
    if any(item["type"] == "stage2_diagnosis_update_needed" for item in learning_actions):
        return "当前更像问题识别偏差，应优先回流阶段二重新问诊。"
    return "当前路径只有部分命中，建议保留有效动作并重组阶段三方案。"


def build_review_task_package(
    root: Path,
    source_session_ref: str,
    solution_package: dict,
    feedback_payload: dict,
    learning_actions: list[dict],
    dashboard_ref: str,
    profile_payload: dict,
    dashboard_payload: dict,
) -> list[dict]:
    tasks: list[dict] = []
    executed = {str(item).strip() for item in feedback_payload["executed_tasks"]}
    session_tasks = solution_package.get("tasks", [])
    remaining_tasks = [item for item in session_tasks if str(item.get("id", "")).strip() not in executed]
    improved = feedback_payload["improved"]
    primary_bottleneck = feedback_payload.get("new_bottlenecks", ["当前主要瓶颈待补充"])[0] if feedback_payload.get("new_bottlenecks") else "当前主要瓶颈待补充"
    owner_goal = str(profile_payload.get("goals_and_preferences", {}).get("primary_goal_12m", "")).strip()
    dashboard_metrics = summarize_dashboard_metrics(dashboard_payload)

    def add_task(task: dict) -> None:
        clean = enrich_task_with_execution_friction(task)
        clean["id"] = f"R{len(tasks) + 1}"
        tasks.append(clean)

    if improved == "yes":
        for item in remaining_tasks[:2]:
            resource_refs = [str(ref).strip() for ref in item.get("resource_refs", []) if str(ref).strip()]
            resources = [load_resource_item(root, ref) for ref in resource_refs]
            task_payload = build_task_from_stage3_task(item, resources, primary_bottleneck)
            task_payload["source_ref"] = source_session_ref
            task_payload["diagnosis"] = f"当前路径已经有效，下一步是继续放大已验证动作，并服务于 12 个月目标：{owner_goal or '待补充'}。"
            add_task(task_payload)
        add_task(
            {
                "title": "同步前线数据看板",
                "diagnosis": "阶段四继续放大的前提是看板数据真实，否则下轮推演会漂移。",
                "strategy_ref": "数据同步",
                "action": "把本周最新核心指标、最新内容表现和关键观察同步到数据看板。",
                "estimated_time": "0.5 小时",
                "source_ref": dashboard_ref,
                "success_check": "看板中的核心指标、待办事项和预警等级已更新。",
                "execution_steps": [
                    "同步最新 3 个核心指标。",
                    "补充最新 1 到 3 条内容表现。",
                    "写明本周继续放大的唯一变量。",
                ],
                "template_fields": ["核心指标", "内容表现", "待办事项"],
                "tool_checks": dashboard_metrics,
                "risk_notes": ["不要凭感觉判断有效，要把数据变化写进看板。"],
                "execution_bundle": build_resource_bundle_summary([], []),
            }
        )
    elif improved == "partial":
        executed_tasks = [item for item in session_tasks if str(item.get("id", "")).strip() in executed]
        if executed_tasks:
            for item in executed_tasks[:2]:
                resource_refs = [str(ref).strip() for ref in item.get("resource_refs", []) if str(ref).strip()]
                resources = [load_resource_item(root, ref) for ref in resource_refs]
                task_payload = build_task_from_stage3_task(item, resources, primary_bottleneck)
                task_payload["source_ref"] = source_session_ref
                task_payload["diagnosis"] = f"该任务已经带来部分改善，说明方向对，但还没穿透当前瓶颈：{primary_bottleneck}"
                task_payload["success_check"] = "至少有一个关键指标继续改善，且能说明本次优化对应了什么变化。"
                add_task(task_payload)
        route_resources = [load_resource_item(root, ref) for ref in solution_package.get("resource_bundle", {}).get("action_refs", []) + solution_package.get("resource_bundle", {}).get("template_refs", []) + solution_package.get("resource_bundle", {}).get("tool_refs", [])]
        for item in build_partial_gap_tasks(feedback_payload.get("new_bottlenecks", []), route_resources, dashboard_ref):
            add_task(item)
        for item in learning_actions:
            if item["type"] in {"stage3_route_update_needed", "stage2_diagnosis_update_needed"}:
                add_task(
                    {
                        "title": "重新定位当前主瓶颈",
                        "diagnosis": "已有部分改善，说明不是完全错路，而是阶段三任务包还不够贴近真实阻塞点。",
                        "strategy_ref": item["type"],
                        "action": item["proposed_change"],
                        "estimated_time": "0.5 小时",
                        "source_ref": item["target_ref"],
                        "success_check": "新的主瓶颈被明确写出，并生成下一轮动作。",
                        "execution_steps": [
                            "回看本周已执行动作中，哪一步确实拉动了指标。",
                            "把没有贡献的动作从下周任务包里删除。",
                            "只保留 1 个最有希望继续改善的路径重新排优先级。",
                        ],
                        "template_fields": ["有效动作", "无效动作", "下一轮唯一变量"],
                        "tool_checks": dashboard_metrics,
                        "risk_notes": ["不要因为部分有效就把整条路径都当成正确。"],
                        "execution_bundle": build_resource_bundle_summary([], [item["target_ref"]]),
                    }
                )
                break
        add_task(
            {
                "title": "更新看板并标记预警",
                "diagnosis": "本轮不是失败，但已经暴露出新的阻塞点，需要让系统后续推演基于更新后的战场状态。",
                "strategy_ref": "dashboard_update",
                "action": "同步本轮指标变化和新暴露问题，把当前前线标记为 warning。",
                "estimated_time": "0.5 小时",
                "source_ref": dashboard_ref,
                "success_check": "看板已反映本轮波动，并形成新的待办项。",
                "execution_steps": [
                    "更新视频播放、点击、成交等变化。",
                    "把新暴露问题写入待办事项。",
                    "确认看板的最新反馈与复盘引用已经刷新。",
                ],
                "template_fields": ["指标变化", "新暴露问题", "下一轮待办"],
                "tool_checks": dashboard_metrics,
                "risk_notes": ["不要只写结果，不写新暴露问题。"],
                "execution_bundle": build_resource_bundle_summary([], []),
            }
        )
    else:
        for item in learning_actions:
            if item["type"] in {"stage1_replenishment_needed", "stage2_diagnosis_update_needed", "stage3_route_update_needed"}:
                add_task(
                    {
                        "title": f"执行学习动作：{item['type']}",
                        "diagnosis": "当前路径没有改善，优先级已经从执行转为修正底层判断。",
                        "strategy_ref": item["type"],
                        "action": item["proposed_change"],
                        "estimated_time": "1 小时",
                        "source_ref": item["target_ref"],
                        "success_check": "学习动作已完成，并产出可复用的新结论或新证据。",
                        "execution_steps": [
                            "把当前失败路径中的关键假设逐条列出。",
                            "明确是诊断错、路由错还是证据缺口。",
                            "把修正结果写回下轮阶段二或阶段三入口。",
                        ],
                        "template_fields": ["错误假设", "修正结论", "新入口"],
                        "tool_checks": dashboard_metrics,
                        "risk_notes": ["不要在未修正判断前继续加动作。"],
                        "execution_bundle": build_resource_bundle_summary([], [item["target_ref"]]),
                    }
                )
        add_task(
            {
                "title": "暂停扩张并保持最小观测",
                "diagnosis": "当前路径无改善，继续扩张只会放大错误。",
                "strategy_ref": "最小观测",
                "action": "本周停止新增大动作，只保留最小数据同步与关键异常观察。",
                "estimated_time": "0.5 小时",
                "source_ref": dashboard_ref,
                "success_check": "关键指标已完成 1 次同步，并记录是否继续恶化。",
                "execution_steps": [
                    "停止新增选题和新增品类。",
                    "仅同步关键指标并记录异常。",
                    "等待修正后的阶段二或阶段三入口。",
                ],
                "template_fields": ["关键指标", "异常现象", "停止项"],
                "tool_checks": dashboard_metrics,
                "risk_notes": ["不要在无改善状态下同时试多个新方向。"],
                "execution_bundle": build_resource_bundle_summary([], []),
            }
        )

    if not tasks:
        add_task(
            {
                "title": "维持最小闭环",
                "diagnosis": "当前数据不足以形成更强动作。",
                "strategy_ref": "最小闭环",
                "action": "同步看板、回看反馈、等待下一轮更完整数据。",
                "estimated_time": "0.5 小时",
                "source_ref": dashboard_ref,
                "success_check": "阶段四记录链不断档。",
                "execution_steps": ["同步看板", "记录观察", "等待下一轮数据"],
                "template_fields": ["看板", "观察"],
                "tool_checks": dashboard_metrics,
                "risk_notes": ["不要用空数据做强判断。"],
                "execution_bundle": build_resource_bundle_summary([], []),
            }
        )
    return tasks


def build_decision_options(
    task_package: list[dict],
    learning_actions: list[dict],
    feedback_payload: dict,
    profile_payload: dict,
) -> list[dict]:
    goals = profile_payload.get("goals_and_preferences", {}) if isinstance(profile_payload, dict) else {}
    resources = profile_payload.get("resource_profile", {}) if isinstance(profile_payload, dict) else {}
    try:
        risk_score = int(goals.get("risk_score", 5) or 5)
    except (TypeError, ValueError):
        risk_score = 5
    weekly_hours = parse_hour_value(resources.get("weekly_hours", ""))
    improved = str(feedback_payload.get("improved", "")).strip()
    average_friction = 0
    if task_package:
        average_friction = round(
            sum(int(item.get("execution_friction", {}).get("estimated_friction_score", 0) or 0) for item in task_package) / len(task_package)
        )
    top_task_ids = [item["id"] for item in task_package[:2] if item.get("id")]
    highest_friction_task = max(
        task_package,
        key=lambda item: int(item.get("execution_friction", {}).get("estimated_friction_score", 0) or 0),
        default={},
    )
    highest_friction_id = str(highest_friction_task.get("id", "")).strip()
    has_stage1_gap = any(item.get("type") == "stage1_replenishment_needed" for item in learning_actions)
    has_stage2_gap = any(item.get("type") == "stage2_diagnosis_update_needed" for item in learning_actions)
    has_stage3_gap = any(item.get("type") == "stage3_route_update_needed" for item in learning_actions)

    options = [
        {
            "option_id": "O1",
            "title": "按推荐任务包推进",
            "when_to_choose": "已有改善，且本周可投入时间足够覆盖推荐任务。",
            "tradeoff": f"好处是节奏最快；代价是平均执行阻力约 {average_friction or '待估算'} / 10，需要连续投入。",
            "recommended": improved == "yes" or (improved == "partial" and not has_stage1_gap and not has_stage2_gap),
            "linked_task_ids": top_task_ids,
        },
        {
            "option_id": "O2",
            "title": "先修正诊断再执行",
            "when_to_choose": "本轮只是部分改善或没有改善，怀疑当前卡点识别有偏差。",
            "tradeoff": "好处是先校正方向；代价是本周新增结果可能变少，但能避免继续放大错误路径。",
            "recommended": improved == "no" or has_stage2_gap or has_stage3_gap or has_stage1_gap,
            "linked_task_ids": [item["id"] for item in task_package if item.get("strategy_ref") in {"stage1_replenishment_needed", "stage2_diagnosis_update_needed", "stage3_route_update_needed"}],
        },
        {
            "option_id": "O3",
            "title": "只做最小下一步",
            "when_to_choose": "本周时间有限，或任务阻力过高，不适合整包执行。",
            "tradeoff": "好处是完成率最高；代价是推进速度更慢，只适合维持闭环与拿关键反馈。",
            "recommended": weekly_hours <= 4 or risk_score <= 4 or average_friction >= 7,
            "linked_task_ids": [highest_friction_id] if highest_friction_id else top_task_ids[:1],
        },
    ]

    prioritized: list[dict] = []
    seen: set[str] = set()
    for item in sorted(options, key=lambda current: (not current["recommended"], current["option_id"])):
        option_id = str(item.get("option_id", "")).strip()
        if option_id and option_id not in seen:
            prioritized.append(item)
            seen.add(option_id)
    return prioritized


def build_review_body(payload: dict) -> str:
    lines = [
        f"# 【智能体生成】{payload['frontline_name']}本周作战方案 / {payload['week_range']}",
        "",
        "## 生成依据",
        "",
        f"- **用户档案：** `{payload['profile_ref']}`",
        f"- **数据看板：** {', '.join(f'`{item}`' for item in payload['dashboard_refs'])}",
        f"- **最近反馈：** {', '.join(f'`{item}`' for item in payload['feedback_refs'])}",
        f"- **档案摘要：** 12个月目标={payload['owner_goal']}；每周可投入={payload['weekly_hours']}；风险偏好={payload['risk_score']}；主偏好能力={payload['focus_area']}",
        f"- **上周数据：** {'；'.join(payload['dashboard_metric_summary']) or '待补充'}",
        f"- **图谱推演：** {payload['route_summary']}",
        "",
        "## 本周核心判断",
        "",
        f"- **主瓶颈：** {payload['primary_bottleneck']}",
        f"- **优先目标：** {payload['priority_goal']}",
        f"- **本周不建议做的事：** {'；'.join(payload['avoid_list']) or '无'}",
        "",
        "## 决策留白",
        "",
        f"- **决策问题：** {payload['decision_prompt']}",
        f"- **必须填写理由：** {'是' if payload['rationale_required'] else '否'}",
        "- **可选路径：**",
    ]
    for item in payload["decision_options"]:
        recommended = "推荐" if item.get("recommended") else "可选"
        linked_task_ids = [str(task_id).strip() for task_id in item.get("linked_task_ids", []) if str(task_id).strip()]
        task_text = "、".join(linked_task_ids) if linked_task_ids else "无"
        lines.extend(
            [
                f"  - `{item['option_id']}` {item['title']} [{recommended}]",
                f"    - **适用时机：** {item['when_to_choose']}",
                f"    - **取舍代价：** {item['tradeoff']}",
                f"    - **关联任务：** {task_text}",
            ]
        )
    lines.extend(
        [
            "- **老板填写区：** 我选择 `____`，原因是：`____`。",
            "",
        "## 交互人格输出",
        "",
        f"- **人格原型：** {payload['interaction_persona'].get('archetype', 'JARVIS')}",
        f"- **语气设定：** {payload['interaction_persona'].get('tone', '待补充')}",
        f"- **重大挫折回应：** {payload['interaction_persona'].get('setback_response', '待补充')}",
        "",
            "## 主动关怀与警报",
            "",
        ]
    )
    if payload["milestone_messages"]:
        lines.append("- **主动关怀消息：**")
        for item in payload["milestone_messages"]:
            lines.append(f"  - {item}")
    else:
        lines.append("- **主动关怀消息：** 当前未触发新的里程碑消息。")
    if payload["red_alert_messages"]:
        lines.append("- **红色警报：**")
        for item in payload["red_alert_messages"]:
            lines.append(f"  - {item}")
    else:
        lines.append("- **红色警报：** 当前未触发红色警报。")
    lines.extend(
        [
            "",
        "## 本周任务包",
        "",
        f"- **任务包总耗时：** {payload['total_estimated_hours']}",
        "",
        ]
    )
    for item in payload["task_package"]:
        lines.extend(
            [
                f"### 任务 {item['id']}：{item['title']}",
                f"- **诊断：** {item['diagnosis']}",
                f"- **策略：** {item['strategy_ref']}",
                f"- **动作：** {item['action']}",
                f"- **预计耗时：** {item['estimated_time']}",
                f"- **来源：** `{item['source_ref']}`",
                f"- **成功检查：** {item['success_check']}",
                "",
            ]
        )
        if item.get("execution_steps"):
            lines.append("- **执行步骤：**")
            for index, step in enumerate(item["execution_steps"], start=1):
                lines.append(f"  {index}. {step}")
        execution_friction = item.get("execution_friction", {})
        if execution_friction:
            platforms = execution_friction.get("platforms", [])
            platform_text = "、".join(platforms) if platforms else "当前任务未识别到额外平台"
            lines.append("- **执行阻力：**")
            lines.append(
                f"  - 认知负荷={execution_friction.get('cognitive_load', 'medium')}；平台数={execution_friction.get('platform_count', 1)}；上下文切换={execution_friction.get('context_switch_count', 0)}；阻力评分={execution_friction.get('estimated_friction_score', 0)} / 10"
            )
            lines.append(f"  - 涉及平台：{platform_text}")
            lines.append(f"  - 最小下一步：{execution_friction.get('minimum_next_step', '待补充')}")
            lines.append(
                f"  - 自动化候选：{'是' if execution_friction.get('automation_candidate') else '否'}；聚合建议：{execution_friction.get('consolidation_tip', '待补充')}"
            )
        bundle = item.get("execution_bundle", {})
        bundle_lines: list[str] = []
        for key, label in [
            ("action_packs", "动作包"),
            ("template_resources", "模板资源"),
            ("tool_calls", "工具调用"),
        ]:
            entries = bundle.get(key, [])
            if entries:
                bundle_lines.append(f"  - {label}：")
                for resource in entries:
                    bundle_lines.append(f"    - `{resource['resource_id']}` {resource['title']} -> `{resource['ref']}`")
        if bundle.get("case_refs"):
            bundle_lines.append(f"  - 关联案例：{', '.join(f'`{ref}`' for ref in bundle['case_refs'])}")
        if bundle_lines:
            lines.append("- **执行包：**")
            lines.extend(bundle_lines)
        if item.get("template_fields"):
            lines.append(f"- **模板字段：** {'；'.join(item['template_fields'])}")
        if item.get("tool_checks"):
            lines.append(f"- **检查清单：** {'；'.join(item['tool_checks'])}")
        if item.get("risk_notes"):
            lines.append(f"- **风险提示：** {'；'.join(item['risk_notes'])}")
        lines.append("")
    lines.extend(["## 授权项", ""])
    for key, label in [
        ("update_dashboard", "自动更新数据看板"),
        ("reopen_stage2", "自动回流阶段二"),
        ("trigger_stage1_replenishment", "自动挂起阶段一补库"),
    ]:
        lines.append(f"- **{label}：** {'是' if payload['authorizations'][key] else '否'}")
    lines.extend(
        [
            "",
            "## 老板确认",
            "",
            "- [ ] 我已阅读并理解本周方案。",
            "- [ ] 我已在“决策留白”里选择 1 条路径，并写下理由。",
            "- [ ] 我授权系统在本周执行后自动更新数据看板。",
            "- [ ] 我会按本周任务包回填执行反馈。",
        ]
    )
    lines.extend(["", "## 学习动作", ""])
    for item in payload["learning_actions"]:
        lines.append(f"- `{item['type']}` -> `{item['target_ref']}`：{item['proposed_change']}")
    lines.extend(
        [
            "",
            "## Structured Weekly Review",
            "",
            "```yaml",
            yaml.safe_dump({"weekly_review": payload["structured_payload"]}, allow_unicode=True, sort_keys=False).strip(),
            "```",
        ]
    )
    return "\n".join(lines).strip()


def update_dashboard_from_feedback(
    root: Path,
    dashboard_ref: str,
    profile_ref: str,
    frontline_name: str,
    platform: str,
    domain: str,
    metric_changes: list[dict],
    new_bottlenecks: list[str],
    feedback_ref: str,
    improved: str,
) -> str:
    existing_meta, existing_payload = load_dashboard(root, dashboard_ref)
    _profile_meta, profile_payload = load_profile(root, profile_ref)
    sync_protocol = profile_payload.get("sync_protocol", default_sync_protocol()) if isinstance(profile_payload, dict) else default_sync_protocol()
    milestone_rules = profile_payload.get("milestone_rules", default_milestone_rules()) if isinstance(profile_payload, dict) else default_milestone_rules()
    red_alert_protocol = profile_payload.get("red_alert_protocol", default_red_alert_protocol()) if isinstance(profile_payload, dict) else default_red_alert_protocol()
    metrics_update = [{"label": item["label"], "value": item["after"] or item["before"]} for item in metric_changes if item["label"]]
    payload = {
        "frontline_name": frontline_name,
        "platform": platform,
        "domain": domain,
        "status": "active",
        "alert_level": infer_alert_level(improved),
        "alert_reason": "收到新的执行反馈，需要回看当前前线状态。",
        "metrics": metrics_update,
        "content_items": [],
        "todos": new_bottlenecks or ["等待下一轮阶段四反馈。"],
        "notes": ["本次更新来自阶段四执行反馈。"],
        "source_refs": [feedback_ref],
        "sync_protocol": sync_protocol,
        "content_capture_fields": default_content_capture_fields(),
        "red_alert_protocol": red_alert_protocol,
        "milestone_messages": [],
        "red_alert_messages": [],
        "generated_stage2_session_ref": "",
        "generated_red_alert_dispatch_ref": "",
    }
    if existing_payload:
        payload["metrics"] = merge_metrics(existing_payload.get("metrics", []), metrics_update)
        payload["content_items"] = existing_payload.get("content_items", [])
        payload["todos"] = new_bottlenecks or existing_payload.get("todos", [])
        payload["notes"] = list(dict.fromkeys(existing_payload.get("notes", []) + ["本次状态已按阶段四反馈刷新。"]))
        payload["source_refs"] = list(dict.fromkeys(existing_payload.get("source_refs", []) + [feedback_ref]))
        payload["sync_protocol"] = existing_payload.get("sync_protocol", sync_protocol)
        payload["content_capture_fields"] = existing_payload.get("content_capture_fields", default_content_capture_fields())
        payload["red_alert_protocol"] = existing_payload.get("red_alert_protocol", red_alert_protocol)
        payload["generated_stage2_session_ref"] = str(existing_payload.get("generated_stage2_session_ref", "")).strip()
        payload["generated_red_alert_dispatch_ref"] = str(existing_payload.get("generated_red_alert_dispatch_ref", "")).strip()
    payload["milestone_messages"] = detect_milestone_messages(payload, milestone_rules)
    payload["red_alert_messages"] = detect_red_alert_messages(payload, payload.get("red_alert_protocol", red_alert_protocol))
    generated_stage2_session_ref = maybe_generate_stage2_red_alert_session(
        root=root,
        profile_ref=profile_ref,
        dashboard_ref=dashboard_ref,
        dashboard_payload=payload,
    )
    if generated_stage2_session_ref:
        payload["generated_stage2_session_ref"] = generated_stage2_session_ref
    generated_red_alert_dispatch_ref = generate_red_alert_dispatch(
        root=root,
        profile_ref=profile_ref,
        dashboard_ref=dashboard_ref,
        dashboard_payload=payload,
        generated_stage2_session_ref=payload["generated_stage2_session_ref"],
    )
    if generated_red_alert_dispatch_ref:
        payload["generated_red_alert_dispatch_ref"] = generated_red_alert_dispatch_ref

    meta = {
        "artifact_type": "frontline_dashboard",
        "dashboard_id": f"dashboard_{slugify(frontline_name)}".lower(),
        "title": f"【数据看板】{frontline_name}",
        "profile_ref": profile_ref,
        "frontline_name": frontline_name,
        "platform": platform,
        "domain": domain,
        "status": "active",
        "alert_level": payload["alert_level"],
        "last_synced_at": now_text(),
        "latest_feedback_ref": feedback_ref,
        "latest_review_ref": str(existing_meta.get("latest_review_ref", "")).strip() if existing_meta else "",
        "date": datetime.now().date().isoformat(),
    }
    path = root / dashboard_ref
    write_artifact(path, meta, build_dashboard_body(payload))
    return dashboard_ref


def generate_review(
    root: Path,
    profile_ref: str,
    source_feedback_ref: str,
    week_range: str,
    review_ref: str | None = None,
) -> str:
    profile_meta, profile_payload = load_profile(root, profile_ref)
    feedback_meta, feedback_body = read_markdown(root / source_feedback_ref)
    feedback_payload = extract_yaml_block(feedback_body, "Structured Stage4 Feedback").get("stage4_feedback", {})
    if not isinstance(feedback_payload, dict):
        raise SystemExit("ERROR: 阶段四 feedback 缺少有效 structured payload。")
    source_session_ref = str(feedback_payload.get("source_stage3_session", "")).strip()
    session_meta, solution_package = load_stage3_session(root, source_session_ref)
    learning_actions = feedback_payload.get("learning_actions", [])
    dashboard_ref = str(feedback_meta.get("dashboard_ref", "")).strip()
    dashboard_refs = [dashboard_ref] if dashboard_ref else []
    _dashboard_meta, dashboard_payload = load_dashboard(root, dashboard_ref) if dashboard_ref else (None, {})

    primary_bottleneck = feedback_payload.get("new_bottlenecks", ["当前主要瓶颈待补充"])[0] if feedback_payload.get("new_bottlenecks") else "当前主要瓶颈待补充"
    priority_goal = str(solution_package.get("target_goal", "")).strip() or str(session_meta.get("input_goal", "")).strip()
    avoid_list = []
    if feedback_payload.get("improved") == "no":
        avoid_list.append("不要在当前未验证路径上继续加码")
    if session_meta.get("autonomous_mode") is True:
        avoid_list.append("不要把 bootstrap 路径误当成成熟打法")
    if not avoid_list:
        avoid_list.append("不要脱离看板和反馈凭感觉扩动作")

    task_package = build_review_task_package(
        root=root,
        source_session_ref=source_session_ref,
        solution_package=solution_package,
        feedback_payload=feedback_payload,
        learning_actions=learning_actions,
        dashboard_ref=dashboard_ref or source_feedback_ref,
        profile_payload=profile_payload,
        dashboard_payload=dashboard_payload or {},
    )
    route_summary = f"{session_meta.get('normalized_goal', session_meta.get('input_goal', ''))} -> {solution_package.get('primary_strategy', '待补充')}"
    secondary_strategies = solution_package.get("secondary_strategies", [])
    if secondary_strategies:
        route_summary += f" -> {', '.join(str(item).strip() for item in secondary_strategies if str(item).strip())}"
    total_hours = sum(parse_hour_value(item.get("estimated_time", "")) for item in task_package)
    total_estimated_hours = f"{total_hours} 小时" if total_hours else "待估算"
    goals = profile_payload.get("goals_and_preferences", {}) if isinstance(profile_payload, dict) else {}
    resources = profile_payload.get("resource_profile", {}) if isinstance(profile_payload, dict) else {}
    dashboard_metric_summary = summarize_dashboard_metrics(dashboard_payload or {})
    interaction_persona = profile_payload.get("interaction_persona", default_interaction_persona()) if isinstance(profile_payload, dict) else default_interaction_persona()
    milestone_rules = profile_payload.get("milestone_rules", default_milestone_rules()) if isinstance(profile_payload, dict) else default_milestone_rules()
    red_alert_protocol = profile_payload.get("red_alert_protocol", default_red_alert_protocol()) if isinstance(profile_payload, dict) else default_red_alert_protocol()
    human_judgment_policy = profile_payload.get("human_judgment_policy", default_human_judgment_policy()) if isinstance(profile_payload, dict) else default_human_judgment_policy()
    milestone_messages = detect_milestone_messages(dashboard_payload or {}, milestone_rules)
    red_alert_messages = detect_red_alert_messages(dashboard_payload or {}, red_alert_protocol)
    decision_options = build_decision_options(
        task_package=task_package,
        learning_actions=learning_actions,
        feedback_payload=feedback_payload,
        profile_payload=profile_payload,
    )

    authorizations = feedback_payload.get("authorization", {})
    structured_payload = {
        "source_refs": [profile_ref, *dashboard_refs, source_feedback_ref, source_session_ref],
        "core_judgment": {
            "primary_bottleneck": primary_bottleneck,
            "priority_goal": priority_goal,
            "avoid_list": avoid_list,
        },
        "task_package": task_package,
        "decision_options": decision_options,
        "decision_prompt": str(human_judgment_policy.get("decision_prompt", "")).strip() or "本周只能押注一个主路径时，你选择哪一个？请写出选择理由。",
        "rationale_required": bool(human_judgment_policy.get("rationale_required", True)),
        "owner_snapshot": {
            "primary_goal_12m": str(goals.get("primary_goal_12m", "")).strip(),
            "weekly_hours": str(resources.get("weekly_hours", "")).strip(),
            "risk_score": goals.get("risk_score"),
            "focus_area": str(goals.get("focus_area", "")).strip(),
        },
        "dashboard_snapshot": {
            "frontline_name": str(dashboard_payload.get("frontline_name", "")).strip(),
            "metric_summary": dashboard_metric_summary,
        },
        "interaction_persona": interaction_persona,
        "human_judgment_policy": human_judgment_policy,
        "milestone_messages": milestone_messages,
        "red_alert_messages": red_alert_messages,
        "route_summary": route_summary,
        "total_estimated_hours": total_estimated_hours,
        "authorizations": {
            "update_dashboard": bool(authorizations.get("update_dashboard")),
            "reopen_stage2": bool(authorizations.get("reopen_stage2")),
            "trigger_stage1_replenishment": bool(authorizations.get("trigger_stage1_replenishment")),
        },
        "learning_actions": learning_actions,
    }

    frontline_name = str(feedback_payload.get("frontline_name", "")).strip() or str(session_meta.get("platform", "")).strip()
    if not review_ref:
        review_ref = f"stage4_models/reviews/{datetime.now().date()}_{slugify(frontline_name)}.md"
    meta = {
        "artifact_type": "weekly_strategy_review",
        "review_id": f"weekly_review_{datetime.now().strftime('%Y%m%d')}_{slugify(frontline_name)}".lower(),
        "title": f"【每周战略复盘会】{frontline_name}",
        "status": "ready",
        "profile_ref": profile_ref,
        "dashboard_refs": dashboard_refs,
        "feedback_refs": [source_feedback_ref],
        "week_range": week_range,
        "date": datetime.now().date().isoformat(),
    }
    payload = {
        "frontline_name": frontline_name,
        "profile_ref": profile_ref,
        "dashboard_refs": dashboard_refs,
        "feedback_refs": [source_feedback_ref],
        "week_range": week_range,
        "primary_bottleneck": primary_bottleneck,
        "priority_goal": priority_goal,
        "avoid_list": avoid_list,
        "owner_goal": str(goals.get("primary_goal_12m", "")).strip() or str(profile_meta.get("primary_goal", "")).strip(),
        "weekly_hours": str(resources.get("weekly_hours", "")).strip() or "待补充",
        "risk_score": str(goals.get("risk_score", profile_meta.get("risk_score", ""))).strip() or "待补充",
        "focus_area": str(goals.get("focus_area", profile_meta.get("focus_area", ""))).strip() or "待补充",
        "dashboard_metric_summary": dashboard_metric_summary,
        "interaction_persona": interaction_persona,
        "decision_options": decision_options,
        "decision_prompt": structured_payload["decision_prompt"],
        "rationale_required": structured_payload["rationale_required"],
        "milestone_messages": milestone_messages,
        "red_alert_messages": red_alert_messages,
        "route_summary": route_summary,
        "total_estimated_hours": total_estimated_hours,
        "task_package": task_package,
        "authorizations": structured_payload["authorizations"],
        "learning_actions": learning_actions,
        "structured_payload": structured_payload,
    }
    path = root / review_ref
    write_artifact(path, meta, build_review_body(payload))

    if dashboard_refs:
        dashboard_meta, dashboard_payload = load_dashboard(root, dashboard_refs[0])
        if dashboard_meta and dashboard_payload:
            dashboard_meta["latest_review_ref"] = review_ref
            write_artifact(root / dashboard_refs[0], dashboard_meta, build_dashboard_body(dashboard_payload))

    feedback_meta["generated_review_ref"] = review_ref
    write_artifact(root / source_feedback_ref, feedback_meta, feedback_body)
    return review_ref


def load_feedback_payload(root: Path, ref: str) -> tuple[dict, dict]:
    path = root / ref
    if not path.exists():
        raise SystemExit(f"ERROR: 未找到阶段四 feedback：{ref}")
    meta, body = read_markdown(path)
    payload = extract_yaml_block(body, "Structured Stage4 Feedback").get("stage4_feedback", {})
    if not isinstance(payload, dict):
        raise SystemExit("ERROR: 阶段四 feedback 缺少有效 structured payload。")
    return meta, payload


def build_monthly_model_review_body(payload: dict) -> str:
    lines = [
        f"# 【月度模型修正会】{payload['month_range']}",
        "",
        "## 生成依据",
        "",
        f"- **用户档案：** `{payload['profile_ref']}`",
        f"- **反馈记录：** {', '.join(f'`{item}`' for item in payload['feedback_refs'])}",
        "",
        "## 本月反馈概览",
        "",
        f"- **反馈记录数：** {payload['feedback_count']}",
        f"- **平均有效性评分：** {payload['average_effectiveness_score']} 分",
        f"- **最高频主瓶颈：** {'；'.join(payload['top_bottlenecks']) or '待补充'}",
        "",
        "## 模型修正清单",
        "",
    ]
    for item in payload["correction_backlog"]:
        lines.extend(
            [
                f"### {item['slot']}",
                f"- **状态：** {item['status']}",
                f"- **涉及记录：** {', '.join(f'`{ref}`' for ref in item['feedback_refs'])}",
                f"- **目标文件：** `{item['target_ref']}`",
                f"- **执行动作：** {item['proposed_change']}",
                "",
            ]
        )
    lines.extend(["## 修正执行决议", ""])
    for item in payload["execution_decisions"]:
        lines.append(f"- `{item['slot']}` -> `{item['target_ref']}`：{item['decision']}")
    lines.extend(
        [
            "",
            "## Structured Monthly Model Review",
            "",
            "```yaml",
            yaml.safe_dump({"monthly_model_review": payload["structured_payload"]}, allow_unicode=True, sort_keys=False).strip(),
            "```",
        ]
    )
    return "\n".join(lines).strip()


def generate_monthly_model_review(
    root: Path,
    profile_ref: str,
    feedback_refs: list[str],
    month_range: str,
    review_ref: str | None = None,
) -> str:
    _profile_meta, _profile_payload = load_profile(root, profile_ref)
    normalized_feedback_refs = [str(ref).strip() for ref in feedback_refs if str(ref).strip()]
    if not normalized_feedback_refs:
        raise SystemExit("ERROR: 月度模型修正会至少需要 1 条 feedback 记录。")

    feedback_payloads: list[tuple[str, dict, dict]] = []
    bottlenecks: list[str] = []
    total_score = 0
    slot_backlog: dict[str, dict] = {}

    for ref in normalized_feedback_refs:
        meta, payload = load_feedback_payload(root, ref)
        feedback_payloads.append((ref, meta, payload))
        corrections = payload.get("model_corrections", {}) if isinstance(payload, dict) else {}
        total_score += int(corrections.get("effectiveness_score", 0) or 0)
        bottlenecks.extend(str(item).strip() for item in payload.get("new_bottlenecks", []) if str(item).strip())
        for slot in corrections.get("correction_slots", []):
            slot_name = str(slot.get("slot", "")).strip()
            if not slot_name or str(slot.get("status", "")).strip() != "required":
                continue
            existing = slot_backlog.setdefault(
                slot_name,
                {
                    "slot": slot_name,
                    "status": "required",
                    "feedback_refs": [],
                    "target_ref": str(slot.get("target_ref", "")).strip(),
                    "proposed_change": str(slot.get("proposed_change", "")).strip(),
                },
            )
            existing["feedback_refs"].append(ref)
            if len(str(slot.get("proposed_change", "")).strip()) > len(existing["proposed_change"]):
                existing["proposed_change"] = str(slot.get("proposed_change", "")).strip()
            if not existing["target_ref"]:
                existing["target_ref"] = str(slot.get("target_ref", "")).strip()

    correction_backlog = list(slot_backlog.values())
    if not correction_backlog:
        correction_backlog = [
            {
                "slot": "本月无新增模型修正",
                "status": "not_needed",
                "feedback_refs": normalized_feedback_refs,
                "target_ref": profile_ref,
                "proposed_change": "本月暂无需要新增的图谱、专家模型或资源库修正。",
            }
        ]

    execution_decisions = []
    for item in correction_backlog:
        execution_decisions.append(
            {
                "slot": item["slot"],
                "target_ref": item["target_ref"],
                "decision": f"将本月同类修正合并为 1 条正式修正工单，并在下次执行前完成回写。{item['proposed_change']}",
            }
        )

    top_bottlenecks = list(dict.fromkeys(bottlenecks))[:3]
    average_score = round(total_score / len(normalized_feedback_refs), 1) if normalized_feedback_refs else 0.0
    structured_payload = {
        "source_refs": [profile_ref, *normalized_feedback_refs],
        "summary": {
            "feedback_count": len(normalized_feedback_refs),
            "average_effectiveness_score": average_score,
            "top_bottlenecks": top_bottlenecks,
        },
        "correction_backlog": correction_backlog,
        "execution_decisions": execution_decisions,
    }

    if not review_ref:
        safe_month = month_range.replace(" ", "").replace("~", "_").replace("/", "-")
        review_ref = f"stage4_models/model_reviews/{safe_month}.md"
    meta = {
        "artifact_type": "monthly_model_review",
        "review_id": f"monthly_model_review_{slugify(month_range)}".lower(),
        "title": f"【月度模型修正会】{month_range}",
        "status": "ready",
        "profile_ref": profile_ref,
        "feedback_refs": normalized_feedback_refs,
        "month_range": month_range,
        "date": datetime.now().date().isoformat(),
    }
    payload = {
        "profile_ref": profile_ref,
        "feedback_refs": normalized_feedback_refs,
        "month_range": month_range,
        "feedback_count": len(normalized_feedback_refs),
        "average_effectiveness_score": average_score,
        "top_bottlenecks": top_bottlenecks,
        "correction_backlog": correction_backlog,
        "execution_decisions": execution_decisions,
        "structured_payload": structured_payload,
    }
    write_artifact(root / review_ref, meta, build_monthly_model_review_body(payload))
    return review_ref


def handle_init_profile(root: Path, args: argparse.Namespace) -> str:
    profile_ref = args.profile_ref or DEFAULT_PROFILE_REF
    sync_protocol = {
        "frequency": args.sync_frequency or "daily",
        "time": args.sync_time or "17:00",
        "duration": args.sync_duration or "10分钟",
        "method": args.sync_method or "手动同步",
        "instruction": args.sync_instruction or "每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。",
    }
    payload = {
        "owner_name": args.owner_name,
        "resource_profile": {
            "monthly_cashflow": args.monthly_cashflow,
            "weekly_hours": args.weekly_hours,
            "core_skills": args.skill or [],
            "startup_resources": args.startup_resource or [],
        },
        "goals_and_preferences": {
            "primary_goal_12m": args.goal_12m,
            "risk_score": args.risk_score,
            "focus_area": args.focus_area,
            "interaction_preferences": args.interaction_preference or ["每周战略复盘"],
        },
        "frontlines": args.frontline or [],
        "sync_protocol": sync_protocol,
        "interaction_persona": default_interaction_persona(),
        "milestone_rules": default_milestone_rules(),
        "red_alert_protocol": default_red_alert_protocol(),
        "human_judgment_policy": default_human_judgment_policy(),
    }
    meta = {
        "artifact_type": "owner_profile",
        "profile_id": f"owner_profile_{slugify(args.owner_name)}".lower(),
        "title": f"【我的商业档案】{args.owner_name}",
        "owner_name": args.owner_name,
        "status": "active",
        "review_cycle": args.review_cycle,
        "primary_goal": args.goal_12m,
        "risk_score": args.risk_score,
        "focus_area": args.focus_area,
        "frontlines": args.frontline or [],
        "date": datetime.now().date().isoformat(),
    }
    path = root / profile_ref
    write_artifact(path, meta, build_owner_profile_body(payload))
    entry_path = root / PROFILE_ENTRY_REF
    entry_path.write_text(build_profile_entry_body(profile_ref), encoding="utf-8")
    return profile_ref


def handle_sync_dashboard(root: Path, args: argparse.Namespace) -> str:
    profile_ref = args.profile_ref or DEFAULT_PROFILE_REF
    _profile_meta, profile_payload = load_profile(root, profile_ref)
    dashboard_ref = args.dashboard_ref or infer_dashboard_ref(args.frontline_name)
    existing_meta, existing_payload = load_dashboard(root, dashboard_ref)
    sync_protocol = profile_payload.get("sync_protocol", default_sync_protocol()) if isinstance(profile_payload, dict) else default_sync_protocol()
    milestone_rules = profile_payload.get("milestone_rules", default_milestone_rules()) if isinstance(profile_payload, dict) else default_milestone_rules()
    red_alert_protocol = profile_payload.get("red_alert_protocol", default_red_alert_protocol()) if isinstance(profile_payload, dict) else default_red_alert_protocol()
    metrics = [{"label": key, "value": value} for key, value in (parse_key_value(item) for item in args.metric or []) if key]
    payload = {
        "frontline_name": args.frontline_name,
        "platform": args.platform,
        "domain": args.domain,
        "status": "active",
        "alert_level": args.alert_level,
        "alert_reason": args.alert_reason or "按手动同步结果更新。",
        "metrics": metrics,
        "content_items": args.content_item or [],
        "todos": args.todo or [],
        "notes": args.note or [],
        "source_refs": [],
        "sync_protocol": sync_protocol,
        "content_capture_fields": default_content_capture_fields(),
        "red_alert_protocol": red_alert_protocol,
        "milestone_messages": [],
        "red_alert_messages": [],
        "generated_stage2_session_ref": "",
        "generated_red_alert_dispatch_ref": "",
    }
    if existing_payload:
        payload["metrics"] = merge_metrics(existing_payload.get("metrics", []), metrics)
        payload["content_items"] = args.content_item or existing_payload.get("content_items", [])
        payload["todos"] = args.todo or existing_payload.get("todos", [])
        payload["notes"] = existing_payload.get("notes", []) + (args.note or [])
        payload["source_refs"] = existing_payload.get("source_refs", [])
        payload["sync_protocol"] = existing_payload.get("sync_protocol", sync_protocol)
        payload["content_capture_fields"] = existing_payload.get("content_capture_fields", default_content_capture_fields())
        payload["red_alert_protocol"] = existing_payload.get("red_alert_protocol", red_alert_protocol)
        payload["generated_stage2_session_ref"] = str(existing_payload.get("generated_stage2_session_ref", "")).strip()
        payload["generated_red_alert_dispatch_ref"] = str(existing_payload.get("generated_red_alert_dispatch_ref", "")).strip()
    payload["milestone_messages"] = detect_milestone_messages(payload, milestone_rules)
    payload["red_alert_messages"] = detect_red_alert_messages(payload, payload.get("red_alert_protocol", red_alert_protocol))
    generated_stage2_session_ref = maybe_generate_stage2_red_alert_session(
        root=root,
        profile_ref=profile_ref,
        dashboard_ref=dashboard_ref,
        dashboard_payload=payload,
    )
    if generated_stage2_session_ref:
        payload["generated_stage2_session_ref"] = generated_stage2_session_ref
    generated_red_alert_dispatch_ref = generate_red_alert_dispatch(
        root=root,
        profile_ref=profile_ref,
        dashboard_ref=dashboard_ref,
        dashboard_payload=payload,
        generated_stage2_session_ref=payload["generated_stage2_session_ref"],
    )
    if generated_red_alert_dispatch_ref:
        payload["generated_red_alert_dispatch_ref"] = generated_red_alert_dispatch_ref

    meta = {
        "artifact_type": "frontline_dashboard",
        "dashboard_id": f"dashboard_{slugify(args.frontline_name)}".lower(),
        "title": f"【数据看板】{args.frontline_name}",
        "profile_ref": profile_ref,
        "frontline_name": args.frontline_name,
        "platform": args.platform,
        "domain": args.domain,
        "status": "active",
        "alert_level": args.alert_level,
        "last_synced_at": now_text(),
        "latest_feedback_ref": str(existing_meta.get("latest_feedback_ref", "")).strip() if existing_meta else "",
        "latest_review_ref": str(existing_meta.get("latest_review_ref", "")).strip() if existing_meta else "",
        "date": datetime.now().date().isoformat(),
    }
    path = root / dashboard_ref
    write_artifact(path, meta, build_dashboard_body(payload))
    return dashboard_ref


def handle_process_feedback(root: Path, args: argparse.Namespace) -> tuple[str, str | None]:
    profile_ref = args.profile_ref or DEFAULT_PROFILE_REF
    _profile_meta, _profile_payload = load_profile(root, profile_ref)
    session_meta, solution_package = load_stage3_session(root, args.source_stage3_session)
    audit_ref = str(session_meta.get("audit_ref", "")).strip()
    _audit_meta, audit_payload = load_stage3_audit(root, audit_ref)

    frontline_name = args.frontline_name or f"{session_meta.get('platform', '')} / {session_meta.get('input_goal', '')}".strip(" /")
    dashboard_ref = args.dashboard_ref or infer_dashboard_ref(frontline_name)
    feedback_ref = args.feedback_ref or f"stage4_models/feedback/{datetime.now().date()}_{slugify(frontline_name)}.md"
    metric_changes = parse_metric_changes(args.metric_change or [])

    learning_actions = build_learning_actions(
        improved=args.improved,
        session_meta=session_meta,
        audit_ref=audit_ref,
        audit_payload=audit_payload,
        dashboard_ref=dashboard_ref,
        feedback_ref=feedback_ref,
        allow_dashboard_update=args.allow_dashboard_update,
        allow_review_generation=args.allow_review_generation,
        allow_reopen_stage2=args.allow_reopen_stage2,
        allow_stage1_replenishment=args.allow_stage1_replenishment,
        new_bottlenecks=args.new_bottleneck or [],
    )
    summary_judgment = derive_summary_judgment(args.improved, learning_actions)
    needs_stage2 = any(item["type"] == "stage2_diagnosis_update_needed" for item in learning_actions)
    needs_stage1 = any(item["type"] == "stage1_replenishment_needed" for item in learning_actions)
    primary_bottleneck = (args.new_bottleneck or ["当前主要瓶颈待补充"])[0]
    effectiveness_score, effectiveness_note = derive_effectiveness_score(args.improved, args.new_bottleneck or [], learning_actions)
    model_correction_slots = build_model_correction_slots(
        learning_actions=learning_actions,
        primary_bottleneck=primary_bottleneck,
        source_session_ref=args.source_stage3_session,
        feedback_ref=feedback_ref,
    )

    structured_payload = {
        "frontline_name": frontline_name,
        "source_stage3_session": args.source_stage3_session,
        "executed_tasks": args.executed_task or [],
        "observed_metric_changes": metric_changes,
        "improved": args.improved,
        "new_bottlenecks": args.new_bottleneck or [],
        "observations": args.observation or [],
        "authorization": {
            "update_dashboard": args.allow_dashboard_update,
            "generate_review": args.allow_review_generation,
            "reopen_stage2": args.allow_reopen_stage2,
            "trigger_stage1_replenishment": args.allow_stage1_replenishment,
        },
        "learning_actions": learning_actions,
        "model_corrections": {
            "effectiveness_score": effectiveness_score,
            "effectiveness_note": effectiveness_note,
            "correction_slots": model_correction_slots,
        },
    }

    payload = {
        "frontline_name": frontline_name,
        "target_goal": str(solution_package.get("target_goal", "")).strip() or str(session_meta.get("input_goal", "")).strip(),
        "source_stage3_session": args.source_stage3_session,
        "executed_tasks": args.executed_task or [],
        "improved": args.improved,
        "observed_metric_changes": metric_changes,
        "new_bottlenecks": args.new_bottleneck or [],
        "observations": args.observation or [],
        "summary_judgment": summary_judgment,
        "needs_stage2": needs_stage2,
        "needs_stage1": needs_stage1,
        "learning_actions": learning_actions,
        "effectiveness_score": effectiveness_score,
        "effectiveness_note": effectiveness_note,
        "model_correction_slots": model_correction_slots,
        "structured_payload": structured_payload,
    }

    if args.allow_dashboard_update and not (root / dashboard_ref).exists():
        _profile_meta, profile_payload = load_profile(root, profile_ref)
        sync_protocol = profile_payload.get("sync_protocol", default_sync_protocol()) if isinstance(profile_payload, dict) else default_sync_protocol()
        milestone_rules = profile_payload.get("milestone_rules", default_milestone_rules()) if isinstance(profile_payload, dict) else default_milestone_rules()
        red_alert_protocol = profile_payload.get("red_alert_protocol", default_red_alert_protocol()) if isinstance(profile_payload, dict) else default_red_alert_protocol()
        seed_metrics = [{"label": item["label"], "value": item["after"] or item["before"]} for item in metric_changes if item["label"]]
        seed_dashboard_payload = {
            "frontline_name": frontline_name,
            "platform": str(session_meta.get("platform", "")).strip(),
            "domain": str(session_meta.get("domain", "")).strip(),
            "status": "active",
            "alert_level": infer_alert_level(args.improved),
            "alert_reason": "首次阶段四反馈自动创建看板。",
            "metrics": seed_metrics,
            "content_items": [],
            "todos": args.new_bottleneck or ["等待下一轮阶段四反馈。"],
            "notes": ["首次看板由阶段四执行反馈自动创建。"],
            "source_refs": [],
            "sync_protocol": sync_protocol,
            "content_capture_fields": default_content_capture_fields(),
            "red_alert_protocol": red_alert_protocol,
            "milestone_messages": [],
            "red_alert_messages": [],
            "generated_stage2_session_ref": "",
            "generated_red_alert_dispatch_ref": "",
        }
        seed_dashboard_payload["milestone_messages"] = detect_milestone_messages(seed_dashboard_payload, milestone_rules)
        seed_dashboard_payload["red_alert_messages"] = detect_red_alert_messages(seed_dashboard_payload, red_alert_protocol)
        generated_stage2_session_ref = maybe_generate_stage2_red_alert_session(
            root=root,
            profile_ref=profile_ref,
            dashboard_ref=dashboard_ref,
            dashboard_payload=seed_dashboard_payload,
        )
        if generated_stage2_session_ref:
            seed_dashboard_payload["generated_stage2_session_ref"] = generated_stage2_session_ref
        generated_red_alert_dispatch_ref = generate_red_alert_dispatch(
            root=root,
            profile_ref=profile_ref,
            dashboard_ref=dashboard_ref,
            dashboard_payload=seed_dashboard_payload,
            generated_stage2_session_ref=seed_dashboard_payload["generated_stage2_session_ref"],
        )
        if generated_red_alert_dispatch_ref:
            seed_dashboard_payload["generated_red_alert_dispatch_ref"] = generated_red_alert_dispatch_ref
        seed_dashboard_meta = {
            "artifact_type": "frontline_dashboard",
            "dashboard_id": f"dashboard_{slugify(frontline_name)}".lower(),
            "title": f"【数据看板】{frontline_name}",
            "profile_ref": profile_ref,
            "frontline_name": frontline_name,
            "platform": str(session_meta.get("platform", "")).strip(),
            "domain": str(session_meta.get("domain", "")).strip(),
            "status": "active",
            "alert_level": seed_dashboard_payload["alert_level"],
            "last_synced_at": now_text(),
            "latest_feedback_ref": "",
            "latest_review_ref": "",
            "date": datetime.now().date().isoformat(),
        }
        write_artifact(root / dashboard_ref, seed_dashboard_meta, build_dashboard_body(seed_dashboard_payload))

    meta = {
        "artifact_type": "stage4_feedback_record",
        "feedback_id": f"stage4_feedback_{datetime.now().strftime('%Y%m%d')}_{slugify(frontline_name)}".lower(),
        "title": f"【阶段四执行反馈】{frontline_name}",
        "status": "ready",
        "profile_ref": profile_ref,
        "dashboard_ref": dashboard_ref,
        "source_stage3_session": args.source_stage3_session,
        "generated_review_ref": "",
        "improved": args.improved,
        "date": datetime.now().date().isoformat(),
    }
    path = root / feedback_ref
    write_artifact(path, meta, build_feedback_body(payload))

    if args.allow_dashboard_update:
        update_dashboard_from_feedback(
            root=root,
            dashboard_ref=dashboard_ref,
            profile_ref=profile_ref,
            frontline_name=frontline_name,
            platform=str(session_meta.get("platform", "")).strip(),
            domain=str(session_meta.get("domain", "")).strip(),
            metric_changes=metric_changes,
            new_bottlenecks=args.new_bottleneck or [],
            feedback_ref=feedback_ref,
            improved=args.improved,
        )

    generated_review_ref: str | None = None
    if args.allow_review_generation:
        generated_review_ref = generate_review(
            root=root,
            profile_ref=profile_ref,
            source_feedback_ref=feedback_ref,
            week_range=args.week_range or f"{datetime.now().date()} ~ {datetime.now().date()}",
            review_ref=args.review_ref,
        )
    return feedback_ref, generated_review_ref


def handle_generate_review(root: Path, args: argparse.Namespace) -> str:
    profile_ref = args.profile_ref or DEFAULT_PROFILE_REF
    _profile_meta, _profile_payload = load_profile(root, profile_ref)
    if not args.source_feedback:
        raise SystemExit("ERROR: `generate-review` 模式必须提供 `--source-feedback`。")
    return generate_review(
        root=root,
        profile_ref=profile_ref,
        source_feedback_ref=args.source_feedback,
        week_range=args.week_range or f"{datetime.now().date()} ~ {datetime.now().date()}",
        review_ref=args.review_ref,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Buildmate stage-4 profile/dashboard/feedback/review cycle.")
    parser.add_argument("--mode", required=True, choices=["init-profile", "sync-dashboard", "process-feedback", "generate-review", "generate-model-review"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile-ref", default=DEFAULT_PROFILE_REF)

    parser.add_argument("--owner-name")
    parser.add_argument("--monthly-cashflow")
    parser.add_argument("--weekly-hours")
    parser.add_argument("--skill", action="append", default=[])
    parser.add_argument("--startup-resource", action="append", default=[])
    parser.add_argument("--goal-12m")
    parser.add_argument("--risk-score", type=int, default=5)
    parser.add_argument("--focus-area")
    parser.add_argument("--interaction-preference", action="append", default=[])
    parser.add_argument("--frontline", action="append", default=[])
    parser.add_argument("--review-cycle", default="quarterly")
    parser.add_argument("--sync-frequency", default="daily")
    parser.add_argument("--sync-time", default="17:00")
    parser.add_argument("--sync-duration", default="10分钟")
    parser.add_argument("--sync-method", default="手动同步")
    parser.add_argument("--sync-instruction", default="每天下午5点，花10分钟，把各前线关键数据更新到对应数据看板。")

    parser.add_argument("--dashboard-ref")
    parser.add_argument("--frontline-name")
    parser.add_argument("--platform")
    parser.add_argument("--domain")
    parser.add_argument("--metric", action="append", default=[])
    parser.add_argument("--content-item", action="append", default=[])
    parser.add_argument("--todo", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--alert-level", default="normal")
    parser.add_argument("--alert-reason", default="")

    parser.add_argument("--source-stage3-session")
    parser.add_argument("--feedback-ref")
    parser.add_argument("--executed-task", action="append", default=[])
    parser.add_argument("--metric-change", action="append", default=[])
    parser.add_argument("--improved", choices=["yes", "partial", "no"], default="partial")
    parser.add_argument("--new-bottleneck", action="append", default=[])
    parser.add_argument("--observation", action="append", default=[])
    parser.add_argument("--allow-dashboard-update", action="store_true")
    parser.add_argument("--allow-review-generation", action="store_true")
    parser.add_argument("--allow-reopen-stage2", action="store_true")
    parser.add_argument("--allow-stage1-replenishment", action="store_true")

    parser.add_argument("--source-feedback")
    parser.add_argument("--source-feedback-ref", action="append", default=[])
    parser.add_argument("--review-ref")
    parser.add_argument("--week-range")
    parser.add_argument("--month-range")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if args.mode == "init-profile":
        for field_name in ["owner_name", "monthly_cashflow", "weekly_hours", "goal_12m", "focus_area"]:
            if getattr(args, field_name) in {None, ""}:
                raise SystemExit(f"ERROR: `init-profile` 模式缺少必要参数：{field_name}")
        profile_ref = handle_init_profile(root, args)
        print(f"OK: stage4 profile ready -> {profile_ref}")
        return

    if args.mode == "sync-dashboard":
        for field_name in ["frontline_name", "platform", "domain"]:
            if getattr(args, field_name) in {None, ""}:
                raise SystemExit(f"ERROR: `sync-dashboard` 模式缺少必要参数：{field_name}")
        dashboard_ref = handle_sync_dashboard(root, args)
        print(f"OK: stage4 dashboard ready -> {dashboard_ref}")
        return

    if args.mode == "process-feedback":
        if not args.source_stage3_session:
            raise SystemExit("ERROR: `process-feedback` 模式必须提供 `--source-stage3-session`。")
        feedback_ref, review_ref = handle_process_feedback(root, args)
        print(f"OK: stage4 feedback ready -> {feedback_ref}")
        if review_ref:
            print(f"OK: stage4 review ready -> {review_ref}")
        return

    if args.mode == "generate-review":
        review_ref = handle_generate_review(root, args)
        print(f"OK: stage4 review ready -> {review_ref}")
        return

    if args.mode == "generate-model-review":
        feedback_refs = args.source_feedback_ref or ([args.source_feedback] if args.source_feedback else [])
        review_ref = generate_monthly_model_review(
            root=root,
            profile_ref=args.profile_ref or DEFAULT_PROFILE_REF,
            feedback_refs=feedback_refs,
            month_range=args.month_range or datetime.now().strftime("%Y-%m"),
            review_ref=args.review_ref,
        )
        print(f"OK: stage4 model review ready -> {review_ref}")
        return


if __name__ == "__main__":
    main()
