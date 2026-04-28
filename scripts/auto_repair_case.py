#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _buildmate_lib import normalize_inferred_marker, read_markdown, write_markdown


def repair_inferred_markers(body: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    pattern = re.compile(
        r"^(?P<prefix>\s*-\s*(?:\*\*是否推测：\*\*|是否推测：)\s*)(?P<value>.+?)\s*$",
        flags=re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        original = match.group("value").strip()
        normalized = normalize_inferred_marker(original, fallback_text=original)
        if not normalized or normalized == original:
            return match.group(0)
        changes.append(f"将“是否推测”从“{original}”归一化为“{normalized}”")
        return f"{match.group('prefix')}{normalized}"

    updated = pattern.sub(replace, body)
    return updated, changes


def auto_repair_case(path: Path, write: bool = True) -> tuple[list[str], bool]:
    meta, body = read_markdown(path)
    updated_body = body
    changes: list[str] = []

    updated_body, inferred_changes = repair_inferred_markers(updated_body)
    changes.extend(inferred_changes)

    if write and changes:
        write_markdown(path, meta, updated_body)
    return changes, bool(changes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-repair low-risk Buildmate stage-1 case formatting errors.")
    parser.add_argument("case_file")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    case_path = Path(args.case_file).resolve()
    changes, changed = auto_repair_case(case_path, write=not args.check_only)

    if not changed:
        print("OK: no auto-repair changes needed.")
        return

    for change in changes:
        print(f"AUTO-REPAIR-APPLIED: {change}")
    if args.check_only:
        print("INFO: check-only mode, no file written.")
    else:
        print("OK: auto-repair completed.")


if __name__ == "__main__":
    main()
