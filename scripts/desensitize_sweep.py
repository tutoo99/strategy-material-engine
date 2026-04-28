#!/usr/bin/env python3
"""
批量隐私脱敏扫描与修复脚本。

对 assets/materials/ 下所有非 template 的 .md 文件执行：
1. source 字段：亦仁→某投资人，老友夜聊→朋友交流，去掉 /Users/naipan/ 绝对路径
2. 正文：亦仁→某投资人，老华→某投资博主
3. 输出修复报告

使用方式：
  /opt/miniconda3/bin/python3 scripts/desensitize_sweep.py
  /opt/miniconda3/bin/python3 scripts/desensitize_sweep.py --dry-run  # 只扫描不修改

注意：修复后需要重建索引：
  /opt/miniconda3/bin/python3 scripts/build_materials_index.py --root . --device cpu --batch-size 2
"""

import re
import os
import argparse

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "materials")

# 替换规则：每条是 (pattern, replacement, scope)
# scope: "source" 只改 source 字段，"body" 只改正文，"both" 两处都改
REPLACE_RULES = [
    (r'^source:\s*亦仁_', 'source: 某投资人_', 'source'),
    (r'^source:\s*老友夜聊_', 'source: 朋友交流_', 'source'),
    (r'/Users/naipan/', '', 'source'),
    (r'亦仁', '某投资人', 'body'),
    (r'老华', '某投资博主', 'body'),
]


def fix_source(line):
    original = line
    for pattern, replacement, scope in REPLACE_RULES:
        if scope in ('source', 'both'):
            line = re.sub(pattern, replacement, line)
    return line, line != original


def fix_body(body):
    original = body
    for pattern, replacement, scope in REPLACE_RULES:
        if scope in ('body', 'both'):
            body = re.sub(pattern, replacement, body)
    return body, body != original


def main():
    parser = argparse.ArgumentParser(description='批量隐私脱敏扫描与修复')
    parser.add_argument('--dry-run', action='store_true', help='只扫描不修改')
    parser.add_argument('--root', default=BASE, help='素材根目录')
    args = parser.parse_args()

    stats = {"total": 0, "source_fixed": 0, "body_fixed": 0, "errors": []}

    for dirpath, dirnames, filenames in os.walk(args.root):
        for fn in filenames:
            if not fn.endswith('.md') or fn == '_template.md':
                continue

            fpath = os.path.join(dirpath, fn)
            stats["total"] += 1

            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()

                lines = content.split('\n')
                new_lines = []
                modified = False

                i = 0
                if lines and lines[0].strip() == '---':
                    new_lines.append(lines[0])
                    i = 1
                    while i < len(lines) and lines[i].strip() != '---':
                        line = lines[i]
                        if line.startswith('source:'):
                            fixed, changed = fix_source(line)
                            if changed:
                                stats["source_fixed"] += 1
                                modified = True
                            new_lines.append(fixed)
                        else:
                            new_lines.append(line)
                        i += 1
                    if i < len(lines):
                        new_lines.append(lines[i])
                        i += 1

                body_text = '\n'.join(lines[i:])
                fixed_body, body_changed = fix_body(body_text)
                if body_changed:
                    stats["body_fixed"] += 1
                    modified = True

                if modified:
                    rel = os.path.relpath(fpath, args.root)
                    if args.dry_run:
                        print(f"WOULD FIX: {rel}")
                    else:
                        new_content = '\n'.join(new_lines) + '\n' + fixed_body
                        with open(fpath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"FIXED: {rel}")

            except Exception as e:
                stats["errors"].append(f"{fpath}: {e}")

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n=== {mode} Summary ===")
    print(f"Files scanned: {stats['total']}")
    print(f"Source fields fixed: {stats['source_fixed']}")
    print(f"Body text fixed: {stats['body_fixed']}")
    if stats['errors']:
        print(f"Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
