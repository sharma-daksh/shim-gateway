import unittest
import sys
import os
import time
import subprocess
import httpx

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

class TestPhase8AuthSecurity(unittest.TestCase):
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

    def test_registration_and_login_lifecycle(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        uname = f"customer_{int(time.time()*1000)}"
        email = f"{uname}@example.com"

        # Register
        reg_res = client.post("/api/auth/register", json={
            "username": uname,
            "email": email,
            "password": "SecurePassword#123",
            "role": "customer"
        })
        self.assertEqual(reg_res.status_code, 200)
        data = reg_res.json()
        self.assertIn("token", data)
        self.assertNotIn("password", data["user"])
        self.assertNotIn("password_hash", data["user"])

        # Login
        login_res = client.post("/api/auth/login", json={
            "username_or_email": uname,
            "password": "SecurePassword#123"
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("token", login_res.json())

        # Failed login with bad password
        bad_login = client.post("/api/auth/login", json={
            "username_or_email": uname,
            "password": "WrongPassword!"
        })
        self.assertEqual(bad_login.status_code, 401)

    def test_protected_endpoints_require_token(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        # Attempt without header
        res_no_auth = client.get("/api/projects")
        self.assertEqual(res_no_auth.status_code, 401)

        # Attempt with garbage token
        res_bad_auth = client.get("/api/projects", headers={"Authorization": "Bearer fake.token.here"})
        self.assertEqual(res_bad_auth.status_code, 401)

    def test_invalid_api_key_rejected(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        res = client.get("/payments/P101", headers={"X-API-Key": "shim_live_invalid_key_999"})
        self.assertEqual(res.status_code, 401)

    def test_customer_isolation_and_project_ownership(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        ts = int(time.time()*1000)

        # Register Customer A
        res_a = client.post("/api/auth/register", json={"username": f"userA_{ts}", "email": f"userA_{ts}@test.com", "password": "passA123"})
        token_a = res_a.json()["token"]

        # Register Customer B
        res_b = client.post("/api/auth/register", json={"username": f"userB_{ts}", "email": f"userB_{ts}@test.com", "password": "passB123"})
        token_b = res_b.json()["token"]

        # Customer A creates Project A
        proj_a = client.post("/api/projects", json={"name": "Project A"}, headers={"Authorization": f"Bearer {token_a}"}).json()
        proj_a_id = proj_a["id"]

        # Customer B lists projects -> Project A MUST NOT appear
        b_list = client.get("/api/projects", headers={"Authorization": f"Bearer {token_b}"}).json()
        b_proj_ids = [p["id"] for p in b_list]
        self.assertNotIn(proj_a_id, b_proj_ids)

        # Customer B attempts to access Project A detail directly -> 403 Forbidden
        direct_access = client.get(f"/api/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(direct_access.status_code, 403)

    def test_role_permissions(self):
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        ts = int(time.time()*1000)

        # Customer token
        cust_res = client.post("/api/auth/register", json={"username": f"cust_{ts}", "email": f"cust_{ts}@test.com", "password": "pass123", "role": "customer"})
        cust_token = cust_res.json()["token"]

        # Admin token
        admin_login = client.post("/api/auth/login", json={"username_or_email": "admin", "password": "admin123"})
        admin_token = admin_login.json()["token"]

        # Customer tries to access admin overview -> 403 Forbidden
        cust_admin_res = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {cust_token}"})
        self.assertEqual(cust_admin_res.status_code, 403)

        # Admin accesses admin overview -> 200 OK
        admin_res = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(admin_res.status_code, 200)
        self.assertEqual(admin_res.json()["status"], "healthy")

if __name__ == "__main__":
    unittest.main()
