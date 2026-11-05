import unittest
import sys
import os
import tempfile
import time

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import (
    init_db,
    get_connection,
    create_project,
    get_project,
    get_project_by_api_key,
    save_endpoint_schema,
    get_latest_schema,
    get_baseline_schema,
    save_schema_change,
    upsert_mapping,
    update_mapping_status,
    get_approved_mappings,
    get_mappings_for_project,
    log_transformation
)

class TestPhase3Database(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)
        # Create dummy user for FK
        conn = get_connection(self.temp_db_path)
        with conn:
            conn.execute(
                "INSERT INTO users (id, username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("usr_1", "testuser", "test@example.com", "hash123", "customer", time.time())
            )

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_project_crud_and_api_key_lookup(self):
        proj = create_project("proj_101", "Payment Bridge", "usr_1", "shim_live_abc123", self.temp_db_path)
        self.assertEqual(proj["id"], "proj_101")

        fetched = get_project("proj_101", self.temp_db_path)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["name"], "Payment Bridge")

        by_key = get_project_by_api_key("shim_live_abc123", self.temp_db_path)
        self.assertIsNotNone(by_key)
        self.assertEqual(by_key["id"], "proj_101")

    def test_schema_persistence_and_restart(self):
        create_project("proj_101", "Payment", "usr_1", "key_test", self.temp_db_path)
        # Save baseline schema (version 1)
        schema_v1 = {"type": "object", "properties": {"price": {"type": "integer"}}}
        save_endpoint_schema(
            project_id="proj_101",
            endpoint_path="/payments/P101",
            version=1,
            version_tag="v1-hash1",
            schema_hash="hash1",
            schema_dict=schema_v1,
            is_baseline=True,
            db_path=self.temp_db_path
        )

        # Save changed schema (version 2)
        schema_v2 = {"type": "object", "properties": {"amount": {"type": "integer"}}}
        save_endpoint_schema(
            project_id="proj_101",
            endpoint_path="/payments/P101",
            version=2,
            version_tag="v2-hash2",
            schema_hash="hash2",
            schema_dict=schema_v2,
            is_baseline=False,
            db_path=self.temp_db_path
        )

        # Simulate restart by reconnecting to the same SQLite file
        baseline = get_baseline_schema("proj_101", "/payments/P101", self.temp_db_path)
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline["version"], 1)
        self.assertIn("price", baseline["schema"]["properties"])

        latest = get_latest_schema("proj_101", "/payments/P101", self.temp_db_path)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["version"], 2)
        self.assertIn("amount", latest["schema"]["properties"])

    def test_project_isolation(self):
        # Project 1
        create_project("proj_A", "Alpha", "usr_1", "key_A", self.temp_db_path)
        save_endpoint_schema(
            "proj_A", "/data", 1, "v1", "h1",
            {"type": "object", "properties": {"alpha_field": {"type": "string"}}},
            True, self.temp_db_path
        )

        # Project 2
        create_project("proj_B", "Beta", "usr_1", "key_B", self.temp_db_path)
        save_endpoint_schema(
            "proj_B", "/data", 1, "v1", "h2",
            {"type": "object", "properties": {"beta_field": {"type": "string"}}},
            True, self.temp_db_path
        )

        schema_a = get_latest_schema("proj_A", "/data", self.temp_db_path)
        schema_b = get_latest_schema("proj_B", "/data", self.temp_db_path)

        self.assertIn("alpha_field", schema_a["schema"]["properties"])
        self.assertNotIn("beta_field", schema_a["schema"]["properties"])
        self.assertIn("beta_field", schema_b["schema"]["properties"])
        self.assertNotIn("alpha_field", schema_b["schema"]["properties"])

    def test_mapping_approval_lifecycle(self):
        create_project("proj_101", "Payment", "usr_1", "key_1", self.temp_db_path)
        upsert_mapping(
            mapping_id="map_1",
            project_id="proj_101",
            endpoint_path="/payments/P101",
            source_field="amount",
            target_field="price",
            source_type="integer",
            target_type="integer",
            similarity_score=0.92,
            confidence=0.88,
            status="PENDING",
            explanation="High semantic similarity between amount and price",
            db_path=self.temp_db_path
        )

        # Initially PENDING -> should not appear in approved mappings
        approved = get_approved_mappings("proj_101", "/payments/P101", self.temp_db_path)
        self.assertEqual(len(approved), 0)

        # Approve mapping
        updated = update_mapping_status("map_1", "APPROVED", approved_by="usr_1", db_path=self.temp_db_path)
        self.assertTrue(updated)

        approved_after = get_approved_mappings("proj_101", "/payments/P101", self.temp_db_path)
        self.assertEqual(len(approved_after), 1)
        self.assertEqual(approved_after[0]["source_field"], "amount")
        self.assertEqual(approved_after[0]["target_field"], "price")
        self.assertEqual(approved_after[0]["approved_by"], "usr_1")

    def test_transformation_logging(self):
        create_project("proj_101", "Payment", "usr_1", "key_1", self.temp_db_path)
        log_id = log_transformation(
            project_id="proj_101",
            endpoint_path="/payments/P101",
            method="GET",
            status_code=200,
            original_payload={"payment_id": "P101", "amount": 500},
            transformed_payload={"payment_id": "P101", "price": 500},
            mappings_applied=[{"source": "amount", "target": "price"}],
            transformation_occurred=True,
            latency_ms=1.45,
            db_path=self.temp_db_path
        )
        self.assertGreater(log_id, 0)

if __name__ == "__main__":
    unittest.main()
