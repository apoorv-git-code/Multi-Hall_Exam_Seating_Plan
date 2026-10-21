# DESIGN.md: Phase 2 Seat Mapping

Status: implemented in Step 6. Code: `src/grid/`. This document is the exact
description of what the code does. If the code changes, update this file and log
the change in `PROGRESS.md`.

## 1. Problem

Phase 1 gives every student a color so that students of one color share no
course. Phase 2 must place every student on a physical seat so that:

* H1 to H5 (README section 4.3) always hold. The critical one is **H4**: two
  students on neighbouring seats must not share a course.
* The soft penalty (README section 4.4) is kept low.

Phase 1 alone does not solve Phase 2. Two students of different colors may or may
not conflict, and a hall grid has up to four neighbours per seat. Phase 2 checks
every pair it creates against the conflict graph.

## 2. Inputs and output

| Item | Meaning |
|------|---------|
| `students`, `graph` | Vertex `i` of the conflict graph is `students[i]`. |
| `result` | Phase 1 coloring (`ColoringResult`). Any algorithm works. |
| `halls` | Halls in priority order. |
| `config` | Uses `weights`, `neighbourhood` (default `"4"`), `backtracking.node_limit`. |
| Output | `Allocation(seats, colors)`. Some usable seats stay empty. |

## 3. Seat visiting sequence

All usable seats form one sequence: halls in input order, and inside a hall the
**snake order** (even rows left to right, odd rows right to left, blocked seats
skipped). Consecutive seats in the sequence are physical neighbours, so a color
group laid along the sequence forms a connected strip of the grid.

Seating stops as soon as every student is placed. Seats after that point and
unused halls stay empty. Halls are therefore filled one after another, which
keeps utilisation of the opened halls high.

## 4. Search

A depth-first search walks the sequence, one seat per level.

**Candidates at a seat.** Let `near` be the students already seated on
neighbouring seats (all placed neighbours, in the configured neighbourhood). A
student `v` is *compatible* if the conflict graph has no edge between `v` and any
student in `near`. The search collects up to `K = 8` compatible students, scanning

1. the color class of the most recently seated student first (keeps color groups
   together, so most neighbours are same-color and automatically compatible),
2. then the other classes in ascending color order.

**Ordering of candidates.** Candidates of the current class come first. Inside each
group they are ordered by the soft penalty they would add at that seat
(`adjacent_pair_penalty` for neighbours, `distance_two_pair_penalty` for seats two
away). The order is stable, so ties keep class and vertex order.

**Buffer option.** After the students, the option "leave this seat empty" is
appended, but only if enough seats remain afterwards for all unseated students
(H5). A seat is therefore left empty only when no compatible student exists, or
when backtracking has rejected all students.

**Local backtracking.** If a level has no options left (for example the sequence
ran out of seats while students remain), the search undoes the previous level's
choice and tries its next option. Because empty seats are the last option at each
level, the first path found is the pure greedy path and backtracking only happens
when the greedy path runs short of seats.

**Termination.**

| Outcome | When |
|---------|------|
| Success | every student is seated |
| `InfeasibleAllocationError` | total capacity below the number of students, or the whole search space was exhausted, or more than `S + node_limit` options were tried (S = number of usable seats) |

The result is always checked by `validate_allocation`. If that ever fails the
mapper raises `RuntimeError` (an internal bug, never a data problem).

## 5. Why the result never violates H4

A student is placed only after being checked against every already-seated
neighbour. A pair of neighbouring seats is checked when the later of the two is
filled, so every neighbouring pair is checked exactly once. Neighbours that are
filled later are checked at that time. Backtracking removes placements without
leaving residue (occupancy and class pointers are restored).

## 6. Soft score definitions

`score = w_same_branch * A + w_consecutive_roll * B + w_distance_two_conflict * C + w_wasted_seat * D`

| Symbol | Count |
|--------|-------|
| A | neighbour pairs in the same branch |
| B | neighbour pairs in the same branch with roll numbers differing by exactly 1 |
| C | pairs two seats apart on a row or column (`(r,c)` and `(r,c+2)`, `(r,c)` and `(r+2,c)`) that share a course; the seat in between may be blocked or empty |
| D | wasted seats |

Refinements to the README wording:

* **B compares roll numbers only inside one branch.** Roll numbers of different
  branches are unrelated (the generator numbers them per branch).
* **Wasted seats.** Only halls with at least one student count. An empty usable
  seat in such a hall is a *buffer* if one of its neighbours is occupied, and
  *wasted* otherwise. Buffers are not penalised. Wasted seats are unused capacity
  inside opened halls, for example the unused tail of the last hall.
* All neighbour counts use the configured neighbourhood.

## 7. Complexity

| Part | Time | Space |
|------|------|-------|
| `get_neighbors`, `get_distance_two_seats` | O(1) | O(1) |
| Seat sequence | O(rows x cols) per hall | O(S) |
| Candidate collection at one seat | O(R x deg x log Delta) for R students scanned (R is usually about K) | O(K) |
| Whole mapping, typical (no backtracking) | O(S x (R x deg x log Delta + K log K)) | O(S x K + V) |
| Whole mapping, worst case | exponential in S, capped at `S + node_limit` options | O(S x K + V) |
| `validate_allocation` | O(S x c) | O(V + S) |
| `compute_soft_score` | O(S x c) | O(V + S) |

README section 3.3 lists seat mapping as O(S x c). That bound holds for
validation and scoring. The mapping itself is O(S x R x deg x log Delta) in the
typical case because each seat searches the pool of unseated students.

## 8. Observed behaviour (seed 42, default halls with capacity about 1.25 V)

Welsh-Powell coloring, 4-neighbourhood, default weights.

| Dataset | Colors | Buffers | Wasted | Time |
|---------|--------|---------|--------|------|
| 50 students, 12 courses (3 to 5 each) | 22 | 21 | 3 | under 10 ms |
| 200 students, 12 courses | 87 | 49 | 21 | 10 ms |
| 500 students, 12 courses | 208 | 55 | 81 | 90 ms |
| 1000 students, 12 courses | 401 | 51 | 59 | 340 ms |
| 200 students, 40 courses (1 to 3 each) | 18 | 3 | 67 | 10 ms |
| 1000 students, 60 courses (2 to 4 each) | 67 | 6 | 104 | 30 ms |

The 12-course datasets are extremely dense (about 84 percent of student pairs
conflict), so they need many buffers. Sparse datasets need few.

## 9. Limitations

1. **Candidate cap.** Only `K = 8` compatible students are tried at each seat. On
   instances with more than 8 compatible students the search is not complete, so
   a feasible tight-capacity instance could be reported infeasible. When there are
   at most 8 students the search is complete; Step 6 tests compare it with
   exhaustive search on tiny instances.
2. **Dense data with the 8-neighbourhood.** With diagonals counted, dense
   datasets (such as 200 students and 12 courses with capacity 1.25 V) are
   usually infeasible. The mapper reports this after exhausting the budget, which
   can take several seconds at the default `node_limit`.
3. **Fixed hall order.** Halls are used in input order. Choosing halls by size is
   not done.
4. **Phase 1 independence.** Phase 2 does not need a minimal coloring. A smaller
   color count mainly helps by making color classes larger, which reduces buffers.
5. **8-neighbourhood** is supported by every grid function through the optional
   `neighbourhood` argument. It is an extension and is not part of the default
   experiments.
