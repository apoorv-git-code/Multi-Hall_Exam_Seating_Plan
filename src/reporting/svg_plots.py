"""Hand-written SVG charts (no plotting library).

Two generic charts (``line_chart_svg``, ``bar_chart_svg``) and a helper that
turns benchmark rows into the project's standard plots (``benchmark_plots``).

Design notes:
    * Series are told apart by color **and** marker shape / dash style, so
      printed black-and-white copies stay readable.
    * All text is escaped with ``html.escape``.
    * This module does not import ``math``. Tick spacing and the base-10
      logarithm for log axes are computed with plain loops.
    * Output is a standalone SVG document with a white background.
"""

from __future__ import annotations

import html
from pathlib import Path

from src.analysis.metrics import mean
from src.structures.sorting import merge_sort

PALETTE: tuple[str, ...] = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e")
_DASHES: tuple[str, ...] = ("", "7 4", "2 3", "10 3 2 3", "4 4")
_MARKERS: tuple[str, ...] = ("circle", "square", "triangle", "diamond", "cross")

#: Smallest runtime plotted on the log axis of ``benchmark_plots`` (milliseconds).
RUNTIME_FLOOR_MS = 0.001

_W = 720
_H = 420
_ML = 74
_MR = 160
_MT = 50
_MB = 64


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _fmt(value: float) -> str:
    """Short tick label: integers without decimals, others with up to 3 significant digits."""
    if value == int(value) and abs(value) < 1e9:
        return str(int(value))
    return f"{value:.3g}"


def _log10(x: float) -> float:
    """Base-10 logarithm using loops and bisection (x must be > 0)."""
    exponent = 0
    while x >= 10.0:
        x /= 10.0
        exponent += 1
    while x < 1.0:
        x *= 10.0
        exponent -= 1
    low, high = 0.0, 1.0   # find t in [0, 1] with 10 ** t == x
    for _ in range(50):
        mid = (low + high) / 2.0
        if 10.0 ** mid < x:
            low = mid
        else:
            high = mid
    return exponent + (low + high) / 2.0


def _nice_ticks(high: float, target: int = 5) -> list[float]:
    """Return evenly spaced ticks from 0 up to a nice value >= ``high``."""
    if high <= 0:
        return [0.0, 1.0]
    raw = high / target
    base = 1.0
    while raw >= 10.0 * base:
        base *= 10.0
    while raw < base:
        base /= 10.0
    step = base
    for factor in (1.0, 2.0, 5.0, 10.0):
        step = factor * base
        if step >= raw:
            break
    ticks = [0.0]
    while ticks[-1] < high - 1e-12 * high:
        ticks.append(ticks[-1] + step)
    return ticks


def _log_ticks(low: float, high: float) -> list[float]:
    """Return powers of ten covering ``[low, high]`` (at least two ticks)."""
    value = 1.0
    while value > low:
        value /= 10.0
    while value * 10.0 <= low:
        value *= 10.0
    ticks = [value]
    while ticks[-1] < high:
        ticks.append(ticks[-1] * 10.0)
    if len(ticks) < 2:
        ticks.append(ticks[-1] * 10.0)
    return ticks


def _marker(kind: str, x: float, y: float, color: str) -> str:
    r = 4.5
    if kind == "circle":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>'
    if kind == "square":
        return f'<rect x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r}" height="{2 * r}" fill="{color}"/>'
    if kind == "triangle":
        return (f'<polygon points="{x:.1f},{y - r - 1:.1f} {x - r - 1:.1f},{y + r:.1f} '
                f'{x + r + 1:.1f},{y + r:.1f}" fill="{color}"/>')
    if kind == "diamond":
        return (f'<polygon points="{x:.1f},{y - r - 1:.1f} {x + r + 1:.1f},{y:.1f} '
                f'{x:.1f},{y + r + 1:.1f} {x - r - 1:.1f},{y:.1f}" fill="{color}"/>')
    return (f'<path d="M{x - r:.1f},{y - r:.1f} L{x + r:.1f},{y + r:.1f} '
            f'M{x - r:.1f},{y + r:.1f} L{x + r:.1f},{y - r:.1f}" stroke="{color}" stroke-width="2"/>')


def _frame(title: str, x_label: str, y_label: str) -> list[str]:
    """Return the opening tags, title and axis labels."""
    px0, px1 = _ML, _W - _MR
    py0, py1 = _MT, _H - _MB
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{_H}" '
        f'viewBox="0 0 {_W} {_H}" font-family="Arial, Helvetica, sans-serif" font-size="12">',
        f'<rect width="{_W}" height="{_H}" fill="#ffffff"/>',
        f'<text x="{_W / 2:.0f}" y="26" text-anchor="middle" font-size="16" font-weight="bold" '
        f'fill="#111">{_esc(title)}</text>',
        f'<text x="{(px0 + px1) / 2:.0f}" y="{_H - 14}" text-anchor="middle" fill="#111">{_esc(x_label)}</text>',
        f'<text x="18" y="{(py0 + py1) / 2:.0f}" text-anchor="middle" fill="#111" '
        f'transform="rotate(-90 18 {(py0 + py1) / 2:.0f})">{_esc(y_label)}</text>',
    ]


def _legend(names: list[str], kinds: str) -> list[str]:
    """Legend on the right: ``kinds`` is 'line' (dash + marker) or 'bar' (swatch)."""
    out: list[str] = []
    x = _W - _MR + 18
    for i, name in enumerate(names):
        y = _MT + 12 + i * 22
        color = PALETTE[i % len(PALETTE)]
        if kinds == "line":
            dash = _DASHES[i % len(_DASHES)]
            dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
            out.append(f'<line x1="{x}" y1="{y}" x2="{x + 26}" y2="{y}" stroke="{color}" stroke-width="2"{dash_attr}/>')
            out.append(_marker(_MARKERS[i % len(_MARKERS)], x + 13, y, color))
        else:
            out.append(f'<rect x="{x}" y="{y - 7}" width="26" height="14" fill="{color}"/>')
        out.append(f'<text x="{x + 34}" y="{y + 4}" fill="#111">{_esc(name)}</text>')
    return out


def line_chart_svg(
    series: dict[str, list[tuple[float, float]]],
    title: str,
    x_label: str,
    y_label: str,
    log_y: bool = False,
) -> str:
    """Draw a multi-series line chart with markers.

    Args:
        series: ``name -> [(x, y), ...]``. Points are drawn in ascending x order.
            The x axis is linear with a tick at every distinct x value.
        title: Chart title.
        x_label: Label under the x axis.
        y_label: Label beside the y axis.
        log_y: Use a base-10 logarithmic y axis (all y must be > 0). Otherwise
            the y axis is linear and starts at 0 (all y must be >= 0).

    Raises:
        ValueError: If there are no points, a y value is out of range for the
            chosen axis, or a series name list is empty.

    Time: O(P log P) for P points. Space: O(P).
    """
    names = list(series.keys())
    ordered: dict[str, list[tuple[float, float]]] = {}
    xs: list[float] = []
    ys: list[float] = []
    for name in names:
        pts = merge_sort(series[name], key=lambda p: p[0])
        ordered[name] = pts
        for x, y in pts:
            if log_y and y <= 0:
                raise ValueError("log_y requires every y value to be > 0")
            if y < 0:
                raise ValueError("y values must be >= 0")
            if x not in xs:
                xs.append(x)
            ys.append(y)
    if len(ys) == 0:
        raise ValueError("line chart needs at least one point")
    xs = merge_sort(xs)

    px0, px1 = _ML, _W - _MR
    py0, py1 = _MT, _H - _MB
    x_lo, x_hi = xs[0], xs[-1]

    def sx(x: float) -> float:
        if x_hi == x_lo:
            return (px0 + px1) / 2.0
        return px0 + 24 + (x - x_lo) / (x_hi - x_lo) * (px1 - px0 - 48)

    y_max = ys[0]
    y_min = ys[0]
    for y in ys:
        if y > y_max:
            y_max = y
        if y < y_min:
            y_min = y
    if log_y:
        ticks = _log_ticks(y_min, y_max)
        lg_lo, lg_hi = _log10(ticks[0]), _log10(ticks[-1])

        def sy(y: float) -> float:
            return py1 - (_log10(y) - lg_lo) / (lg_hi - lg_lo) * (py1 - py0)
    else:
        ticks = _nice_ticks(y_max)
        top = ticks[-1]

        def sy(y: float) -> float:
            return py1 - y / top * (py1 - py0)

    out = _frame(title, x_label, y_label)
    for t in ticks:
        y = sy(t)
        out.append(f'<line x1="{px0}" y1="{y:.1f}" x2="{px1}" y2="{y:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{px0 - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#333">{_esc(_fmt(t))}</text>')
    for x in xs:
        out.append(f'<line x1="{sx(x):.1f}" y1="{py1}" x2="{sx(x):.1f}" y2="{py1 + 5}" stroke="#333"/>')
        out.append(f'<text x="{sx(x):.1f}" y="{py1 + 20}" text-anchor="middle" fill="#333">{_esc(_fmt(x))}</text>')
    out.append(f'<line x1="{px0}" y1="{py0}" x2="{px0}" y2="{py1}" stroke="#333"/>')
    out.append(f'<line x1="{px0}" y1="{py1}" x2="{px1}" y2="{py1}" stroke="#333"/>')

    for i, name in enumerate(names):
        color = PALETTE[i % len(PALETTE)]
        pts = ordered[name]
        if len(pts) == 0:
            continue
        dash = _DASHES[i % len(_DASHES)]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        coords = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
        out.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"{dash_attr}/>')
        for x, y in pts:
            out.append(_marker(_MARKERS[i % len(_MARKERS)], sx(x), sy(y), color))
    out.extend(_legend(names, "line"))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def bar_chart_svg(
    categories: list[str],
    series: dict[str, list[float]],
    title: str,
    x_label: str,
    y_label: str,
) -> str:
    """Draw a grouped bar chart: one group per category, one bar per series.

    Bars carry their value as a label when there are at most 24 bars.

    Raises:
        ValueError: If ``categories`` is empty, a series length differs from the
            number of categories, or a value is negative.

    Time: O(categories * series). Space: O(categories * series).
    """
    if len(categories) == 0:
        raise ValueError("bar chart needs at least one category")
    names = list(series.keys())
    if len(names) == 0:
        raise ValueError("bar chart needs at least one series")
    peak = 0.0
    for name in names:
        if len(series[name]) != len(categories):
            raise ValueError(f"series {name!r} must have {len(categories)} values")
        for v in series[name]:
            if v < 0:
                raise ValueError("bar values must be >= 0")
            if v > peak:
                peak = v

    px0, px1 = _ML, _W - _MR
    py0, py1 = _MT, _H - _MB
    ticks = _nice_ticks(peak)
    top = ticks[-1]

    def sy(v: float) -> float:
        return py1 - v / top * (py1 - py0)

    out = _frame(title, x_label, y_label)
    for t in ticks:
        y = sy(t)
        out.append(f'<line x1="{px0}" y1="{y:.1f}" x2="{px1}" y2="{y:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{px0 - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#333">{_esc(_fmt(t))}</text>')
    out.append(f'<line x1="{px0}" y1="{py0}" x2="{px0}" y2="{py1}" stroke="#333"/>')
    out.append(f'<line x1="{px0}" y1="{py1}" x2="{px1}" y2="{py1}" stroke="#333"/>')

    group_w = (px1 - px0) / len(categories)
    bar_w = group_w * 0.8 / len(names)
    label_bars = len(categories) * len(names) <= 24
    for ci, cat in enumerate(categories):
        gx = px0 + ci * group_w + group_w * 0.1
        for si, name in enumerate(names):
            v = series[name][ci]
            x = gx + si * bar_w
            y = sy(v)
            color = PALETTE[si % len(PALETTE)]
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 1:.1f}" height="{py1 - y:.1f}" fill="{color}"/>')
            if label_bars:
                out.append(f'<text x="{x + (bar_w - 1) / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
                           f'font-size="10" fill="#111">{_esc(_fmt(v))}</text>')
        out.append(f'<text x="{px0 + ci * group_w + group_w / 2:.1f}" y="{py1 + 20}" '
                   f'text-anchor="middle" fill="#333">{_esc(cat)}</text>')
    out.extend(_legend(names, "bar"))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _group_by_algorithm(rows: list[dict], field: str, floor: float | None = None
                        ) -> dict[str, list[tuple[float, float]]]:
    """Average ``field`` per (algorithm, n_students); rows with ``None`` are skipped."""
    buckets: dict[str, dict[float, list[float]]] = {}
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        if floor is not None and value < floor:
            value = floor
        buckets.setdefault(row["algorithm"], {}).setdefault(row["n_students"], []).append(float(value))
    result: dict[str, list[tuple[float, float]]] = {}
    for algorithm, by_size in buckets.items():
        result[algorithm] = [(size, mean(vals)) for size, vals in by_size.items()]
    return result


def benchmark_plots(rows: list[dict]) -> dict[str, str]:
    """Build the standard benchmark plots from benchmark rows.

    Returns a dict ``file name -> SVG text`` with up to three entries:

    * ``runtime_vs_size.svg``: coloring runtime (ms, log axis) against ``V``;
      runtimes below ``RUNTIME_FLOOR_MS`` are drawn at that floor.
    * ``colors_vs_size.svg``: colors used (grouped bars) per size.
    * ``soft_score_vs_size.svg``: soft score against ``V`` (rows without a
      score, for example infeasible placements, are skipped).

    Rows repeated for the same algorithm and size are averaged. A plot with no
    data is left out.

    Time: O(R log R) for R rows. Space: O(R).
    """
    plots: dict[str, str] = {}
    runtime = _group_by_algorithm(rows, "runtime_ms", RUNTIME_FLOOR_MS)
    if runtime:
        plots["runtime_vs_size.svg"] = line_chart_svg(
            runtime, "Coloring runtime vs number of students",
            "Students (V)", "Runtime (ms, log scale)", log_y=True)

    colors = _group_by_algorithm(rows, "colors_used")
    if colors:
        sizes: list[float] = []
        for pts in colors.values():
            for size, _v in pts:
                if size not in sizes:
                    sizes.append(size)
        sizes = merge_sort(sizes)
        bars: dict[str, list[float]] = {}
        for algorithm, pts in colors.items():
            lookup = {size: value for size, value in pts}
            bars[algorithm] = [lookup.get(size, 0.0) for size in sizes]
        plots["colors_vs_size.svg"] = bar_chart_svg(
            [_fmt(s) for s in sizes], bars, "Colors used by each algorithm",
            "Students (V)", "Colors used")

    scores = _group_by_algorithm(rows, "soft_score")
    if scores:
        plots["soft_score_vs_size.svg"] = line_chart_svg(
            scores, "Soft-constraint score vs number of students",
            "Students (V)", "Soft score (lower is better)")
    return plots


def save_benchmark_plots(rows: list[dict], out_dir: str) -> list[str]:
    """Write the plots of ``benchmark_plots`` into ``out_dir``; return their paths.

    Time: as ``benchmark_plots`` plus file writes. Space: O(output size).
    """
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, svg in benchmark_plots(rows).items():
        target = folder / name
        target.write_text(svg, encoding="utf-8")
        written.append(str(target))
    return written
