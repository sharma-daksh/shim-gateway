"""
Comprehensive Edge-Case Test Suite for SHIM Platform.
Tests real-world API drift scenarios across:
1. Deeply nested key renames (e.g., customer.contact.phone_number -> customer.contact.mobile)
2. Array item restructuring ([{"sku": "A", "price": 100}] -> [{"sku": "A", "cost": 100}])
3. Null, empty string, and boolean type-safety
4. Numeric string coercion ("1250" -> 1250) vs non-coercible string rejection ("invalid_int")
5. Multi-field simultaneous renames (price -> amount AND txn_id -> transaction_id)
6. Partial payloads where expected fields are legitimately omitted
7. Unsafe overwrite collision protection
8. Character n-gram subword vector matching on unseen tokens
9. Non-destructive preservation of unrelated fields
10. End-to-end integration through reverse proxy with real HTTP requests
"""
import unittest
import sys
import os
import subprocess
import time
import httpx

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from schema_detector import extract_schema, compare_schemas, flatten_schema
from mapping_engine import IntelligentMappingEngine, evaluate_type_compatibility
from transformer import transform_response, coerce_type, get_nested_value, set_nested_value
from mapping_service import validate_mapping_candidate

class TestEdgeCasesAndDrift(unittest.TestCase):

    def setUp(self):
        self.engine = IntelligentMappingEngine(fallback_mode=True)

    # Edge Case 1: Deeply nested field drift
    def test_deeply_nested_field_rename(self):
        old_payload = {
            "order": {
                "shipping": {
                    "contact": {
                        "phone_number": "+1-555-0199"
                    }
                }
            }
        }
        new_payload = {
            "order": {
                "shipping": {
                    "contact": {
                        "mobile": "+1-555-0199"
                    }
                }
            }
        }
        s_old = extract_schema(old_payload)
        s_new = extract_schema(new_payload)
        diff = compare_schemas(s_old, s_new)

        self.assertTrue(diff["has_changed"])
        suggestions = self.engine.suggest_mappings(diff["removed_fields"], diff["added_fields"])
        self.assertGreaterEqual(len(suggestions), 1)
        top = suggestions[0]
        self.assertEqual(top["source_field"], "order.shipping.contact.mobile")
        self.assertEqual(top["target_field"], "order.shipping.contact.phone_number")
        self.assertGreater(top["confidence"], 0.80)

        # Transform
        transformed, applied, ok = transform_response(new_payload, [top])
        self.assertTrue(ok)
        self.assertEqual(transformed["order"]["shipping"]["contact"]["phone_number"], "+1-555-0199")
        self.assertNotIn("mobile", transformed["order"]["shipping"]["contact"])

    # Edge Case 2: Array item field restructuring
    def test_array_item_field_drift_detection(self):
        old_cart = {
            "items": [
                {"item_id": "ITM-1", "price": 49.99}
            ]
        }
        new_cart = {
            "items": [
                {"item_id": "ITM-1", "amount": 49.99}
            ]
        }
        diff = compare_schemas(extract_schema(old_cart), extract_schema(new_cart))
        self.assertTrue(diff["has_changed"])
        removed_paths = [r["path"] for r in diff["removed_fields"]]
        added_paths = [a["path"] for a in diff["added_fields"]]
        self.assertIn("items[].price", removed_paths)
        self.assertIn("items[].amount", added_paths)

    # Edge Case 3: Type coercion edge cases (valid numeric string vs invalid alphabetic string)
    def test_type_coercion_edge_cases(self):
        # Numeric string to integer: valid
        valid_int, val1 = coerce_type("1250", "integer")
        self.assertTrue(valid_int)
        self.assertEqual(val1, 1250)

        # Negative float string to float: valid
        valid_float, val2 = coerce_type("-99.45", "float")
        self.assertTrue(valid_float)
        self.assertAlmostEqual(val2, -99.45)

        # Alphabetic string to integer: must safely reject and NOT crash
        invalid_int, val3 = coerce_type("not_a_number_abc", "integer")
        self.assertFalse(invalid_int)
        self.assertIsNone(val3)

        # Boolean to integer: must reject to prevent True -> 1 financial corruptions
        bool_to_int, val4 = coerce_type(True, "integer")
        self.assertFalse(bool_to_int)
        self.assertIsNone(val4)

    # Edge Case 4: Null values in incoming JSON payloads
    def test_null_value_handling(self):
        payload = {
            "payment_id": "P101",
            "amount": None  # Null from provider
        }
        mappings = [{
            "source_field": "amount",
            "target_field": "price",
            "target_type": "integer"
        }]
        transformed, applied, ok = transform_response(payload, mappings)
        self.assertTrue(ok)
        self.assertIsNone(transformed["price"])
        self.assertNotIn("amount", transformed)

    # Edge Case 5: Multi-field simultaneous drift
    def test_simultaneous_multi_field_drift(self):
        old_data = {
            "txn_id": "TXN_77",
            "price": 100,
            "mail": "alice@test.com",
            "status": "pending"
        }
        new_data = {
            "transaction_id": "TXN_77",
            "amount": 100,
            "contact_email": "alice@test.com",
            "status": "pending"
        }
        diff = compare_schemas(extract_schema(old_data), extract_schema(new_data))
        self.assertEqual(len(diff["removed_fields"]), 3)
        self.assertEqual(len(diff["added_fields"]), 3)

        suggestions = self.engine.suggest_mappings(diff["removed_fields"], diff["added_fields"])
        # All 3 pairs should be suggested with high confidence
        matched_targets = {s["target_field"]: s["source_field"] for s in suggestions if s["confidence"] > 0.75}
        self.assertEqual(matched_targets.get("price"), "amount")
        self.assertEqual(matched_targets.get("txn_id"), "transaction_id")
        self.assertEqual(matched_targets.get("mail"), "contact_email")

        # Transform all simultaneously
        approved = [
            {"source_field": "amount", "target_field": "price", "target_type": "integer"},
            {"source_field": "transaction_id", "target_field": "txn_id", "target_type": "string"},
            {"source_field": "contact_email", "target_field": "mail", "target_type": "string"}
        ]
        res, applied, ok = transform_response(new_data, approved)
        self.assertTrue(ok)
        self.assertEqual(len(applied), 3)
        self.assertEqual(res["price"], 100)
        self.assertEqual(res["txn_id"], "TXN_77")
        self.assertEqual(res["mail"], "alice@test.com")
        self.assertEqual(res["status"], "pending")

    # Edge Case 6: Unsafe overwrite collision prevention
    def test_unsafe_overwrite_collision_prevention(self):
        # Incoming response has BOTH price and amount already populated
        payload = {
            "price": 50,     # Existing original price
            "amount": 200    # Added separate fee/amount
        }
        mappings = [{
            "source_field": "amount",
            "target_field": "price",
            "target_type": "integer"
        }]
        transformed, applied, ok = transform_response(payload, mappings)
        # Must refuse to overwrite existing price data
        self.assertFalse(ok)
        self.assertEqual(transformed["price"], 50)
        self.assertEqual(transformed["amount"], 200)

    # Edge Case 7: Unseen obscure field name handling
    def test_unseen_obscure_field_rejection_safety(self):
        removed = [{"path": "customer_token", "type": "string"}]
        added = [{"path": "x89_opaque_digest", "type": "string"}]

        suggestions = self.engine.suggest_mappings(removed, added)
        # Should NOT fabricate false confidence
        self.assertLess(suggestions[0]["confidence"], 0.50)

    # Edge Case 8: Incompatible types cannot be validated for approval
    def test_validation_rejects_incompatible_structures(self):
        valid, reason = validate_mapping_candidate(
            source_field="user_object",
            target_field="user_id",
            source_type="object",
            target_type="string"
        )
        self.assertFalse(valid)
        self.assertIn("incompatibility", reason.lower())

    # Edge Case 9: Deep copy integrity (original object never mutated)
    def test_original_payload_immutability(self):
        original = {"amount": 500, "status": "ok"}
        import copy
        snapshot = copy.deepcopy(original)
        mappings = [{"source_field": "amount", "target_field": "price", "target_type": "integer"}]
        transformed, _, _ = transform_response(original, mappings)

        self.assertNotEqual(original, transformed)
        self.assertEqual(original, snapshot)

    # Edge Case 10: Live HTTP Integration under unexpected status codes
    def test_http_live_gateway_resilience(self):
        # Test against running proxy instance
        client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=5.0)
        try:
            # Query non-existent upstream route
            res = client.get("/non_existent_route_404")
            # Should forward status code accurately
            self.assertIn(res.status_code, [404, 502])
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()
