import unittest
import sys
import os
import time
import subprocess
import httpx
import json

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

class TestPhase7CompleteIntegration(unittest.TestCase):
    mock_process = None
    proxy_process = None

    @classmethod
    def setUpClass(cls):
        # Start mock provider on 8001
        cls.mock_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "mock_provider:app", "--host", "127.0.0.1", "--port", "8001"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Start proxy on 8000
        cls.proxy_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "proxy:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        for _ in range(30):
            time.sleep(0.2)
            try:
                r1 = httpx.get("http://127.0.0.1:8001/health", timeout=1.0)
                r2 = httpx.get("http://127.0.0.1:8000/health", timeout=1.0)
                if r1.status_code == 200 and r2.status_code == 200:
                    break
            except Exception:
                pass

    @classmethod
    def tearDownClass(cls):
        if cls.proxy_process:
            cls.proxy_process.terminate()
            cls.proxy_process.wait()
        if cls.mock_process:
            cls.mock_process.terminate()
            cls.mock_process.wait()

    def test_complete_end_to_end_adaptive_lifecycle(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)

        # 1. Login as admin to manage project
        login_res = client.post("/api/auth/login", json={"username_or_email": "admin", "password": "admin123"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 2. Create an isolated project for this test
        proj_res = client.post("/api/projects", json={"name": "End-to-End Test Project"}, headers=auth_headers)
        self.assertEqual(proj_res.status_code, 200)
        project = proj_res.json()
        project_id = project["id"]
        api_key = project["api_key"]
        project_headers = {"X-API-Key": api_key}

        # 3. Upstream mock is in 'original' mode (returns price: 500)
        httpx.post("http://127.0.0.1:8001/admin/schema-mode?mode=original")
        res1 = client.get("/payments/P101", headers=project_headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["price"], 500)
        self.assertNotIn("amount", data1)
        self.assertEqual(res1.headers.get("x-shim-transformed"), "false")

        # Verify baseline schema was stored
        schemas_res = client.get(f"/api/projects/{project_id}/schemas", headers=auth_headers)
        self.assertEqual(schemas_res.status_code, 200)
        schemas = schemas_res.json()
        self.assertGreaterEqual(len(schemas), 1)
        self.assertTrue(schemas[-1]["is_baseline"])

        # 4. External API changes response schema: 'price' disappears, 'amount' appears
        httpx.post("http://127.0.0.1:8001/admin/schema-mode?mode=changed")
        res2 = client.get("/payments/P101", headers=project_headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        # Since mapping is not yet approved, proxy safely passes raw new response without corrupting
        self.assertEqual(data2["amount"], 500)
        self.assertNotIn("price", data2)

        # 5. Verify SHIM detected the schema change and generated an intelligent mapping suggestion
        changes_res = client.get(f"/api/projects/{project_id}/changes", headers=auth_headers)
        self.assertEqual(changes_res.status_code, 200)
        changes = changes_res.json()
        self.assertGreaterEqual(len(changes), 1)

        mappings_res = client.get(f"/api/projects/{project_id}/mappings", headers=auth_headers)
        self.assertEqual(mappings_res.status_code, 200)
        mappings = mappings_res.json()
        self.assertGreaterEqual(len(mappings), 1)
        suggested_map = next(m for m in mappings if m["source_field"] == "amount" and m["target_field"] == "price")
        self.assertEqual(suggested_map["status"], "PENDING")
        self.assertGreaterEqual(suggested_map["confidence"], 0.85)

        # 6. Customer / Admin reviews and APPROVES the mapping
        approve_res = client.post(f"/api/mappings/{suggested_map['id']}/approve", headers=auth_headers)
        self.assertEqual(approve_res.status_code, 200)

        # 7. Subsequent request: SHIM automatically transforms the response back into expected format!
        res3 = client.get("/payments/P101", headers=project_headers)
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        # The application expects price: SHIM transformed 'amount' back into 'price'!
        self.assertEqual(data3["price"], 500)
        self.assertNotIn("amount", data3)
        self.assertEqual(res3.headers.get("x-shim-transformed"), "true")
        self.assertEqual(res3.headers.get("x-shim-mappings-applied"), "1")

        # 8. Check Transformation History
        history_res = client.get(f"/api/projects/{project_id}/history", headers=auth_headers)
        self.assertEqual(history_res.status_code, 200)
        history = history_res.json()
        self.assertGreaterEqual(len(history), 1)
        self.assertTrue(history[0]["transformation_occurred"])

if __name__ == "__main__":
    unittest.main()
