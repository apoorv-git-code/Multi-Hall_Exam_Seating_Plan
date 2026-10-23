"""Plain-text charts: seating grids, aligned tables, horizontal bar charts.

Every function returns a string. Nothing here prints or writes files, so the
CLI decides where the text goes.

Coordinates follow the project convention: ``(row, col)`` with ``(0, 0)`` at the
front-left, so row 0 is printed directly under the FRONT marker.
"""

from __future__ import annotations

from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student

#: Valid values for the ``label`` argument of ``render_hall_chart``.
LABEL_MODES: tuple[str, ...] = ("id", "roll", "branch", "color")


def _seat_label(mode: str, student: Student, color: int | None, width: int) -> str:
    """Return the short text shown for one seated student."""
    if mode == "id":
        return student.sap_id[-width:]
    if mode == "roll":
        return str(student.roll_no)
    if mode == "branch":
        return student.branch[:width]
    return "?" if color is None else str(color)


def render_hall_chart(
    hall: Hall,
    allocation: Allocation,
    students: list[Student],
    label: str = "id",
    width: int = 4,
) -> str:
    """Draw one hall as a text grid.

    Args:
        hall: The hall to draw.
        allocation: The seating plan.
        students: All students (to look up labels).
        label: What each seat shows: ``"id"`` (last ``width`` characters of the
            SAP ID), ``"roll"``, ``"branch"`` (first ``width`` characters) or
            ``"color"`` (Phase 1 color class).
        width: Maximum characters for ``"id"`` and ``"branch"`` labels.

    Returns:
        A multi-line string. Empty usable seats show ``-``, blocked seats ``#``.

    Raises:
        ValueError: If ``label`` is not in ``LABEL_MODES`` or ``width < 1``.

    Time: O(rows * cols + seated). Space: O(rows * cols).
    """
    if label not in LABEL_MODES:
        raise ValueError(f"label must be one of {list(LABEL_MODES)}, got {label!r}")
    if width < 1:
        raise ValueError("width must be >= 1")

    by_id = {student.sap_id: student for student in students}
    seat_text: dict[tuple[int, int], str] = {}
    for sap_id, (hall_id, row, col) in allocation.seats.items():
        if hall_id != hall.hall_id or sap_id not in by_id:
            continue
        seat_text[(row, col)] = _seat_label(
            label, by_id[sap_id], allocation.colors.get(sap_id), width
        )

    cell = 2
    for text in seat_text.values():
        if len(text) > cell:
            cell = len(text)
    row_label_width = len(str(hall.rows - 1)) + 1  # "r" plus digits

    lines: list[str] = []
    lines.append(
        f"Hall {hall.hall_id}: {hall.rows} rows x {hall.cols} columns, "
        f"capacity {hall.capacity()}, seated {len(seat_text)}"
    )
    grid_width = hall.cols * (cell + 1) - 1
    lines.append((" " * (row_label_width + 1) + "FRONT".center(grid_width)).rstrip())
    header = " " * (row_label_width + 1)
    header += " ".join(("c" + str(c)).rjust(cell) for c in range(hall.cols))
    lines.append(header)
    for r in range(hall.rows):
        parts: list[str] = []
        for c in range(hall.cols):
            if (r, c) in hall.blocked:
                parts.append("#" * cell)
            elif (r, c) in seat_text:
                parts.append(seat_text[(r, c)].rjust(cell))
            else:
                parts.append("-" * cell)
        lines.append(("r" + str(r)).rjust(row_label_width) + " " + " ".join(parts))
    return "\n".join(lines)


def render_all_halls(
    halls: list[Hall],
    allocation: Allocation,
    students: list[Student],
    label: str = "id",
    width: int = 4,
    include_empty_halls: bool = False,
) -> str:
    """Draw every hall that holds students (or every hall if requested).

    Returns the charts separated by a blank line, followed by a legend line. If
    nothing is seated and ``include_empty_halls`` is False, returns
    ``"(no students seated)"``.

    Time: O(total cells + seated). Space: O(total cells).
    """
    occupied: set[str] = set()
    for hall_id, _row, _col in allocation.seats.values():
        occupied.add(hall_id)
    charts: list[str] = []
    for hall in halls:
        if include_empty_halls or hall.hall_id in occupied:
            charts.append(render_hall_chart(hall, allocation, students, label, width))
    if not charts:
        return "(no students seated)"
    legend = "Legend: '-' empty seat, '#' blocked seat"
    if label == "id":
        legend += f", labels are the last {width} characters of the SAP ID"
    elif label == "roll":
        legend += ", labels are roll numbers"
    elif label == "branch":
        legend += ", labels are branch codes"
    else:
        legend += ", labels are Phase 1 color classes"
    return "\n\n".join(charts) + "\n\n" + legend


def _format_cell(value: object, float_digits: int) -> str:
    """Format one table value: None -> '-', bool -> yes/no, float -> fixed digits."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{float_digits}f}"
    return str(value)


def render_table(
    rows: list[dict],
    columns: list[str],
    float_digits: int = 2,
) -> str:
    """Render ``rows`` as an aligned text table with the given columns.

    Numbers are right-aligned, everything else left-aligned. Missing keys and
    ``None`` show ``-``; booleans show ``yes``/``no``.

    Time: O(rows * columns). Space: O(rows * columns).
    """
    if len(columns) == 0:
        raise ValueError("columns must not be empty")
    body: list[list[str]] = []
    numeric: list[bool] = [True] * len(columns)
    for row in rows:
        cells: list[str] = []
        for index, name in enumerate(columns):
            value = row.get(name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                numeric[index] = False
            cells.append(_format_cell(value, float_digits))
        body.append(cells)
    widths = [len(name) for name in columns]
    for cells in body:
        for index, text in enumerate(cells):
            if len(text) > widths[index]:
                widths[index] = len(text)

    def line(cells: list[str]) -> str:
        parts: list[str] = []
        for index, text in enumerate(cells):
            if numeric[index]:
                parts.append(text.rjust(widths[index]))
            else:
                parts.append(text.ljust(widths[index]))
        return "  ".join(parts).rstrip()

    out = [line(list(columns)), "  ".join("-" * w for w in widths)]
    for cells in body:
        out.append(line(cells))
    return "\n".join(out)


def render_bar_chart(
    items: list[tuple[str, float]],
    width: int = 40,
    title: str | None = None,
    value_digits: int = 2,
) -> str:
    """Draw a horizontal bar chart: one ``#`` bar per ``(label, value)`` pair.

    Bars are scaled to the largest value. A positive value always gets at least
    one ``#``. Negative values are not supported.

    Raises:
        ValueError: If ``width < 1`` or any value is negative.

    Time: O(n). Space: O(n).
    """
    if width < 1:
        raise ValueError("width must be >= 1")
    for _label, value in items:
        if value < 0:
            raise ValueError("bar values must be >= 0")
    lines: list[str] = []
    if title:
        lines.append(title)
    if len(items) == 0:
        lines.append("(no data)")
        return "\n".join(lines)
    label_width = 0
    peak = 0.0
    for label, value in items:
        if len(label) > label_width:
            label_width = len(label)
        if value > peak:
            peak = value
    for label, value in items:
        length = 0
        if peak > 0:
            length = int(value / peak * width + 0.5)
            if value > 0 and length == 0:
                length = 1
        shown = str(int(value)) if value == int(value) else f"{value:.{value_digits}f}"
        lines.append(f"{label.ljust(label_width)} | {'#' * length} {shown}")
    return "\n".join(lines)
