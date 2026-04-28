#!/usr/bin/env python3

from __future__ import annotations

import argparse
import socket
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from _buildmate_lib import (
    classify_link_target,
    ensure_list,
    extract_markdown_links,
    list_markdown_files,
    read_markdown,
    write_jsonl,
)

SKIP_DIR_NAMES = {"imported", "case_drafts", "drafts"}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def collect_case_links(meta: dict, body: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in ensure_list(meta.get("resource_links")) + ensure_list(meta.get("proof_refs")) + extract_markdown_links(body):
        target = str(value).strip()
        if not target or target in seen:
            continue
        seen.add(target)
        ordered.append(target)
    return ordered


def check_remote_url(target: str, timeout: float) -> tuple[str, int | None, str]:
    try:
        request = urllib.request.Request(target, method="HEAD")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return "healthy", response.status, ""
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 405}:
            try:
                request = urllib.request.Request(target, method="GET")
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return "healthy", response.status, ""
            except Exception as inner_exc:  # noqa: BLE001
                return "network_error", getattr(inner_exc, "code", None), str(inner_exc)
        return "broken", exc.code, str(exc)
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        return "network_error", None, str(exc)


def check_local_ref(root: Path, target: str) -> tuple[str, str]:
    candidate = Path(target).expanduser()
    if not candidate.is_absolute():
        candidate = (root / target).resolve()
    return ("healthy", str(candidate)) if candidate.exists() else ("missing", str(candidate))


def summarize_case_status(link_rows: list[dict]) -> str:
    statuses = {str(row.get("status", "")).strip() for row in link_rows}
    if not link_rows:
        return "no_resources"
    if statuses <= {"healthy"}:
        return "healthy"
    if "missing" in statuses or "broken" in statuses:
        return "degraded"
    if statuses <= {"pending_remote_check"}:
        return "unchecked"
    return "mixed"


def build_summary_markdown(case_rows: list[dict]) -> str:
    lines = [
        "# 阶段一资源巡检报告",
        "",
        f"- **巡检时间：** {now_text()}",
        f"- **案例数：** {len(case_rows)}",
        "",
        "## 汇总",
        "",
    ]
    for row in case_rows:
        lines.append(
            f"- `{row['case_ref']}` -> 状态=`{row['resource_health_status']}`；资源数={row['resource_count']}；健康={row['healthy_count']}；缺失={row['missing_count']}；待远程检查={row['pending_remote_count']}"
        )
    return "\n".join(lines).strip() + "\n"


def audit_case_resources(
    root: Path,
    cases_dir_name: str = "assets/cases",
    output_dir_name: str = "index/cases",
    check_http: bool = False,
    timeout: float = 5.0,
) -> tuple[int, int]:
    cases_dir = root / cases_dir_name
    output_dir = root / output_dir_name
    case_rows: list[dict] = []
    link_rows: list[dict] = []

    for path in list_markdown_files(cases_dir):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        meta, body = read_markdown(path)
        case_ref = str(path.relative_to(root))
        links = collect_case_links(meta, body)
        current_rows: list[dict] = []

        for target in links:
            link_type = classify_link_target(target)
            status = "unknown"
            resolved_ref = ""
            response_code = None
            error_text = ""
            if link_type == "remote":
                if check_http:
                    status, response_code, error_text = check_remote_url(target, timeout)
                else:
                    status = "pending_remote_check"
            elif link_type == "local":
                status, resolved_ref = check_local_ref(root, target)
            elif link_type == "ignored":
                status = "ignored"
            else:
                status = "unknown"

            row = {
                "case_id": str(meta.get("case_id", "")).strip(),
                "case_ref": case_ref,
                "target": target,
                "link_type": link_type,
                "status": status,
                "resolved_ref": resolved_ref,
                "response_code": response_code,
                "error": error_text,
                "checked_at": now_text(),
            }
            link_rows.append(row)
            current_rows.append(row)

        case_rows.append(
            {
                "case_id": str(meta.get("case_id", "")).strip(),
                "case_ref": case_ref,
                "resource_count": len(current_rows),
                "healthy_count": sum(1 for item in current_rows if item["status"] == "healthy"),
                "missing_count": sum(1 for item in current_rows if item["status"] in {"missing", "broken"}),
                "pending_remote_count": sum(1 for item in current_rows if item["status"] == "pending_remote_check"),
                "resource_health_status": summarize_case_status(current_rows),
                "checked_at": now_text(),
            }
        )

    write_jsonl(output_dir / "resource_health.jsonl", link_rows)
    write_jsonl(output_dir / "resource_health_summary.jsonl", case_rows)
    (output_dir / "resource_health_report.md").write_text(build_summary_markdown(case_rows), encoding="utf-8")
    return len(case_rows), len(link_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Buildmate case resource links and generate a heartbeat report.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--cases-dir", default="assets/cases")
    parser.add_argument("--output-dir", default="index/cases")
    parser.add_argument("--check-http", action="store_true")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    case_count, link_count = audit_case_resources(
        root=root,
        cases_dir_name=args.cases_dir,
        output_dir_name=args.output_dir,
        check_http=args.check_http,
        timeout=args.timeout,
    )
    print(f"Audited {link_count} resource links across {case_count} cases into {root / args.output_dir}")


if __name__ == "__main__":
    main()
