#!/usr/bin/env python3
"""Verify report immutability invariants.

CLAUDE.md rule 4: Reports are immutable. Once `generated_at` is set, it is
NEVER updated. A report is a point-in-time snapshot. `source_snapshot` captures
credibility scores at generation time.

This script checks:
1. Report.generated_at is Optional initially (not set at creation)
2. Report has a source_snapshot field for credibility capture
3. No route in the API codebase updates generated_at after initial write
4. Alembic migration does NOT allow nullable generated_at to be set again

Usage:
    python scripts/verify_reports_immutable.py
    uv run --package anveshak-sdk python scripts/verify_reports_immutable.py
"""
import ast
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent


def check_report_model() -> list[str]:
    """Check Report Pydantic model has correct immutability structure."""
    violations = []
    model_file = ROOT / "sdk/anveshak-sdk/src/anveshak/models/report.py"

    if not model_file.exists():
        violations.append(f"MISSING: {model_file} does not exist")
        return violations

    source = model_file.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "Report"):
            continue

        fields = {}
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields[item.target.id] = item

        # generated_at must exist
        if "generated_at" not in fields:
            violations.append("Report model is missing `generated_at` field")
        else:
            # Must be Optional (None initially)
            annotation = fields["generated_at"].annotation
            annotation_str = ast.unparse(annotation)
            if "Optional" not in annotation_str and "None" not in annotation_str:
                violations.append(
                    f"Report.generated_at must be Optional — got: {annotation_str}"
                )

        # source_snapshot must exist
        if "source_snapshot" not in fields:
            violations.append("Report model is missing `source_snapshot` field")

    if not any(
        isinstance(n, ast.ClassDef) and n.name == "Report" for n in ast.walk(tree)
    ):
        violations.append(f"No Report class found in {model_file}")

    return violations


def check_no_generated_at_update() -> list[str]:
    """Scan API routes for any UPDATE query touching generated_at."""
    violations = []
    routes_dir = ROOT / "services/api/src/anveshak/api/routes"

    if not routes_dir.exists():
        return violations

    for py_file in routes_dir.rglob("*.py"):
        source = py_file.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines, 1):
            if "generated_at" in line and (
                "UPDATE" in line.upper()
                or "SET" in line.upper()
                or "execute" in line
            ):
                # Allow INSERT (first-time write) but not UPDATE
                if "INSERT" not in line.upper() and "SELECT" not in line.upper():
                    violations.append(
                        f"Potential generated_at mutation in {py_file.name}:{i}\n"
                        f"  {line.strip()}"
                    )

    return violations


def check_migration_generated_at() -> list[str]:
    """Check migration creates generated_at as nullable (never forced)."""
    violations = []
    migrations_dir = ROOT / "services/api/migrations/versions"

    if not migrations_dir.exists():
        return violations

    for py_file in migrations_dir.glob("*.py"):
        source = py_file.read_text()
        # Check that any generated_at column is nullable
        lines = source.splitlines()
        for i, line in enumerate(lines, 1):
            if "generated_at" in line and "Column" in line:
                if "nullable=False" in line:
                    violations.append(
                        f"Migration {py_file.name}:{i} sets generated_at nullable=False — "
                        f"must be nullable (set once by ARQ job, not on INSERT)"
                    )

    return violations


def check_report_source_warnings_table() -> list[str]:
    """Verify report_source_warnings table exists in migration for retroactive flagging."""
    violations = []
    migrations_dir = ROOT / "services/api/migrations/versions"

    if not migrations_dir.exists():
        return violations

    found = False
    for py_file in sorted(migrations_dir.glob("*.py")):
        if "report_source_warnings" in py_file.read_text():
            found = True
            break

    if not found:
        violations.append(
            "Migration missing report_source_warnings table — "
            "needed for retroactive flagging when source credibility degrades after report generation"
        )

    return violations


def main() -> int:
    print("Verifying report immutability invariants...\n")
    all_violations = []

    checks = [
        ("Report model structure", check_report_model),
        ("No generated_at mutation in routes", check_no_generated_at_update),
        ("Migration generated_at is nullable", check_migration_generated_at),
        ("report_source_warnings table exists", check_report_source_warnings_table),
    ]

    for label, fn in checks:
        violations = fn()
        status = "FAIL" if violations else "OK"
        print(f"  [{status}] {label}")
        for v in violations:
            print(f"         {v}")
        all_violations.extend(violations)

    print()
    if all_violations:
        print(f"FAILED — {len(all_violations)} violation(s) found.")
        print(
            "Fix: Report immutability is a CLAUDE.md rule. "
            "generated_at is set ONCE by the ARQ report-generation job. "
            "It must never be updated. Use report_source_warnings for retroactive flags."
        )
        return 1

    print("PASSED — report immutability invariants are intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
