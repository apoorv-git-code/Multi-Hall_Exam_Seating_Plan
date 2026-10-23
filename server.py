"""FastAPI wrapper around the exam-seating engine in ``src/``.

This file contains no allocation, coloring or scoring algorithms. Every number
comes from the existing backend modules:

    dataset   src.dataio.generator / parser / validator
    allocate  src.analysis.benchmark.run_pipeline  (graph -> coloring -> seat_mapper -> metrics)
    benchmark src.analysis.benchmark.benchmark_dataset / run_benchmarks
    export    src.reporting.csv_export / html_export / svg_plots / report_builder

Two presentation helpers (``seat_heat`` and the empty-seat classification) only
*distribute* the backend's own penalty values over individual seats so the UI
can draw a heatmap. They call ``src.grid.scoring`` and ``src.grid.hall_grid``
primitives, and ``heat_reconciles`` in every response proves that the per-seat
numbers add up to the backend's ``compute_soft_score``.

Sessions: each browser gets an opaque HttpOnly cookie ("exam_session") that selects its own dataset,
last allocation and benchmark. Idle sessions expire (SESSION_TTL_SECONDS), at most MAX_SESSIONS are
kept, and MAX_CONCURRENT_JOBS limits simultaneous CPU-heavy runs. Sessions live in this process's
memory, so run ONE worker process (see Dockerfile), or add sticky sessions / a shared store first.

Run:  uvicorn server:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import copy
import math
import os
import secrets
import sys
import tempfile
import threading
import time
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.analysis.benchmark import (  # noqa: E402
    ALGORITHMS,
    PipelineRun,
    benchmark_dataset,
    run_benchmarks,
    run_pipeline,
)
from src.dataio.generator import generate_dataset, generate_halls, generate_students  # noqa: E402
from src.dataio.parser import DEFAULT_CONFIG, load_halls, load_students  # noqa: E402
from src.dataio.validator import (  # noqa: E402
    DataFormatError,
    check_capacity,
    validate_config,
    validate_halls,
    validate_students,
)
from src.graph.conflict_graph import build_conflict_graph  # noqa: E402
from src.graph.graph_metrics import graph_summary  # noqa: E402
from src.grid.hall_grid import get_distance_two_seats, get_neighbors, usable_seats  # noqa: E402
from src.grid.scoring import (  # noqa: E402
    adjacent_pair_penalty,
    compute_soft_score,
    distance_two_pair_penalty,
)
from src.models.hall import Hall  # noqa: E402
from src.models.student import Student  # noqa: E402
from src.reporting.csv_export import write_allocation_csv  # noqa: E402
from src.reporting.html_export import render_seating_html  # noqa: E402
from src.reporting.report_builder import build_summary_report  # noqa: E402
from src.reporting.svg_plots import RUNTIME_FLOOR_MS, benchmark_plots, line_chart_svg  # noqa: E402

# ---------------------------------------------------------------------------
# Limits (this server is a single-user showcase; protect it from huge requests)
# ---------------------------------------------------------------------------

MAX_STUDENTS = 2000
MAX_HALLS = 50
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_BACKTRACKING_NODES = 2_000_000
MAX_BACKTRACKING_SECONDS = 30.0
MAX_BENCHMARK_SECONDS = 120.0
SAMPLE_DIR = ROOT / "data" / "sample"

# Session / concurrency settings (override with environment variables).
SESSION_COOKIE = "exam_session"
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 2 * 60 * 60))   # idle time before a session expires
MAX_SESSIONS = int(os.environ.get("MAX_SESSIONS", 200))                          # oldest idle session is evicted beyond this
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", 4))              # simultaneous allocations/benchmarks
JOB_WAIT_SECONDS = float(os.environ.get("JOB_WAIT_SECONDS", 20))                 # how long a request waits for a free slot
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"                      # set to 1 behind HTTPS

# ---------------------------------------------------------------------------
# Algorithm registry (the single place that maps UI names to backend names)
# ---------------------------------------------------------------------------

ALGORITHM_INFO: dict[str, dict] = {
    "greedy": {
        "label": "Greedy First-Fit",
        "aliases": [],
        "description": "Colors vertices in input order with the smallest free color. O(V + E).",
        "exact": False,
    },
    "welsh_powell": {
        "label": "Welsh-Powell (LDF)",
        "aliases": ["ldf", "largest_degree_first"],
        "description": "Sorts vertices by degree, descending, then first-fit. This is the "
                       "Largest-Degree-First (LDF) heuristic. O(V log V + E).",
        "exact": False,
    },
    "backtracking": {
        "label": "Exact Backtracking (bounded)",
        "aliases": ["exact"],
        "description": "Depth-first search with pruning under node and time limits. Exact only "
                       "when it finishes (search_completed = true).",
        "exact": True,
    },
}

#: Names a user may reasonably ask for that the backend does not implement.
UNAVAILABLE_ALGORITHMS: dict[str, str] = {
    "dsatur": "DSatur is not implemented in src/algorithms (README lists it as an optional extension).",
}

assert set(ALGORITHM_INFO) == set(ALGORITHMS), "ALGORITHM_INFO is out of sync with src.analysis.benchmark.ALGORITHMS"

_ALIASES = {alias: key for key, info in ALGORITHM_INFO.items() for alias in info["aliases"]}


def resolve_algorithm(name: str) -> str:
    """Return the canonical backend algorithm id for ``name`` or raise HTTP 422."""
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key in ALGORITHM_INFO:
        return key
    if key in _ALIASES:
        return _ALIASES[key]
    if key in UNAVAILABLE_ALGORITHMS:
        raise HTTPException(422, UNAVAILABLE_ALGORITHMS[key])
    raise HTTPException(422, f"unknown algorithm {name!r}; available: {sorted(ALGORITHM_INFO)}")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class StudentOut(BaseModel):
    sap_id: str
    name: str
    roll_no: int
    branch: str
    courses: list[str]


class HallOut(BaseModel):
    hall_id: str
    rows: int
    cols: int
    blocked: list[tuple[int, int]]
    capacity: int


class GenerateRequest(BaseModel):
    n_students: int = Field(100, ge=1, le=MAX_STUDENTS, description="Number of students")
    n_halls: int = Field(2, ge=1, le=MAX_HALLS, description="Number of halls")
    n_courses: int = Field(
        40, ge=1, le=500,
        description="Distinct courses. Fewer courses means more shared courses, so a denser conflict graph.",
    )
    seed: int = Field(42, ge=0, le=2_147_483_647)


class JsonDataset(BaseModel):
    students: list[StudentOut]
    halls: list[HallOut]


class DatasetResponse(BaseModel):
    source: str
    n_students: int
    n_halls: int
    total_capacity: int
    n_distinct_courses: int
    branches: list[str]
    n_edges: int
    density: float = Field(description="Conflict-graph density: edges / (V(V-1)/2)")
    capacity_warning: str | None = None
    students: list[StudentOut]
    halls: list[HallOut]
    students_csv: str | None = None
    halls_csv: str | None = None


class Weights(BaseModel):
    """Soft-constraint weights; the same keys as ``config/default_config.json``."""

    w_same_branch: float = Field(DEFAULT_CONFIG["weights"]["w_same_branch"], ge=0, le=100)
    w_consecutive_roll: float = Field(DEFAULT_CONFIG["weights"]["w_consecutive_roll"], ge=0, le=100)
    w_distance_two_conflict: float = Field(DEFAULT_CONFIG["weights"]["w_distance_two_conflict"], ge=0, le=100)
    w_wasted_seat: float = Field(DEFAULT_CONFIG["weights"]["w_wasted_seat"], ge=0, le=100)


class EngineOptions(BaseModel):
    neighbourhood: Literal["4", "8"] = "4"
    backtracking_node_limit: int = Field(DEFAULT_CONFIG["backtracking"]["node_limit"], ge=1, le=MAX_BACKTRACKING_NODES)
    backtracking_time_limit_seconds: float = Field(
        DEFAULT_CONFIG["backtracking"]["time_limit_seconds"], gt=0, le=MAX_BACKTRACKING_SECONDS)


class AllocateRequest(EngineOptions):
    algorithm: str = "welsh_powell"
    weights: Weights = Weights()

    @field_validator("algorithm")
    @classmethod
    def _known_algorithm(cls, value: str) -> str:
        return resolve_algorithm(value)


class SeatOut(BaseModel):
    sap_id: str
    name: str
    roll_no: int
    branch: str
    courses: list[str]
    hall_id: str
    row: int = Field(description="0-based; row 0 is the front")
    col: int = Field(description="0-based; col 0 is the left")
    seat_label: str
    color: int = Field(description="Phase 1 conflict-graph color class")
    penalty: float = Field(description="Sum of soft penalties of every pair this seat takes part in")


class EmptySeatOut(BaseModel):
    hall_id: str
    row: int
    col: int
    kind: Literal["buffer", "wasted"]
    penalty: float


class HallLayout(HallOut):
    seated: int


class Metrics(BaseModel):
    colors_used: int
    chromatic_lower_bound: int = Field(description="Size of the largest course (a clique), a lower bound on chi(G)")
    chromatic_number: int | None = Field(description="chi(G) when proven (search completed or bound met), else null")
    proven_optimal: bool
    capacity_utilisation_pct: float | None
    coloring_runtime_ms: float
    pipeline_runtime_ms: float
    soft_score: float | None
    hard_constraints_satisfied: bool | None
    violations: list[str]
    nodes_explored: int
    search_completed: bool
    seated: int
    total_students: int
    buffer_seats: int | None
    wasted_seats: int | None
    used_halls: int | None
    n_edges: int
    density: float
    max_degree: int


class SoftBreakdown(BaseModel):
    counts: dict[str, int]
    weights: dict[str, float]
    contributions: dict[str, float]
    total: float
    heat_max: float
    heat_reconciles: bool


class ColorClass(BaseModel):
    color: int
    count: int


class AlgorithmRef(BaseModel):
    id: str
    label: str


class AllocateResponse(BaseModel):
    status: Literal["ok", "infeasible"]
    message: str | None
    algorithm: AlgorithmRef
    neighbourhood: str
    metrics: Metrics
    soft: SoftBreakdown | None
    halls: list[HallLayout]
    seats: list[SeatOut]
    empty_seats: list[EmptySeatOut]
    color_classes: list[ColorClass]


class BenchmarkRequest(EngineOptions):
    mode: Literal["density", "size"] = "density"
    algorithms: list[str] = Field(default_factory=lambda: list(ALGORITHMS), min_length=1, max_length=3)
    n_students: int = Field(100, ge=10, le=1000, description="density mode: fixed student count")
    course_counts: list[int] = Field(
        default_factory=lambda: [80, 40, 25, 15], min_length=1, max_length=10,
        description="density mode: one dataset per value; fewer courses gives a denser graph")
    sizes: list[int] = Field(default_factory=lambda: [50, 100, 200], min_length=1, max_length=8)
    n_courses: int = Field(40, ge=2, le=500, description="size mode: courses per dataset")
    repeats: int = Field(1, ge=1, le=5)
    seed: int = Field(42, ge=0, le=2_147_483_647)
    weights: Weights = Weights()
    # Benchmarks run many allocations, so their backtracking limits default lower.
    backtracking_node_limit: int = Field(50_000, ge=1, le=MAX_BACKTRACKING_NODES)
    backtracking_time_limit_seconds: float = Field(2.0, gt=0, le=MAX_BACKTRACKING_SECONDS)

    @field_validator("algorithms")
    @classmethod
    def _known_algorithms(cls, values: list[str]) -> list[str]:
        resolved: list[str] = []
        for value in values:
            key = resolve_algorithm(value)
            if key not in resolved:
                resolved.append(key)
        return resolved

    @field_validator("course_counts")
    @classmethod
    def _course_range(cls, values: list[int]) -> list[int]:
        if any(v < 2 or v > 500 for v in values):
            raise ValueError("every course count must be between 2 and 500")
        return values

    @field_validator("sizes")
    @classmethod
    def _size_range(cls, values: list[int]) -> list[int]:
        if any(v < 10 or v > 1000 for v in values):
            raise ValueError("every size must be between 10 and 1000")
        return values


class BenchmarkSeries(BaseModel):
    algorithm: str
    label: str
    points: list[dict]


class BenchmarkResponse(BaseModel):
    mode: str
    x_key: str
    x_label: str
    rows: list[dict]
    series: list[BenchmarkSeries]
    plots: list[str] = Field(description="SVG names available from GET /api/export/svg?plot=<name>")
    truncated: bool = Field(description="True if the wall-clock budget stopped the run early")
    elapsed_seconds: float
    note: str


# ---------------------------------------------------------------------------
# In-memory session state (single-user showcase)
# ---------------------------------------------------------------------------

@dataclass
class RunRecord:
    run: PipelineRun
    config: dict
    pipeline_ms: float


class Session:
    """Everything one browser session owns. Nothing here is shared between sessions."""

    def __init__(self, sid: str, now: float) -> None:
        self.sid = sid
        self.created = self.last_seen = now
        self.lock = threading.RLock()          # serialises requests of ONE session only
        self.students: list[Student] | None = None
        self.halls: list[Hall] | None = None
        self.source: str = ""
        self.last_run: RunRecord | None = None
        self.benchmark_svgs: dict[str, str] = {}
        self.benchmark_rows: list[dict] = []

    def reset(self) -> None:
        with self.lock:
            self.students = self.halls = self.last_run = None
            self.source = ""
            self.benchmark_svgs, self.benchmark_rows = {}, []


class SessionStore:
    """Thread-safe LRU store of sessions with an idle timeout and a hard size cap.

    Entries are kept in least-recently-used order, so expired sessions are always at the
    front and purging is O(number expired). ``clock`` is injectable for tests.
    """

    def __init__(self, ttl: float, max_sessions: int, clock=time.monotonic) -> None:
        self.ttl, self.max_sessions, self.clock = ttl, max_sessions, clock
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        while self._items:
            oldest = next(iter(self._items.values()))
            if now - oldest.last_seen <= self.ttl:
                break
            self._items.popitem(last=False)

    def get_or_create(self, sid: str | None) -> tuple[Session, bool]:
        """Return ``(session, created)``; an unknown, forged or expired id yields a fresh session."""
        with self._lock:
            now = self.clock()
            self._purge(now)
            session = self._items.get(sid) if sid else None
            if session is not None:
                session.last_seen = now
                self._items.move_to_end(sid)
                return session, False
            session = Session(secrets.token_urlsafe(32), now)
            self._items[session.sid] = session
            while len(self._items) > self.max_sessions:
                self._items.popitem(last=False)
            return session, True

    def drop(self, sid: str) -> None:
        with self._lock:
            self._items.pop(sid, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


SESSIONS = SessionStore(SESSION_TTL_SECONDS, MAX_SESSIONS)
JOB_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_JOBS)


@contextmanager
def job_slot():
    """Limit simultaneous CPU-heavy jobs across all sessions; answer 503 instead of queueing forever."""
    if not JOB_SLOTS.acquire(timeout=JOB_WAIT_SECONDS):
        raise HTTPException(503, "The server is busy running other allocations. Please retry in a moment.",
                            headers={"Retry-After": "5"})
    try:
        yield
    finally:
        JOB_SLOTS.release()


def current_session(request: Request) -> Session:
    return request.state.session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_config(options: EngineOptions, weights: Weights) -> dict:
    """Create a validated engine config from request options (DEFAULT_CONFIG is never mutated)."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["neighbourhood"] = options.neighbourhood
    config["weights"] = weights.model_dump()
    config["backtracking"] = {
        "node_limit": options.backtracking_node_limit,
        "time_limit_seconds": options.backtracking_time_limit_seconds,
    }
    errors = validate_config(config)
    if errors:
        raise HTTPException(422, "; ".join(errors))
    return config


def student_out(s: Student) -> StudentOut:
    return StudentOut(sap_id=s.sap_id, name=s.name, roll_no=s.roll_no, branch=s.branch,
                      courses=sorted(s.courses))


def hall_out(h: Hall) -> HallOut:
    return HallOut(hall_id=h.hall_id, rows=h.rows, cols=h.cols,
                   blocked=sorted(h.blocked), capacity=h.capacity())


def install_dataset(session: Session, students: list[Student], halls: list[Hall], source: str) -> None:
    with session.lock:
        session.students, session.halls, session.source = students, halls, source
        session.last_run = None          # an old allocation no longer matches the data


def dataset_response(session: Session, students_csv: str | None = None, halls_csv: str | None = None) -> DatasetResponse:
    source = session.source
    students, halls = session.students, session.halls
    assert students is not None and halls is not None
    info = graph_summary(build_conflict_graph(students))
    capacity = sum(h.capacity() for h in halls)
    problems = check_capacity(students, halls)
    courses: set[str] = set()
    for s in students:
        courses |= s.courses
    return DatasetResponse(
        source=source, n_students=len(students), n_halls=len(halls), total_capacity=capacity,
        n_distinct_courses=len(courses), branches=sorted({s.branch for s in students}),
        n_edges=info["n_edges"], density=round(info["density"], 4),
        capacity_warning=problems[0] if problems else None,
        students=[student_out(s) for s in students], halls=[hall_out(h) for h in halls],
        students_csv=students_csv, halls_csv=halls_csv,
    )


def seat_label(hall_id: str, row: int, col: int) -> str:
    """Human label; rows and columns are shown 1-based, row 1 is the front."""
    return f"{hall_id}-R{row + 1}C{col + 1}"


def seat_heat(run: PipelineRun, students: list[Student], halls: list[Hall], config: dict):
    """Spread the backend's soft penalties over individual seats (for the heatmap).

    Each neighbouring or distance-two pair contributes its backend penalty
    (``adjacent_pair_penalty`` / ``distance_two_pair_penalty``) to BOTH seats.
    Empty seats are classified like ``soft_breakdown``: *buffer* if a neighbour
    is occupied, else *wasted* (which carries ``w_wasted_seat``).

    Returns ``(seat_penalty, empty_seats, pair_total, wasted_count)`` where
    ``pair_total + w_wasted_seat * wasted_count`` equals the backend soft score.
    """
    assert run.allocation is not None
    weights, nb = config["weights"], config["neighbourhood"]
    by_id = {s.sap_id: s for s in students}
    hall_by_id = {h.hall_id: h for h in halls}
    occupant = {seat: sap for sap, seat in run.allocation.seats.items()}
    heat: dict[tuple[str, int, int], float] = defaultdict(float)
    pair_total = 0.0

    for (hid, r, c), sap in occupant.items():
        hall, a = hall_by_id[hid], by_id[sap]
        for pairs, penalty_fn in ((get_neighbors(hall, r, c, nb), adjacent_pair_penalty),
                                  (get_distance_two_seats(hall, r, c), distance_two_pair_penalty)):
            for nr, nc in pairs:
                if (nr, nc) < (r, c):
                    continue                      # count each unordered pair once
                other = occupant.get((hid, nr, nc))
                if other is None:
                    continue
                p = penalty_fn(a, by_id[other], weights)
                if p:
                    heat[(hid, r, c)] += p
                    heat[(hid, nr, nc)] += p
                    pair_total += p

    empty: list[EmptySeatOut] = []
    wasted = 0
    used = {hid for hid, _, _ in occupant}
    for hall in halls:
        if hall.hall_id not in used:
            continue
        for r, c in usable_seats(hall):
            if (hall.hall_id, r, c) in occupant:
                continue
            touches = any((hall.hall_id, nr, nc) in occupant for nr, nc in get_neighbors(hall, r, c, nb))
            if touches:
                empty.append(EmptySeatOut(hall_id=hall.hall_id, row=r, col=c, kind="buffer", penalty=0.0))
            else:
                wasted += 1
                empty.append(EmptySeatOut(hall_id=hall.hall_id, row=r, col=c, kind="wasted",
                                          penalty=weights["w_wasted_seat"]))
    return heat, empty, pair_total, wasted


def build_allocate_response(record: RunRecord, students: list[Student], halls: list[Hall],
                            algorithm: str) -> AllocateResponse:
    run, config = record.run, record.config
    info, coloring = run.graph_info, run.coloring
    lower = info.get("clique_lower_bound")
    if lower is None:
        # Older backend builds do not put the bound into graph_info; derive it from the data.
        from src.graph.graph_metrics import course_clique_lower_bound
        lower = course_clique_lower_bound(students)
    proven = bool((algorithm == "backtracking" and coloring.completed) or coloring.num_colors == lower)
    ref = AlgorithmRef(id=algorithm, label=ALGORITHM_INFO[algorithm]["label"])
    layouts = [HallLayout(**hall_out(h).model_dump(), seated=0) for h in halls]

    base = dict(
        colors_used=coloring.num_colors, chromatic_lower_bound=lower,
        chromatic_number=coloring.num_colors if proven else None, proven_optimal=proven,
        coloring_runtime_ms=round(coloring.runtime_ms, 4), pipeline_runtime_ms=round(record.pipeline_ms, 3),
        nodes_explored=coloring.nodes_explored, search_completed=coloring.completed,
        total_students=len(students), n_edges=info["n_edges"], density=round(info["density"], 4),
        max_degree=info["max_degree"],
    )

    if run.allocation is None or run.quality is None:
        metrics = Metrics(**base, capacity_utilisation_pct=None, soft_score=None,
                          hard_constraints_satisfied=None, violations=[], seated=0,
                          buffer_seats=None, wasted_seats=None, used_halls=None)
        return AllocateResponse(
            status="infeasible", message=run.error or "No valid allocation found.", algorithm=ref,
            neighbourhood=config["neighbourhood"], metrics=metrics, soft=None, halls=layouts,
            seats=[], empty_seats=[], color_classes=[])

    q, weights = run.quality, config["weights"]
    heat, empty, pair_total, wasted = seat_heat(run, students, halls, config)
    by_id = {s.sap_id: s for s in students}
    seats: list[SeatOut] = []
    per_hall: dict[str, int] = defaultdict(int)
    class_counts: dict[int, int] = defaultdict(int)
    for s in students:
        if s.sap_id not in run.allocation.seats:
            continue
        hid, r, c = run.allocation.seats[s.sap_id]
        color = run.allocation.colors.get(s.sap_id, 0)
        per_hall[hid] += 1
        class_counts[color] += 1
        seats.append(SeatOut(**student_out(by_id[s.sap_id]).model_dump(), hall_id=hid, row=r, col=c,
                             seat_label=seat_label(hid, r, c), color=color,
                             penalty=round(heat.get((hid, r, c), 0.0), 4)))
    for layout in layouts:
        layout.seated = per_hall.get(layout.hall_id, 0)

    counts = {k: int(q[k]) for k in ("same_branch_pairs", "consecutive_roll_pairs", "distance_two_pairs",
                                     "wasted_seats", "buffer_seats", "used_halls", "seated")}
    contributions = {
        "same_branch": weights["w_same_branch"] * counts["same_branch_pairs"],
        "consecutive_roll": weights["w_consecutive_roll"] * counts["consecutive_roll_pairs"],
        "distance_two_conflict": weights["w_distance_two_conflict"] * counts["distance_two_pairs"],
        "wasted_seat": weights["w_wasted_seat"] * counts["wasted_seats"],
    }
    score = compute_soft_score(run.allocation, students, halls, weights, config["neighbourhood"])
    reconciles = (abs(pair_total + weights["w_wasted_seat"] * wasted - score) < 1e-6
                  and wasted == counts["wasted_seats"] and abs(score - q["soft_score"]) < 1e-6)
    metrics = Metrics(
        **base, capacity_utilisation_pct=round(q["hall_utilisation"] * 100, 2), soft_score=round(q["soft_score"], 4),
        hard_constraints_satisfied=bool(q["valid"]), violations=list(q["violations"]), seated=counts["seated"],
        buffer_seats=counts["buffer_seats"], wasted_seats=counts["wasted_seats"], used_halls=counts["used_halls"])
    soft = SoftBreakdown(
        counts=counts, weights={k: float(v) for k, v in weights.items()},
        contributions={k: round(v, 4) for k, v in contributions.items()}, total=round(score, 4),
        heat_max=round(max(heat.values(), default=0.0), 4), heat_reconciles=reconciles)
    return AllocateResponse(
        status="ok", message=None, algorithm=ref, neighbourhood=config["neighbourhood"], metrics=metrics,
        soft=soft, halls=layouts, seats=seats, empty_seats=empty,
        color_classes=[ColorClass(color=k, count=class_counts[k]) for k in sorted(class_counts)])


def require_dataset(session: Session) -> tuple[list[Student], list[Hall]]:
    if session.students is None or session.halls is None:
        raise HTTPException(409, "No dataset loaded. Use /api/dataset/generate, /upload, /load or /sample first.")
    return session.students, session.halls


def clean_row(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        out[key] = round(value, 4) if isinstance(value, float) else value
    return out


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="Exam Seating Allocation API", version="1.0.0",
              description="HTTP wrapper around the graph-coloring seating engine in src/.")

_origins = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
).split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["Content-Disposition"])


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    """Attach the caller's session (creating one and setting the cookie if needed) to /api/ requests."""
    if not request.url.path.startswith("/api/") or request.method == "OPTIONS":
        return await call_next(request)
    session, created = SESSIONS.get_or_create(request.cookies.get(SESSION_COOKIE))
    request.state.session = session
    response = await call_next(request)
    if created:
        response.set_cookie(SESSION_COOKIE, session.sid, max_age=SESSION_TTL_SECONDS, httponly=True,
                            samesite="lax", secure=COOKIE_SECURE, path="/")
    return response


@app.get("/healthz", include_in_schema=False)
def liveness() -> dict:
    """Liveness probe for Docker/load balancers. Lives outside /api/, so it never creates a session."""
    return {"status": "ok"}


@app.get("/api/health")
def health(request: Request) -> dict:
    return {"status": "ok", "algorithms": list(ALGORITHMS), "dataset_loaded": current_session(request).students is not None}


@app.get("/api/session")
def session_info(request: Request) -> dict:
    """What this browser session currently holds (data is private to the session cookie)."""
    s = current_session(request)
    return {"ttl_seconds": SESSION_TTL_SECONDS, "idle_seconds": round(SESSIONS.clock() - s.last_seen, 1),
            "dataset_loaded": s.students is not None, "has_allocation": s.last_run is not None,
            "has_benchmark": bool(s.benchmark_svgs)}


@app.delete("/api/session")
def reset_session(request: Request) -> dict:
    """Forget this session's dataset, allocation and benchmark (e.g. after uploading private data)."""
    current_session(request).reset()
    return {"status": "reset"}


@app.get("/api/algorithms")
def algorithms() -> dict:
    """Algorithms the backend really implements, plus names that are deliberately unavailable."""
    return {
        "available": [{"id": key, **info} for key, info in ALGORITHM_INFO.items()],
        "unavailable": [{"id": key, "reason": why} for key, why in UNAVAILABLE_ALGORITHMS.items()],
        "default_weights": Weights().model_dump(),
    }


# ---- dataset ---------------------------------------------------------------

@app.post("/api/dataset/generate", response_model=DatasetResponse)
def generate(req: GenerateRequest, request: Request) -> DatasetResponse:
    """Generate a seeded dataset with ``src.dataio.generator.generate_dataset`` (what scripts/generate_dataset.py runs)."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            s_path, h_path = generate_dataset(req.n_students, req.n_courses, req.n_halls, req.seed, tmp)
            students, halls = load_students(s_path), load_halls(h_path)
            s_csv, h_csv = Path(s_path).read_text(encoding="utf-8"), Path(h_path).read_text(encoding="utf-8")
        except (ValueError, DataFormatError) as exc:
            raise HTTPException(422, str(exc)) from exc
    session = current_session(request)
    install_dataset(session, students, halls, f"generated (seed {req.seed})")
    return dataset_response(session, s_csv, h_csv)


@app.post("/api/dataset/upload", response_model=DatasetResponse)
async def upload(request: Request, students_file: UploadFile = File(...), halls_file: UploadFile = File(...)) -> DatasetResponse:
    """Upload ``students.csv`` and ``halls.csv`` (same formats as data/sample/)."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, upload_file in (("students.csv", students_file), ("halls.csv", halls_file)):
            data = await upload_file.read()
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"{upload_file.filename}: file is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
            path = Path(tmp) / name
            path.write_bytes(data)
            paths.append(str(path))
        try:
            students, halls = load_students(paths[0]), load_halls(paths[1])
        except DataFormatError as exc:
            raise HTTPException(422, str(exc).replace(tmp, "upload")) from exc
    if len(students) > MAX_STUDENTS:
        raise HTTPException(422, f"at most {MAX_STUDENTS} students are supported by this server")
    session = current_session(request)
    install_dataset(session, students, halls, "uploaded CSV")
    return dataset_response(session)


@app.post("/api/dataset/load", response_model=DatasetResponse)
def load_json(body: JsonDataset, request: Request) -> DatasetResponse:
    """Load a dataset sent as JSON (validated by src.dataio.validator)."""
    students = [Student(s.sap_id, s.name, s.roll_no, s.branch, frozenset(s.courses)) for s in body.students]
    halls = [Hall(h.hall_id, h.rows, h.cols, frozenset(map(tuple, h.blocked))) for h in body.halls]
    errors = validate_students(students) + validate_halls(halls)
    if errors:
        raise HTTPException(422, "; ".join(errors[:10]))
    if len(students) > MAX_STUDENTS:
        raise HTTPException(422, f"at most {MAX_STUDENTS} students are supported by this server")
    session = current_session(request)
    install_dataset(session, students, halls, "uploaded JSON")
    return dataset_response(session)


@app.post("/api/dataset/sample", response_model=DatasetResponse)
def load_sample(request: Request) -> DatasetResponse:
    """Load the dataset shipped in data/sample/."""
    try:
        students = load_students(str(SAMPLE_DIR / "students.csv"))
        halls = load_halls(str(SAMPLE_DIR / "halls.csv"))
    except DataFormatError as exc:
        raise HTTPException(404, f"sample data unavailable: {exc}") from exc
    session = current_session(request)
    install_dataset(session, students, halls, "bundled sample")
    return dataset_response(session)


@app.get("/api/dataset", response_model=DatasetResponse)
def current_dataset(request: Request) -> DatasetResponse:
    session = current_session(request)
    with session.lock:
        require_dataset(session)
        return dataset_response(session)


# ---- allocate ---------------------------------------------------------------

@app.post("/api/allocate", response_model=AllocateResponse)
def allocate(req: AllocateRequest, request: Request) -> AllocateResponse:
    """Run graph -> coloring -> seat mapping -> evaluation on the loaded dataset.

    An allocation that Phase 2 cannot complete is returned with ``status = "infeasible"``
    (HTTP 200) together with the coloring metrics, so the UI can explain it.
    """
    session = current_session(request)
    with session.lock:
        students, halls = require_dataset(session)
        config = build_config(req, req.weights)
        with job_slot():
            started = time.perf_counter()
            run = run_pipeline(students, halls, req.algorithm, config)
        record = RunRecord(run=run, config=config, pipeline_ms=(time.perf_counter() - started) * 1000.0)
        session.last_run = record if run.allocation is not None else None
        return build_allocate_response(record, students, halls, req.algorithm)


# ---- benchmark ---------------------------------------------------------------

def _series(rows: list[dict], x_key: str, algorithms: list[str], y_key: str) -> list[dict]:
    result = []
    for name in algorithms:
        pts = [{"x": r[x_key], "y": r[y_key], "n_courses": r.get("n_courses"), "valid": r["valid"]}
               for r in rows if r["algorithm"] == name]
        result.append({"algorithm": name, "label": ALGORITHM_INFO[name]["label"],
                       "points": sorted(pts, key=lambda p: p["x"])})
    return result


@app.post("/api/benchmark", response_model=BenchmarkResponse)
def benchmark(req: BenchmarkRequest, request: Request) -> BenchmarkResponse:
    """Compare algorithms using ``src.analysis.benchmark``.

    ``density`` mode generates one dataset per course count (same students, fewer
    courses = denser conflict graph) and runs ``benchmark_dataset`` on each.
    ``size`` mode calls ``run_benchmarks`` for the given student counts.
    Runtime is the coloring runtime (the mean of ``repeats`` runs), as defined by the backend.
    """
    config = build_config(req, req.weights)
    algos = tuple(req.algorithms)
    started = time.perf_counter()
    truncated = False
    rows: list[dict] = []
    session = current_session(request)

    with session.lock, job_slot():
        if req.mode == "density":
            for k in req.course_counts:
                if time.perf_counter() - started > MAX_BENCHMARK_SECONDS:
                    truncated = True
                    break
                students = generate_students(req.n_students, k, req.seed)
                halls = generate_halls(max(1, math.ceil(req.n_students / 100)), req.n_students, req.seed)
                graph = build_conflict_graph(students)
                density = graph_summary(graph)["density"]
                rows += benchmark_dataset(students, halls, config, algos, req.repeats, with_breakdown=True,
                                          extra={"density": round(density, 4), "n_courses": k}, graph=graph)
            x_key, x_label = "density", "Conflict-graph density"
        else:
            for size in req.sizes:
                if time.perf_counter() - started > MAX_BENCHMARK_SECONDS:
                    truncated = True
                    break
                rows += run_benchmarks([size], req.repeats, req.seed, config, algos, n_courses=req.n_courses)
            x_key, x_label = "n_students", "Students (V)"
        if not rows:
            raise HTTPException(408, "benchmark budget exhausted before any dataset finished")

        rows = [clean_row(r) for r in rows]
        svgs: dict[str, str] = {}
        if req.mode == "density":
            for y_key, name, title, y_label, log_y in (
                ("runtime_ms", "runtime_vs_density.svg", "Coloring runtime vs conflict-graph density", "Runtime (ms, log scale)", True),
                ("colors_used", "colors_vs_density.svg", "Colors used vs conflict-graph density", "Colors used", False),
            ):
                series = {}
                for s in _series(rows, x_key, list(algos), y_key):
                    series[s["label"]] = [(p["x"], max(p["y"], RUNTIME_FLOOR_MS) if log_y else p["y"]) for p in s["points"]]
                svgs[name] = line_chart_svg(series, title, x_label, y_label, log_y=log_y)
        else:
            svgs = benchmark_plots(rows)
        session.benchmark_svgs, session.benchmark_rows = svgs, rows

    note = ("Runtime is coloring time only (graph building and seat mapping excluded), averaged over "
            f"{req.repeats} run(s). Backtracking is capped at {req.backtracking_node_limit} nodes / "
            f"{req.backtracking_time_limit_seconds} s, so its rows may be bounds rather than optima (see 'completed').")
    return BenchmarkResponse(
        mode=req.mode, x_key=x_key, x_label=x_label, rows=rows,
        series=[BenchmarkSeries(**s) for s in _series(rows, x_key, list(algos), "runtime_ms")],
        plots=list(svgs), truncated=truncated, elapsed_seconds=round(time.perf_counter() - started, 2), note=note)


# ---- export -------------------------------------------------------------------

@app.get("/api/export/{fmt}")
def export(request: Request, fmt: Literal["csv", "html", "svg", "md"], plot: str | None = None) -> Response:
    """Download the latest result.

    csv  seat manifest (src.reporting.csv_export)      html  seating cards (html_export)
    md   summary report (report_builder)               svg   benchmark plot (svg_plots); ?plot=<name>
    """
    session = current_session(request)
    with session.lock:
        if fmt == "svg":
            if not session.benchmark_svgs:
                raise HTTPException(409, "Run a benchmark first (POST /api/benchmark).")
            name = plot or next(iter(session.benchmark_svgs))
            if name not in session.benchmark_svgs:
                raise HTTPException(404, f"unknown plot {name!r}; available: {list(session.benchmark_svgs)}")
            return Response(session.benchmark_svgs[name], media_type="image/svg+xml",
                            headers={"Content-Disposition": f'attachment; filename="{name}"'})

        students, halls = require_dataset(session)
        record = session.last_run
        if record is None or record.run.allocation is None:
            raise HTTPException(409, "No successful allocation to export. Run an allocation first (sessions expire after "
                                f"{SESSION_TTL_SECONDS // 60} minutes of inactivity).")
        allocation = record.run.allocation
        if fmt == "csv":
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "allocation.csv"
                write_allocation_csv(allocation, students, target)
                body, media, name = target.read_bytes(), "text/csv", "seat_manifest.csv"
        elif fmt == "html":
            body, media, name = render_seating_html(halls, allocation, students).encode("utf-8"), "text/html", "seating_chart.html"
        else:
            text = build_summary_report(students, halls, allocation, record.config,
                                        run_info=record.run.run_info(), graph_info=record.run.graph_info)
            body, media, name = text.encode("utf-8"), "text/markdown", "summary_report.md"
        return Response(body, media_type=f"{media}; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---- optional: serve the built frontend from the same process ---------------------

_DIST = ROOT / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
