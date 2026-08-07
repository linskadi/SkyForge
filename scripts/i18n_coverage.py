#!/usr/bin/env python3
"""i18n coverage analyzer for SkyForge frontend.

Reconstructs the *exact* merged message tree the app builds at runtime
(common.json is the locale root; every other <module>.json is shallow-merged
at the top level via loadLocaleModule) and cross-checks every static i18n
key referenced in source against that tree.

Outputs:
  - referenced keys missing in zh-CN
  - referenced keys missing in en
  - zh-CN vs en parity (defined keys only)
"""
import json
import os
import re
import sys
from collections import defaultdict

# 自动定位前端目录：脚本位于 scripts/，项目根目录为其父级
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ROOT = os.path.join(PROJECT_ROOT, "studio", "frontend")
SRC = os.path.join(ROOT, "src", "i18n", "locales")

if not os.path.isdir(SRC):
    print(f"ERROR: i18n locales directory not found: {SRC}", file=sys.stderr)
    sys.exit(1)
KNOWN_MODULES = {
    "common", "dashboard", "generate", "records", "lab", "compose",
    "misra", "hitl", "anchor", "architecture", "compliance", "settings", "data",
}

# ---------------------------------------------------------------------------
# 1. Build merged flattened key sets per locale (mirror app merge semantics)
# ---------------------------------------------------------------------------
def flatten(prefix, obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(f"{prefix}.{k}" if prefix else k, v, out)
    else:
        out.add(prefix)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_locale(locale):
    locale_dir = os.path.join(SRC, locale)
    merged = {}
    # common.json is the root for the locale
    common_path = os.path.join(locale_dir, "common.json")
    if os.path.exists(common_path):
        merged.update(load_json(common_path))
    # every other module file is shallow-merged at the top level
    for fn in sorted(os.listdir(locale_dir)):
        if not fn.endswith(".json") or fn == "common.json":
            continue
        mod = load_json(os.path.join(locale_dir, fn))
        if isinstance(mod, dict):
            merged.update(mod)
    keys = set()
    flatten("", merged, keys)
    return keys, merged

zh_keys, zh_tree = build_locale("zh-CN")
en_keys, en_tree = build_locale("en")

# ---------------------------------------------------------------------------
# 2. Extract static i18n key references from source
# ---------------------------------------------------------------------------
# Patterns capturing the literal 1st argument of i18n calls.
patterns = [
    re.compile(r"\$(?:t|tc|te)\(\s*['\"`]([^'\"`]+)['\"`]"),          # $t('...') in templates
    re.compile(r"\bdataT\(\s*['\"`]([^'\"`]+)['\"`]"),               # dataT('...')
    re.compile(r"i18n\.global\.t\(\s*['\"`]([^'\"`]+)['\"`]"),       # i18n.global.t('...')
    re.compile(r"(?<![A-Za-z0-9_$.])t\(\s*['\"`]([^'\"`]+)['\"`]"),  # standalone t('...')
]

ref_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
refs = defaultdict(set)  # key -> set of "file:line"

exts = (".ts", ".vue")
for dirpath, _, files in os.walk(os.path.join(ROOT, "src")):
    for fn in files:
        if not fn.endswith(exts):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            continue
        rel = os.path.relpath(fp, ROOT)
        for i, line in enumerate(lines, 1):
            for pat in patterns:
                for m in pat.finditer(line):
                    key = m.group(1)
                    # drop keys containing interpolation / non-literal parts
                    if "$" in key or "{" in key or "+" in key:
                        continue
                    if not ref_re.match(key):
                        continue
                    refs[key].add(f"{rel}:{i}")

# ---------------------------------------------------------------------------
# 3. Reports
# ---------------------------------------------------------------------------
ref_keys = set(refs.keys())

missing_zh = sorted(k for k in ref_keys if k not in zh_keys)
missing_en = sorted(k for k in ref_keys if k not in en_keys)

# Only treat as "likely real" the ones whose first segment is a known module
# or section; everything else is shown separately as "uncertain".
def first_seg(k):
    return k.split(".", 1)[0]

likely_zh = [k for k in missing_zh if first_seg(k) in KNOWN_MODULES | zh_tree.keys()]
uncertain_zh = [k for k in missing_zh if k not in likely_zh]

# Parity (defined keys)
parity_zh_only = sorted(k for k in zh_keys if k not in en_keys)
parity_en_only = sorted(k for k in en_keys if k not in zh_keys)

print("=" * 70)
print("i18n COVERAGE REPORT  (SkyForge frontend)")
print("=" * 70)
print(f"\nLocale key counts:  zh-CN={len(zh_keys)}   en={len(en_keys)}")
print(f"Distinct referenced keys in source: {len(ref_keys)}")

print("\n--- [A] Referenced keys MISSING in zh-CN ({}) ---".format(len(missing_zh)))
for k in likely_zh:
    print(f"  [zh] {k}")
    for loc in sorted(refs[k])[:6]:
        print(f"        {loc}")
if uncertain_zh:
    print("  (uncertain first-segment, possibly non-i18n t() calls):")
    for k in uncertain_zh:
        print(f"  [?] {k}  <- {sorted(refs[k])[:3]}")

print("\n--- [B] Referenced keys MISSING in en ({}) ---".format(len(missing_en)))
for k in missing_en:
    tag = "" if k in missing_zh else "  (present in zh-CN)"
    print(f"  [en] {k}{tag}")

print("\n--- [C] zh-CN keys NOT present in en (en coverage gap, {} ) ---".format(len(parity_zh_only)))
# Only report if the key looks like a real translation key (skip pure structural noise)
for k in parity_zh_only:
    print(f"  {k}")

print("\n--- [D] en keys NOT present in zh-CN (unexpected, {} ) ---".format(len(parity_en_only)))
for k in parity_en_only:
    print(f"  {k}")

# ---------------------------------------------------------------------------
# 4. Candidate fixes: referenced key whose zh-CN twin uses a different prefix
#    e.g. code uses 'common.backend.mock' but tree has 'backend.mock'
# ---------------------------------------------------------------------------
print("\n--- [E] Possible mis-prefixed references (tree has a shorter/longer form) ---")
seen = set()
for k in missing_zh:
    parts = k.split(".")
    # try dropping the first segment
    if len(parts) > 1:
        alt = ".".join(parts[1:])
        if alt in zh_keys and alt not in seen:
            seen.add(alt)
            print(f"  ref '{k}'  ~ maybe should be '{alt}'")
    # try prefixing with 'common'
    cand = "common." + k
    if cand in zh_keys:
        print(f"  ref '{k}'  ~ maybe should be '{cand}'")

print("\nDONE.")
