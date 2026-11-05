import unittest
import sys
import os
import time
import subprocess
import httpx

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

class TestPhase910FrontendBackendIntegration(unittest.TestCase):
    mock_process = None
    proxy_process = None

    @classmethod
    def setUpClass(cls):
        cls.mock_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "mock_provider:app", "--host", "127.0.0.1", "--port", "8001"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
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

    def test_frontend_routes_served(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        res_root = client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("SHIM — Adaptive API Compatibility Layer", res_root.text)
        self.assertIn("sphere-canvas", res_root.text)
        self.assertNotIn("Admin Telemetry", res_root.text)
        self.assertNotIn("Creator Dashboard", res_root.text)

    def test_anonymous_extension_download_tracking(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)

        # Check initial stats
        stats_before = client.get("/api/downloads/stats").json()
        initial_count = stats_before["total_downloads"]

        # Trigger download without any sign-in / auth headers
        dl_res = client.get("/download/shim-vscode-extension.vsix")
        self.assertEqual(dl_res.status_code, 200)
        self.assertGreater(len(dl_res.content), 100)

        # Verify download counter incremented
        stats_after = client.get("/api/downloads/stats").json()
        self.assertEqual(stats_after["total_downloads"], initial_count + 1)

    def test_frontend_backed_by_live_endpoints(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)

        # 1. Admin login for backend API
        login_res = client.post("/api/auth/login", json={"username_or_email": "admin", "password": "admin123"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Stats including download count
        overview_res = client.get("/api/admin/overview", headers=headers)
        self.assertEqual(overview_res.status_code, 200)
        overview = overview_res.json()
        self.assertIn("total_requests", overview)
        self.assertIn("total_downloads", overview)

        # 3. Schemas for default project
        schemas_res = client.get("/api/projects/default_project/schemas", headers=headers)
        self.assertEqual(schemas_res.status_code, 200)

        # 4. History logs
        history_res = client.get("/api/projects/default_project/history", headers=headers)
        self.assertEqual(history_res.status_code, 200)

if __name__ == "__main__":
    unittest.main()
