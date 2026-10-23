import unittest
from src.models.student import Student
from src.graph.conflict_graph import build_conflict_graph
from src.algorithms.greedy_first_fit import color_greedy_first_fit
from src.algorithms.welsh_powell import color_welsh_powell
from src.algorithms.backtracking import color_backtracking

def s(i, course):
    return Student(str(i), str(i), i, "CSE", frozenset(course))

def valid_coloring(graph, colors):
    return len(colors) == graph.n and all(colors[u] != colors[v]
        for u in range(graph.n) for v in graph.adj[u])

class ColoringTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_conflict_graph([s(0, {"A"}), s(1, {"A","B"}),
                                           s(2, {"B"}), s(3, {"C"})])

    def test_greedy_produces_proper_coloring(self):
        r = color_greedy_first_fit(self.graph)
        self.assertTrue(valid_coloring(self.graph, r.colors))
        self.assertEqual(r.num_colors, len(set(r.colors)))

    def test_welsh_powell_produces_proper_coloring(self):
        r = color_welsh_powell(self.graph)
        self.assertTrue(valid_coloring(self.graph, r.colors))

    def test_backtracking_respects_limits_and_is_valid(self):
        r = color_backtracking(self.graph, node_limit=10000, time_limit_seconds=1.0)
        self.assertTrue(valid_coloring(self.graph, r.colors))
        self.assertLessEqual(r.num_colors, color_welsh_powell(self.graph).num_colors)

    def test_empty_graph(self):
        g = build_conflict_graph([])
        self.assertEqual(color_welsh_powell(g).num_colors, 0)

if __name__ == "__main__": unittest.main()
