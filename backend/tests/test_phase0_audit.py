import unittest
import sys
import os
import time
import subprocess
import httpx
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import mock_provider
import proxy

class TestPhase0MockProviderDirect(unittest.TestCase):
    """Test mock provider directly using TestClient"""
    def setUp(self):
        self.client = TestClient(mock_provider.app)
        mock_provider.provider_state["schema_mode"] = "original"
        mock_provider.provider_state["simulate_failure"] = False

    def test_mock_provider_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "mock_payment_provider")

    def test_original_schema_response(self):
        res = self.client.get("/payments/P101")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["payment_id"], "P101")
        self.assertIn("price", data)
        self.assertNotIn("amount", data)
        self.assertEqual(data["price"], 500)
        self.assertEqual(data["status"], "success")

    def test_changed_schema_response(self):
        # Change mode to changed
        res_mode = self.client.post("/admin/schema-mode?mode=changed")
        self.assertEqual(res_mode.status_code, 200)
        
        res = self.client.get("/payments/P101")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["payment_id"], "P101")
        self.assertIn("amount", data)
        self.assertNotIn("price", data)
        self.assertEqual(data["amount"], 500)
        self.assertEqual(data["status"], "success")

    def test_provider_simulated_failure(self):
        # Enable failure
        res_fail = self.client.post("/admin/simulate-failure?enable=true&status_code=500")
        self.assertEqual(res_fail.status_code, 200)

        res = self.client.get("/payments/P101")
        self.assertEqual(res.status_code, 500)
        self.assertIn("Mock payment provider simulated upstream error", res.text)


class TestPhase0ProxyDirect(unittest.TestCase):
    """Test proxy behavior directly and error handling when upstream fails"""
    def setUp(self):
        self.client = TestClient(proxy.app)

    def test_proxy_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "shim_proxy")

    def test_proxy_upstream_down_handling(self):
        # When upstream port is down or unreachable, proxy should return 502 Bad Gateway
        # Note: Port 8001 is not running yet during this isolated unit test
        res = self.client.get("/payments/P101")
        self.assertIn(res.status_code, [502, 504])


class TestPhase0LiveIntegration(unittest.TestCase):
    """Test running both servers as live processes on ports 8001 and 8000"""
    mock_process = None
    proxy_process = None

    @classmethod
    def setUpClass(cls):
        # Launch mock provider on 8001
        cls.mock_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "mock_provider:app", "--host", "127.0.0.1", "--port", "8001"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Launch proxy on 8000
        cls.proxy_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "proxy:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Wait up to 5 seconds for servers to start
        for _ in range(25):
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

    def test_both_services_running(self):
        r1 = httpx.get("http://127.0.0.1:8001/health", timeout=2.0)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["service"], "mock_payment_provider")

        r2 = httpx.get("http://127.0.0.1:8000/health", timeout=2.0)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["service"], "shim_proxy")

    def test_proxy_forwards_original_response(self):
        # Set mode to original
        httpx.post("http://127.0.0.1:8001/admin/schema-mode?mode=original")
        # Request through proxy
        res = httpx.get("http://127.0.0.1:8000/payments/P101", timeout=2.0)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["payment_id"], "P101")
        self.assertEqual(data["price"], 500)
        self.assertNotIn("amount", data)

    def test_proxy_forwards_changed_response(self):
        # Set mode to changed
        httpx.post("http://127.0.0.1:8001/admin/schema-mode?mode=changed")
        # Request through proxy
        res = httpx.get("http://127.0.0.1:8000/payments/P101", timeout=2.0)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["payment_id"], "P101")
        self.assertEqual(data["amount"], 500)
        self.assertNotIn("price", data)

    def test_proxy_forwards_provider_failure(self):
        # Enable failure on provider
        httpx.post("http://127.0.0.1:8001/admin/simulate-failure?enable=true&status_code=500")
        try:
            res = httpx.get("http://127.0.0.1:8000/payments/P101", timeout=2.0)
            self.assertEqual(res.status_code, 500)
        finally:
            # Disable failure
            httpx.post("http://127.0.0.1:8001/admin/simulate-failure?enable=false")

if __name__ == "__main__":
    unittest.main()
