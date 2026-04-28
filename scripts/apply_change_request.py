#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from _buildmate_lib import read_markdown, write_markdown
from validate_change_request import validate_change_request


ALLOWED_COMMAND_PREFIXES = {
    ("python3", "scripts/validate_change_request.py"),
    ("python3", "scripts/validate_strategy_node_patch.py"),
    ("python3", "scripts/validate_case.py"),
    ("python3", "scripts/validate_session.py"),
    ("python3", "scripts/validate_stage3_session.py"),
    ("python3", "scripts/validate_stage3_audit.py"),
    ("python3", "scripts/validate_stage4_artifact.py"),
    ("python3", "scripts/build_case_index.py"),
    ("python3", "scripts/build_stage3_seed_map.py"),
}


def extract_payload(body: str) -> dict:
    import re

    match = re.search(
        r"##\s+Structured Change Request\s*```yaml\s*(.*?)\s*```",
        body,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1).strip()) or {}
    if not isinstance(payload, dict):
        return {}
    request = payload.get("change_request", {})
    return request if isinstance(request, dict) else {}


def resolve_target(root: Path, ref: str) -> Path:
    target = (root / ref).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise SystemExit(f"ERROR: 非法目标路径：{ref}")
    return target


def append_content(target: Path, content: str) -> None:
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    normalized_existing = existing.rstrip()
    normalized_content = content.rstrip()
    merged = normalized_content if not normalized_existing else f"{normalized_existing}\n\n{normalized_content}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{merged}\n", encoding="utf-8")


def append_section(target: Path, section_title: str, content: str) -> None:
    header = f"## {section_title.strip()}"
    block = f"{header}\n\n{content.rstrip()}"
    append_content(target, block)


def create_file(target: Path, content: str) -> None:
    if target.exists():
        raise SystemExit(f"ERROR: create_file 模式下目标已存在：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8")


def run_command(root: Path, command: str) -> None:
    parts = shlex.split(command)
    if len(parts) < 2:
        raise SystemExit(f"ERROR: 非法命令：{command}")
    if tuple(parts[:2]) not in ALLOWED_COMMAND_PREFIXES:
        raise SystemExit(f"ERROR: 不允许执行的命令前缀：{' '.join(parts[:2])}")
    completed = subprocess.run(parts, cwd=root, check=False, text=True)
    if completed.returncode != 0:
        raise SystemExit(f"ERROR: 命令执行失败：{command}")


def apply_changes(root: Path, payload: dict) -> None:
    for change in payload.get("changes", []):
        target = resolve_target(root, str(change.get("target_ref", "")).strip())
        mode = str(change.get("patch_mode", "")).strip()
        content = str(change.get("content", "")).rstrip()
        if mode == "append":
            append_content(target, content)
        elif mode == "append_section":
            append_section(target, str(change.get("section_title", "")).strip(), content)
        elif mode == "create_file":
            create_file(target, content)
        else:
            raise SystemExit(f"ERROR: 不支持的 patch_mode：{mode}")


def mark_applied(request_path: Path, meta: dict, body: str) -> None:
    meta["status"] = "applied"
    meta["applied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_markdown(request_path, meta, body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a Buildmate change-request artifact.")
    parser.add_argument("request_file")
    parser.add_argument("--skip-followups", action="store_true")
    args = parser.parse_args()

    request_path = Path(args.request_file).resolve()
    errors, warnings = validate_change_request(request_path)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    root = request_path.parent.parent.parent.resolve()
    meta, body = read_markdown(request_path)
    payload = extract_payload(body)
    if not payload:
        raise SystemExit("ERROR: 缺少有效的 Structured Change Request payload。")

    apply_changes(root, payload)
    if not args.skip_followups:
        for command in payload.get("validation_commands", []):
            run_command(root, str(command).strip())
        for command in payload.get("rebuild_actions", []):
            run_command(root, str(command).strip())
    mark_applied(request_path, meta, body)
    print(f"OK: applied change request {request_path.relative_to(root)}")


if __name__ == "__main__":
    main()
