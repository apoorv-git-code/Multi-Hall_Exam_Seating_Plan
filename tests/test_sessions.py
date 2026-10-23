"""Per-session state tests: isolation, cookie security, expiry, caps, concurrency."""

import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402

GEN = {"n_students": 40, "n_halls": 1, "n_courses": 40, "seed": 3}


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class SessionTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        server.SESSIONS = server.SessionStore(ttl=100, max_sessions=3, clock=self.clock)
        server.JOB_SLOTS = threading.BoundedSemaphore(4)
        self.a, self.b = TestClient(server.app), TestClient(server.app)

    def load(self, client, **kw):
        r = client.post("/api/dataset/generate", json={**GEN, **kw})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


class TestIsolation(SessionTestCase):
    def test_sessions_do_not_see_each_others_data(self):
        self.load(self.a)
        self.assertEqual(self.a.get("/api/dataset").status_code, 200)
        self.assertEqual(self.b.get("/api/dataset").status_code, 409)
        self.assertEqual(self.b.post("/api/allocate", json={}).status_code, 409)
        self.assertFalse(self.b.get("/api/health").json()["dataset_loaded"])
        self.assertTrue(self.a.get("/api/health").json()["dataset_loaded"])

    def test_results_and_exports_are_per_session(self):
        self.load(self.a)
        self.assertEqual(self.a.post("/api/allocate", json={}).json()["status"], "ok")
        self.assertEqual(self.a.get("/api/export/csv").status_code, 200)
        self.assertEqual(self.b.get("/api/export/csv").status_code, 409)
        self.a.post("/api/benchmark", json={"n_students": 30, "course_counts": [40], "algorithms": ["greedy"]})
        self.assertEqual(self.a.get("/api/export/svg").status_code, 200)
        self.assertEqual(self.b.get("/api/export/svg").status_code, 409)

    def test_one_session_overwriting_data_does_not_affect_another(self):
        self.load(self.a, n_students=40)
        self.load(self.b, n_students=70)
        self.assertEqual(self.a.get("/api/dataset").json()["n_students"], 40)
        self.assertEqual(self.b.get("/api/dataset").json()["n_students"], 70)
        self.load(self.b, n_students=20)
        self.assertEqual(self.a.get("/api/dataset").json()["n_students"], 40)

    def test_concurrent_allocations_stay_separate(self):
        self.load(self.a, n_students=40)
        self.load(self.b, n_students=60)
        results = {}

        def work(name, client):
            results[name] = client.post("/api/allocate", json={"algorithm": "welsh_powell"}).json()

        threads = [threading.Thread(target=work, args=(n, c)) for n, c in (("a", self.a), ("b", self.b))]
        [t.start() for t in threads]
        [t.join(30) for t in threads]
        self.assertEqual(len(results["a"]["seats"]), 40)
        self.assertEqual(len(results["b"]["seats"]), 60)

    def test_reset_clears_only_my_session(self):
        self.load(self.a)
        self.load(self.b)
        self.a.post("/api/allocate", json={})
        r = self.a.delete("/api/session")
        self.assertEqual((r.status_code, r.json()), (200, {"status": "reset"}))
        self.assertEqual(self.a.get("/api/dataset").status_code, 409)
        self.assertEqual(self.a.get("/api/export/csv").status_code, 409)
        self.assertEqual(self.b.get("/api/dataset").status_code, 200)

    def test_session_info(self):
        info = self.a.get("/api/session").json()
        self.assertEqual((info["dataset_loaded"], info["has_allocation"], info["has_benchmark"]), (False, False, False))
        self.load(self.a)
        self.a.post("/api/allocate", json={})
        info = self.a.get("/api/session").json()
        self.assertEqual((info["dataset_loaded"], info["has_allocation"]), (True, True))
        self.assertEqual(info["ttl_seconds"], server.SESSION_TTL_SECONDS)


class TestCookie(SessionTestCase):
    def test_cookie_is_issued_once_with_safe_attributes(self):
        first = self.a.get("/api/health")
        cookie = first.headers["set-cookie"]
        self.assertIn(f"{server.SESSION_COOKIE}=", cookie)
        for attr in ("HttpOnly", "Path=/", "SameSite=lax", "Max-Age="):
            self.assertIn(attr, cookie)
        self.assertNotIn("Secure", cookie)
        self.assertNotIn("set-cookie", self.a.get("/api/health").headers)      # not re-issued

    def test_session_ids_are_long_and_unique(self):
        ids = set()
        for _ in range(3):
            c = TestClient(server.app)
            c.get("/api/health")
            ids.add(c.cookies.get(server.SESSION_COOKIE))
        self.assertEqual(len(ids), 3)
        self.assertTrue(all(len(i) >= 40 for i in ids))

    def test_forged_cookie_gets_a_fresh_empty_session(self):
        self.load(self.a)
        real = self.a.cookies.get(server.SESSION_COOKIE)
        forged = TestClient(server.app, cookies={server.SESSION_COOKIE: real[:-3] + "xyz"})
        r = forged.get("/api/dataset")
        self.assertEqual(r.status_code, 409)
        issued = r.headers["set-cookie"].split(";")[0].split("=", 1)[1]
        self.assertNotEqual(issued, real)                    # a brand-new id was issued, not the forged one
        self.assertNotIn(real[:-3] + "xyz", r.headers["set-cookie"])

    def test_preflight_and_non_api_requests_do_not_create_sessions(self):
        self.a.options("/api/allocate", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        self.a.get("/definitely-not-an-api-route")
        self.assertEqual(len(server.SESSIONS), 0)

    def test_liveness_probe_never_creates_sessions(self):
        for _ in range(20):
            r = self.a.get("/healthz")
            self.assertEqual((r.status_code, r.json()), (200, {"status": "ok"}))
        self.assertEqual(len(server.SESSIONS), 0)
        self.assertNotIn("set-cookie", r.headers)

    def test_cors_allows_credentials_for_listed_origins_only(self):
        ok = self.a.options("/api/allocate", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        self.assertEqual(ok.headers["access-control-allow-credentials"], "true")
        self.assertEqual(ok.headers["access-control-allow-origin"], "http://localhost:5173")
        bad = self.a.options("/api/allocate", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
        self.assertNotIn("access-control-allow-origin", bad.headers)

    def test_secure_flag_follows_configuration(self):
        original = server.COOKIE_SECURE
        server.COOKIE_SECURE = True
        try:
            self.assertIn("Secure", TestClient(server.app).get("/api/health").headers["set-cookie"])
        finally:
            server.COOKIE_SECURE = original


class TestLifetime(SessionTestCase):
    def test_idle_session_expires(self):
        self.load(self.a)
        self.clock.now += 101
        self.assertEqual(self.a.get("/api/dataset").status_code, 409)           # data gone
        self.assertEqual(self.a.get("/api/health").status_code, 200)            # but the client simply gets a new session

    def test_activity_keeps_a_session_alive(self):
        self.load(self.a)
        for _ in range(5):
            self.clock.now += 60                                                # each gap < ttl, total 300 > ttl
            self.assertEqual(self.a.get("/api/dataset").status_code, 200)

    def test_expired_sessions_are_purged_from_memory(self):
        self.load(self.a)
        self.load(self.b)
        self.assertEqual(len(server.SESSIONS), 2)
        self.clock.now += 500
        TestClient(server.app).get("/api/health")
        self.assertEqual(len(server.SESSIONS), 1)

    def test_cap_evicts_least_recently_used(self):
        clients = [TestClient(server.app) for _ in range(4)]
        for c in clients[:3]:
            self.load(c)
        self.clock.now += 1
        clients[0].get("/api/dataset")                       # clients[0] is now the most recently used
        self.load(clients[3])                                # 4th session exceeds the cap of 3
        self.assertEqual(len(server.SESSIONS), 3)
        self.assertEqual(clients[0].get("/api/dataset").status_code, 200)
        self.assertEqual(clients[1].get("/api/dataset").status_code, 409)       # least recently used: evicted


class TestJobSlots(SessionTestCase):
    def test_busy_server_answers_503_with_retry_after(self):
        self.load(self.a)
        server.JOB_SLOTS = threading.BoundedSemaphore(1)
        server.JOB_SLOTS.acquire()                           # someone else holds the only slot
        original = server.JOB_WAIT_SECONDS
        server.JOB_WAIT_SECONDS = 0.05
        try:
            r = self.a.post("/api/allocate", json={})
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.headers["retry-after"], "5")
            self.assertEqual(self.a.post("/api/benchmark", json={"n_students": 20, "course_counts": [40]}).status_code, 503)
        finally:
            server.JOB_WAIT_SECONDS = original
            server.JOB_SLOTS.release()
        self.assertEqual(self.a.post("/api/allocate", json={}).status_code, 200)     # recovers

    def test_slot_is_released_after_a_failed_job(self):
        self.load(self.a)
        server.JOB_SLOTS = threading.BoundedSemaphore(1)
        self.a.post("/api/allocate", json={"weights": {"w_same_branch": -5}})       # rejected before running
        self.assertEqual(self.a.post("/api/allocate", json={}).status_code, 200)
        self.assertEqual(self.a.post("/api/allocate", json={}).status_code, 200)


class TestSessionStoreUnit(unittest.TestCase):
    def test_get_or_create_semantics(self):
        clock = FakeClock()
        store = server.SessionStore(ttl=10, max_sessions=2, clock=clock)
        s1, created = store.get_or_create(None)
        self.assertTrue(created)
        again, created = store.get_or_create(s1.sid)
        self.assertFalse(created)
        self.assertIs(again, s1)
        other, created = store.get_or_create("unknown")
        self.assertTrue(created)
        self.assertNotEqual(other.sid, "unknown")
        store.drop(s1.sid)
        self.assertEqual(len(store), 1)


if __name__ == "__main__":
    unittest.main()
