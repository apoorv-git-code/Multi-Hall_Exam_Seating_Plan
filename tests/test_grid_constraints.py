import unittest
from src.models.student import Student
from src.models.hall import Hall
from src.models.allocation import Allocation
from src.grid.hall_grid import get_neighbors, usable_seats, snake_order
from src.constraints.constraints import validate_allocation, students_conflict
from src.constraints.scoring import compute_soft_score

def s(i, courses, branch="CSE", roll=None):
    return Student(str(i), str(i), i if roll is None else roll, branch, frozenset(courses))

class GridConstraintTests(unittest.TestCase):
    def test_neighbors_respect_edges_and_blocked_seats(self):
        h = Hall("H", 2, 3, frozenset({(0, 1)}))
        self.assertEqual(get_neighbors(h, 0, 0), [(1, 0)])
        self.assertEqual(len(get_neighbors(h, 1, 1)), 2)
        self.assertEqual(len(usable_seats(h)), 5)
        self.assertEqual(len(snake_order(h)), 5)

    def test_shared_course_detection(self):
        self.assertTrue(students_conflict(s(1, {"OS"}), s(2, {"OS", "DB"})))
        self.assertFalse(students_conflict(s(1, {"OS"}), s(2, {"DB"})))

    def test_hard_constraint_validation(self):
        ss = [s(1, {"OS"}), s(2, {"OS"})]
        h = Hall("H", 1, 2, frozenset())
        a = Allocation(seats={"1": ("H",0,0), "2": ("H",0,1)})
        errors = validate_allocation(a, ss, [h])
        self.assertTrue(any("H4" in e for e in errors), errors)

    def test_valid_nonadjacent_seating(self):
        ss = [s(1, {"OS"}), s(2, {"OS"})]
        h = Hall("H", 1, 3, frozenset())
        a = Allocation(seats={"1": ("H",0,0), "2": ("H",0,2)})
        self.assertEqual(validate_allocation(a, ss, [h]), [])

    def test_soft_score_is_numeric(self):
        ss = [s(1, {"A"}, roll=1), s(2, {"B"}, roll=2)]
        h = Hall("H", 1, 2, frozenset())
        a = Allocation(seats={"1": ("H",0,0), "2": ("H",0,1)})
        weights = {"w_same_branch": 1, "w_consecutive_roll": 2,
                   "w_distance_two_conflict": 3, "w_wasted_seat": 1}
        score = compute_soft_score(a, ss, [h], weights)
        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)

if __name__ == "__main__": unittest.main()
