"""CSV export helpers for allocation plans and benchmark results.

Exports:
    * ``write_allocation_csv``: writes ``allocation.csv`` (README section 4.5).
    * ``write_benchmark_csv``: writes ``benchmark_results.csv``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.models.allocation import Allocation
from src.models.student import Student


def write_allocation_csv(
    allocation: Allocation,
    students: list[Student],
    path: str | Path,
) -> None:
    """Write student seat assignments to CSV (sap_id,hall_id,row,col,color).

    Rows are sorted by (hall_id, row, col).

    Args:
        allocation: The final allocation mapping.
        students: The list of students.
        path: Output file path.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[str, str, int, int, int]] = []
    for s in students:
        if s.sap_id in allocation.seats:
            hall_id, r, c = allocation.seats[s.sap_id]
            color = allocation.colors.get(s.sap_id, 0)
            rows.append((s.sap_id, hall_id, r, c, color))

    rows.sort(key=lambda item: (item[1], item[2], item[3]))

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sap_id", "hall_id", "row", "col", "color"])
        for row in rows:
            writer.writerow(row)


def write_benchmark_csv(
    path: str | Path | list[dict],
    rows: list[dict] | str | Path | None = None,
) -> None:
    """Write benchmark result rows to CSV.

    Accepts either (path, rows) or (rows, path) for compatibility.
    """
    if isinstance(path, list) and (isinstance(rows, (str, Path)) or rows is None):
        path, rows = rows, path
    out_path = Path(str(path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    row_list: list[dict] = rows if isinstance(rows, list) else []

    if not row_list:
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "algorithm", "n_students", "n_edges", "colors_used",
                "runtime_ms", "nodes_explored", "completed",
                "hall_utilisation", "soft_score", "valid"
            ])
        return

    fieldnames = list(row_list[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in row_list:
            writer.writerow(row)

