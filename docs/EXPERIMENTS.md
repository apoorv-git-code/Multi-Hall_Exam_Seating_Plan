# Experimental Results and Benchmark Protocol

## Scope and reproducibility

The project README proposes student counts of 50, 200, 500, and 1,000+, with Greedy First-Fit, Welsh–Powell, and bounded backtracking compared. A result is meaningful only when dataset seed, course-generation distribution, hall layouts, blocked-seat pattern, Python version, and algorithm limits are held constant or recorded.

**Evidence status:** The supplied archive contains benchmark scripts (`benchmark.py`, `run_benchmarks.py`) but no checked-in, machine-generated benchmark-results file that establishes numeric findings. Therefore this document does not invent measured milliseconds, color counts, or scores. Run the commands below in the project environment and use the emitted CSV/output as the empirical table for a defense.

## Experiment matrix

| Case | Students | Hall layout | Target conflict density | Purpose |
|---|---:|---|---|---|
| A | 50 | one compact hall, low blocking | low | small-input baseline |
| B | 200 | two medium halls, scattered blocked seats | low / medium | scaling and hall boundaries |
| C | 500 | several halls with unequal capacities | medium | realistic multi-hall load |
| D | 1,000+ | multiple larger halls, mixed blocked seats | medium / high | stress test and feasibility |
| E | fixed `V` | same capacity, varied blocked-seat layout | fixed student graph | isolate grid geometry effects |

Treat density as `ρ = 2E / (V(V−1))` for `V > 1`; for fewer than two vertices define it as zero. If the dataset generator does not expose a density control, report the observed density rather than claiming the target was achieved.

## Metrics to capture

- Graph: `V`, `E`, density `ρ`, maximum degree.
- Coloring: algorithm, colors used, runtime in milliseconds, nodes explored, `completed`.
- Allocation: valid/invalid, hard-constraint violation count, hall utilization, soft score.
- Reproducibility: random seed, Python version, OS, configuration and time/node limits.

## Expected qualitative hypotheses (not measured findings)

1. First-Fit should have low overhead and approximately linear graph-scan cost after graph construction.
2. Welsh–Powell adds sorting overhead (`O(V log V)`) and may use fewer colors on degree-skewed graphs; it is not guaranteed to beat First-Fit on every input.
3. Backtracking can improve color count on small/moderate graphs, but runtime can rise sharply and limits may yield `completed = false`.
4. Denser conflict graphs generally have more edges and fewer compatible seat choices, increasing coloring difficulty and potentially making allocation infeasible.
5. Equal total capacity does not imply equal feasibility: blocked seats and adjacency topology can affect placement and buffer-seat availability.

These are hypotheses based on algorithm design. Validate them against recorded runs before presenting them as observations.

## Suggested run procedure

1. Use fixed seeds and save the exact generated student/hall CSVs.
2. Run every coloring algorithm against the same student graph.
3. Repeat each case at least five times for timing; report median and range, while noting deterministic algorithm outputs.
4. Check all hard constraints for every produced allocation. Never compare soft scores for invalid allocations as if they were valid solutions.
5. Export results to CSV and include the raw artifact with the submission. Report failed/infeasible runs instead of silently dropping them.

## Results table template

| Case | Algorithm | V | E | ρ | Colors | Median ms | Nodes | Completed | Valid | Soft score |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|
| A–E | fill from benchmark output | | | | | | | | | |

No empirical values are populated until the benchmark scripts have actually run and produced evidence.
