"""CSV Summary Skill - Analyze CSV files and create reports.

Requires filesystem.read and workspace.read permissions.
Restricts file access to workspace and skill directories only.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any


def execute(ctx: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute the CSV summary skill.

    Args:
        ctx: SkillContext with permissions and workspace info.
        inputs: User-provided inputs (e.g., {"csv_path": "data.csv"}).

    Returns:
        Summary report with row count, column count, columns, missing values.
    """
    csv_path = inputs.get("csv_path", "")
    if not csv_path:
        return {
            "status": "failed",
            "result": {},
            "actions": [],
            "warnings": ["No csv_path provided. Usage: {\"csv_path\": \"path/to/file.csv\"}"],
            "approval_required": False,
        }

    # Check permissions
    if not ctx.has_permission("filesystem.read"):
        return {
            "status": "blocked",
            "result": {},
            "actions": [],
            "warnings": ["filesystem.read permission required but not approved."],
            "approval_required": True,
        }

    # Resolve path with restriction
    try:
        resolved = ctx.resolve_path(csv_path)
    except PermissionError as exc:
        return {
            "status": "blocked",
            "result": {},
            "actions": [],
            "warnings": [str(exc)],
            "approval_required": False,
        }

    path = Path(resolved)
    if not path.exists():
        return {
            "status": "failed",
            "result": {},
            "actions": [],
            "warnings": [f"File not found: {resolved}"],
            "approval_required": False,
        }

    # Read and analyze CSV
    try:
        content = path.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        columns = reader.fieldnames or []
        row_count = len(rows)
        column_count = len(columns)

        # Missing value analysis
        missing = {}
        for col in columns:
            missing_count = sum(1 for row in rows if not row.get(col, "").strip())
            missing[col] = missing_count

        return {
            "status": "completed",
            "result": {
                "file": str(path),
                "row_count": row_count,
                "column_count": column_count,
                "columns": columns,
                "missing_values": missing,
                "total_missing": sum(missing.values()),
            },
            "actions": [],
            "warnings": [],
            "approval_required": False,
        }

    except Exception as exc:
        return {
            "status": "failed",
            "result": {},
            "actions": [],
            "warnings": [f"Error reading CSV: {exc}"],
            "approval_required": False,
        }


def run(ctx: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Alias for execute()."""
    return execute(ctx, inputs)
