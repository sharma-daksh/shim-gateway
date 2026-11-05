import unittest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from schema_detector import (
    extract_schema,
    flatten_schema,
    compare_schemas,
    compute_schema_hash,
    SchemaVersionRegistry
)

class TestPhase2SchemaDetection(unittest.TestCase):
    def test_original_schema_storage(self):
        registry = SchemaVersionRegistry()
        payload = {
            "payment_id": "P101",
            "price": 500,
            "status": "success"
        }
        changed, info = registry.register_response("/payments/P101", payload)
        self.assertFalse(changed)
        self.assertEqual(info["status"], "baseline_established")
        self.assertEqual(info["version"], 1)

        baseline = registry.get_baseline("/payments/P101")
        self.assertIsNotNone(baseline)
        flat = flatten_schema(baseline)
        self.assertEqual(flat["payment_id"], "string")
        self.assertEqual(flat["price"], "integer")
        self.assertEqual(flat["status"], "string")

    def test_ordinary_value_changes_ignored(self):
        registry = SchemaVersionRegistry()
        payload1 = {"payment_id": "P101", "price": 500, "status": "success"}
        payload2 = {"payment_id": "P999", "price": 1250, "status": "pending"}

        registry.register_response("/payments/P101", payload1)
        changed, info = registry.register_response("/payments/P101", payload2)
        
        # Structure is identical, only values changed -> should not report change
        self.assertFalse(changed)
        self.assertEqual(info["status"], "unchanged")
        self.assertEqual(info["version"], 1)

    def test_price_to_amount_detection(self):
        old_data = {"payment_id": "P101", "price": 500, "status": "success"}
        new_data = {"payment_id": "P101", "amount": 500, "status": "success"}

        old_schema = extract_schema(old_data)
        new_schema = extract_schema(new_data)
        diff = compare_schemas(old_schema, new_schema)

        self.assertTrue(diff["has_changed"])
        # Check removed field 'price'
        removed_paths = [r["path"] for r in diff["removed_fields"]]
        self.assertIn("price", removed_paths)

        # Check added field 'amount'
        added_paths = [a["path"] for a in diff["added_fields"]]
        self.assertIn("amount", added_paths)

        # Check potential rename pairing
        renames = diff["potential_renames"]
        self.assertTrue(any(r["old_field"] == "price" and r["new_field"] == "amount" for r in renames))

    def test_data_type_changes(self):
        # price as integer vs price as string
        data_int = {"payment_id": "P101", "price": 500}
        data_str = {"payment_id": "P101", "price": "500.00"}

        s_int = extract_schema(data_int)
        s_str = extract_schema(data_str)
        diff = compare_schemas(s_int, s_str)

        self.assertTrue(diff["has_changed"])
        self.assertEqual(len(diff["type_changes"]), 1)
        self.assertEqual(diff["type_changes"][0]["path"], "price")
        self.assertEqual(diff["type_changes"][0]["old_type"], "integer")
        self.assertEqual(diff["type_changes"][0]["new_type"], "string")

    def test_nested_objects_and_arrays(self):
        old_data = {
            "order_id": "ORD-1",
            "customer": {
                "name": "Alice",
                "address": {"city": "New York", "zip": 10001}
            },
            "items": [{"sku": "SKU1", "qty": 2}]
        }
        new_data = {
            "order_id": "ORD-1",
            "customer": {
                "name": "Alice",
                "address": {"city": "New York", "postal_code": "10001"} # zip -> postal_code & int -> str
            },
            "items": [{"sku": "SKU1", "qty": 2, "tax": 1.5}] # added tax
        }

        s_old = extract_schema(old_data)
        s_new = extract_schema(new_data)
        diff = compare_schemas(s_old, s_new)

        self.assertTrue(diff["has_changed"])
        removed = [r["path"] for r in diff["removed_fields"]]
        added = [a["path"] for a in diff["added_fields"]]

        self.assertIn("customer.address.zip", removed)
        self.assertIn("customer.address.postal_code", added)
        self.assertIn("items[].tax", added)

    def test_independent_endpoint_schemas(self):
        registry = SchemaVersionRegistry()
        payments_data = {"payment_id": "P101", "amount": 500}
        users_data = {"user_id": "U1", "email": "user@example.com"}

        registry.register_response("/payments", payments_data)
        registry.register_response("/users", users_data)

        p_base = registry.get_baseline("/payments")
        u_base = registry.get_baseline("/users")

        self.assertIn("payment_id", flatten_schema(p_base))
        self.assertNotIn("user_id", flatten_schema(p_base))
        self.assertIn("user_id", flatten_schema(u_base))
        self.assertNotIn("payment_id", flatten_schema(u_base))

if __name__ == "__main__":
    unittest.main()
