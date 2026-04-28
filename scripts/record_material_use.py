#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml

from _material_lib import ensure_string_list, parse_frontmatter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_path")
    parser.add_argument("--article-id", required=True)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    material_path = root / args.material_path
    text = material_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    use_count = int(meta.get("use_count", 0) or 0) + 1
    used_in_articles = ensure_string_list(meta.get("used_in_articles"))
    if args.article_id not in used_in_articles:
        used_in_articles.append(args.article_id)

    meta["use_count"] = use_count
    meta["last_used_at"] = datetime.now(timezone.utc).isoformat()
    meta["used_in_articles"] = used_in_articles

    frontmatter = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    material_path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
    print(f"Recorded usage for {material_path}")


if __name__ == "__main__":
    main()
