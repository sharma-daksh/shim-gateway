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

import mock_provider
import proxy
from config import settings

class TestPhase1BackendFoundation(unittest.TestCase):
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
        # Poll health endpoints until ready
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

    def setUp(self):
        # Reset provider states
        httpx.post("http://127.0.0.1:8001/admin/schema-mode?mode=original")
        httpx.post("http://127.0.0.1:8001/admin/simulate-failure?enable=false")
        httpx.post("http://127.0.0.1:8001/admin/simulate-delay?seconds=0.0")
        httpx.post("http://127.0.0.1:8001/admin/simulate-invalid-json?enable=false")

    def test_http_methods(self):
        """Test GET, POST, PUT, PATCH, DELETE through proxy"""
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        
        # GET
        res_get = client.get("/payments/echo")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["method"], "GET")

        # POST
        res_post = client.post("/payments/echo", json={"action": "charge", "amount": 100})
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()["method"], "POST")
        self.assertEqual(res_post.json()["body_json"]["action"], "charge")

        # PUT
        res_put = client.put("/payments/echo", json={"action": "update", "notes": "paid"})
        self.assertEqual(res_put.status_code, 200)
        self.assertEqual(res_put.json()["method"], "PUT")
        self.assertEqual(res_put.json()["body_json"]["notes"], "paid")

        # PATCH
        res_patch = client.patch("/payments/echo", json={"status": "confirmed"})
        self.assertEqual(res_patch.status_code, 200)
        self.assertEqual(res_patch.json()["method"], "PATCH")
        self.assertEqual(res_patch.json()["body_json"]["status"], "confirmed")

        # DELETE
        res_delete = client.delete("/payments/echo")
        self.assertEqual(res_delete.status_code, 200)
        self.assertEqual(res_delete.json()["method"], "DELETE")

    def test_query_parameters_and_headers(self):
        """Test query parameters preservation and custom header forwarding"""
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        params = {"tier": "gold", "discount": "20", "user_id": "usr_99"}
        headers = {
            "X-Client-Id": "client-abc-123",
            "Authorization": "Bearer token_xyz_789"
        }
        res = client.get("/payments/echo", params=params, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["query_params"], params)
        self.assertEqual(data["headers"].get("x-client-id"), "client-abc-123")
        self.assertEqual(data["headers"].get("authorization"), "Bearer token_xyz_789")

    def test_timeout_handling(self):
        """Verify proxy returns 504 when upstream delays beyond configured read timeout"""
        # Configure upstream mock to sleep for 6.0s (settings.READ_TIMEOUT is 5.0s)
        httpx.post("http://127.0.0.1:8001/admin/simulate-delay?seconds=6.0")
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=8.0)
        res = client.get("/payments/P101")
        self.assertEqual(res.status_code, 504)
        self.assertIn("Gateway Timeout", res.json()["detail"])

    def test_invalid_json_handling(self):
        """Verify proxy returns 502 with structured error when upstream returns malformed JSON"""
        httpx.post("http://127.0.0.1:8001/admin/simulate-invalid-json?enable=true")
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        res = client.get("/payments/P101")
        self.assertEqual(res.status_code, 502)
        data = res.json()
        self.assertEqual(data["error"], "Upstream Invalid JSON")

    def test_provider_failures_forwarded(self):
        """Verify upstream 500 and 503 are preserved and not masked as 200"""
        httpx.post("http://127.0.0.1:8001/admin/simulate-failure?enable=true&status_code=503")
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        res = client.get("/payments/P101")
        self.assertEqual(res.status_code, 503)

    def test_status_code_preservation(self):
        """Verify standard 4xx and custom status codes are accurately passed through"""
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        for code in [400, 404, 422]:
            res = client.get(f"/status/{code}")
            self.assertEqual(res.status_code, code)

    def test_ssrf_protection(self):
        """Verify proxy blocks target URLs targeting instance metadata or disallowed schemes"""
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        
        # Attempt to redirect proxy to AWS/GCP metadata service
        res_metadata = client.get(
            "/payments/P101",
            headers={"X-Shim-Target-URL": "http://169.254.169.254/latest/meta-data"}
        )
        self.assertEqual(res_metadata.status_code, 403)
        self.assertIn("SSRF policy", res_metadata.json()["detail"])

        # Attempt forbidden scheme file://
        res_file = client.get(
            "/payments/P101",
            headers={"X-Shim-Target-URL": "file:///etc/passwd"}
        )
        self.assertEqual(res_file.status_code, 403)

    def test_existing_functionality_preserved(self):
        """Verify Phase 0 baseline price vs amount switching remains fully functional"""
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        
        # Original mode
        httpx.post("http://127.0.0.1:8001/admin/schema-mode?mode=original")
        res1 = client.get("/payments/P101")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["price"], 500)
        self.assertNotIn("amount", res1.json())

        # Changed mode
        httpx.post("http://127.0.0.1:8001/admin/schema-mode?mode=changed")
        res2 = client.get("/payments/P101")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["amount"], 500)
        self.assertNotIn("price", res2.json())

if __name__ == "__main__":
    unittest.main()
