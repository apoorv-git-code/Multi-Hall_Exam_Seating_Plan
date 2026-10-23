"""Printable HTML seating charts.

One self-contained page: one section per hall with a seating grid and a seat
list, page breaks between halls when printed. Every piece of student or hall
text is escaped with ``html.escape`` (the only use of the ``html`` module).

Coordinates are written exactly as in ``allocation.csv``: row 0 is the front,
column 0 is the left.
"""

from __future__ import annotations

import html
from pathlib import Path

from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student
from src.structures.sorting import merge_sort

_STYLE = """
:root { color-scheme: light; }
body { font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #111; background: #fff; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 0 0 4px; }
h3 { font-size: 14px; margin: 16px 0 6px; }
p.meta { margin: 0 0 12px; color: #444; font-size: 13px; }
.front { text-align: center; font-weight: bold; letter-spacing: 4px; border-bottom: 3px solid #111;
         margin: 8px 0 6px; padding-bottom: 2px; font-size: 12px; }
table { border-collapse: collapse; }
table.grid td, table.grid th { border: 1px solid #555; text-align: center; vertical-align: middle; }
table.grid th { background: #eee; font-size: 11px; padding: 2px 6px; }
table.grid td { width: 92px; height: 54px; padding: 2px; font-size: 10px; }
td.empty { background: #fafafa; color: #aaa; }
td.blocked { background: repeating-linear-gradient(45deg, #ccc, #ccc 4px, #eee 4px, #eee 8px); color: #666; }
td.seat .sid { display: block; font-weight: bold; font-size: 11px; }
td.seat .nm { display: block; }
td.seat .br { display: block; color: #444; }
table.list { font-size: 12px; margin-top: 4px; }
table.list th, table.list td { border: 1px solid #999; padding: 2px 8px; text-align: left; }
table.list th { background: #eee; }
.hall { margin-bottom: 32px; }
@page { size: A4 landscape; margin: 12mm; }
@media print { .hall { page-break-after: always; } .hall:last-of-type { page-break-after: auto; } }
""".strip()


def _esc(text: object) -> str:
    """Escape any value for safe use in HTML text or attributes."""
    return html.escape(str(text), quote=True)


def render_seating_html(
    halls: list[Hall],
    allocation: Allocation,
    students: list[Student],
    title: str = "Exam Seating Chart",
    include_empty_halls: bool = False,
) -> str:
    """Return a complete HTML document with one section per hall.

    Args:
        halls: Halls to draw (in order).
        allocation: The seating plan.
        students: All students (names, branches, roll numbers).
        title: Page title and heading.
        include_empty_halls: Draw halls that hold no student too.

    Returns:
        The HTML text.

    Time: O(total cells + seated log seated). Space: O(total cells + seated).
    """
    by_id = {student.sap_id: student for student in students}
    per_hall: dict[str, dict[tuple[int, int], Student]] = {}
    for sap_id, (hall_id, row, col) in allocation.seats.items():
        if sap_id in by_id:
            per_hall.setdefault(hall_id, {})[(row, col)] = by_id[sap_id]

    shown = [h for h in halls if include_empty_halls or h.hall_id in per_hall]
    seated_total = 0
    for hall in shown:
        seated_total += len(per_hall.get(hall.hall_id, {}))

    out: list[str] = []
    out.append("<!DOCTYPE html>")
    out.append('<html lang="en"><head><meta charset="utf-8">')
    out.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    out.append(f"<title>{_esc(title)}</title>")
    out.append(f"<style>\n{_STYLE}\n</style></head><body>")
    out.append(f"<h1>{_esc(title)}</h1>")
    out.append(
        f'<p class="meta">{seated_total} students seated in {len(shown)} '
        f"hall{'s' if len(shown) != 1 else ''}. Row 0 is the front; column 0 is the left.</p>"
    )
    if len(shown) == 0:
        out.append("<p>No students are seated.</p>")

    for hall in shown:
        seats = per_hall.get(hall.hall_id, {})
        out.append('<section class="hall">')
        out.append(f"<h2>Hall {_esc(hall.hall_id)}</h2>")
        out.append(
            f'<p class="meta">{hall.rows} rows &times; {hall.cols} columns, '
            f"capacity {hall.capacity()}, seated {len(seats)}</p>"
        )
        out.append('<div class="front">FRONT</div>')
        out.append('<table class="grid"><tr><th></th>')
        for c in range(hall.cols):
            out.append(f"<th>C{c}</th>")
        out.append("</tr>")
        for r in range(hall.rows):
            out.append(f"<tr><th>R{r}</th>")
            for c in range(hall.cols):
                if (r, c) in hall.blocked:
                    out.append('<td class="blocked">blocked</td>')
                elif (r, c) in seats:
                    s = seats[(r, c)]
                    out.append(
                        '<td class="seat">'
                        f'<span class="sid">{_esc(s.sap_id)}</span>'
                        f'<span class="nm">{_esc(s.name)}</span>'
                        f'<span class="br">{_esc(s.branch)} &middot; {_esc(s.roll_no)}</span>'
                        "</td>"
                    )
                else:
                    out.append('<td class="empty">empty</td>')
            out.append("</tr>")
        out.append("</table>")

        out.append("<h3>Seat list</h3>")
        out.append(
            '<table class="list"><tr><th>Row</th><th>Col</th><th>SAP ID</th>'
            "<th>Name</th><th>Branch</th><th>Roll</th></tr>"
        )
        for (r, c) in merge_sort(list(seats.keys())):
            s = seats[(r, c)]
            out.append(
                f"<tr><td>{r}</td><td>{c}</td><td>{_esc(s.sap_id)}</td>"
                f"<td>{_esc(s.name)}</td><td>{_esc(s.branch)}</td><td>{_esc(s.roll_no)}</td></tr>"
            )
        out.append("</table></section>")

    out.append("</body></html>")
    return "\n".join(out) + "\n"


def write_seating_html(
    path: str,
    halls: list[Hall],
    allocation: Allocation,
    students: list[Student],
    title: str = "Exam Seating Chart",
    include_empty_halls: bool = False,
) -> None:
    """Write ``render_seating_html`` output to ``path`` (parent folders are created).

    Time: as ``render_seating_html``. Space: O(output size).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_seating_html(halls, allocation, students, title, include_empty_halls),
        encoding="utf-8",
    )
