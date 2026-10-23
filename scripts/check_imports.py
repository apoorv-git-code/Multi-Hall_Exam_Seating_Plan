#!/usr/bin/env python3
"""Enforce dependency boundaries using Python's AST (no third-party packages).

Current rule: reporting code must not import graph or algorithm implementation
modules. The checker handles both the src/ package layout and legacy root-level
reporting files. Exit 0 means no violations; exit 1 means violations were found.
"""
from __future__ import annotations
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTING_DIRS = (ROOT / "src" / "reporting", ROOT / "reporting")
REPORTING_FILES = (
    ROOT / "report_builder.py", ROOT / "csv_export.py",
    ROOT / "html_export.py", ROOT / "text_chart.py",
)
FORBIDDEN_PREFIXES = ("src.graph", "src.algorithms", "graph", "algorithms")


def module_name(path: Path) -> str:
    try:
        rel = path.relative_to(ROOT).with_suffix("")
    except ValueError:
        return path.stem
    return ".".join(rel.parts)


def is_reporting(path: Path) -> bool:
    return any(path == d or d in path.parents for d in REPORTING_DIRS) or path in REPORTING_FILES


def imported_modules(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            yield base, node.lineno
            for alias in node.names:
                if alias.name in {"graph", "algorithms"}:
                    yield f"{base}.{alias.name}".strip("."), node.lineno


def main() -> int:
    violations = []
    files = []
    for directory in REPORTING_DIRS:
        if directory.exists():
            files.extend(p for p in directory.rglob("*.py") if "__pycache__" not in p.parts)
    files.extend(p for p in REPORTING_FILES if p.exists())
    for path in sorted(set(files)):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            print(f"ERROR: cannot parse {path.relative_to(ROOT)}: {exc}", file=sys.stderr)
            return 2
        for imported, line in imported_modules(tree):
            if any(imported == prefix or imported.startswith(prefix + ".")
                   for prefix in FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(ROOT)}:{line}: forbidden import {imported!r}")
    if violations:
        print("Architectural boundary violations:")
        print("\n".join(f"  {v}" for v in violations))
        return 1
    print(f"Import boundary check passed ({len(set(files))} reporting file(s) scanned).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
