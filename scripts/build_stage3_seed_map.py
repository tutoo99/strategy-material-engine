#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
from itertools import combinations
from pathlib import Path

import yaml

from _buildmate_lib import ensure_list, list_markdown_files, read_markdown, slugify, write_jsonl

SKIP_DIR_NAMES = {"imported", "case_drafts", "drafts"}
DEFAULT_VOCABULARY_PATH = "references/stage3-tag-vocabulary.md"
DEFAULT_STRATEGY_PROFILES_PATH = "strategy_models/routes/strategy_profiles.yaml"
DEFAULT_GOAL_PROFILES_PATH = "strategy_models/routes/goal_profiles.yaml"
DEFAULT_SITUATION_PROFILES_PATH = "strategy_models/routes/situation_profiles.yaml"


def parse_quality_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def parse_date_value(value: object) -> date | None:
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def infer_case_quality(meta: dict) -> dict:
    status = str(meta.get("status", "")).strip()
    explicit_trust_level = str(meta.get("trust_level", "")).strip()
    trust_level = explicit_trust_level or ("production" if status in {"approved", "reviewed"} else "observation")
    verification_status = str(meta.get("verification_status", "")).strip() or (
        "verified" if status == "approved" else "weakly_verified" if status == "reviewed" else "unverified"
    )
    proof_refs = ensure_list(meta.get("proof_refs"))
    try:
        reproducibility_score = int(meta.get("reproducibility_score", 0) or 0)
    except (TypeError, ValueError):
        reproducibility_score = 0
    eligible_for_stage2 = trust_level == "production" and verification_status != "unverified"
    eligible_for_stage3 = eligible_for_stage2
    return {
        "trust_level": trust_level,
        "verification_status": verification_status,
        "proof_refs": proof_refs,
        "proof_count": len(proof_refs),
        "reproducibility_score": reproducibility_score,
        "eligible_for_stage2": eligible_for_stage2,
        "eligible_for_stage3": eligible_for_stage3,
        "legacy_inferred": not explicit_trust_level,
    }


def compute_active_status(
    approved_case_count: int,
    evidence_case_count: int,
    last_evidence_date: date | None,
) -> tuple[str, int | None]:
    freshness_days: int | None = None
    if last_evidence_date is not None:
        freshness_days = max(0, (date.today() - last_evidence_date).days)
    if approved_case_count <= 0 and evidence_case_count <= 0:
        return "archived", freshness_days
    if freshness_days is not None and freshness_days > 730:
        return "archived", freshness_days
    if approved_case_count <= 0 or (freshness_days is not None and freshness_days > 365):
        return "cooling", freshness_days
    return "active", freshness_days


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def load_strategy_profiles(path: Path) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    if not path.exists():
        return profiles
    for item in load_yaml(path).get("strategies", []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if label:
            profiles[label] = item
    return profiles


def load_goal_profiles(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [item for item in load_yaml(path).get("goals", []) if isinstance(item, dict)]


def load_situation_profiles(path: Path) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    if not path.exists():
        return profiles
    for item in load_yaml(path).get("situations", []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if label:
            profiles[label] = item
    return profiles


def load_stage3_vocabulary(path: Path) -> dict[str, set[str]]:
    if not path.exists():
        return {"strategy_tags": set(), "resource_refs": set()}

    strategy_tags: set[str] = set()
    resource_refs: set[str] = set()
    current_section = ""

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "## strategy_tags 最小标准词":
            current_section = "strategy_tags"
            continue
        if line == "## resource_refs 最小标准词":
            current_section = "resource_refs"
            continue
        if line.startswith("## "):
            current_section = ""
            continue
        if not current_section or not line.startswith("- "):
            continue

        term = line[2:].strip()
        if term.startswith("`") and term.endswith("`"):
            term = term[1:-1]
        if not term:
            continue

        if current_section == "strategy_tags":
            strategy_tags.add(term)
        elif current_section == "resource_refs":
            resource_refs.add(term)

    return {
        "strategy_tags": strategy_tags,
        "resource_refs": resource_refs,
    }


def split_standardized_terms(values: list[str], allowed_terms: set[str]) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    skipped: list[str] = []
    for value in unique_preserve_order(values):
        if not allowed_terms or value in allowed_terms:
            kept.append(value)
        else:
            skipped.append(value)
    return kept, skipped


def build_stage3_seed_map(
    root: Path,
    cases_dir_name: str = "assets/cases",
    output_dir_name: str = "index/stage3",
    vocabulary_path: str = DEFAULT_VOCABULARY_PATH,
    strategy_profiles_path: str = DEFAULT_STRATEGY_PROFILES_PATH,
    goal_profiles_path: str = DEFAULT_GOAL_PROFILES_PATH,
    situation_profiles_path: str = DEFAULT_SITUATION_PROFILES_PATH,
    standardized_only: bool = True,
) -> dict[str, int]:
    cases_dir = root / cases_dir_name
    output_dir = root / output_dir_name
    vocabulary_file = root / vocabulary_path
    strategy_profiles_file = root / strategy_profiles_path
    goal_profiles_file = root / goal_profiles_path
    situation_profiles_file = root / situation_profiles_path
    vocabulary = load_stage3_vocabulary(vocabulary_file)
    strategy_profiles = load_strategy_profiles(strategy_profiles_file)
    goal_profiles = load_goal_profiles(goal_profiles_file)
    situation_profiles = load_situation_profiles(situation_profiles_file)
    allowed_strategy_tags = vocabulary["strategy_tags"]
    allowed_resource_refs = vocabulary["resource_refs"]

    strategy_index: dict[str, dict] = {}
    resource_index: dict[str, dict] = {}
    strategy_resource_edge_index: dict[tuple[str, str], dict] = {}
    case_strategy_edge_index: dict[tuple[str, str], dict] = {}
    case_resource_edge_index: dict[tuple[str, str], dict] = {}
    strategy_strategy_edge_index: dict[tuple[str, str], dict] = {}
    filtered_strategy_terms: dict[str, set[str]] = defaultdict(set)
    filtered_resource_terms: dict[str, set[str]] = defaultdict(set)
    filtered_cases = 0

    scanned_cases = 0
    linked_cases = 0

    for path in list_markdown_files(cases_dir):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue

        scanned_cases += 1
        meta, _body = read_markdown(path)
        case_ref = str(path.relative_to(root))
        raw_strategy_tags = ensure_list(meta.get("strategy_tags"))
        raw_resource_refs = ensure_list(meta.get("resource_refs"))
        if standardized_only:
            strategy_tags, skipped_strategy_tags = split_standardized_terms(raw_strategy_tags, allowed_strategy_tags)
            resource_refs, skipped_resource_refs = split_standardized_terms(raw_resource_refs, allowed_resource_refs)
        else:
            strategy_tags = unique_preserve_order(raw_strategy_tags)
            resource_refs = unique_preserve_order(raw_resource_refs)
            skipped_strategy_tags = []
            skipped_resource_refs = []

        if skipped_strategy_tags or skipped_resource_refs:
            filtered_cases += 1
        for term in skipped_strategy_tags:
            filtered_strategy_terms[term].add(case_ref)
        for term in skipped_resource_refs:
            filtered_resource_terms[term].add(case_ref)

        if not strategy_tags and not resource_refs:
            continue

        linked_cases += 1
        case_id = str(meta.get("case_id", "")).strip()
        status = str(meta.get("status", "")).strip()
        quality_score = parse_quality_score(meta.get("quality_score"))
        platform = str(meta.get("platform", "")).strip()
        domain = str(meta.get("domain", "")).strip()
        case_date = parse_date_value(meta.get("date"))
        quality_gate = infer_case_quality(meta)

        for tag in strategy_tags:
            node = strategy_index.setdefault(
                tag,
                {
                    "node_id": f"strategy_{slugify(tag)}",
                    "node_type": "strategy",
                    "label": tag,
                    "case_refs": set(),
                    "case_ids": set(),
                    "resource_refs": set(),
                    "action_refs": set(),
                    "template_refs": set(),
                    "tool_refs": set(),
                    "platform_resource_refs": set(),
                    "preferred_case_refs": set(),
                    "platforms": set(),
                    "domains": set(),
                    "statuses": set(),
                    "trust_levels": set(),
                    "verification_statuses": set(),
                    "approved_case_count": 0,
                    "reviewed_case_count": 0,
                    "draft_case_count": 0,
                    "production_case_count": 0,
                    "observation_case_count": 0,
                    "proof_case_count": 0,
                    "max_reproducibility_score": 0,
                    "last_evidence_date": None,
                    "invocation_count": 0,
                    "last_invoked_at": None,
                    "success_rate_30d": None,
                    "success_rate_lifetime": None,
                    "deprecation_reason": "",
                    "max_quality_score": 0.0,
                },
            )
            node["case_refs"].add(case_ref)
            if case_id:
                node["case_ids"].add(case_id)
            node["resource_refs"].update(resource_refs)
            if platform:
                node["platforms"].add(platform)
            if domain:
                node["domains"].add(domain)
            if status:
                node["statuses"].add(status)
            node["trust_levels"].add(quality_gate["trust_level"])
            node["verification_statuses"].add(quality_gate["verification_status"])
            node["max_quality_score"] = max(node["max_quality_score"], quality_score)
            node["max_reproducibility_score"] = max(node["max_reproducibility_score"], quality_gate["reproducibility_score"])
            if quality_gate["trust_level"] == "production":
                node["production_case_count"] += 1
            elif quality_gate["trust_level"] == "observation":
                node["observation_case_count"] += 1
            if quality_gate["proof_count"] > 0:
                node["proof_case_count"] += 1
            if case_date and (node["last_evidence_date"] is None or case_date > node["last_evidence_date"]):
                node["last_evidence_date"] = case_date
            if status == "approved":
                node["approved_case_count"] += 1
            elif status == "reviewed":
                node["reviewed_case_count"] += 1
            elif status == "draft":
                node["draft_case_count"] += 1

        for ref in resource_refs:
            node = resource_index.setdefault(
                ref,
                {
                    "node_id": f"resource_{slugify(ref)}",
                    "node_type": "resource",
                    "label": ref,
                    "case_refs": set(),
                    "case_ids": set(),
                    "strategy_tags": set(),
                    "platforms": set(),
                    "domains": set(),
                    "statuses": set(),
                    "trust_levels": set(),
                    "verification_statuses": set(),
                    "approved_case_count": 0,
                    "reviewed_case_count": 0,
                    "draft_case_count": 0,
                    "production_case_count": 0,
                    "observation_case_count": 0,
                    "proof_case_count": 0,
                    "max_reproducibility_score": 0,
                    "last_evidence_date": None,
                    "max_quality_score": 0.0,
                },
            )
            node["case_refs"].add(case_ref)
            if case_id:
                node["case_ids"].add(case_id)
            node["strategy_tags"].update(strategy_tags)
            if platform:
                node["platforms"].add(platform)
            if domain:
                node["domains"].add(domain)
            if status:
                node["statuses"].add(status)
            node["trust_levels"].add(quality_gate["trust_level"])
            node["verification_statuses"].add(quality_gate["verification_status"])
            node["max_quality_score"] = max(node["max_quality_score"], quality_score)
            node["max_reproducibility_score"] = max(node["max_reproducibility_score"], quality_gate["reproducibility_score"])
            if quality_gate["trust_level"] == "production":
                node["production_case_count"] += 1
            elif quality_gate["trust_level"] == "observation":
                node["observation_case_count"] += 1
            if quality_gate["proof_count"] > 0:
                node["proof_case_count"] += 1
            if case_date and (node["last_evidence_date"] is None or case_date > node["last_evidence_date"]):
                node["last_evidence_date"] = case_date
            if status == "approved":
                node["approved_case_count"] += 1
            elif status == "reviewed":
                node["reviewed_case_count"] += 1
            elif status == "draft":
                node["draft_case_count"] += 1

        for tag in strategy_tags:
            for ref in resource_refs:
                key = (tag, ref)
                edge = strategy_resource_edge_index.setdefault(
                    key,
                    {
                        "edge_id": f"edge_{slugify(tag)}__{slugify(ref)}",
                        "from_strategy_tag": tag,
                        "to_resource_ref": ref,
                        "relation": "co_occurs_in_case",
                        "case_refs": set(),
                        "case_ids": set(),
                        "platforms": set(),
                        "domains": set(),
                        "statuses": set(),
                        "approved_case_count": 0,
                        "reviewed_case_count": 0,
                        "draft_case_count": 0,
                        "max_quality_score": 0.0,
                    },
                )
                edge["case_refs"].add(case_ref)
                if case_id:
                    edge["case_ids"].add(case_id)
                if platform:
                    edge["platforms"].add(platform)
                if domain:
                    edge["domains"].add(domain)
                if status:
                    edge["statuses"].add(status)
                edge["max_quality_score"] = max(edge["max_quality_score"], quality_score)
                if status == "approved":
                    edge["approved_case_count"] += 1
                elif status == "reviewed":
                    edge["reviewed_case_count"] += 1
                elif status == "draft":
                    edge["draft_case_count"] += 1

        for tag in strategy_tags:
            key = (case_ref, tag)
            edge = case_strategy_edge_index.setdefault(
                key,
                {
                    "edge_id": f"edge_{slugify(case_ref)}__{slugify(tag)}",
                    "from_case_ref": case_ref,
                    "from_case_id": case_id,
                    "from_case_title": str(meta.get("title", "")).strip(),
                    "to_strategy_tag": tag,
                    "relation": "case_contains_strategy",
                    "platform": platform,
                    "domain": domain,
                    "status": status,
                    "quality_score": quality_score,
                },
            )
            if case_id and not edge["from_case_id"]:
                edge["from_case_id"] = case_id
            if platform and not edge["platform"]:
                edge["platform"] = platform
            if domain and not edge["domain"]:
                edge["domain"] = domain
            if status and not edge["status"]:
                edge["status"] = status
            edge["quality_score"] = max(edge["quality_score"], quality_score)

        for ref in resource_refs:
            key = (case_ref, ref)
            edge = case_resource_edge_index.setdefault(
                key,
                {
                    "edge_id": f"edge_{slugify(case_ref)}__{slugify(ref)}",
                    "from_case_ref": case_ref,
                    "from_case_id": case_id,
                    "from_case_title": str(meta.get("title", "")).strip(),
                    "to_resource_ref": ref,
                    "relation": "case_contains_resource",
                    "platform": platform,
                    "domain": domain,
                    "status": status,
                    "quality_score": quality_score,
                },
            )
            if case_id and not edge["from_case_id"]:
                edge["from_case_id"] = case_id
            if platform and not edge["platform"]:
                edge["platform"] = platform
            if domain and not edge["domain"]:
                edge["domain"] = domain
            if status and not edge["status"]:
                edge["status"] = status
            edge["quality_score"] = max(edge["quality_score"], quality_score)

        for left_tag, right_tag in combinations(sorted(strategy_tags), 2):
            key = (left_tag, right_tag)
            edge = strategy_strategy_edge_index.setdefault(
                key,
                {
                    "edge_id": f"edge_{slugify(left_tag)}__{slugify(right_tag)}",
                    "from_strategy_tag": left_tag,
                    "to_strategy_tag": right_tag,
                    "relation": "strategy_co_occurs_in_case",
                    "case_refs": set(),
                    "case_ids": set(),
                    "shared_resource_refs": set(),
                    "platforms": set(),
                    "domains": set(),
                    "statuses": set(),
                    "approved_case_count": 0,
                    "reviewed_case_count": 0,
                    "draft_case_count": 0,
                    "max_quality_score": 0.0,
                },
            )
            edge["case_refs"].add(case_ref)
            if case_id:
                edge["case_ids"].add(case_id)
            edge["shared_resource_refs"].update(resource_refs)
            if platform:
                edge["platforms"].add(platform)
            if domain:
                edge["domains"].add(domain)
            if status:
                edge["statuses"].add(status)
            edge["max_quality_score"] = max(edge["max_quality_score"], quality_score)
            if status == "approved":
                edge["approved_case_count"] += 1
            elif status == "reviewed":
                edge["reviewed_case_count"] += 1
            elif status == "draft":
                edge["draft_case_count"] += 1

    for tag, node in strategy_index.items():
        profile = strategy_profiles.get(tag, {})
        node["action_refs"].update(str(item).strip() for item in profile.get("action_refs", []) if str(item).strip())
        node["template_refs"].update(str(item).strip() for item in profile.get("template_refs", []) if str(item).strip())
        node["tool_refs"].update(str(item).strip() for item in profile.get("tool_refs", []) if str(item).strip())
        node["platform_resource_refs"].update(
            str(item).strip() for item in profile.get("platform_resource_refs", []) if str(item).strip()
        )
        node["preferred_case_refs"].update(
            str(item).strip() for item in profile.get("preferred_case_refs", []) if str(item).strip()
        )
        node["resource_refs"].update(node["platform_resource_refs"])

    strategy_rows = []
    for item in strategy_index.values():
        action_refs = sorted(item["action_refs"])
        template_refs = sorted(item["template_refs"])
        tool_refs = sorted(item["tool_refs"])
        platform_resource_refs = sorted(item["platform_resource_refs"])
        preferred_case_refs = sorted(item["preferred_case_refs"])
        strategy_rows.append(
            {
                "node_id": item["node_id"],
                "node_type": item["node_type"],
                "label": item["label"],
                "case_refs": sorted(item["case_refs"]),
                "case_ids": sorted(item["case_ids"]),
                "resource_refs": sorted(item["resource_refs"]),
                "action_refs": action_refs,
                "template_refs": template_refs,
                "tool_refs": tool_refs,
                "platform_resource_refs": platform_resource_refs,
                "preferred_case_refs": preferred_case_refs,
                "resource_container_ready": bool(action_refs or template_refs or tool_refs or preferred_case_refs),
                "platforms": sorted(item["platforms"]),
                "domains": sorted(item["domains"]),
                "statuses": sorted(item["statuses"]),
                "trust_levels": sorted(item["trust_levels"]),
                "verification_statuses": sorted(item["verification_statuses"]),
                "evidence_case_count": len(item["case_refs"]),
                "approved_case_count": item["approved_case_count"],
                "reviewed_case_count": item["reviewed_case_count"],
                "draft_case_count": item["draft_case_count"],
                "production_case_count": item["production_case_count"],
                "observation_case_count": item["observation_case_count"],
                "proof_case_count": item["proof_case_count"],
                "max_reproducibility_score": item["max_reproducibility_score"],
                "last_evidence_date": item["last_evidence_date"].isoformat() if item["last_evidence_date"] else "",
                "active_status": compute_active_status(
                    item["approved_case_count"],
                    len(item["case_refs"]),
                    item["last_evidence_date"],
                )[0],
                "evidence_freshness_days": compute_active_status(
                    item["approved_case_count"],
                    len(item["case_refs"]),
                    item["last_evidence_date"],
                )[1],
                "invocation_count": item["invocation_count"],
                "last_invoked_at": item["last_invoked_at"],
                "success_rate_30d": item["success_rate_30d"],
                "success_rate_lifetime": item["success_rate_lifetime"],
                "deprecation_reason": item["deprecation_reason"],
                "max_quality_score": item["max_quality_score"],
            }
        )
    strategy_rows.sort(key=lambda row: (-row["approved_case_count"], -row["evidence_case_count"], row["label"]))

    resource_rows = []
    for item in resource_index.values():
        resource_rows.append(
            {
                "node_id": item["node_id"],
                "node_type": item["node_type"],
                "label": item["label"],
                "case_refs": sorted(item["case_refs"]),
                "case_ids": sorted(item["case_ids"]),
                "strategy_tags": sorted(item["strategy_tags"]),
                "platforms": sorted(item["platforms"]),
                "domains": sorted(item["domains"]),
                "statuses": sorted(item["statuses"]),
                "trust_levels": sorted(item["trust_levels"]),
                "verification_statuses": sorted(item["verification_statuses"]),
                "evidence_case_count": len(item["case_refs"]),
                "approved_case_count": item["approved_case_count"],
                "reviewed_case_count": item["reviewed_case_count"],
                "draft_case_count": item["draft_case_count"],
                "production_case_count": item["production_case_count"],
                "observation_case_count": item["observation_case_count"],
                "proof_case_count": item["proof_case_count"],
                "max_reproducibility_score": item["max_reproducibility_score"],
                "last_evidence_date": item["last_evidence_date"].isoformat() if item["last_evidence_date"] else "",
                "max_quality_score": item["max_quality_score"],
            }
        )
    resource_rows.sort(key=lambda row: (-row["approved_case_count"], -row["evidence_case_count"], row["label"]))

    strategy_resource_edge_rows = []
    for item in strategy_resource_edge_index.values():
        strategy_resource_edge_rows.append(
            {
                "edge_id": item["edge_id"],
                "from_strategy_tag": item["from_strategy_tag"],
                "to_resource_ref": item["to_resource_ref"],
                "relation": item["relation"],
                "case_refs": sorted(item["case_refs"]),
                "case_ids": sorted(item["case_ids"]),
                "platforms": sorted(item["platforms"]),
                "domains": sorted(item["domains"]),
                "statuses": sorted(item["statuses"]),
                "evidence_case_count": len(item["case_refs"]),
                "approved_case_count": item["approved_case_count"],
                "reviewed_case_count": item["reviewed_case_count"],
                "draft_case_count": item["draft_case_count"],
                "max_quality_score": item["max_quality_score"],
            }
        )
    strategy_resource_edge_rows.sort(
        key=lambda row: (-row["approved_case_count"], -row["evidence_case_count"], row["from_strategy_tag"], row["to_resource_ref"])
    )

    case_strategy_edge_rows = list(case_strategy_edge_index.values())
    case_strategy_edge_rows.sort(key=lambda row: (row["from_case_ref"], row["to_strategy_tag"]))

    case_resource_edge_rows = list(case_resource_edge_index.values())
    case_resource_edge_rows.sort(key=lambda row: (row["from_case_ref"], row["to_resource_ref"]))

    strategy_strategy_edge_rows = []
    for item in strategy_strategy_edge_index.values():
        strategy_strategy_edge_rows.append(
            {
                "edge_id": item["edge_id"],
                "from_strategy_tag": item["from_strategy_tag"],
                "to_strategy_tag": item["to_strategy_tag"],
                "relation": item["relation"],
                "case_refs": sorted(item["case_refs"]),
                "case_ids": sorted(item["case_ids"]),
                "shared_resource_refs": sorted(item["shared_resource_refs"]),
                "platforms": sorted(item["platforms"]),
                "domains": sorted(item["domains"]),
                "statuses": sorted(item["statuses"]),
                "evidence_case_count": len(item["case_refs"]),
                "approved_case_count": item["approved_case_count"],
                "reviewed_case_count": item["reviewed_case_count"],
                "draft_case_count": item["draft_case_count"],
                "max_quality_score": item["max_quality_score"],
            }
        )
    strategy_strategy_edge_rows.sort(
        key=lambda row: (-row["approved_case_count"], -row["evidence_case_count"], row["from_strategy_tag"], row["to_strategy_tag"])
    )

    goal_strategy_edge_rows = []
    for goal in goal_profiles:
        goal_label = str(goal.get("label", "")).strip()
        if not goal_label:
            continue
        for relation, strategies in [
            ("is_path_to", goal.get("primary_strategies", [])),
            ("combines_with", goal.get("secondary_strategies", [])),
        ]:
            for strategy_label in [str(item).strip() for item in strategies if str(item).strip()]:
                node = strategy_index.get(strategy_label)
                profile = strategy_profiles.get(strategy_label, {})
                if not node:
                    continue
                goal_strategy_edge_rows.append(
                    {
                        "edge_id": f"edge_{slugify(goal_label)}__{slugify(strategy_label)}",
                        "edge_type": "goal_to_strategy",
                        "from_goal": goal_label,
                        "to_strategy": strategy_label,
                        "relation": relation,
                        "trigger_conditions": [
                            f"用户目标={goal_label}",
                            *[f"平台优先={item}" for item in goal.get("preferred_platforms", []) if str(item).strip()],
                            *[f"用户类型优先={item}" for item in goal.get("preferred_user_types", []) if str(item).strip()],
                            *[f"领域优先={item}" for item in goal.get("preferred_domains", []) if str(item).strip()],
                        ],
                        "applicable_params": [
                            *[f"平台={item}" for item in profile.get("applicable_platforms", []) if str(item).strip()],
                            *[f"用户类型={item}" for item in profile.get("applicable_user_types", []) if str(item).strip()],
                            *[f"领域={item}" for item in profile.get("applicable_domains", []) if str(item).strip()],
                            *[str(item).strip() for item in profile.get("activation_rules", []) if str(item).strip()],
                        ],
                        "not_applicable_warning": "；".join(
                            [
                                *[str(item).strip() for item in profile.get("not_applicable_rules", []) if str(item).strip()],
                                *[str(item).strip() for item in goal.get("risk_notes", []) if str(item).strip()],
                            ]
                        ),
                        "call_output": {
                            "action_refs": sorted(node["action_refs"]),
                            "template_refs": sorted(node["template_refs"]),
                            "tool_refs": sorted(node["tool_refs"]),
                            "preferred_case_refs": sorted(node["preferred_case_refs"]),
                        },
                    }
                )
    goal_strategy_edge_rows.sort(key=lambda row: (row["from_goal"], row["relation"], row["to_strategy"]))

    situation_rows = []
    situation_strategy_edge_rows = []
    strategy_situation_edge_rows = []
    for situation_label, situation in sorted(situation_profiles.items(), key=lambda item: str(item[1].get("situation_id", "")).strip() or item[0]):
        situation_id = str(situation.get("situation_id", "")).strip() or f"S_{slugify(situation_label)}".upper()
        preferred_rules = [item for item in situation.get("preferred_strategy_rules", []) if isinstance(item, dict)]
        preferred_reason_map = {
            str(item.get("strategy_ref", "")).strip(): str(item.get("reason", "")).strip()
            for item in preferred_rules
            if str(item.get("strategy_ref", "")).strip()
        }
        suitable_strategy_refs = unique_preserve_order(
            [
                *preferred_reason_map.keys(),
                *[
                    strategy_label
                    for strategy_label, profile in sorted(strategy_profiles.items())
                    if situation_label in [str(item).strip() for item in profile.get("applicable_user_types", []) if str(item).strip()]
                ],
            ]
        )
        blocked_rules = [item for item in situation.get("not_suitable_strategy_rules", []) if isinstance(item, dict)]
        blocked_strategy_refs = unique_preserve_order(
            [str(item.get("strategy_ref", "")).strip() for item in blocked_rules if str(item.get("strategy_ref", "")).strip()]
        )
        representative_case_refs = unique_preserve_order(
            [str(item).strip() for item in situation.get("representative_case_refs", []) if str(item).strip()]
            + [
                str(case_ref).strip()
                for strategy_label in suitable_strategy_refs
                for case_ref in strategy_profiles.get(strategy_label, {}).get("preferred_case_refs", [])
                if str(case_ref).strip()
            ]
        )
        suitable_platforms = unique_preserve_order(
            [
                str(item).strip()
                for strategy_label in suitable_strategy_refs
                for item in strategy_profiles.get(strategy_label, {}).get("applicable_platforms", [])
                if str(item).strip()
            ]
        )
        suitable_domains = unique_preserve_order(
            [
                str(item).strip()
                for strategy_label in suitable_strategy_refs
                for item in strategy_profiles.get(strategy_label, {}).get("applicable_domains", [])
                if str(item).strip()
            ]
        )

        situation_rows.append(
            {
                "node_id": f"situation_{slugify(situation_id)}",
                "node_type": "situation",
                "situation_id": situation_id,
                "label": situation_label,
                "title": str(situation.get("title", "")).strip() or situation_label,
                "summary": str(situation.get("summary", "")).strip(),
                "resource_features": unique_preserve_order(
                    [str(item).strip() for item in situation.get("resource_features", []) if str(item).strip()]
                ),
                "skill_features": unique_preserve_order(
                    [str(item).strip() for item in situation.get("skill_features", []) if str(item).strip()]
                ),
                "psychological_features": unique_preserve_order(
                    [str(item).strip() for item in situation.get("psychological_features", []) if str(item).strip()]
                ),
                "default_constraints": unique_preserve_order(
                    [str(item).strip() for item in situation.get("default_constraints", []) if str(item).strip()]
                ),
                "representative_case_refs": representative_case_refs,
                "suitable_strategy_refs": suitable_strategy_refs,
                "not_suitable_strategy_refs": blocked_strategy_refs,
                "platforms": suitable_platforms,
                "domains": suitable_domains,
                "evidence_case_count": len(representative_case_refs),
            }
        )

        for strategy_label in suitable_strategy_refs:
            profile = strategy_profiles.get(strategy_label, {})
            node = strategy_index.get(strategy_label, {})
            if not profile:
                continue
            reason = preferred_reason_map.get(strategy_label) or "该策略的资源门槛、平台要求和验证节奏与当前情境匹配。"
            trigger_conditions = unique_preserve_order(
                [
                    f"情境节点={situation_id}:{situation_label}",
                    f"用户类型={situation_label}",
                    *[f"默认约束={item}" for item in situation.get("default_constraints", []) if str(item).strip()],
                    *[f"平台匹配={item}" for item in profile.get("applicable_platforms", []) if str(item).strip()],
                    *[f"领域匹配={item}" for item in profile.get("applicable_domains", []) if str(item).strip()],
                ]
            )
            applicable_params = unique_preserve_order(
                [
                    *[str(item).strip() for item in situation.get("resource_features", []) if str(item).strip()],
                    *[str(item).strip() for item in situation.get("skill_features", []) if str(item).strip()],
                    *[str(item).strip() for item in profile.get("activation_rules", []) if str(item).strip()],
                ]
            )
            warning = "；".join(
                unique_preserve_order([str(item).strip() for item in profile.get("not_applicable_rules", []) if str(item).strip()])
            )
            call_output = {
                "action_refs": sorted(node.get("action_refs", [])),
                "template_refs": sorted(node.get("template_refs", [])),
                "tool_refs": sorted(node.get("tool_refs", [])),
                "preferred_case_refs": sorted(node.get("preferred_case_refs", [])),
            }
            situation_strategy_edge_rows.append(
                {
                    "edge_id": f"edge_{slugify(situation_label)}__{slugify(strategy_label)}__fits",
                    "edge_type": "situation_to_strategy",
                    "from_situation_id": situation_id,
                    "from_situation": situation_label,
                    "to_strategy": strategy_label,
                    "relation": "particularly_suits",
                    "reason": reason,
                    "trigger_conditions": trigger_conditions,
                    "applicable_params": applicable_params,
                    "not_applicable_warning": warning,
                    "call_output": call_output,
                }
            )
            strategy_situation_edge_rows.append(
                {
                    "edge_id": f"edge_{slugify(strategy_label)}__{slugify(situation_label)}__fits",
                    "edge_type": "strategy_to_situation",
                    "from_strategy": strategy_label,
                    "to_situation_id": situation_id,
                    "to_situation": situation_label,
                    "relation": "particularly_suits",
                    "reason": reason,
                    "trigger_conditions": trigger_conditions,
                    "applicable_params": applicable_params,
                    "not_applicable_warning": warning,
                    "call_output": call_output,
                }
            )

        for rule in blocked_rules:
            strategy_label = str(rule.get("strategy_ref", "")).strip()
            if not strategy_label:
                continue
            profile = strategy_profiles.get(strategy_label, {})
            reason = str(rule.get("reason", "")).strip() or "该策略超出当前情境的资源和执行承受范围。"
            fallback_strategy_refs = unique_preserve_order(
                [str(item).strip() for item in rule.get("fallback_strategy_refs", []) if str(item).strip()]
            )
            warning = "；".join(
                unique_preserve_order(
                    [
                        reason,
                        *[str(item).strip() for item in profile.get("not_applicable_rules", []) if str(item).strip()],
                    ]
                )
            )
            trigger_conditions = unique_preserve_order(
                [
                    f"情境节点={situation_id}:{situation_label}",
                    f"用户类型={situation_label}",
                    *[f"默认约束={item}" for item in situation.get("default_constraints", []) if str(item).strip()],
                ]
            )
            applicable_params = unique_preserve_order(
                [
                    *[str(item).strip() for item in situation.get("resource_features", []) if str(item).strip()],
                    *[str(item).strip() for item in situation.get("psychological_features", []) if str(item).strip()],
                ]
            )
            call_output = {
                "action_refs": [],
                "template_refs": [],
                "tool_refs": [],
                "preferred_case_refs": unique_preserve_order(
                    [str(item).strip() for item in situation.get("representative_case_refs", []) if str(item).strip()]
                ),
                "fallback_strategy_refs": fallback_strategy_refs,
            }
            situation_strategy_edge_rows.append(
                {
                    "edge_id": f"edge_{slugify(situation_label)}__{slugify(strategy_label)}__blocked",
                    "edge_type": "situation_to_strategy",
                    "from_situation_id": situation_id,
                    "from_situation": situation_label,
                    "to_strategy": strategy_label,
                    "relation": "not_suitable_for",
                    "reason": reason,
                    "trigger_conditions": trigger_conditions,
                    "applicable_params": applicable_params,
                    "not_applicable_warning": warning,
                    "call_output": call_output,
                }
            )
            strategy_situation_edge_rows.append(
                {
                    "edge_id": f"edge_{slugify(strategy_label)}__{slugify(situation_label)}__blocked",
                    "edge_type": "strategy_to_situation",
                    "from_strategy": strategy_label,
                    "to_situation_id": situation_id,
                    "to_situation": situation_label,
                    "relation": "not_suitable_for",
                    "reason": reason,
                    "trigger_conditions": trigger_conditions,
                    "applicable_params": applicable_params,
                    "not_applicable_warning": warning,
                    "call_output": call_output,
                }
            )

    situation_rows.sort(key=lambda row: (row["situation_id"], row["label"]))
    situation_strategy_edge_rows.sort(key=lambda row: (row["from_situation"], row["relation"], row["to_strategy"]))
    strategy_situation_edge_rows.sort(key=lambda row: (row["from_strategy"], row["relation"], row["to_situation"]))

    write_jsonl(output_dir / "strategy_nodes.jsonl", strategy_rows)
    write_jsonl(output_dir / "situation_nodes.jsonl", situation_rows)
    write_jsonl(output_dir / "resource_nodes.jsonl", resource_rows)
    write_jsonl(output_dir / "strategy_resource_edges.jsonl", strategy_resource_edge_rows)
    write_jsonl(output_dir / "case_strategy_edges.jsonl", case_strategy_edge_rows)
    write_jsonl(output_dir / "case_resource_edges.jsonl", case_resource_edge_rows)
    write_jsonl(output_dir / "strategy_strategy_edges.jsonl", strategy_strategy_edge_rows)
    write_jsonl(output_dir / "goal_strategy_edges.jsonl", goal_strategy_edge_rows)
    write_jsonl(output_dir / "situation_strategy_edges.jsonl", situation_strategy_edge_rows)
    write_jsonl(output_dir / "strategy_situation_edges.jsonl", strategy_situation_edge_rows)

    report_lines = [
        "# 阶段三种子图谱报告",
        "",
        f"- 标准词模式：`{'on' if standardized_only else 'off'}`",
        f"- 词表文件：`{vocabulary_path}`",
        f"- 扫描案例数：`{scanned_cases}`",
        f"- 进入阶段三连边案例数：`{linked_cases}`",
        f"- 策略节点数：`{len(strategy_rows)}`",
        f"- 情境节点数：`{len(situation_rows)}`",
        f"- 资源节点数：`{len(resource_rows)}`",
        f"- 策略->资源边数：`{len(strategy_resource_edge_rows)}`",
        f"- 案例->策略边数：`{len(case_strategy_edge_rows)}`",
        f"- 案例->资源边数：`{len(case_resource_edge_rows)}`",
        f"- 策略->策略共现边数：`{len(strategy_strategy_edge_rows)}`",
        f"- 目标->策略路由边数：`{len(goal_strategy_edge_rows)}`",
        f"- 情境->策略路由边数：`{len(situation_strategy_edge_rows)}`",
        f"- 策略->情境关系边数：`{len(strategy_situation_edge_rows)}`",
        f"- 含非标准词案例数：`{filtered_cases}`",
        f"- 被过滤策略词数：`{len(filtered_strategy_terms)}`",
        f"- 被过滤资源词数：`{len(filtered_resource_terms)}`",
        "",
        "## 优先策略节点",
        "",
    ]

    for row in strategy_rows[:12]:
        report_lines.extend(
            [
                f"### {row['label']}",
                f"- 证据病例数：`{row['evidence_case_count']}`",
                f"- 其中 approved：`{row['approved_case_count']}`",
                f"- 动作包索引：{', '.join(row['action_refs']) if row['action_refs'] else '无'}",
                f"- 模板资源索引：{', '.join(row['template_refs']) if row['template_refs'] else '无'}",
                f"- 工具调用指令：{', '.join(row['tool_refs']) if row['tool_refs'] else '无'}",
                f"- 平台资源词：{', '.join(row['platform_resource_refs']) if row['platform_resource_refs'] else '无'}",
                f"- 成功案例快照：{', '.join(row['preferred_case_refs']) if row['preferred_case_refs'] else '无'}",
                f"- 关联案例：{', '.join(row['case_refs']) if row['case_refs'] else '无'}",
                "",
            ]
        )

    report_lines.extend(["## 情境节点卡", ""])
    for row in situation_rows[:12]:
        report_lines.extend(
            [
                f"### {row['situation_id']} {row['label']}",
                f"- 标题：`{row['title']}`",
                f"- 摘要：{row['summary'] or '无'}",
                f"- 资源特征：{', '.join(row['resource_features']) if row['resource_features'] else '无'}",
                f"- 技能特征：{', '.join(row['skill_features']) if row['skill_features'] else '无'}",
                f"- 心理特征：{', '.join(row['psychological_features']) if row['psychological_features'] else '无'}",
                f"- 默认约束：{', '.join(row['default_constraints']) if row['default_constraints'] else '无'}",
                f"- 代表案例：{', '.join(row['representative_case_refs']) if row['representative_case_refs'] else '无'}",
                f"- 适用策略：{', '.join(row['suitable_strategy_refs']) if row['suitable_strategy_refs'] else '无'}",
                f"- 禁区策略：{', '.join(row['not_suitable_strategy_refs']) if row['not_suitable_strategy_refs'] else '无'}",
                "",
            ]
        )

    report_lines.extend(["## 优先资源节点", ""])
    for row in resource_rows[:12]:
        report_lines.extend(
            [
                f"### {row['label']}",
                f"- 证据病例数：`{row['evidence_case_count']}`",
                f"- 其中 approved：`{row['approved_case_count']}`",
                f"- 关联策略：{', '.join(row['strategy_tags']) if row['strategy_tags'] else '无'}",
                f"- 关联案例：{', '.join(row['case_refs']) if row['case_refs'] else '无'}",
                "",
            ]
        )

    report_lines.extend(["## 优先策略到资源边", ""])
    for row in strategy_resource_edge_rows[:20]:
        report_lines.extend(
            [
                f"- `{row['from_strategy_tag']}` -> `{row['to_resource_ref']}`",
                f"  - 证据病例数：`{row['evidence_case_count']}`；approved：`{row['approved_case_count']}`",
                f"  - 案例：{', '.join(row['case_refs']) if row['case_refs'] else '无'}",
            ]
        )

    report_lines.extend(["", "## 优先策略共现边", ""])
    for row in strategy_strategy_edge_rows[:20]:
        report_lines.extend(
            [
                f"- `{row['from_strategy_tag']}` <-> `{row['to_strategy_tag']}`",
                f"  - 共现案例数：`{row['evidence_case_count']}`；approved：`{row['approved_case_count']}`",
                f"  - 共享资源：{', '.join(row['shared_resource_refs']) if row['shared_resource_refs'] else '无'}",
                f"  - 案例：{', '.join(row['case_refs']) if row['case_refs'] else '无'}",
            ]
        )

    report_lines.extend(["", "## 案例边文件", ""])
    report_lines.extend(
        [
            f"- `case_strategy_edges.jsonl`: `{len(case_strategy_edge_rows)}` 条",
            f"- `case_resource_edges.jsonl`: `{len(case_resource_edge_rows)}` 条",
            f"- `goal_strategy_edges.jsonl`: `{len(goal_strategy_edge_rows)}` 条",
            f"- `situation_nodes.jsonl`: `{len(situation_rows)}` 条",
            f"- `situation_strategy_edges.jsonl`: `{len(situation_strategy_edge_rows)}` 条",
            f"- `strategy_situation_edges.jsonl`: `{len(strategy_situation_edge_rows)}` 条",
        ]
    )

    if filtered_strategy_terms:
        report_lines.extend(["", "## 被过滤的非标准策略词", ""])
        for term, case_refs in sorted(filtered_strategy_terms.items()):
            report_lines.append(f"- `{term}`: {', '.join(sorted(case_refs))}")

    if filtered_resource_terms:
        report_lines.extend(["", "## 被过滤的非标准资源词", ""])
        for term, case_refs in sorted(filtered_resource_terms.items()):
            report_lines.append(f"- `{term}`: {', '.join(sorted(case_refs))}")

    report_lines.append("")
    (output_dir / "stage3_seed_report.md").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "stage3_seed_report.md").write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")

    return {
        "scanned_cases": scanned_cases,
        "linked_cases": linked_cases,
        "strategy_nodes": len(strategy_rows),
        "situation_nodes": len(situation_rows),
        "resource_nodes": len(resource_rows),
        "strategy_resource_edges": len(strategy_resource_edge_rows),
        "case_strategy_edges": len(case_strategy_edge_rows),
        "case_resource_edges": len(case_resource_edge_rows),
        "strategy_strategy_edges": len(strategy_strategy_edge_rows),
        "goal_strategy_edges": len(goal_strategy_edge_rows),
        "situation_strategy_edges": len(situation_strategy_edge_rows),
        "strategy_situation_edges": len(strategy_situation_edge_rows),
        "filtered_cases": filtered_cases,
        "filtered_strategy_terms": len(filtered_strategy_terms),
        "filtered_resource_terms": len(filtered_resource_terms),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-3 seed nodes and candidate edges from case metadata.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--cases-dir", default="assets/cases")
    parser.add_argument("--output-dir", default="index/stage3")
    parser.add_argument("--vocabulary", default=DEFAULT_VOCABULARY_PATH)
    parser.add_argument("--strategy-profiles", default=DEFAULT_STRATEGY_PROFILES_PATH)
    parser.add_argument("--goal-profiles", default=DEFAULT_GOAL_PROFILES_PATH)
    parser.add_argument("--situation-profiles", default=DEFAULT_SITUATION_PROFILES_PATH)
    parser.add_argument("--allow-nonstandard", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    stats = build_stage3_seed_map(
        root=root,
        cases_dir_name=args.cases_dir,
        output_dir_name=args.output_dir,
        vocabulary_path=args.vocabulary,
        strategy_profiles_path=args.strategy_profiles,
        goal_profiles_path=args.goal_profiles,
        situation_profiles_path=args.situation_profiles,
        standardized_only=not args.allow_nonstandard,
    )
    print(
        "Built stage3 seed map: "
        f"cases={stats['linked_cases']}/{stats['scanned_cases']}, "
        f"strategy_nodes={stats['strategy_nodes']}, "
        f"situation_nodes={stats['situation_nodes']}, "
        f"resource_nodes={stats['resource_nodes']}, "
        f"strategy_resource_edges={stats['strategy_resource_edges']}, "
        f"case_strategy_edges={stats['case_strategy_edges']}, "
        f"case_resource_edges={stats['case_resource_edges']}, "
        f"strategy_strategy_edges={stats['strategy_strategy_edges']}, "
        f"goal_strategy_edges={stats['goal_strategy_edges']}, "
        f"situation_strategy_edges={stats['situation_strategy_edges']}, "
        f"strategy_situation_edges={stats['strategy_situation_edges']}, "
        f"filtered_cases={stats['filtered_cases']}, "
        f"filtered_strategy_terms={stats['filtered_strategy_terms']}, "
        f"filtered_resource_terms={stats['filtered_resource_terms']}"
    )


if __name__ == "__main__":
    main()
