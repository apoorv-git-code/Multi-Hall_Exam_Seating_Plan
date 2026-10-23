import unittest
from src.models.student import Student
from src.models.hall import Hall
from src.models.allocation import Allocation
from src.graph.conflict_graph import build_conflict_graph

def student(i, courses):
    return Student(str(i), f"S{i}", i, "CSE", frozenset(courses))

class ModelGraphTests(unittest.TestCase):
    def test_hall_capacity_excludes_blocked(self):
        h = Hall("H1", 2, 3, frozenset({(0, 1), (1, 2)}))
        self.assertEqual(h.capacity(), 4)

    def test_allocation_defaults_are_independent(self):
        a, b = Allocation(), Allocation()
        a.seats["1"] = ("H1", 0, 0)
        self.assertEqual(b.seats, {})

    def test_graph_edges_for_shared_courses(self):
        ss = [student(1, {"MATH", "OS"}), student(2, {"OS"}), student(3, {"DB"})]
        g = build_conflict_graph(ss)
        self.assertEqual(g.n, 3)
        self.assertTrue(g.has_edge(0, 1))
        self.assertFalse(g.has_edge(0, 2))
        self.assertFalse(g.has_edge(1, 2))
        self.assertEqual(g.num_edges(), 1)

    def test_graph_is_symmetric_without_self_loops(self):
        g = build_conflict_graph([student(1, {"A"}), student(2, {"A"})])
        for v in range(g.n):
            self.assertNotIn(v, g.adj[v])
            for u in g.adj[v]:
                self.assertIn(v, g.adj[u])

if __name__ == "__main__": unittest.main()
