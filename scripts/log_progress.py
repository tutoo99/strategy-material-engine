#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from _buildmate_lib import read_markdown, write_markdown


PROGRESS_HEADING = "进度播报记录"


def count_progress_entries(section: str) -> int:
    return len(re.findall(r"^###\s+进度播报\s+\d+\s*$", section, flags=re.MULTILINE))


def extract_progress_section(body: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(PROGRESS_HEADING)}\s*(.*?)(?=^##\s+.+$|\Z)",
        body,
        flags=re.DOTALL | re.MULTILINE,
    )
    return match.group(1).strip() if match else ""


def upsert_progress_section(body: str, section_content: str) -> str:
    replacement = f"## {PROGRESS_HEADING}\n\n{section_content.strip()}\n\n"
    existing = re.search(
        rf"^##\s+{re.escape(PROGRESS_HEADING)}\s*.*?(?=^##\s+.+$|\Z)",
        body,
        flags=re.DOTALL | re.MULTILINE,
    )
    if existing:
        return body[: existing.start()] + replacement + body[existing.end() :]

    feedback_heading = re.search(r"^##\s+用户反馈\s*$", body, flags=re.MULTILINE)
    if feedback_heading:
        return body[: feedback_heading.start()] + replacement + body[feedback_heading.start() :]

    return body.rstrip() + "\n\n" + replacement


def build_entry(
    index: int,
    stage: str,
    step: str,
    action: str,
    next_required: str,
    eta: str,
    trigger_type: str,
    timestamp: str,
    completed: str,
    reason: str,
    gap: str,
) -> str:
    lines = [
        f"### 进度播报 {index}",
        f"- **时间：** {timestamp}",
        f"- **触发类型：** {trigger_type}",
        f"- **当前阶段：** {stage}",
        f"- **当前步骤：** {step}",
        f"- **当前动作：** {action}",
        f"- **下一步需要你提供：** {next_required}",
        f"- **预计剩余时间：** {eta}",
    ]
    if completed.strip():
        lines.append(f"- **当前已完成：** {completed.strip()}")
    if reason.strip():
        lines.append(f"- **仍在处理的原因：** {reason.strip()}")
    if gap.strip():
        lines.append(f"- **剩余缺口：** {gap.strip()}")
    return "\n".join(lines)


def append_progress(
    path: Path,
    stage: str,
    step: str,
    action: str,
    next_required: str,
    eta: str,
    trigger_type: str,
    timestamp: str,
    completed: str,
    reason: str,
    gap: str,
) -> int:
    meta, body = read_markdown(path)

    progress_section = extract_progress_section(body)
    next_index = count_progress_entries(progress_section) + 1
    entry = build_entry(
        index=next_index,
        stage=stage,
        step=step,
        action=action,
        next_required=next_required,
        eta=eta,
        trigger_type=trigger_type,
        timestamp=timestamp,
        completed=completed,
        reason=reason,
        gap=gap,
    )

    section_parts = [progress_section.strip(), entry.strip()] if progress_section.strip() else [entry.strip()]
    updated_section = "\n\n".join(section_parts)
    updated_body = upsert_progress_section(body, updated_section)

    meta["progress_protocol"] = "hybrid-3min"
    meta["progress_event_count"] = next_index
    meta["last_progress_at"] = timestamp

    write_markdown(path, meta, updated_body)
    return next_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a Buildmate progress update to a stage-2 session file.")
    parser.add_argument("session_file")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--next", dest="next_required", required=True)
    parser.add_argument("--eta", required=True)
    parser.add_argument(
        "--trigger-type",
        default="key_step_start",
        choices=["stage_start", "stage_switch", "key_step_start", "timeout", "manual"],
    )
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--completed", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--gap", default="")
    args = parser.parse_args()

    timestamp = args.timestamp.strip() or datetime.now().strftime("%Y-%m-%d %H:%M")
    count = append_progress(
        path=Path(args.session_file).resolve(),
        stage=args.stage.strip(),
        step=args.step.strip(),
        action=args.action.strip(),
        next_required=args.next_required.strip(),
        eta=args.eta.strip(),
        trigger_type=args.trigger_type.strip(),
        timestamp=timestamp,
        completed=args.completed.strip(),
        reason=args.reason.strip(),
        gap=args.gap.strip(),
    )
    print(f"OK: progress update appended. progress_event_count={count}")


if __name__ == "__main__":
    main()
