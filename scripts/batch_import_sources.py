#!/opt/miniconda3/bin/python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from _buildmate_lib import assert_project_root
from _io_safety import atomic_write_text


def run_command(cmd: list[str], *, env: dict[str, str] | None = None, timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def print_process_output(result: subprocess.CompletedProcess) -> None:
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def parse_imported_source(stdout: str) -> Path | None:
    for line in stdout.splitlines():
        if line.startswith("Imported source:"):
            return Path(line.split(":", 1)[1].strip())
    return None


def parse_existing_source(stdout: str) -> Path | None:
    for prefix in ("Existing source:", "Duplicate candidate:", "Candidate:"):
        for line in stdout.splitlines():
            if line.startswith(prefix):
                return Path(line.split(":", 1)[1].strip())
    return None


def parse_created_case_draft(stdout: str) -> Path | None:
    for line in stdout.splitlines():
        if line.startswith("Created case draft:"):
            return Path(line.split(":", 1)[1].strip())
    return None


def parse_registered_case(stdout: str) -> Path | None:
    for line in stdout.splitlines():
        if line.startswith("Registered approved case:"):
            return Path(line.split(":", 1)[1].strip())
    return None


def parse_source_material_result(stdout: str, plan_path: Path | None) -> dict:
    payload: dict = {}
    if plan_path and plan_path.exists():
        try:
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    if not payload and stdout.strip().startswith("{"):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {}

    draft_write = payload.get("draft_write") if isinstance(payload, dict) else {}
    if not isinstance(draft_write, dict):
        draft_write = {}
    return {
        "material_count": as_int(payload.get("material_count") if isinstance(payload, dict) else 0),
        "draft_write": draft_write,
    }


def as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def relative_to_root(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def append_common_import_args(cmd: list[str], args: argparse.Namespace) -> None:
    cmd.extend(["--bucket", args.bucket])
    cmd.extend(["--source-type", args.source_type])
    cmd.extend(["--dedupe-mode", args.dedupe_mode])
    if args.force_import:
        cmd.append("--force-import")
    if args.update_existing:
        cmd.append("--update-existing")
    if args.author:
        cmd.extend(["--author", args.author])
    if args.origin:
        cmd.extend(["--origin", args.origin])
    if args.date:
        cmd.extend(["--date", args.date])
    if args.tags:
        cmd.extend(["--tags", args.tags])


def build_stable_env() -> dict[str, str]:
    stable_env = os.environ.copy()
    stable_env.setdefault("OMP_NUM_THREADS", "1")
    stable_env.setdefault("MKL_NUM_THREADS", "1")
    stable_env.setdefault("OPENBLAS_NUM_THREADS", "1")
    stable_env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    stable_env.setdefault("HF_HUB_OFFLINE", "1")
    stable_env.setdefault("TRANSFORMERS_OFFLINE", "1")
    return stable_env


def process_one_source(
    *,
    input_path: Path,
    root: Path,
    scripts_dir: Path,
    args: argparse.Namespace,
    env: dict[str, str],
) -> dict:
    record: dict = {
        "input_path": str(input_path),
        "status": "pending",
        "source_path": "",
        "source_material_status": "",
        "source_material_plan_path": "",
        "source_material_plan_count": 0,
        "source_material_draft_count": 0,
        "source_material_skipped_count": 0,
        "source_material_failed_count": 0,
        "case_draft_path": "",
        "case_path": "",
        "derived_material_count": 0,
        "errors": [],
    }

    import_cmd = [
        sys.executable,
        str(scripts_dir / "import_source_and_route.py"),
        str(input_path),
        "--root",
        str(root),
    ]
    append_common_import_args(import_cmd, args)
    result = run_command(import_cmd, env=env)
    print_process_output(result)
    if result.returncode != 0:
        record["status"] = "failed_import"
        record["errors"].append(result.stderr.strip() or result.stdout.strip())
        return record

    imported_source = parse_imported_source(result.stdout)
    if imported_source is None:
        existing_source = parse_existing_source(result.stdout)
        if existing_source is not None and args.use_existing_source:
            imported_source = existing_source
            record["status"] = "using_existing_source"
        else:
            record["status"] = "skipped_or_duplicate"
            if existing_source is not None:
                record["source_path"] = str(existing_source)
            return record
    else:
        record["status"] = "imported_source"

    if not imported_source.is_absolute():
        imported_source = root / imported_source
    imported_source = imported_source.resolve()
    if not imported_source.exists() or not imported_source.is_file():
        record["status"] = "failed_source_resolution"
        record["errors"].append(f"Source file not found after import: {imported_source}")
        return record
    record["source_path"] = relative_to_root(imported_source, root)

    if args.plan_source_materials:
        material_result = plan_source_materials(
            root=root,
            scripts_dir=scripts_dir,
            source_path=imported_source,
            record=record,
            args=args,
            env=env,
        )
        if material_result.returncode != 0:
            record["status"] = "failed_plan_source_materials"
            record["errors"].append(material_result.stderr.strip() or material_result.stdout.strip())
            return record

    if not args.extract_case:
        if args.plan_source_materials:
            record["status"] = "completed"
        elif record["status"] == "using_existing_source":
            record["status"] = "using_existing_source"
        else:
            record["status"] = "imported_source"
        return record

    case_draft_output = root / "assets/case_drafts" / f"{imported_source.stem}.md"
    extract_cmd = [
        sys.executable,
        str(scripts_dir / "extract_case.py"),
        str(imported_source),
        "--root",
        str(root),
        "--output",
        str(case_draft_output),
    ]
    if args.overwrite_case_draft:
        extract_cmd.append("--overwrite")
    if args.llm:
        extract_cmd.append("--llm")
        if args.llm_backend:
            extract_cmd.extend(["--llm-backend", args.llm_backend])
        if args.llm_model:
            extract_cmd.extend(["--llm-model", args.llm_model])
        if args.llm_timeout:
            extract_cmd.extend(["--llm-timeout", str(args.llm_timeout)])
    result = run_command(extract_cmd, env=env, timeout=args.extract_timeout)
    print_process_output(result)
    if result.returncode != 0:
        record["status"] = "failed_extract_case"
        record["errors"].append(result.stderr.strip() or result.stdout.strip())
        return record
    case_draft = parse_created_case_draft(result.stdout) or case_draft_output
    record["case_draft_path"] = relative_to_root(case_draft, root)

    if not args.register_case:
        record["status"] = "created_case_draft"
        return record

    register_cmd = [
        sys.executable,
        str(scripts_dir / "register_case.py"),
        str(case_draft),
        "--root",
        str(root),
        "--source-path",
        record["source_path"],
    ]
    if args.skip_case_preflight:
        register_cmd.append("--skip-preflight")
    if args.overwrite_case:
        register_cmd.append("--overwrite")
    if args.force_register_duplicate:
        register_cmd.append("--force-register-duplicate")
    result = run_command(register_cmd, env=env)
    print_process_output(result)
    if result.returncode != 0:
        record["status"] = "failed_register_case"
        record["errors"].append(result.stderr.strip() or result.stdout.strip())
        return record
    case_path = parse_registered_case(result.stdout)
    if case_path is None:
        record["status"] = "failed_register_case"
        record["errors"].append("register_case.py did not report a registered path")
        return record
    record["case_path"] = relative_to_root(case_path, root)

    if not args.derive_materials:
        record["status"] = "registered_case"
        return record

    derive_cmd = [
        sys.executable,
        str(scripts_dir / "derive_materials_from_case.py"),
        str(case_path),
        "--root",
        str(root),
    ]
    if args.overwrite_materials:
        derive_cmd.append("--overwrite")
    result = run_command(derive_cmd, env=env)
    print_process_output(result)
    if result.returncode != 0:
        record["status"] = "failed_derive_materials"
        record["errors"].append(result.stderr.strip() or result.stdout.strip())
        return record
    record["derived_material_count"] = sum(1 for line in result.stdout.splitlines() if line.startswith("Created material:"))
    record["status"] = "completed"
    return record


def plan_source_materials(
    *,
    root: Path,
    scripts_dir: Path,
    source_path: Path,
    record: dict,
    args: argparse.Namespace,
    env: dict[str, str],
) -> subprocess.CompletedProcess:
    plan_path: Path | None = None
    if args.write_source_material_plan:
        plan_path = Path(args.write_source_material_plan)
        if len(args.input_paths) > 1:
            plan_path = plan_path / f"{source_path.stem}.material-plan.{args.source_material_format}"
        if not plan_path.is_absolute():
            plan_path = root / plan_path

    cmd = [
        sys.executable,
        str(scripts_dir / "plan_source_materials.py"),
        str(source_path),
        "--root",
        str(root),
        "--format",
        args.source_material_format,
    ]
    if plan_path is not None:
        cmd.extend(["--write-plan", str(plan_path)])
    if args.create_source_material_drafts:
        cmd.append("--create-drafts")
        cmd.append("--progress")
    if args.dry_run_source_material_drafts:
        cmd.append("--dry-run-drafts")
        cmd.append("--progress")
    if args.overwrite_source_material_drafts:
        cmd.append("--overwrite")
    if args.plan_source_materials_llm:
        cmd.append("--llm")
    if args.source_material_llm_model:
        cmd.extend(["--llm-model", args.source_material_llm_model])
    if args.source_material_llm_timeout:
        cmd.extend(["--llm-timeout", str(args.source_material_llm_timeout)])
    if args.source_material_llm_max_materials:
        cmd.extend(["--llm-max-materials", str(args.source_material_llm_max_materials)])

    result = run_command(cmd, env=env)
    print_process_output(result)

    if plan_path is not None:
        record["source_material_plan_path"] = relative_to_root(plan_path, root)
    parsed = parse_source_material_result(result.stdout, plan_path)
    draft_write = parsed.get("draft_write", {})
    record["source_material_status"] = "planned"
    if args.create_source_material_drafts or args.dry_run_source_material_drafts:
        record["source_material_status"] = "drafted" if result.returncode == 0 else "failed"
    record["source_material_plan_count"] = parsed.get("material_count", 0)
    record["source_material_draft_count"] = as_int(draft_write.get("created")) + as_int(draft_write.get("overwritten"))
    record["source_material_skipped_count"] = as_int(draft_write.get("skipped_existing"))
    record["source_material_failed_count"] = as_int(draft_write.get("failed"))
    if args.dry_run_source_material_drafts:
        record["source_material_status"] = "dry_run"
        record["source_material_draft_count"] = as_int(draft_write.get("would_create")) + as_int(draft_write.get("would_overwrite"))
    return result


def flush_dirty_indexes(root: Path, scripts_dir: Path, args: argparse.Namespace, env: dict[str, str]) -> None:
    cmd = [
        sys.executable,
        str(scripts_dir / "flush_indexes.py"),
        "--root",
        str(root),
        "--device",
        args.device,
        "--batch-size",
        str(args.batch_size),
    ]
    result = run_command(cmd, env=env, timeout=args.flush_timeout)
    print_process_output(result)
    if result.returncode != 0:
        raise SystemExit(f"Batch import finished, but index flush failed: {result.stderr.strip() or result.stdout.strip()}")


def write_report(root: Path, records: list[dict]) -> Path:
    report_dir = root / ".runtime" / "batch_import"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "latest_report.json"
    atomic_write_text(report_path, json.dumps({"records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch import source files, then optionally build cases/materials and flush indexes once.")
    parser.add_argument("input_paths", nargs="+")
    parser.add_argument("--root", default=".")
    parser.add_argument("--bucket", default="auto", choices=["auto", "buildmate", "materials"])
    parser.add_argument("--source-type", default="article")
    parser.add_argument("--author", default="", help="Override author for every input.")
    parser.add_argument("--origin", default="", help="Override origin for every input.")
    parser.add_argument("--date", default="", help="Override date for every input.")
    parser.add_argument("--tags", default="", help="Comma-separated tags applied to every input.")
    parser.add_argument("--dedupe-mode", default="strict", choices=["strict", "review", "off"])
    parser.add_argument("--force-import", action="store_true")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument(
        "--use-existing-source",
        action="store_true",
        help="When import finds an existing duplicate source, continue downstream steps from that source.",
    )
    parser.add_argument(
        "--plan-source-materials",
        action="store_true",
        help="Run plan_source_materials.py for each imported or reused source.",
    )
    parser.add_argument(
        "--create-source-material-drafts",
        action="store_true",
        help="Create atomic material draft files from the source material plan.",
    )
    parser.add_argument(
        "--dry-run-source-material-drafts",
        action="store_true",
        help="Preview source material draft writes without creating files.",
    )
    parser.add_argument(
        "--overwrite-source-material-drafts",
        action="store_true",
        help="Overwrite existing source material draft files when creating drafts.",
    )
    parser.add_argument(
        "--source-material-format",
        choices=["markdown", "json"],
        default="json",
        help="Output format for source material planning.",
    )
    parser.add_argument(
        "--write-source-material-plan",
        default="",
        help="Optional file path for one input, or directory for multiple inputs, to save source material plans.",
    )
    parser.add_argument(
        "--plan-source-materials-llm",
        action="store_true",
        help="Use DeepSeek when planning source material splits.",
    )
    parser.add_argument("--source-material-llm-model", default="")
    parser.add_argument("--source-material-llm-timeout", type=float, default=180.0)
    parser.add_argument("--source-material-llm-max-materials", type=int, default=20)
    parser.add_argument("--extract-case", action="store_true", help="Create a case draft from each newly imported source.")
    parser.add_argument("--register-case", action="store_true", help="Register each created case draft as an approved case.")
    parser.add_argument("--derive-materials", action="store_true", help="Derive template materials from each registered case.")
    parser.add_argument("--llm", action="store_true", help="Use DeepSeek for case extraction.")
    parser.add_argument("--llm-backend", default="auto", choices=["auto", "deepseek"])
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--extract-timeout", type=float, default=180.0)
    parser.add_argument("--skip-case-preflight", action="store_true")
    parser.add_argument("--overwrite-case-draft", action="store_true")
    parser.add_argument("--overwrite-case", action="store_true")
    parser.add_argument("--overwrite-materials", action="store_true")
    parser.add_argument("--force-register-duplicate", action="store_true")
    parser.add_argument("--flush", action="store_true", help="Flush dirty indexes once after the whole batch.")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--flush-timeout", type=float, default=600.0)
    args = parser.parse_args()

    if args.derive_materials and not args.register_case:
        raise SystemExit("--derive-materials requires --register-case")
    if args.register_case and not args.extract_case:
        raise SystemExit("--register-case requires --extract-case")
    if (args.create_source_material_drafts or args.dry_run_source_material_drafts) and not args.plan_source_materials:
        raise SystemExit("--create-source-material-drafts/--dry-run-source-material-drafts require --plan-source-materials")
    if args.plan_source_materials_llm and not args.plan_source_materials:
        raise SystemExit("--plan-source-materials-llm requires --plan-source-materials")
    if args.create_source_material_drafts and args.dry_run_source_material_drafts:
        raise SystemExit("--create-source-material-drafts and --dry-run-source-material-drafts are mutually exclusive")

    root = assert_project_root(Path(args.root))
    scripts_dir = Path(__file__).resolve().parent
    env = build_stable_env()

    records: list[dict] = []
    for raw_path in args.input_paths:
        input_path = Path(raw_path).expanduser().resolve()
        if not input_path.exists() or not input_path.is_file():
            records.append(
                {
                    "input_path": str(input_path),
                    "status": "missing_input",
                    "source_path": "",
                    "source_material_status": "",
                    "source_material_plan_path": "",
                    "source_material_plan_count": 0,
                    "source_material_draft_count": 0,
                    "source_material_skipped_count": 0,
                    "source_material_failed_count": 0,
                    "case_draft_path": "",
                    "case_path": "",
                    "derived_material_count": 0,
                    "errors": [f"Input file not found: {input_path}"],
                }
            )
            continue
        print(f"Batch item: {input_path}")
        records.append(
            process_one_source(
                input_path=input_path,
                root=root,
                scripts_dir=scripts_dir,
                args=args,
                env=env,
            )
        )

    if args.flush:
        flush_dirty_indexes(root, scripts_dir, args, env)

    report_path = write_report(root, records)
    status_counts: dict[str, int] = {}
    for record in records:
        status = str(record.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    print(json.dumps({"status_counts": status_counts, "report_path": str(report_path)}, ensure_ascii=False))

    failed = [record for record in records if str(record.get("status", "")).startswith("failed_") or record.get("status") == "missing_input"]
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
