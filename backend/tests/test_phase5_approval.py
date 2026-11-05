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
    upsert_mapping,
    get_approved_mappings
)
from mapping_service import (
    validate_mapping_candidate,
    approve_mapping_request,
    reject_mapping_request,
    disable_mapping_request
)

class TestPhase5MappingApproval(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)
        conn = get_connection(self.temp_db_path)
        with conn:
            conn.execute(
                "INSERT INTO users (id, username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("usr_1", "testuser", "test@example.com", "hash123", "customer", time.time())
            )
        create_project("proj_1", "Project 1", "usr_1", "key_1", self.temp_db_path)
        create_project("proj_2", "Project 2", "usr_1", "key_2", self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_pending_mappings_cannot_transform(self):
        # Insert a pending mapping
        upsert_mapping(
            mapping_id="map_pending",
            project_id="proj_1",
            endpoint_path="/payments/P101",
            source_field="amount",
            target_field="price",
            source_type="integer",
            target_type="integer",
            similarity_score=0.92,
            confidence=0.88,
            status="PENDING",
            db_path=self.temp_db_path
        )
        approved = get_approved_mappings("proj_1", "/payments/P101", self.temp_db_path)
        self.assertEqual(len(approved), 0, "Pending mappings must not be in approved list")

    def test_valid_mapping_can_be_approved(self):
        upsert_mapping(
            mapping_id="map_valid",
            project_id="proj_1",
            endpoint_path="/payments/P101",
            source_field="amount",
            target_field="price",
            source_type="integer",
            target_type="integer",
            similarity_score=0.92,
            confidence=0.88,
            status="PENDING",
            db_path=self.temp_db_path
        )
        ok, msg = approve_mapping_request("map_valid", "proj_1", "usr_1", self.temp_db_path)
        self.assertTrue(ok)
        self.assertIn("approved", msg.lower())

        approved = get_approved_mappings("proj_1", "/payments/P101", self.temp_db_path)
        self.assertEqual(len(approved), 1)

    def test_invalid_mapping_cannot_be_approved(self):
        # Incompatible type: object to integer
        upsert_mapping(
            mapping_id="map_bad_type",
            project_id="proj_1",
            endpoint_path="/payments/P101",
            source_field="raw_details",
            target_field="price",
            source_type="object",
            target_type="integer",
            similarity_score=0.90,
            confidence=0.85,
            status="PENDING",
            db_path=self.temp_db_path
        )
        ok, msg = approve_mapping_request("map_bad_type", "proj_1", "usr_1", self.temp_db_path)
        self.assertFalse(ok)
        self.assertIn("incompatibility", msg.lower())

    def test_rejected_and_disabled_mappings_not_applied(self):
        upsert_mapping(
            mapping_id="map_toggle",
            project_id="proj_1",
            endpoint_path="/payments/P101",
            source_field="amount",
            target_field="price",
            source_type="integer",
            target_type="integer",
            similarity_score=0.92,
            confidence=0.88,
            status="PENDING",
            db_path=self.temp_db_path
        )
        # Approve first
        approve_mapping_request("map_toggle", "proj_1", "usr_1", self.temp_db_path)
        self.assertEqual(len(get_approved_mappings("proj_1", "/payments/P101", self.temp_db_path)), 1)

        # Disable
        disable_mapping_request("map_toggle", "proj_1", "usr_1", self.temp_db_path)
        self.assertEqual(len(get_approved_mappings("proj_1", "/payments/P101", self.temp_db_path)), 0)

        # Reject
        reject_mapping_request("map_toggle", "proj_1", "usr_1", self.temp_db_path)
        self.assertEqual(len(get_approved_mappings("proj_1", "/payments/P101", self.temp_db_path)), 0)

    def test_project_level_access_control(self):
        # Map belongs to proj_1; user attempts to approve under proj_2
        upsert_mapping(
            mapping_id="map_proj1",
            project_id="proj_1",
            endpoint_path="/payments/P101",
            source_field="amount",
            target_field="price",
            source_type="integer",
            target_type="integer",
            similarity_score=0.92,
            confidence=0.88,
            status="PENDING",
            db_path=self.temp_db_path
        )
        ok, msg = approve_mapping_request("map_proj1", "proj_2", "usr_1", self.temp_db_path)
        self.assertFalse(ok)
        self.assertIn("access denied", msg.lower())

if __name__ == "__main__":
    unittest.main()
