# Multi-Hall Exam Seating Allocation Using Graph Coloring, Greedy Heuristics, and Backtracking with Pruning

**Course:** Design and Analysis of Algorithms (DAA)
**Type:** Individual course project (50% of internal assessment)
**Implementation language:** Python 3.10+ (standard library only)
**Constraint:** Everything algorithmic is implemented from scratch. No external libraries.

---

## Table of Contents

1. [Project Overview and Objectives](#1-project-overview-and-objectives)
2. [Technology and Library Policy](#2-technology-and-library-policy)
3. [Supported Algorithms and Complexity](#3-supported-algorithms-and-complexity)
4. [System Architecture and Constraints](#4-system-architecture-and-constraints)
5. [Folder Structure Reference](#5-folder-structure-reference)
6. [Build and Execution Instructions](#6-build-and-execution-instructions)
7. [Testing Strategy](#7-testing-strategy)
8. [Experiment Plan](#8-experiment-plan)
9. [Multi-Session Continuity Protocol](#9-multi-session-continuity-protocol)
10. [Development Rules](#10-development-rules)
11. [Roadmap](#11-roadmap)
12. [Academic Integrity Note](#12-academic-integrity-note)

---

## 1. Project Overview and Objectives

### 1.1 Background

During university examinations, students who take the same course are easier to copy from when they sit next to each other. Arranging seats by hand across several halls, each with a different size and layout, is slow and error-prone. This project builds an automated allocation system that places students into exam halls so that students sharing a course are never seated in neighbouring seats.

### 1.2 Objectives

1. Model exam seating as a graph coloring problem plus a 2D grid placement problem.
2. Implement three algorithms from scratch and compare them:
   - Greedy First-Fit coloring
   - Welsh-Powell coloring (degree-ordered greedy)
   - Backtracking with pruning (exact search with limits)
3. Support multiple halls with different capacities, rows, columns, and blocked seats.
4. Enforce hard constraints (never violated) and optimise soft constraints (scored).
5. Measure runtime, colors used, nodes explored, hall utilisation, and arrangement quality on datasets of 50, 200, 500, and 1000+ students.
6. Produce printable seating charts, CSV exports, and a summary report.
7. Provide a full time and space complexity analysis for each algorithm.

### 1.3 Graph Modeling Approach

**Conflict graph** `G = (V, E)`:

- Each student is a vertex.
- An edge `(u, v)` exists if students `u` and `v` share at least one course.
- A proper coloring assigns each student a color (a "group") so that connected students never share a color.
- Each color class is therefore a set of students with pairwise **no shared courses**. Such students can safely sit next to each other.

**Seat grid** for each hall:

- A hall is a `rows x cols` grid. Each cell is a seat. Some seats may be blocked (broken, reserved, or missing).
- Two seats are neighbours if they are directly left, right, front, or back of each other (4-neighbourhood).
- Allocation is valid only if, for every pair of neighbouring occupied seats, the two students are **not** connected in the conflict graph.

### 1.4 Two-Phase Pipeline

| Phase | Input | Output | Purpose |
|-------|-------|--------|---------|
| Phase 1: Coloring | Conflict graph | Color classes (conflict-free groups) | Partition students into groups with no internal conflicts. Fewer colors means more freedom for seating. |
| Phase 2: Seat mapping | Color classes, hall grids, constraints | Seat assignment per student | Place groups on the grids so that no two neighbouring seats hold conflicting students. Validate every adjacency and repair boundary conflicts using local backtracking. If a boundary conflict cannot be repaired, a seat is left empty as a buffer when hall capacity allows. |

The exact Phase 2 placement strategy is documented in `docs/DESIGN.md` when the grid module is built (Step 6) and may be refined there. Any change is logged in `PROGRESS.md`.

### 1.5 NP-Hardness

- Deciding whether a graph can be colored with `k` colors is **NP-complete** for every `k >= 3`.
- Finding the chromatic number (the minimum number of colors) is **NP-hard**.
- The seating problem generalises coloring: when each hall is large enough and neighbourhood constraints dominate, solving it optimally is at least as hard.
- Consequence: no known polynomial-time algorithm finds optimal solutions in general. Greedy heuristics are fast but may use more colors than necessary. Backtracking is exact but exponential in the worst case, so this project caps it with node and time limits and reports the best solution found.

---

## 2. Technology and Library Policy

### 2.1 Language and Tools

- Python 3.10 or newer.
- No `pip install` step. There is no `requirements.txt` because there are no dependencies.

### 2.2 Allowed (standard library, non-algorithmic use only)

`os`, `sys`, `time`, `random` (seeded dataset generation only), `csv`, `json`, `argparse`, `pathlib`, `dataclasses`, `typing`, `math` (basic arithmetic only), `unittest`, `datetime`, `html` (escaping only).

Built-in `list`, `dict`, `set`, `tuple`, and `str` types are allowed as basic containers.

### 2.3 Not Allowed

| Category | Banned |
|----------|--------|
| Third-party | `networkx`, `numpy`, `scipy`, `pandas`, `matplotlib`, `sympy`, `ortools`, `sortedcontainers` |
| Standard-library algorithm helpers in core modules | `heapq`, `bisect`, `itertools`, `functools.cmp_to_key` |
| Built-in sorting in core modules | `sorted()` and `list.sort()` inside `src/algorithms/`, `src/graph/`, and `src/grid/` |

All sorting required by the algorithms (for example, ordering vertices by degree in Welsh-Powell) uses the custom implementation in `src/structures/sorting.py`. Plots are generated by hand-written SVG and HTML, so no plotting library is used.

`scripts/check_imports.py` and `tests/test_no_banned_imports.py` scan the source tree and fail if a banned import appears.

---

## 3. Supported Algorithms and Complexity

### 3.1 Notation

| Symbol | Meaning |
|--------|---------|
| `V` | Number of students (vertices) |
| `E` | Number of conflict edges |
| `Δ` | Maximum vertex degree in the conflict graph |
| `m` | Number of colors allowed or used |
| `S` | Total number of usable seats across all halls |
| `H` | Number of halls |
| `c` | Maximum number of courses per student (small constant) |
| `n_k` | Number of students enrolled in course `k` |

### 3.2 Comparison Table

| Algorithm | Strategy | Time (worst case) | Extra space | Colors guarantee | Optimal? |
|-----------|----------|-------------------|-------------|------------------|----------|
| **Greedy First-Fit** | Process vertices in the given order. Give each vertex the smallest color not used by its neighbours. | `O(V + E)` using a marker array for forbidden colors | `O(V)` (graph storage is `O(V + E)`) | At most `Δ + 1` colors | No. Result depends on vertex order. |
| **Welsh-Powell** | Sort vertices by degree (descending), then apply greedy first-fit in that order. | `O(V log V + E)` with a comparison sort (custom merge sort) | `O(V)` | At most `Δ + 1` colors. Tighter bound is `max over i of min(d_i + 1, i)`. | No, but usually uses fewer colors than plain first-fit. |
| **Backtracking with Pruning** | Depth-first search that assigns colors vertex by vertex, rejects any assignment that conflicts with a neighbour, and cuts branches early. | `O(m^V · Δ)` for a fixed `m` (exponential). Finding the minimum colors by trying `m = 1, 2, ...` repeats this search. | `O(V)` recursion stack (graph storage is `O(V + E)`) | Exact when the search completes. With node or time limits, returns the best coloring found so far. | Yes, when it completes within limits. |

### 3.3 Supporting Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Conflict graph construction | `O(Σ n_k²)`, at most `O(V²)` | `O(V + E)` | Group students by course, then connect every pair within a course. Dense when courses are large. |
| Custom merge sort (degree ordering) | `O(V log V)` | `O(V)` | Stable. Used by Welsh-Powell. |
| Seat mapping (Phase 2 placement) | `O(S · c)` | `O(S)` | Each seat has at most 4 neighbours. Each conflict test compares course lists. |
| Allocation validation | `O(S · c)` | `O(1)` extra | Checks every neighbouring pair of occupied seats. |
| Soft-constraint scoring | `O(S · c)` | `O(1)` extra | Penalty sum over neighbouring pairs. |

### 3.4 Pruning Techniques in Backtracking

1. **Consistency check:** reject a color if any already-colored neighbour has it.
2. **Symmetry breaking:** the first vertex always gets color 0, and a vertex may use a new color only if it is exactly one more than the highest color used so far. This removes permutations of the same partition.
3. **Vertex ordering:** process high-degree vertices first (largest-first), so conflicts appear early and branches die sooner.
4. **Best-known cutoff:** abandon a branch as soon as the colors used reach the best complete solution found so far.
5. **Safety limits:** configurable node limit and time limit, so large inputs finish. A run that hits a limit is flagged as incomplete.

Pruning improves practical speed but does **not** change the worst-case exponential bound.

---

## 4. System Architecture and Constraints

### 4.1 Data Flow

```
 students.csv   halls.csv   config.json
      |             |            |
      v             v            v
 +--------------------------------------+
 |  dataio: parser + validator          |
 +--------------------------------------+
      |                      |
      v                      v
 +--------------+     +---------------+
 | conflict     |     | hall grids    |
 | graph (G)    |     | (rows x cols) |
 +--------------+     +---------------+
      |                      |
      v                      |
 +--------------------+      |
 | Phase 1: coloring  |      |
 |  - Greedy FF       |      |
 |  - Welsh-Powell    |      |
 |  - Backtracking    |      |
 +--------------------+      |
      |                      |
      +----------+-----------+
                 v
        +-------------------+
        | Phase 2: seat     |
        | mapper + repair   |
        +-------------------+
                 |
                 v
        +-------------------+
        | constraint checks |
        | + soft scoring    |
        +-------------------+
                 |
                 v
 +----------------------------------------+
 | reporting: text chart, CSV, HTML, SVG, |
 | summary report, benchmark plots        |
 +----------------------------------------+
```

### 4.2 Grid Model and Spatial Constraints

- Each hall has `rows` and `cols`. Seat coordinates are `(row, col)` with `(0, 0)` at the front-left.
- **Neighbours of `(r, c)`:**
  - Left: `(r, c - 1)`
  - Right: `(r, c + 1)`
  - Front: `(r - 1, c)`
  - Back: `(r + 1, c)`
- Cells outside the grid are ignored.
- **Blocked seats** are never assigned and are treated as gaps. A blocked seat does not link its two sides, so two students on either side of a blocked seat are not neighbours.
- Neighbourhood type is configurable. The default is the 4-neighbourhood above. A diagonal option (8-neighbourhood) is reserved as an optional extension.
- Hall capacity = `rows x cols - blocked seats`. Different halls may have different dimensions.

### 4.3 Hard Constraints (never violated)

| ID | Constraint |
|----|------------|
| H1 | Every student is assigned to exactly one seat in exactly one hall. |
| H2 | A seat holds at most one student. |
| H3 | No blocked seat is used. |
| H4 | No two neighbouring occupied seats (left, right, front, back) hold students who share a course. |
| H5 | Hall capacity is respected. Total seats must be at least the number of students, otherwise the system reports infeasibility. |

An allocation that violates any hard constraint is rejected by the validator and reported as invalid.

### 4.4 Soft Constraints (scored, minimised)

Soft constraints improve quality but may be relaxed when the hard constraints leave no alternative.

| ID | Soft constraint | Default weight key |
|----|-----------------|--------------------|
| S1 | Avoid neighbours from the same branch. | `w_same_branch` |
| S2 | Avoid neighbours with consecutive roll numbers. | `w_consecutive_roll` |
| S3 | Avoid students sharing a course within two seats of each other in the same row or column (distance 2 along a line). | `w_distance_two_conflict` |
| S4 | Penalise unused seats beyond what buffering requires (encourages high hall utilisation). | `w_wasted_seat` |

**Penalty score** (lower is better):

```
score = w_same_branch * (#neighbour pairs, same branch)
      + w_consecutive_roll * (#neighbour pairs, consecutive roll numbers)
      + w_distance_two_conflict * (#pairs at distance 2 sharing a course)
      + w_wasted_seat * (#wasted seats)
```

Weights are read from `config/default_config.json`.

### 4.5 Data Formats (planned schemas)

**`students.csv`**

| Column | Type | Description |
|--------|------|-------------|
| `sap_id` | string | Unique student ID (SAP ID) |
| `name` | string | Student name |
| `roll_no` | integer | Roll number |
| `branch` | string | Branch or department code |
| `courses` | string | Course codes separated by `;` (for example `CS201;MA101`) |

**`halls.csv`**

| Column | Type | Description |
|--------|------|-------------|
| `hall_id` | string | Unique hall ID |
| `rows` | integer | Number of rows |
| `cols` | integer | Number of columns |
| `blocked` | string | Blocked seats as `r:c` separated by `;` (empty if none) |

**`allocation.csv` (output)**

| Column | Type | Description |
|--------|------|-------------|
| `sap_id` | string | Student ID |
| `hall_id` | string | Assigned hall |
| `row` | integer | Row index |
| `col` | integer | Column index |
| `color` | integer | Color class from Phase 1 |

**`benchmark_results.csv` (output)**

| Column | Description |
|--------|-------------|
| `algorithm` | `greedy`, `welsh_powell`, or `backtracking` |
| `n_students` | Input size `V` |
| `n_edges` | Conflict edges `E` |
| `colors_used` | Colors in the final coloring |
| `runtime_ms` | Average runtime in milliseconds |
| `nodes_explored` | Search nodes (backtracking only, otherwise 0) |
| `completed` | Whether the search finished within limits |
| `hall_utilisation` | Seated students divided by total capacity |
| `soft_score` | Penalty score of the allocation |
| `valid` | Whether all hard constraints hold |

---

## 5. Folder Structure Reference

```
exam-seating-allocation/
├── README.md
├── PROGRESS.md
├── .gitignore
├── main.py
├── config/
│   └── default_config.json
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── student.py
│   │   ├── hall.py
│   │   └── allocation.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── conflict_graph.py
│   │   └── graph_metrics.py
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── coloring_result.py
│   │   ├── greedy_first_fit.py
│   │   ├── welsh_powell.py
│   │   └── backtracking.py
│   ├── structures/
│   │   ├── __init__.py
│   │   └── sorting.py
│   ├── grid/
│   │   ├── __init__.py
│   │   ├── hall_grid.py
│   │   ├── seat_mapper.py
│   │   ├── constraints.py
│   │   └── scoring.py
│   ├── dataio/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   ├── parser.py
│   │   └── validator.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── metrics.py
│   │   └── benchmark.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── menu.py
│   │   └── prompts.py
│   └── reporting/
│       ├── __init__.py
│       ├── text_chart.py
│       ├── csv_export.py
│       ├── html_export.py
│       ├── svg_plots.py
│       └── report_builder.py
├── data/
│   ├── sample/
│   ├── generated/
│   └── results/
├── output/
│   ├── seating_charts/
│   ├── plots/
│   └── reports/
├── tests/
│   ├── __init__.py
│   ├── test_sorting.py
│   ├── test_parser.py
│   ├── test_generator.py
│   ├── test_conflict_graph.py
│   ├── test_greedy_first_fit.py
│   ├── test_welsh_powell.py
│   ├── test_backtracking.py
│   ├── test_hall_grid.py
│   ├── test_seat_mapper.py
│   ├── test_constraints.py
│   ├── test_reporting.py
│   └── test_no_banned_imports.py
├── docs/
│   ├── DESIGN.md
│   ├── COMPLEXITY_ANALYSIS.md
│   ├── EXPERIMENTS.md
│   ├── VIVA_NOTES.md
│   └── report/
└── scripts/
    ├── generate_dataset.py
    ├── run_benchmarks.py
    ├── run_demo.py
    └── check_imports.py
```

### 5.1 Separation of Concerns

| Folder | Responsibility | Depends on |
|--------|----------------|------------|
| `src/models/` | Plain data classes: `Student`, `Hall`, `Allocation`. No logic beyond simple accessors. | nothing |
| `src/structures/` | Hand-written data structures and utilities used by algorithms (custom merge sort). | nothing |
| `src/graph/` | Builds the conflict graph from student enrolments. Computes degree and density metrics. | `models` |
| `src/algorithms/` | **Core algorithms:** Greedy First-Fit, Welsh-Powell, Backtracking with Pruning, plus the shared result type. | `graph`, `structures` |
| `src/grid/` | **Grid and hall mapping:** neighbour logic, Phase 2 seat placement, hard-constraint validation, soft-constraint scoring. | `models`, `graph` |
| `src/dataio/` | **Data generation and parsing:** CSV and JSON readers, input validation, seeded synthetic dataset generator. | `models` |
| `src/analysis/` | Metrics collection and benchmarking harness (timing, repeats, result rows). | `algorithms`, `grid` |
| `src/cli/` | **CLI interface:** menu-driven interaction and input prompts. No algorithm logic. | everything below it |
| `src/reporting/` | **Visualization and export:** text seating charts, CSV, printable HTML, hand-written SVG plots, summary report. | `models`, `analysis` |
| `data/` | Input datasets (`sample/`, `generated/`) and benchmark results (`results/`). | n/a |
| `output/` | Generated charts, plots, and reports (git-ignored). | n/a |
| `tests/` | Unit and integration tests using `unittest`. | all `src/` |
| `docs/` | Design notes, complexity analysis, experiment write-up, viva notes, final report material. | n/a |
| `scripts/` | Thin runnable entry points for dataset generation, benchmarks, demo, and import checking. | `src/` |

### 5.2 Quick Scaffold

Bash (Linux, macOS, Git Bash):

```bash
mkdir -p exam-seating-allocation && cd exam-seating-allocation
mkdir -p config docs/report scripts tests data/sample data/generated data/results \
         output/seating_charts output/plots output/reports \
         src/models src/graph src/algorithms src/structures src/grid \
         src/dataio src/analysis src/cli src/reporting
```

PowerShell (Windows):

```powershell
New-Item -ItemType Directory -Force -Path exam-seating-allocation | Out-Null
Set-Location exam-seating-allocation
"config","docs/report","scripts","tests","data/sample","data/generated","data/results",
"output/seating_charts","output/plots","output/reports","src/models","src/graph",
"src/algorithms","src/structures","src/grid","src/dataio","src/analysis","src/cli",
"src/reporting" | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }
```

---

## 6. Build and Execution Instructions

> **Status note:** The commands below describe the final interface. Each command becomes valid when its module is completed. `PROGRESS.md` records which modules exist.

### 6.1 Prerequisites

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/).
2. Verify the installation:

```bash
python --version
```

On Windows, use `py --version` and `py` in place of `python` if `python` is not recognised.

3. No packages need to be installed.

### 6.2 Compile Check

Python compiles to bytecode automatically. To check every source file for syntax errors without running anything:

```bash
python -m compileall src scripts main.py
```

### 6.3 Generate a Dataset

```bash
python scripts/generate_dataset.py --students 200 --courses 12 --halls 4 --seed 42 --out data/generated/
```

This writes `students.csv` and `halls.csv` into `data/generated/`. The same seed always reproduces the same dataset.

### 6.4 Run the Interactive Menu

```bash
python main.py
```

The menu lets you load data, choose an algorithm, run the allocation, view the seating chart, and export results.

### 6.5 Run Non-Interactively

```bash
python main.py --students data/generated/students.csv --halls data/generated/halls.csv --algorithm welsh_powell --out output/
```

Valid values for `--algorithm` are `greedy`, `welsh_powell`, and `backtracking`.

### 6.6 Run Benchmarks

```bash
python scripts/run_benchmarks.py --sizes 50 200 500 1000 --repeats 5
```

Writes `data/results/benchmark_results.csv` and SVG plots into `output/plots/`.

### 6.7 Demo Run

```bash
python scripts/run_demo.py
```

Runs all three algorithms on a small sample dataset and prints a side-by-side comparison.

### 6.8 Run Tests and Import Check

```bash
python -m unittest discover -s tests -v
python scripts/check_imports.py
```

---

## 7. Testing Strategy

| Level | What is verified |
|-------|------------------|
| Unit: structures | Custom merge sort returns sorted, stable output on empty, single, duplicate, and reversed inputs. |
| Unit: parsing | Valid files load correctly. Malformed rows, duplicate SAP IDs, and bad seat coordinates are rejected with clear errors. |
| Unit: conflict graph | Students sharing a course are connected. Students with disjoint courses are not. The graph is symmetric. |
| Unit: algorithms | Every coloring is proper (no edge has equal colors). Color counts respect the `Δ + 1` bound. Backtracking matches known chromatic numbers on small graphs such as odd cycles and complete graphs. |
| Unit: grid | Neighbour lists are correct at corners, edges, and around blocked seats. |
| Constraint tests | The validator accepts valid allocations and rejects each kind of hard-constraint violation. |
| Integration | The full pipeline produces a valid allocation for generated datasets of several sizes. |
| Static | No banned import appears in the source tree. |

---

## 8. Experiment Plan

| Experiment | Variable | Measured |
|------------|----------|----------|
| E1: Scalability | `V = 50, 200, 500, 1000+` | Runtime of each algorithm |
| E2: Solution quality | Same datasets | Colors used by each algorithm |
| E3: Density sensitivity | Courses per student, course size | Edges `E`, colors, runtime |
| E4: Backtracking limits | Node limit and time limit | Completion rate, best colors found |
| E5: Hall utilisation | Hall sizes and counts | Seats used, buffer seats, soft score |
| E6: Heuristic failure | Crafted adversarial vertex orderings | Cases where greedy uses more colors than optimal |

Each timing is averaged over repeated runs with fixed seeds. Results go to `data/results/` and plots to `output/plots/`. The discussion is written in `docs/EXPERIMENTS.md`.

---

## 9. Multi-Session Continuity Protocol

This project is built across many AI sessions and possibly different accounts. The AI has no memory between sessions, so **`PROGRESS.md` is the single source of truth** for project state.

### 9.1 What `PROGRESS.md` Contains

1. **Current status:** active step and overall completion.
2. **Completed files and modules:** exact paths.
3. **Active step and next steps:** what to build next, in order.
4. **Data schemas:** file formats and in-memory structures.
5. **Key function and class signatures:** the contracts other modules depend on.
6. **Decisions log:** design choices and reasons.
7. **Known issues:** open bugs or limitations.
8. **Changelog:** one line per completed step.

### 9.2 Starting a New Session

Open a new chat and paste the following, in this order:

1. The **session starter prompt** below.
2. The full current `PROGRESS.md`.
3. The full source of any already-written file that the active step imports. Paste only the files needed, not the whole repository.

**Session starter prompt:**

```text
I am building a Design and Analysis of Algorithms course project:
"Multi-Hall Exam Seating Allocation Using Graph Coloring, Greedy Heuristics,
and Backtracking with Pruning". Language: Python 3.10+, standard library only.
Everything algorithmic is implemented from scratch (no external libraries; see
the library policy in README.md section 2).

Rules:
1. Zero truncation. No placeholders, no "rest of the code here", no partial
   files. Every file must be complete and ready to save.
2. Build only the active step in PROGRESS.md. Do not rewrite finished modules.
3. Keep every function signature and data schema in PROGRESS.md unchanged. If a
   change is unavoidable, say so explicitly and update PROGRESS.md.
4. Use docstrings, type hints, and clear comments. Include complexity notes in
   algorithm files.
5. At the end of your response, give an updated PROGRESS.md snippet covering
   completed files, active step, next steps, data schemas, and key signatures.

Below are PROGRESS.md and the files this step depends on.
```

### 9.3 Ending a Session

1. Save every generated file at the path given in `PROGRESS.md`.
2. Run the relevant tests and `python scripts/check_imports.py`.
3. Replace the contents of `PROGRESS.md` with the updated version from the AI response.
4. Commit with a message such as `step-4: greedy first-fit and welsh-powell`.

### 9.4 Resolving Mismatches

- If the code and `PROGRESS.md` disagree, **the code on disk is the truth**. Correct `PROGRESS.md` before the next session.
- If a test fails after a session, paste the failing test output and the relevant file into the next session before moving on.
- Never ask a new session to "continue from memory". Always supply `PROGRESS.md`.

---

## 10. Development Rules

1. **Zero truncation:** no placeholders, no ellipsis comments, no partial implementations.
2. **Modular builds:** one module or small group of modules per prompt.
3. **No external libraries:** see section 2.
4. **Type hints and docstrings** on every public function and class.
5. **Complexity comments** at the top of each algorithm function, stating time and space.
6. **Deterministic behaviour:** all randomness is seeded.
7. **Separation of concerns:** the CLI never contains algorithm logic. Algorithms never print.
8. **State management:** update `PROGRESS.md` at the end of every step.

---

## 11. Roadmap

| Step | Deliverable | Status |
|------|-------------|--------|
| 1 | Directory structure, `README.md`, `PROGRESS.md` | Complete |
| 2 | `models/`, `dataio/` (parser, validator, generator), `config/default_config.json` | Pending |
| 3 | `structures/sorting.py`, `graph/` (conflict graph, metrics) | Pending |
| 4 | `algorithms/` coloring result, Greedy First-Fit, Welsh-Powell | Pending |
| 5 | `algorithms/backtracking.py` (pruning, limits) | Pending |
| 6 | `grid/` (hall grid, constraints, seat mapper, scoring), `docs/DESIGN.md` | Pending |
| 7 | `analysis/` (metrics, benchmark harness) | Pending |
| 8 | `reporting/` (text chart, CSV, HTML, SVG plots, report builder) | Pending |
| 9 | `cli/` and `main.py`, scripts | Pending |
| 10 | Tests, import checker | Pending |
| 11 | Experiments and `docs/` (complexity analysis, experiments, viva notes) | Pending |

---

## 12. Academic Integrity Note

This is an individual project. AI tools may be used for ideas and code generation as permitted by the course, but the student must understand, test, and be able to explain every algorithm and line of code in a viva. No external algorithmic library files are used anywhere in this repository.
