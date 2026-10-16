# Multi-Hall Exam Seating Allocation Using Graph Coloring, Greedy Heuristics, and Backtracking with Pruning

Language: Python 3.10+, standard library only. Algorithms implemented from scratch (see README section 2).
Last updated: Step 1 complete

---

## 1. Current Status

- Active step: **Step 2** (models, data parsing, validation, dataset generator, config)
- Overall: 1 of 11 steps complete

## 2. Completed Files

| Path | Status |
|------|--------|
| `README.md` | Complete (Step 1) |
| `PROGRESS.md` | Complete (Step 1) |

No source code exists yet. The repository folder structure is defined in README section 5.

## 3. Next Steps

1. **Step 2:** `src/models/student.py`, `hall.py`, `allocation.py`; `src/dataio/parser.py`, `validator.py`, `generator.py`; `config/default_config.json`; `__init__.py` files; `.gitignore`.
2. **Step 3:** `src/structures/sorting.py` (merge sort), `src/graph/conflict_graph.py`, `graph_metrics.py`.
3. **Step 4:** `src/algorithms/coloring_result.py`, `greedy_first_fit.py`, `welsh_powell.py`.
4. **Step 5:** `src/algorithms/backtracking.py`.
5. **Step 6:** `src/grid/` modules and `docs/DESIGN.md`.
6. Steps 7 to 11: analysis, reporting, CLI, tests, experiments and docs (see README section 11).

## 4. Data Schemas

**students.csv:** `sap_id` (str, unique), `name` (str), `roll_no` (int), `branch` (str), `courses` (str, codes separated by `;`)

**halls.csv:** `hall_id` (str, unique), `rows` (int), `cols` (int), `blocked` (str, `r:c` separated by `;`, may be empty)

**allocation.csv (output):** `sap_id`, `hall_id`, `row`, `col`, `color`

**benchmark_results.csv (output):** `algorithm`, `n_students`, `n_edges`, `colors_used`, `runtime_ms`, `nodes_explored`, `completed`, `hall_utilisation`, `soft_score`, `valid`

**config/default_config.json (planned keys):**
`neighbourhood` ("4" default), `weights` {`w_same_branch`, `w_consecutive_roll`, `w_distance_two_conflict`, `w_wasted_seat`}, `backtracking` {`node_limit`, `time_limit_seconds`}, `random_seed`, `output_dir`

**Conventions:** seat coordinates are `(row, col)` with `(0, 0)` at front-left. Neighbours are left `(r, c-1)`, right `(r, c+1)`, front `(r-1, c)`, back `(r+1, c)`. Blocked seats are never used and do not link their two sides.

## 5. Planned Interface Contracts (not yet implemented; confirm or update when built)

```python
# src/models/student.py
@dataclass(frozen=True)
class Student:
    sap_id: str
    name: str
    roll_no: int
    branch: str
    courses: frozenset[str]

# src/models/hall.py
@dataclass(frozen=True)
class Hall:
    hall_id: str
    rows: int
    cols: int
    blocked: frozenset[tuple[int, int]]
    def capacity(self) -> int: ...

# src/models/allocation.py
@dataclass
class Allocation:
    seats: dict[str, tuple[str, int, int]]   # sap_id -> (hall_id, row, col)
    colors: dict[str, int]                   # sap_id -> color class

# src/dataio/parser.py
def load_students(path: str) -> list[Student]
def load_halls(path: str) -> list[Hall]
def load_config(path: str) -> dict

# src/graph/conflict_graph.py
class ConflictGraph:
    n: int                      # number of vertices
    adj: list[list[int]]        # adjacency lists by vertex index
    sap_ids: list[str]          # index -> sap_id
def build_conflict_graph(students: list[Student]) -> ConflictGraph

# src/algorithms/coloring_result.py
@dataclass
class ColoringResult:
    colors: list[int]           # color per vertex index
    num_colors: int
    runtime_ms: float
    nodes_explored: int         # 0 for non-backtracking
    completed: bool             # False if a limit stopped the search

# src/algorithms/*.py
def color_greedy_first_fit(graph: ConflictGraph, order: list[int] | None = None) -> ColoringResult
def color_welsh_powell(graph: ConflictGraph) -> ColoringResult
def color_backtracking(graph: ConflictGraph, node_limit: int, time_limit_seconds: float) -> ColoringResult

# src/structures/sorting.py
def merge_sort(items: list, key=None, reverse: bool = False) -> list

# src/grid/*.py
def get_neighbors(hall: Hall, row: int, col: int) -> list[tuple[int, int]]
def map_colors_to_seats(students: list[Student], graph: ConflictGraph, result: ColoringResult, halls: list[Hall], config: dict) -> Allocation
def validate_allocation(allocation: Allocation, students: list[Student], halls: list[Hall]) -> list[str]   # empty list = valid
def compute_soft_score(allocation: Allocation, students: list[Student], halls: list[Hall], weights: dict) -> float
```

## 6. Decisions Log

1. Language: Python 3.10+, standard library only (chosen for readability and fast iteration).
2. No `sorted()`, `.sort()`, `heapq`, `bisect`, or `itertools` inside `algorithms/`, `graph/`, `grid/`. Custom merge sort is used instead.
3. Plots are hand-written SVG and HTML. No plotting library.
4. Model: Phase 1 colors the conflict graph. Phase 2 maps color groups onto hall grids, validates adjacency, repairs boundaries with local backtracking, and leaves buffer seats when needed. Details go in `docs/DESIGN.md` at Step 6.
5. Branch and bound is not used (may be outside the syllabus). Backtracking uses pruning only. DSATUR is an optional extension.
6. Default neighbourhood is 4-direction (left, right, front, back). Diagonals are an optional extension.

## 7. Known Issues

None.

## 8. Changelog

- Step 1: Defined repository structure, wrote `README.md` and `PROGRESS.md`.
