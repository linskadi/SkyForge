"""Generate repository metrics from source instead of hand-maintained claims."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def count(pattern: str, paths: list[Path]) -> int:
    regex = re.compile(pattern)
    return sum(len(regex.findall(path.read_text(encoding="utf-8", errors="ignore"))) for path in paths)


def collect() -> dict[str, int]:
    backend_tests = list((ROOT / "studio/app/tests").glob("test_*.py"))
    frontend_tests = list((ROOT / "studio/frontend/src").rglob("*.test.ts"))
    routes = list((ROOT / "studio/app/api/routes").glob("*.py"))
    return {
        "backend_test_definitions": count(r"\bdef test_", backend_tests),
        "frontend_test_definitions": count(r"\b(?:it|test)\s*\(", frontend_tests),
        "http_route_decorators": count(r"@router\.(?:get|post|put|patch|delete)\(", routes),
        "websocket_route_decorators": count(r"@router\.websocket\(", routes),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(collect(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
