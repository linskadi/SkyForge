#!/usr/bin/env python3
"""Wrap the 6 inconsistently-structured i18n module JSONs under their module name.

The app's dominant convention (anchor/dashboard/generate/hitl/records/settings +
common-as-root) namespaces each module file as {"<module>": {...}}, and all code
references keys as `t('<module>.key')`. Six modules (architecture, compliance,
compose, data, lab, misra) stored keys at the TOP LEVEL instead, so every
`t('<module>.key')` reference was unresolved. This wraps them to match.

Safe: verified no source references these modules' keys bare (which wrapping would
break).
"""
import json
import os
import sys

# 自动定位 i18n 目录：脚本位于 scripts/，项目根目录为其父级
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ROOT = os.path.join(PROJECT_ROOT, "studio", "frontend", "src", "i18n", "locales")

MODULES = ["architecture", "compliance", "compose", "data", "lab", "misra"]
LOCALES = ["zh-CN", "en"]

if not os.path.isdir(ROOT):
    print(f"ERROR: i18n locales directory not found: {ROOT}", file=sys.stderr)
    sys.exit(1)

for locale in LOCALES:
    for mod in MODULES:
        path = os.path.join(ROOT, locale, f"{mod}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if mod in data:
            print(f"SKIP {locale}/{mod}.json (already wrapped)")
            continue
        wrapped = {mod: data}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wrapped, f, ensure_ascii=False, indent="\t")
            f.write("\n")
        print(f"WRAPPED {locale}/{mod}.json ({len(data)} top-level keys -> {mod})")
print("DONE")
