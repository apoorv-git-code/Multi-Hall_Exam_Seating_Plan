# Viva and Presentation Notes

## Project in one minute

The Multi-Hall Exam Seating Allocation Module models each student as a vertex in a conflict graph. Two vertices are connected when those students share at least one course. Graph coloring groups students so that adjacent vertices receive different colors; a grid-based second phase maps students into real seats and checks physical neighbour relationships. Hard constraints determine validity; soft constraints rank otherwise-valid arrangements.

## Likely questions and answers

**Q1. Why is this a graph problem?**  
Students who share a course must not sit in neighbouring seats. A graph represents that pairwise incompatibility as an edge, allowing coloring algorithms to reason about conflict-free groups.

**Q2. What do vertices, edges, and colors mean?**  
A vertex is a student; an edge joins two students sharing a course; a color is a conflict-free group label. A proper coloring assigns different colors to the endpoints of every edge.

**Q3. Does one color correspond to one hall?**  
No. A color is a logical group, not a physical hall. The grid mapper assigns students to coordinates across one or more halls and must still check every physically adjacent pair.

**Q4. Why not use only greedy coloring?**  
Greedy methods are fast and simple, but their output depends on vertex order and may use more colors than necessary. The project includes multiple heuristics for comparison and bounded backtracking for a more expensive search.

**Q5. First-Fit versus Welsh–Powell?**  
First-Fit colors vertices in the supplied order. Welsh–Powell sorts by descending degree first, placing highly constrained vertices early. It incurs sorting cost and often helps on skewed graphs, but neither heuristic is always optimal.

**Q6. Is backtracking optimal?**  
Only when it completes the search/proof. It uses pruning and symmetry breaking to reduce redundant work. If node or time limits stop it, `completed = false` means the result is the best found so far, not a proven optimum.

**Q7. Why is graph coloring hard?**  
For general graphs, deciding whether a graph is 3-colorable is NP-complete, and finding a minimum coloring is NP-hard. Exponential worst-case search motivates fast heuristics and explicit limits.

**Q8. What are hard and soft constraints?**  
Hard constraints must never be violated: each student gets one seat, seats are unique, blocked/out-of-bounds seats are unused, neighbouring students do not share courses, and capacity is sufficient. Soft constraints are preferences such as avoiding same-branch neighbours, consecutive roll numbers, distance-two conflicts, and wasted seats. Lower soft score is better.

**Q9. Why separate hard validity from soft scoring?**  
A low penalty must never compensate for an invalid seating plan. Validity is a gate; soft score compares quality only after hard constraints pass.

**Q10. Why model a hall as a grid?**  
A grid makes physical adjacency explicit and supports irregular layouts through blocked cells. Four-neighbourhood considers up/down/left/right; optional eight-neighbourhood includes diagonals. The chosen policy must match the institution's rules.

**Q11. What does a blocked seat do?**  
It cannot be assigned and is not a neighbour. It acts as a gap rather than connecting seats across it.

**Q12. What is graph density?**  
For a simple undirected graph, `ρ = 2E/[V(V−1)]` for `V > 1`. Higher density means more pairwise course conflicts and usually less freedom for coloring and seating.

**Q13. How do you test correctness?**  
Test data models, graph symmetry/no self-loops, proper coloring of every edge, grid boundaries/blocked seats, hard-constraint violations, numeric soft scores, and integration/reporting/CLI paths. The architectural checker uses Python AST parsing to reject forbidden import dependencies.

**Q14. Why check architecture boundaries?**  
Lower-level reporting code should format supplied metrics rather than import graph or algorithm internals. This reduces coupling, makes tests easier, and keeps dependency direction understandable.

**Q15. What are the limitations?**  
Color count is not a direct guarantee that a particular grid arrangement is feasible. Runtime depends on graph structure; bounded search can stop early; synthetic benchmarks may not represent real course distributions; soft weights encode policy choices.

## Design trade-offs to explain

- **Adjacency lists:** storage `O(V+E)`, efficient for sparse graphs.
- **Greedy heuristics:** predictable, fast, non-optimal.
- **Backtracking:** stronger search, exponential worst case, therefore bounded.
- **Two-phase pipeline:** separates course-conflict grouping from physical seat placement; mapping still requires its own validation.
- **Hard/soft split:** correctness is mandatory, preferences are optimizable.
- **Determinism:** stable ordering and fixed seeds aid reproducibility.
- **Standard library:** lowers setup burden and keeps algorithms transparent for a DAA defense.

## Demo checklist

1. Show input CSV schema and a small example.
2. Explain one shared-course pair becoming an edge.
3. Run at least two coloring heuristics and compare colors/runtime.
4. Show a hall grid with a blocked seat and its neighbour rule.
5. Demonstrate a hard violation and its validation message.
6. Show report/CSV output and benchmark metrics.
7. Explain measured results only from saved benchmark output; distinguish measured facts from expected trends.
