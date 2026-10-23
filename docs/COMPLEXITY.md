# Complexity Analysis

Let `V` be students/vertices, `E` conflict edges, `Δ` maximum degree, `C` maximum courses per student, `H` halls, and `S` total physical grid cells. Let `U ≤ S` be usable seats. Complexity excludes CSV parsing and output I/O unless noted.

## Conflict graph construction

The implementation compares student course sets and builds an undirected adjacency list. With pairwise student comparisons, expected time is `O(V² · C)` (set intersection/disjointness is bounded by course-set size); adjacency storage is `O(V + E)`. In the worst case the graph is dense and `E = Θ(V²)`. `degree(v)` and `has_edge` depend on their implementation; adjacency-list membership is linear in `degree(v)` unless an auxiliary set is maintained.

## Coloring

| Algorithm | Time | Extra space | Notes |
|---|---:|---:|---|
| Greedy First-Fit | `O(V + E)` for the fixed order | `O(V)` | Scans each adjacency list once and maintains color/marker arrays. Color count is at most `Δ + 1`. |
| Welsh–Powell | `O(V log V + E)` | `O(V)` | Stable merge sort orders vertices by descending degree, followed by greedy coloring. |
| Backtracking with pruning | `O(k^V · (V + E))` upper-bound style; exponential worst case | `O(V + E)` | `k` is the candidate color range; pruning, symmetry breaking, clique lower bound, and limits improve practical behavior but not the worst-case guarantee. Node/time limits can terminate search early. |

A returned coloring is checked as proper when every edge `(u,v)` has different endpoint colors. Greedy heuristics are fast but not guaranteed minimum. Backtracking is exact only when it completes its proof/search; a limit-stopped result is the best known solution, not necessarily optimal.

## Grid and allocation

- Neighbour lookup: `O(1)` with a fixed four/eight offset list; returned list is bounded by 4 or 8, so auxiliary space is `O(1)`.
- Enumerating usable seats or snake order: `O(S)` time and `O(U)` output space.
- Hard-constraint validation: `O(V + S)` expected lookup construction and traversal, assuming bounded-degree neighbourhood and expected constant-time dictionaries. Course conflict checks add up to `O(C)` per examined adjacent pair, yielding `O(S·C)` as a conservative bound.
- Soft score: `O(S·C)` conservative, because each local neighbour/distance-two relation is examined a bounded number of times and shared-course checks inspect course sets. Auxiliary maps are `O(V + H)`; the allocation and hall definitions are input storage.
- Seat mapping uses bounded-depth/local backtracking, but the search may still explore many candidate assignments. If `B` is the configured option/node cap and each candidate validation costs `O(1)` neighbour checks plus course comparison, its capped search work is roughly `O(B·C)` beyond seat/index preparation. Without a cap, combinatorial worst-case search can be exponential in `V`.

## Reporting and CLI

Building lookup tables and a per-hall summary is linear in students and seats, `O(V + S)` excluding formatting/output size. CSV/HTML/Markdown writing is linear in emitted output bytes. CLI argument parsing is `O(1)` relative to input size; loading and running the selected pipeline dominate.

## Interpretation

These are asymptotic bounds, not runtime promises. Actual timing depends on graph density, course overlap, hall topology, Python/runtime version, and whether backtracking hits a limit. Benchmark output should record seed, algorithm, `V`, `E`, colors, runtime, explored nodes, completion, validity, and score so comparisons are reproducible.
