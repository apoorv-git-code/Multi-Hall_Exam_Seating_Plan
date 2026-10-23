"""Menu-driven and batch command line interface.

This module only connects user input to the library. It contains no algorithm
logic: coloring, seat mapping, validation and scoring all come from other
packages (``analysis.benchmark.run_pipeline`` runs the whole pipeline).

Two entry points:
    * ``run_menu``: interactive menu (used by ``python main.py`` with no options).
    * ``run_non_interactive``: one batch run (``python main.py --students ...``).

Exit codes: 0 success, 1 unreadable or invalid input data, 3 Phase 2 could not
seat everyone. (argparse itself uses 2 for command-line usage errors.)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.analysis.benchmark import ALGORITHMS, PipelineRun, run_pipeline
from src.cli.prompts import (
    UserQuit,
    ask_choice,
    ask_int,
    ask_text,
    ask_yes_no,
)
from src.dataio.generator import generate_dataset
from src.dataio.parser import DEFAULT_CONFIG, load_config, load_halls, load_students
from src.dataio.validator import DataFormatError, check_capacity
from src.models.hall import Hall
from src.models.student import Student
from src.reporting.csv_export import write_allocation_csv
from src.reporting.html_export import write_seating_html
from src.reporting.report_builder import build_summary_report, write_report
from src.reporting.text_chart import LABEL_MODES, render_all_halls, render_hall_chart, render_table

EXIT_OK = 0
EXIT_DATA_ERROR = 1
EXIT_INFEASIBLE = 3

DEFAULT_STUDENTS_PATH = "data/generated/students.csv"
DEFAULT_HALLS_PATH = "data/generated/halls.csv"
DEFAULT_GENERATED_DIR = "data/generated"
DEFAULT_OUT_DIR = "output"
DEFAULT_ALGORITHM = "welsh_powell"

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


def _print_stderr(message: str) -> None:
    print(message, file=sys.stderr)


def load_default_config(path: str | None = None) -> dict:
    """Load the configuration.

    With ``path`` the file is loaded (and validated). Without it, the project's
    ``config/default_config.json`` is used if it exists, otherwise the built-in
    defaults.

    Raises:
        DataFormatError: If a file cannot be read or is invalid.
    """
    if path is not None:
        return load_config(path)
    bundled = Path(__file__).resolve().parents[2] / "config" / "default_config.json"
    if bundled.exists():
        return load_config(str(bundled))
    return json.loads(json.dumps(DEFAULT_CONFIG))


def format_run_summary(run: PipelineRun, n_students: int) -> list[str]:
    """Return the short result lines printed after a run.

    Time: O(1). Space: O(1).
    """
    c = run.coloring
    lines = [
        f"Algorithm: {run.algorithm}",
        f"Colors used: {c.num_colors} "
        f"(runtime {c.runtime_ms:.2f} ms, nodes explored {c.nodes_explored}, "
        f"search completed: {'yes' if c.completed else 'no'})",
    ]
    if run.allocation is None or run.quality is None:
        lines.append(f"Seat mapping failed: {run.error}")
        lines.append("Try another algorithm, add halls, or reduce conflicts.")
        return lines
    q = run.quality
    lines.append(
        f"Seated: {q['seated']} of {n_students}, hall utilisation {q['hall_utilisation']:.3f}, "
        f"buffer seats {q['buffer_seats']}, wasted seats {q['wasted_seats']}"
    )
    lines.append(
        f"Soft score: {q['soft_score']:.2f} (lower is better). "
        f"Hard constraints: {'satisfied' if q['valid'] else 'VIOLATED'}"
    )
    return lines


def export_results(
    students: list[Student],
    halls: list[Hall],
    run: PipelineRun,
    config: dict,
    out_dir: str,
) -> list[str]:
    """Write all result files into ``out_dir`` and return their paths.

    Files:
        ``allocation.csv``, ``seating_charts/seating_chart.txt``,
        ``seating_charts/seating_chart.html``, ``reports/summary_report.md``.

    Raises:
        ValueError: If the run has no allocation (Phase 2 failed).
    """
    if run.allocation is None:
        raise ValueError("there is no allocation to export")
    base = Path(out_dir)
    paths: list[str] = []

    csv_path = base / "allocation.csv"
    write_allocation_csv(run.allocation, students, str(csv_path))
    paths.append(str(csv_path))

    txt_path = base / "seating_charts" / "seating_chart.txt"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(render_all_halls(halls, run.allocation, students) + "\n", encoding="utf-8")
    paths.append(str(txt_path))

    html_path = base / "seating_charts" / "seating_chart.html"
    write_seating_html(str(html_path), halls, run.allocation, students)
    paths.append(str(html_path))

    report_path = base / "reports" / "summary_report.md"
    text = build_summary_report(
        students, halls, run.allocation, config,
        run_info=run.run_info(), graph_info=run.graph_info,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    write_report(str(report_path), text)
    paths.append(str(report_path))
    return paths


def run_non_interactive(
    students_path: str,
    halls_path: str,
    algorithm: str,
    out_dir: str,
    config: dict,
    output_fn: OutputFn = print,
    error_fn: OutputFn = _print_stderr,
) -> int:
    """Run one allocation from CSV files and write the results.

    Returns:
        ``EXIT_OK``, ``EXIT_DATA_ERROR`` (unreadable or invalid files) or
        ``EXIT_INFEASIBLE`` (Phase 2 could not seat everyone; the coloring
        summary is still printed).
    """
    try:
        students = load_students(students_path)
        halls = load_halls(halls_path)
    except DataFormatError as exc:
        error_fn(f"Error: {exc}")
        return EXIT_DATA_ERROR
    output_fn(f"Loaded {len(students)} students and {len(halls)} halls.")
    problems = check_capacity(students, halls)
    if problems:
        error_fn(f"Error: {problems[0]}")
        return EXIT_INFEASIBLE

    run = run_pipeline(students, halls, algorithm, config)
    for line in format_run_summary(run, len(students)):
        output_fn(line)
    if run.allocation is None:
        return EXIT_INFEASIBLE
    for path in export_results(students, halls, run, config, out_dir):
        output_fn(f"Wrote {path}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

@dataclass
class Session:
    """State of one interactive session."""

    config: dict
    students: list[Student] | None = None
    halls: list[Hall] | None = None
    algorithm: str = DEFAULT_ALGORITHM
    run: PipelineRun | None = None
    out_dir: str = DEFAULT_OUT_DIR


_MENU = (
    ("1", "Load students and halls from CSV files"),
    ("2", "Generate a sample dataset"),
    ("3", "Choose algorithm"),
    ("4", "Run allocation"),
    ("5", "View seating chart"),
    ("6", "Show conflict graph metrics"),
    ("7", "Show summary report"),
    ("8", "Export results"),
    ("0", "Quit"),
)


def _status_line(session: Session) -> str:
    if session.students is None or session.halls is None:
        data = "no data loaded"
    else:
        data = f"{len(session.students)} students, {len(session.halls)} halls"
    result = "allocation ready" if session.run is not None and session.run.allocation is not None else "no allocation yet"
    return f"[{data} | algorithm: {session.algorithm} | {result}]"


def _need_data(session: Session, output_fn: OutputFn) -> bool:
    if session.students is None or session.halls is None:
        output_fn("Load or generate a dataset first (options 1 or 2).")
        return False
    return True


def _need_allocation(session: Session, output_fn: OutputFn) -> bool:
    if session.run is None:
        output_fn("Run the allocation first (option 4).")
        return False
    if session.run.allocation is None:
        output_fn(f"The last run could not seat everyone: {session.run.error}")
        return False
    return True


def _set_data(session: Session, students: list[Student], halls: list[Hall], output_fn: OutputFn) -> None:
    session.students = students
    session.halls = halls
    session.run = None
    output_fn(f"Loaded {len(students)} students and {len(halls)} halls.")
    for message in check_capacity(students, halls):
        output_fn(f"Warning: {message}")


def _action_load(session: Session, input_fn: InputFn, output_fn: OutputFn) -> None:
    students_path = ask_text("Students CSV path", input_fn, output_fn, default=DEFAULT_STUDENTS_PATH)
    halls_path = ask_text("Halls CSV path", input_fn, output_fn, default=DEFAULT_HALLS_PATH)
    try:
        students = load_students(students_path)
        halls = load_halls(halls_path)
    except DataFormatError as exc:
        output_fn(f"Error: {exc}")
        return
    _set_data(session, students, halls, output_fn)


def _action_generate(session: Session, input_fn: InputFn, output_fn: OutputFn) -> None:
    n_students = ask_int("Number of students", input_fn, output_fn, 1, 5000, default=100)
    n_courses = ask_int("Number of courses", input_fn, output_fn, 1, 500, default=12)
    n_halls = ask_int("Number of halls", input_fn, output_fn, 1, 100, default=max(1, -(-n_students // 100)))
    seed = ask_int("Random seed", input_fn, output_fn, 0, 2147483647, default=session.config["random_seed"])
    out_dir = ask_text("Folder to save the CSV files", input_fn, output_fn, default=DEFAULT_GENERATED_DIR)
    students_path, halls_path = generate_dataset(n_students, n_courses, n_halls, seed, out_dir)
    output_fn(f"Wrote {students_path} and {halls_path}.")
    try:
        _set_data(session, load_students(students_path), load_halls(halls_path), output_fn)
    except DataFormatError as exc:
        output_fn(f"Error: {exc}")


def _action_algorithm(session: Session, input_fn: InputFn, output_fn: OutputFn) -> None:
    session.algorithm = ask_choice(
        "Algorithm", list(ALGORITHMS), input_fn, output_fn, default=session.algorithm
    )
    session.run = None
    output_fn(f"Algorithm set to {session.algorithm}.")


def _action_run(session: Session, output_fn: OutputFn) -> None:
    if not _need_data(session, output_fn):
        return
    assert session.students is not None and session.halls is not None
    if session.algorithm == "backtracking":
        limits = session.config["backtracking"]
        output_fn(
            f"Backtracking runs up to {limits['node_limit']} nodes or "
            f"{limits['time_limit_seconds']} seconds. Please wait..."
        )
    session.run = run_pipeline(session.students, session.halls, session.algorithm, session.config)
    for line in format_run_summary(session.run, len(session.students)):
        output_fn(line)


def _action_chart(session: Session, input_fn: InputFn, output_fn: OutputFn) -> None:
    if not _need_allocation(session, output_fn):
        return
    assert session.run is not None and session.run.allocation is not None
    assert session.students is not None and session.halls is not None
    hall_ids = [hall.hall_id for hall in session.halls]
    which = ask_choice("Hall", ["all"] + hall_ids, input_fn, output_fn, default="all")
    label = ask_choice("Seat label", list(LABEL_MODES), input_fn, output_fn, default="id")
    if which == "all":
        output_fn(render_all_halls(session.halls, session.run.allocation, session.students, label))
    else:
        hall = session.halls[hall_ids.index(which)]
        output_fn(render_hall_chart(hall, session.run.allocation, session.students, label))


def _action_graph(session: Session, output_fn: OutputFn) -> None:
    if not _need_data(session, output_fn):
        return
    assert session.students is not None and session.halls is not None
    if session.run is None:
        session.run = run_pipeline(session.students, session.halls, session.algorithm, session.config)
    info = session.run.graph_info
    rows = [{"metric": key, "value": value} for key, value in info.items()]
    output_fn(render_table(rows, ["metric", "value"], float_digits=4))


def _action_report(session: Session, output_fn: OutputFn) -> None:
    if not _need_allocation(session, output_fn):
        return
    assert session.run is not None and session.run.allocation is not None
    assert session.students is not None and session.halls is not None
    output_fn(build_summary_report(
        session.students, session.halls, session.run.allocation, session.config,
        run_info=session.run.run_info(), graph_info=session.run.graph_info,
    ))


def _action_export(session: Session, input_fn: InputFn, output_fn: OutputFn) -> None:
    if not _need_allocation(session, output_fn):
        return
    assert session.run is not None and session.students is not None and session.halls is not None
    out_dir = ask_text("Output folder", input_fn, output_fn, default=session.out_dir)
    if (Path(out_dir) / "allocation.csv").exists():
        if not ask_yes_no(f"Results already exist in {out_dir}. Overwrite?", input_fn, output_fn, default=False):
            output_fn("Export cancelled.")
            return
    session.out_dir = out_dir
    for path in export_results(session.students, session.halls, session.run, session.config, out_dir):
        output_fn(f"Wrote {path}")


def run_menu(
    config: dict,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    session: Session | None = None,
) -> int:
    """Run the interactive menu until the user quits or input ends.

    Args:
        config: Validated configuration (see ``load_default_config``).
        input_fn: Reads one line (default ``input``).
        output_fn: Writes one line (default ``print``).
        session: Optional prepared session (used by tests).

    Returns:
        ``EXIT_OK``. Errors in user data are reported and the menu continues.
    """
    state = session if session is not None else Session(config=config)
    output_fn("=== Multi-Hall Exam Seating Allocation ===")
    try:
        while True:
            output_fn("")
            output_fn(_status_line(state))
            for key, text in _MENU:
                output_fn(f"  {key}) {text}")
            choice = ask_text("Choose an option", input_fn, output_fn).lower()
            if choice in ("0", "q", "quit", "exit"):
                break
            if choice == "1":
                _action_load(state, input_fn, output_fn)
            elif choice == "2":
                _action_generate(state, input_fn, output_fn)
            elif choice == "3":
                _action_algorithm(state, input_fn, output_fn)
            elif choice == "4":
                _action_run(state, output_fn)
            elif choice == "5":
                _action_chart(state, input_fn, output_fn)
            elif choice == "6":
                _action_graph(state, output_fn)
            elif choice == "7":
                _action_report(state, output_fn)
            elif choice == "8":
                _action_export(state, input_fn, output_fn)
            else:
                output_fn("Unknown option. Enter a number from the menu.")
    except UserQuit:
        output_fn("")
    output_fn("Goodbye.")
    return EXIT_OK
