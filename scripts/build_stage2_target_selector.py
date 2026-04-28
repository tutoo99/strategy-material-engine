#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _buildmate_lib import ensure_list, normalize_whitespace, slugify, today_iso, write_markdown


BROAD_TERMS = {
    "怎么赚钱",
    "怎么引流",
    "怎么做增长",
    "怎么做内容",
    "如何赚钱",
    "如何引流",
    "如何增长",
}

METRIC_HINTS = [
    ("阅读量", ["阅读量", "小眼睛", "曝光", "播放"]),
    ("完播率", ["完播率", "留存", "看完"]),
    ("点击率", ["点击率", "ctr", "点击"]),
    ("转化率", ["转化率", "成交", "出单"]),
    ("回复率", ["回复", "破冰", "开口"]),
    ("出单数", ["出单", "订单", "成交"]),
]

PLATFORM_HINTS = [
    "小红书",
    "抖音",
    "B站",
    "YouTube",
    "微信",
    "公众号",
    "私域",
    "独立站",
]

CONCRETE_PATTERNS = [
    "卡",
    "低",
    "不出",
    "不会",
    "没",
    "跟不上",
    "不上去",
    "极低",
    "高但",
    "无",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build stage2 target selector outputs from stage1 case index.")
    parser.add_argument("--root", default=".", help="Path to strategy-material-engine root")
    parser.add_argument("--top", type=int, default=20, help="Max candidates to include in report")
    return parser.parse_args()


def is_broad(symptom: str) -> bool:
    cleaned = normalize_whitespace(symptom)
    if cleaned in BROAD_TERMS:
        return True
    if len(cleaned) <= 4 and ("赚钱" in cleaned or "引流" in cleaned or "增长" in cleaned):
        return True
    return False


def concreteness_score(symptom: str) -> int:
    score = 0
    if any(token in symptom for token, _ in METRIC_HINTS):
        score += 2
    if any(platform in symptom for platform in PLATFORM_HINTS):
        score += 1
    if any(pattern in symptom for pattern in CONCRETE_PATTERNS):
        score += 2
    if re.search(r"\d", symptom):
        score += 1
    if len(symptom) >= 6:
        score += 1
    return score


def detect_metrics(symptom: str) -> list[str]:
    hits: list[str] = []
    lowered = symptom.lower()
    for label, keywords in METRIC_HINTS:
        if any(keyword.lower() in lowered for keyword in keywords):
            hits.append(label)
    return hits


def detect_platforms(symptom: str, case_platform: str) -> list[str]:
    hits: list[str] = []
    haystack = f"{symptom} {case_platform}"
    for platform in PLATFORM_HINTS:
        if platform in haystack and platform not in hits:
            hits.append(platform)
    return hits


def evidence_status(formal_case_count: int, total_frequency: int) -> str:
    if formal_case_count >= 5:
        return "formal"
    if formal_case_count > 0:
        return "bootstrap"
    if total_frequency > 0:
        return "provisional"
    return "empty"


def build_training_ground(root: Path, candidate: dict) -> str:
    training_dir = root / "expert_models" / "training_grounds"
    slug = slugify(candidate["normalized_symptom"])
    output_path = training_dir / f"{slug}.md"
    training_page_title = candidate["training_title"]
    if not training_page_title.endswith("诊断"):
        training_page_title = f"{training_page_title}诊断"
    meta = {
        "training_ground_id": f"stage2_tg_{slug}",
        "title": f"【专家模型训练场：{training_page_title}】",
        "scope": "阶段二",
        "target_symptom": candidate["symptom"],
        "normalized_symptom": candidate["normalized_symptom"],
        "platform": " / ".join(candidate["platforms"]) if candidate["platforms"] else "待补充",
        "scene": "待补充",
        "status": "draft",
        "evidence_status": candidate["evidence_status"],
        "symptom_frequency": candidate["frequency"],
        "formal_case_count": candidate["formal_case_count"],
        "case_refs": candidate["case_refs"][:10],
        "created_from": "index/stage2/target_selection_report.md",
        "date": today_iso(),
    }
    case_lines = "\n".join(f"- `{case_ref}`" for case_ref in candidate["case_refs"][:10]) or "- 待补充"
    metric_line = "、".join(candidate["observable_metrics"]) if candidate["observable_metrics"] else "待补充"
    body = f"""# 【专家模型训练场：{training_page_title}】

---

## 第一步：靶子定义

- **精准问题：** {candidate['symptom']}
- **这一步不解决：**
  - 怎么赚钱
  - 怎么引流
  - 怎么做增长
- **出现频次：** {candidate['frequency']}
- **可观察指标：** {metric_line}
- **适用平台 / 场景 / 环节：** {" / ".join(candidate["platforms"]) if candidate["platforms"] else "待补充"} / 待补充 / 待补充

## 高频证据

{case_lines}

## 会诊记录区

- 待补充。

## 诊断手册草稿区

- 待补充。

## 问诊表单草稿区

- 待补充。

## 治疗包草稿区

- 待补充。

## 临床实习反馈区

- **临床实习记录：** `expert_models/practicums/{slug}.md`
- **目标测试数：** 3
- **当前已完成：** 0
- **固定三问：**
  1. 表单问题看得懂吗？
  2. 诊断结论你觉得说到点上了吗？
  3. 行动建议你觉得能直接操作吗？
- **迭代结论：**
  - 待补充。
"""
    write_markdown(output_path, meta, body)
    return output_path.relative_to(root).as_posix()


def build_scaffold(root: Path, kind: str, candidate: dict, training_ref: str) -> str:
    out_dir = root / "expert_models" / kind
    slug = slugify(candidate["normalized_symptom"])
    output_path = out_dir / f"{slug}.md"
    if kind == "manuals":
        meta = {
            "manual_id": f"stage2_manual_{slug}",
            "title": f"【诊断手册：{candidate['training_title']}】",
            "training_ground_ref": training_ref,
            "consultation_ref": f"expert_models/consultations/{slug}.md",
            "status": "draft",
            "evidence_status": candidate["evidence_status"],
            "date": today_iso(),
        }
        body = f"""# 【诊断手册：{candidate['training_title']}】

## 资源编号规则

- `R-01`：当前手册第一条资源
- `R-02`：当前手册第二条资源
- `R-03`：当前手册第三条资源
- 每个检查站点至少绑定 `1` 个资源编号，没有编号就不能进入正式手册

## 第一站：待补充

- **检查项：**
- **判断方法：**
- **✅ 行动指令：**
  1. **动作：**
  2. **参数：**
  3. **资源编号：** `R-01`
  4. **资源内容：**
  5. **来源病例：**
- **病例引用：**
  - `cases/...`

## 第二站：待补充

- **检查项：**
- **判断方法：**
- **✅ 行动指令：**
  1. **动作：**
  2. **参数：**
  3. **资源编号：** `R-02`
  4. **资源内容：**
  5. **来源病例：**
- **病例引用：**
  - `cases/...`
"""
    elif kind == "forms":
        meta = {
            "form_id": f"stage2_form_{slug}",
            "title": f"【问诊表单：{candidate['training_title']}】",
            "training_ground_ref": training_ref,
            "manual_ref": f"expert_models/manuals/{slug}.md",
            "status": "draft",
            "evidence_status": candidate["evidence_status"],
            "date": today_iso(),
        }
        body = f"""# 【问诊表单：{candidate['training_title']}】

## 症状采集

1. 【平台】是哪里？
2. 【卡住的环节】是什么？
3. 【可观察现象】是什么？
4. 【目标结果】是什么？

## 诊断报告输出格式

## 您的专属优化方案

**诊断结论**：待补充

**✅ 请按顺序执行以下动作（预计总耗时：待补充）：**

### 任务一：待补充
- **动作：**
- **参数：**
- **参考案例：** `cases/...`
- **SOP / 资源：**
- **预计耗时：**

### 任务二：待补充
- **动作：**
- **参数：**
- **参考案例：** `cases/...`
- **SOP / 资源：**
- **预计耗时：**

### 任务三：待补充
- **动作：**
- **参数：**
- **参考案例：** `cases/...`
- **SOP / 资源：**
- **预计耗时：**
"""
    elif kind == "practicums":
        meta = {
            "practicum_id": f"stage2_practicum_{slug}",
            "title": f"【临床实习：{candidate['training_title']}】",
            "training_ground_ref": training_ref,
            "form_ref": f"expert_models/forms/{slug}.md",
            "manual_ref": f"expert_models/manuals/{slug}.md",
            "status": "draft",
            "required_test_count": 3,
            "completed_test_count": 0,
            "date": today_iso(),
        }
        body = f"""# 【临床实习：{candidate['training_title']}】

## 测试计划

- **目标测试数：** 3
- **当前已完成：** 0
- **固定三问：**
  1. 表单问题看得懂吗？
  2. 诊断结论你觉得说到点上了吗？
  3. 行动建议你觉得能直接操作吗？

## 测试对象 1

- **对象标签：**
- **测试前原始内容：**
- **测试前原始数据：**
- **执行任务：**
- **三问反馈：**
  - **表单问题看得懂吗：**
  - **诊断结论你觉得说到点上了吗：**
  - **行动建议你觉得能直接操作吗：**
- **1~2 天后结果变化：**
- **是否改善：** 是 / 否 / 部分
- **有效动作：**
- **无效动作：**
- **新暴露卡点：**

## 测试对象 2

- **对象标签：**
- **测试前原始内容：**
- **测试前原始数据：**
- **执行任务：**
- **三问反馈：**
  - **表单问题看得懂吗：**
  - **诊断结论你觉得说到点上了吗：**
  - **行动建议你觉得能直接操作吗：**
- **1~2 天后结果变化：**
- **是否改善：** 是 / 否 / 部分
- **有效动作：**
- **无效动作：**
- **新暴露卡点：**

## 测试对象 3

- **对象标签：**
- **测试前原始内容：**
- **测试前原始数据：**
- **执行任务：**
- **三问反馈：**
  - **表单问题看得懂吗：**
  - **诊断结论你觉得说到点上了吗：**
  - **行动建议你觉得能直接操作吗：**
- **1~2 天后结果变化：**
- **是否改善：** 是 / 否 / 部分
- **有效动作：**
- **无效动作：**
- **新暴露卡点：**

## 迭代决策

- **如果反馈看不懂：**
- **如果反馈不准：**
- **如果行动有效：**
- **如果行动无效：**
- **下一轮唯一变量：**

## 阶段一回写候选

- **是否生成：** 是 / 否
- **候选对象：**
- **候选原因：**
- **是否已经赚到钱：** 是 / 否
- **金额 / 结果：**
- **下一步：** 如果已赚到钱，按阶段一入口注册为新案例
"""
    else:
        meta = {
            "consultation_id": f"stage2_consultation_{slug}",
            "title": f"【专家会诊记录：{candidate['training_title']}】",
            "training_ground_ref": training_ref,
            "status": "draft",
            "evidence_status": candidate["evidence_status"],
            "date": today_iso(),
        }
        body = f"""# 【专家会诊记录：{candidate['training_title']}】

## 会诊目标

- **训练靶子：** {candidate['symptom']}
- **代表问题：** {candidate['symptom']}

## 病例清单

""" + "\n".join(
            f"### 病例号 {index:02d}\n- **案例：** `{case_ref}`\n- **症状描述：** 待补充\n- **最终结果：** 待补充\n- **关键决策 / 动作：** 待补充\n- **医生诊断结论：** 待补充\n"
            for index, case_ref in enumerate(candidate["case_refs"][:5], start=1)
        )
    write_markdown(output_path, meta, body)
    return output_path.relative_to(root).as_posix()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    index_path = root / "index" / "cases" / "cases_meta.jsonl"
    if not index_path.exists():
        raise SystemExit(f"Missing case index: {index_path}")

    buckets: dict[str, dict] = {}
    with index_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            case = json.loads(line)
            status = str(case.get("status", "")).strip()
            case_ref = str(case.get("path", "")).strip()
            case_platform = normalize_whitespace(case.get("platform", ""))
            for symptom in ensure_list(case.get("symptoms")):
                normalized = normalize_whitespace(symptom)
                if not normalized:
                    continue
                bucket = buckets.setdefault(
                    normalized,
                    {
                        "symptom": normalized,
                        "normalized_symptom": normalized,
                        "frequency": 0,
                        "formal_case_count": 0,
                        "draft_case_count": 0,
                        "case_refs": [],
                        "platforms": [],
                        "observable_metrics": [],
                    },
                )
                bucket["frequency"] += 1
                if case_ref and case_ref not in bucket["case_refs"]:
                    bucket["case_refs"].append(case_ref)
                if status in {"approved", "reviewed"}:
                    bucket["formal_case_count"] += 1
                elif status == "draft":
                    bucket["draft_case_count"] += 1
                for platform in detect_platforms(normalized, case_platform):
                    if platform not in bucket["platforms"]:
                        bucket["platforms"].append(platform)
                for metric in detect_metrics(normalized):
                    if metric not in bucket["observable_metrics"]:
                        bucket["observable_metrics"].append(metric)

    candidates = []
    for symptom, payload in buckets.items():
        excluded = is_broad(symptom)
        candidate = {
            **payload,
            "concreteness_score": concreteness_score(symptom),
            "excluded_as_broad": excluded,
        }
        candidate["evidence_status"] = evidence_status(candidate["formal_case_count"], candidate["frequency"])
        candidate["training_title"] = re.sub(r"^.*?([A-Za-z0-9\u4e00-\u9fff].*)$", r"\1", symptom)
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            item["excluded_as_broad"],
            -item["frequency"],
            -item["concreteness_score"],
            -item["formal_case_count"],
            item["symptom"],
        )
    )

    stage2_index_dir = root / "index" / "stage2"
    stage2_index_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = stage2_index_dir / "symptom_candidates.jsonl"
    with candidates_path.open("w", encoding="utf-8") as handle:
        for rank, candidate in enumerate(candidates, start=1):
            output = dict(candidate)
            output["rank"] = rank
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")

    selected = next((candidate for candidate in candidates if not candidate["excluded_as_broad"]), None)
    training_ref = "未生成"
    consultation_ref = "未生成"
    manual_ref = "未生成"
    form_ref = "未生成"
    practicum_ref = "未生成"
    if selected:
        training_ref = build_training_ground(root, selected)
        consultation_ref = build_scaffold(root, "consultations", selected, training_ref)
        manual_ref = build_scaffold(root, "manuals", selected, training_ref)
        form_ref = build_scaffold(root, "forms", selected, training_ref)
        practicum_ref = build_scaffold(root, "practicums", selected, training_ref)

    report_lines = [
        "# 【阶段二靶子选择报告】",
        "",
        "## 输入",
        "- **案例基因库：** `index/cases/cases_meta.jsonl`",
        "- **统计口径：** `approved / reviewed` 优先，`draft` 作为候选提示",
        "",
        "## 高频症状候选表",
        "",
        "| 排名 | 候选症状 | 出现频次 | 具体度 | 可观察指标 | 正式病例数 | 代表案例 | 是否入选 |",
        "|---|---|---:|---:|---|---:|---|---|",
    ]
    for rank, candidate in enumerate(candidates[: args.top], start=1):
        metrics = " / ".join(candidate["observable_metrics"]) if candidate["observable_metrics"] else "待补充"
        cases = "<br>".join(f"`{case_ref}`" for case_ref in candidate["case_refs"][:2]) or "待补充"
        selected_mark = "是" if selected and candidate["symptom"] == selected["symptom"] else "否"
        report_lines.append(
            f"| {rank} | {candidate['symptom']} | {candidate['frequency']} | {candidate['concreteness_score']} | {metrics} | {candidate['formal_case_count']} | {cases} | {selected_mark} |"
        )

    report_lines.extend(
        [
            "",
            "## 排除的大问题",
            "- 怎么赚钱",
            "- 怎么引流",
            "- 怎么做增长",
            "- 怎么做内容",
            "",
            "## 第一靶子定义卡",
        ]
    )

    if selected:
        metric_line = "、".join(selected["observable_metrics"]) if selected["observable_metrics"] else "待补充"
        platform_line = " / ".join(selected["platforms"]) if selected["platforms"] else "待补充"
        report_lines.extend(
            [
                f"- **靶子名称：** {selected['training_title']}",
                f"- **精准问题：** {selected['symptom']}",
                f"- **入选理由：** 当前基因库中它同时满足高频、具体、可观察、可回链病例四个条件。",
                f"- **出现频次：** {selected['frequency']}",
                f"- **可观察指标：** {metric_line}",
                f"- **适用平台：** {platform_line}",
                f"- **证据状态：** `{selected['evidence_status']}`",
                f"- **训练场路径：** `{training_ref}`",
                f"- **会诊记录路径：** `{consultation_ref}`",
                f"- **诊断手册路径：** `{manual_ref}`",
                f"- **问诊表单路径：** `{form_ref}`",
                f"- **临床实习路径：** `{practicum_ref}`",
            ]
        )
    else:
        report_lines.extend(
            [
                "- **结论：** 当前基因库里没有合格的具体症状。",
                "- **下一动作：** 进入阶段一补库模式，由系统自动补齐高频具体症状案例。",
            ]
        )

    report_path = stage2_index_dir / "target_selection_report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"Wrote {candidates_path.relative_to(root)}")
    print(f"Wrote {report_path.relative_to(root)}")
    if selected:
        print(f"Selected target: {selected['symptom']}")
        print(f"Wrote {training_ref}")
        print(f"Wrote {consultation_ref}")
        print(f"Wrote {manual_ref}")
        print(f"Wrote {form_ref}")
        print(f"Wrote {practicum_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
