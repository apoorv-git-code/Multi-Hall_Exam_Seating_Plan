"""API tests for server.py (run with: python -m unittest discover -s tests -v)."""

import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402


def reset_state():
    """Fresh, empty session store and job slots for every test."""
    server.SESSIONS = server.SessionStore(ttl=3600, max_sessions=50)
    server.JOB_SLOTS = threading.BoundedSemaphore(4)


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        reset_state()
        self.client = TestClient(server.app)

    def generate(self, **kw):
        body = {"n_students": 60, "n_halls": 1, "n_courses": 40, "seed": 7}
        body.update(kw)
        r = self.client.post("/api/dataset/generate", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def allocate(self, **kw):
        r = self.client.post("/api/allocate", json=kw)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


class TestMeta(ApiTestCase):
    def test_health(self):
        r = self.client.get("/api/health").json()
        self.assertEqual(r["status"], "ok")
        self.assertFalse(r["dataset_loaded"])

    def test_algorithms_are_honest(self):
        data = self.client.get("/api/algorithms").json()
        self.assertEqual({a["id"] for a in data["available"]}, {"greedy", "welsh_powell", "backtracking"})
        self.assertEqual([u["id"] for u in data["unavailable"]], ["dsatur"])
        self.assertEqual(set(data["default_weights"]), {"w_same_branch", "w_consecutive_roll",
                                                        "w_distance_two_conflict", "w_wasted_seat"})

    def test_cors_headers(self):
        r = self.client.options("/api/allocate", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5173")


class TestDataset(ApiTestCase):
    def test_generate(self):
        d = self.generate()
        self.assertEqual((d["n_students"], d["n_halls"]), (60, 1))
        self.assertEqual(len(d["students"]), 60)
        self.assertGreaterEqual(d["total_capacity"], 60)
        self.assertTrue(d["students_csv"].startswith("sap_id,name,roll_no,branch,courses"))
        self.assertTrue(d["halls_csv"].startswith("hall_id,rows,cols,blocked"))
        self.assertTrue(0 < d["density"] < 1)

    def test_generate_is_seeded(self):
        self.assertEqual(self.generate()["students_csv"], self.generate()["students_csv"])
        self.assertNotEqual(self.generate()["students_csv"], self.generate(seed=8)["students_csv"])

    def test_fewer_courses_means_denser_graph(self):
        self.assertGreater(self.generate(n_courses=12)["density"], self.generate(n_courses=80)["density"])

    def test_generate_validation(self):
        for bad in ({"n_students": 0}, {"n_students": 99999}, {"n_halls": 0}, {"n_courses": 0}, {"seed": -1}):
            self.assertEqual(self.client.post("/api/dataset/generate", json=bad).status_code, 422, bad)

    def test_sample(self):
        d = self.client.post("/api/dataset/sample").json()
        self.assertGreater(d["n_students"], 0)
        self.assertEqual(self.client.get("/api/dataset").json()["n_students"], d["n_students"])

    def test_get_dataset_without_data(self):
        self.assertEqual(self.client.get("/api/dataset").status_code, 409)

    def test_upload_csv(self):
        files = {"students_file": ("s.csv", (ROOT / "data/sample/students.csv").read_bytes()),
                 "halls_file": ("h.csv", (ROOT / "data/sample/halls.csv").read_bytes())}
        r = self.client.post("/api/dataset/upload", files=files)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["source"], "uploaded CSV")

    def test_upload_bad_csv_is_422_without_leaking_paths(self):
        files = {"students_file": ("s.csv", b"sap_id,name\n1,x\n"), "halls_file": ("h.csv", b"hall_id,rows,cols,blocked\nH1,2,2,\n")}
        r = self.client.post("/api/dataset/upload", files=files)
        self.assertEqual(r.status_code, 422)
        self.assertIn("missing required column", r.json()["detail"])
        self.assertNotIn("/tmp", r.json()["detail"])

    def test_json_load_and_validation(self):
        ok = {"students": [{"sap_id": "A", "name": "a", "roll_no": 1, "branch": "CSE", "courses": ["X"]}],
              "halls": [{"hall_id": "H1", "rows": 1, "cols": 2, "blocked": [], "capacity": 2}]}
        self.assertEqual(self.client.post("/api/dataset/load", json=ok).status_code, 200)
        dup = {**ok, "students": ok["students"] * 2}
        self.assertEqual(self.client.post("/api/dataset/load", json=dup).status_code, 422)

    def test_new_dataset_discards_old_allocation(self):
        self.generate()
        self.allocate()
        self.generate(seed=9)
        self.assertEqual(self.client.get("/api/export/csv").status_code, 409)


class TestAllocate(ApiTestCase):
    def test_requires_dataset(self):
        self.assertEqual(self.client.post("/api/allocate", json={}).status_code, 409)

    def test_every_algorithm_gives_a_complete_valid_plan(self):
        self.generate()
        for name in ("greedy", "welsh_powell", "backtracking"):
            d = self.allocate(algorithm=name)
            self.assertEqual(d["status"], "ok", name)
            self.assertEqual(len(d["seats"]), 60)
            m = d["metrics"]
            self.assertTrue(m["hard_constraints_satisfied"])
            self.assertEqual(m["violations"], [])
            self.assertGreaterEqual(m["colors_used"], m["chromatic_lower_bound"])
            self.assertEqual(m["seated"], 60)

    def test_aliases_and_unavailable_algorithms(self):
        self.generate()
        self.assertEqual(self.allocate(algorithm="LDF")["algorithm"]["id"], "welsh_powell")
        self.assertEqual(self.allocate(algorithm="exact")["algorithm"]["id"], "backtracking")
        r = self.client.post("/api/allocate", json={"algorithm": "dsatur"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("not implemented", r.text)
        self.assertEqual(self.client.post("/api/allocate", json={"algorithm": "magic"}).status_code, 422)

    def test_no_adjacent_seats_share_a_course_checked_from_the_json_alone(self):
        self.generate(n_students=120, n_halls=2, n_courses=40)
        d = self.allocate(algorithm="welsh_powell")
        at = {(s["hall_id"], s["row"], s["col"]): set(s["courses"]) for s in d["seats"]}
        for (h, r, c), courses in at.items():
            for dr, dc in ((0, 1), (1, 0)):
                other = at.get((h, r + dr, c + dc))
                if other is not None:
                    self.assertFalse(courses & other, f"{h} ({r},{c}) shares a course with its neighbour")

    def test_seats_unique_and_not_on_blocked_cells(self):
        self.generate(n_students=100, n_halls=2)
        d = self.allocate()
        blocked = {(h["hall_id"], r, c) for h in d["halls"] for r, c in h["blocked"]}
        coords = [(s["hall_id"], s["row"], s["col"]) for s in d["seats"]]
        self.assertEqual(len(coords), len(set(coords)))
        self.assertFalse(blocked & set(coords))

    def test_heatmap_reconciles_with_backend_score(self):
        self.generate(n_students=100, n_halls=2)
        for nb in ("4", "8"):
            d = self.allocate(neighbourhood=nb)
            self.assertTrue(d["soft"]["heat_reconciles"], nb)
            wasted = sum(1 for e in d["empty_seats"] if e["kind"] == "wasted")
            self.assertEqual(wasted, d["metrics"]["wasted_seats"])
            w = d["soft"]["weights"]
            pair_total = sum(s["penalty"] for s in d["seats"]) / 2
            self.assertAlmostEqual(pair_total + w["w_wasted_seat"] * wasted, d["metrics"]["soft_score"], places=2)

    def test_weights_drive_the_score(self):
        self.generate()
        zero = {k: 0 for k in ("w_same_branch", "w_consecutive_roll", "w_distance_two_conflict", "w_wasted_seat")}
        self.assertEqual(self.allocate(weights=zero)["metrics"]["soft_score"], 0)
        heavy = {**zero, "w_same_branch": 10}
        d = self.allocate(weights=heavy)
        self.assertEqual(d["metrics"]["soft_score"], 10 * d["soft"]["counts"]["same_branch_pairs"])
        self.assertTrue(all(s["penalty"] == 0 or s["penalty"] % 10 == 0 for s in d["seats"]))

    def test_weight_validation(self):
        self.generate()
        self.assertEqual(self.client.post("/api/allocate", json={"weights": {"w_same_branch": -1}}).status_code, 422)
        self.assertEqual(self.client.post("/api/allocate", json={"neighbourhood": "6"}).status_code, 422)
        self.assertEqual(self.client.post("/api/allocate", json={"backtracking_node_limit": 10**9}).status_code, 422)

    def test_metrics_are_consistent(self):
        d = self.generate(n_students=80, n_halls=2)
        a = self.allocate()
        m = a["metrics"]
        capacity = sum(h["capacity"] for h in d["halls"])
        self.assertAlmostEqual(m["capacity_utilisation_pct"], 100 * 80 / capacity, places=1)
        self.assertEqual(sum(c["count"] for c in a["color_classes"]), 80)
        self.assertEqual(len(a["color_classes"]), m["colors_used"])
        self.assertGreaterEqual(m["pipeline_runtime_ms"], m["coloring_runtime_ms"])
        self.assertEqual(sum(h["seated"] for h in a["halls"]), 80)

    def test_proven_chromatic_number(self):
        self.generate(n_students=30, n_courses=60)
        d = self.allocate(algorithm="backtracking")["metrics"]
        if d["search_completed"]:
            self.assertEqual(d["chromatic_number"], d["colors_used"])
            self.assertTrue(d["proven_optimal"])

    def test_dense_instance_reports_infeasible_instead_of_failing(self):
        self.generate(n_students=100, n_halls=1, n_courses=12)
        d = self.allocate(algorithm="greedy", backtracking_node_limit=1000)
        self.assertEqual(d["status"], "infeasible")
        self.assertTrue(d["message"])
        self.assertEqual(d["seats"], [])
        self.assertGreater(d["metrics"]["colors_used"], 0)       # Phase 1 still reported
        self.assertIsNone(d["metrics"]["soft_score"])
        self.assertEqual(self.client.get("/api/export/csv").status_code, 409)

    def test_deterministic(self):
        self.generate()
        a, b = self.allocate(), self.allocate()
        self.assertEqual([s["seat_label"] for s in a["seats"]], [s["seat_label"] for s in b["seats"]])


class TestBenchmark(ApiTestCase):
    def bench(self, **kw):
        body = {"n_students": 40, "course_counts": [60, 30], "repeats": 1,
                "backtracking_node_limit": 2000, "backtracking_time_limit_seconds": 0.5}
        body.update(kw)
        r = self.client.post("/api/benchmark", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_density_mode(self):
        d = self.bench()
        self.assertEqual(d["x_key"], "density")
        self.assertEqual(len(d["rows"]), 2 * 3)
        self.assertEqual({s["algorithm"] for s in d["series"]}, {"greedy", "welsh_powell", "backtracking"})
        for s in d["series"]:
            xs = [p["x"] for p in s["points"]]
            self.assertEqual(xs, sorted(xs))
            self.assertEqual(len(xs), 2)
        for row in d["rows"]:
            self.assertIn("density", row)
            self.assertGreaterEqual(row["runtime_ms"], 0)
        dens = {r["n_courses"]: r["density"] for r in d["rows"]}
        self.assertGreater(dens[30], dens[60])
        self.assertIn("runtime_vs_density.svg", d["plots"])

    def test_algorithm_subset_and_alias(self):
        d = self.bench(algorithms=["ldf", "greedy"])
        self.assertEqual({r["algorithm"] for r in d["rows"]}, {"welsh_powell", "greedy"})

    def test_size_mode(self):
        d = self.bench(mode="size", sizes=[20, 40], n_courses=40)
        self.assertEqual(d["x_key"], "n_students")
        self.assertEqual({r["n_students"] for r in d["rows"]}, {20, 40})

    def test_validation(self):
        for bad in ({"course_counts": [1]}, {"sizes": [5], "mode": "size"}, {"algorithms": ["dsatur"]},
                    {"repeats": 99}, {"algorithms": []}):
            self.assertEqual(self.client.post("/api/benchmark", json=bad).status_code, 422, bad)

    def test_benchmark_does_not_need_or_change_the_loaded_dataset(self):
        self.generate()
        self.bench()
        self.assertEqual(self.client.get("/api/dataset").json()["n_students"], 60)


class TestExport(ApiTestCase):
    def test_exports_require_results(self):
        for fmt in ("csv", "html", "md", "svg"):
            self.assertEqual(self.client.get(f"/api/export/{fmt}").status_code, 409, fmt)

    def test_unknown_format(self):
        self.assertEqual(self.client.get("/api/export/pdf").status_code, 422)

    def test_csv_html_md(self):
        self.generate()
        self.allocate()
        csv = self.client.get("/api/export/csv")
        self.assertEqual(csv.headers["content-type"].split(";")[0], "text/csv")
        self.assertIn("seat_manifest.csv", csv.headers["content-disposition"])
        lines = csv.text.strip().splitlines()
        self.assertEqual(lines[0], "sap_id,hall_id,row,col,color")
        self.assertEqual(len(lines), 61)
        html = self.client.get("/api/export/html")
        self.assertTrue(html.text.startswith("<!DOCTYPE html>"))
        self.assertIn("attachment", html.headers["content-disposition"])
        md = self.client.get("/api/export/md")
        self.assertIn("# Exam Seating Allocation Report", md.text)

    def test_csv_matches_allocate_response(self):
        self.generate()
        a = self.allocate()
        rows = [l.split(",") for l in self.client.get("/api/export/csv").text.strip().splitlines()[1:]]
        got = {r[0]: (r[1], int(r[2]), int(r[3])) for r in rows}
        want = {s["sap_id"]: (s["hall_id"], s["row"], s["col"]) for s in a["seats"]}
        self.assertEqual(got, want)

    def test_svg_after_benchmark(self):
        self.client.post("/api/benchmark", json={"n_students": 30, "course_counts": [50, 25],
                                                 "backtracking_node_limit": 500, "backtracking_time_limit_seconds": 0.2})
        r = self.client.get("/api/export/svg")
        self.assertEqual(r.headers["content-type"], "image/svg+xml")
        self.assertIn("<svg", r.text)
        named = self.client.get("/api/export/svg", params={"plot": "colors_vs_density.svg"})
        self.assertEqual(named.status_code, 200)
        self.assertEqual(self.client.get("/api/export/svg", params={"plot": "nope.svg"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
