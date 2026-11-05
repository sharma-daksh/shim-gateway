import unittest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from transformer import transform_response

class TestPhase6Transformation(unittest.TestCase):
    def test_correct_field_transformation(self):
        # New API payload
        payload = {
            "payment_id": "P101",
            "amount": 500,
            "status": "success"
        }
        approved_mappings = [{
            "source_field": "amount",
            "target_field": "price",
            "target_type": "integer"
        }]

        transformed, applied, was_transformed = transform_response(payload, approved_mappings)
        self.assertTrue(was_transformed)
        self.assertEqual(len(applied), 1)
        self.assertEqual(transformed["price"], 500)
        self.assertNotIn("amount", transformed)
        self.assertEqual(transformed["payment_id"], "P101")
        self.assertEqual(transformed["status"], "success")

    def test_nested_field_transformation(self):
        payload = {
            "order_id": "ORD-1",
            "customer": {
                "name": "Daksh",
                "address": {
                    "city": "Mumbai",
                    "postal_code": "400001"
                }
            }
        }
        approved_mappings = [{
            "source_field": "customer.address.postal_code",
            "target_field": "customer.address.zip",
            "target_type": "string"
        }]

        transformed, applied, was_transformed = transform_response(payload, approved_mappings)
        self.assertTrue(was_transformed)
        self.assertEqual(transformed["customer"]["address"]["zip"], "400001")
        self.assertNotIn("postal_code", transformed["customer"]["address"])
        self.assertEqual(transformed["customer"]["address"]["city"], "Mumbai")
        self.assertEqual(transformed["customer"]["name"], "Daksh")

    def test_preservation_of_unrelated_fields(self):
        payload = {
            "payment_id": "P101",
            "amount": 500,
            "fee": 15,
            "merchant_notes": "Urgent order",
            "deeply": {"nested": {"tag": "beta"}}
        }
        approved_mappings = [{
            "source_field": "amount",
            "target_field": "price",
            "target_type": "integer"
        }]

        transformed, applied, was_transformed = transform_response(payload, approved_mappings)
        self.assertTrue(was_transformed)
        self.assertEqual(transformed["price"], 500)
        self.assertEqual(transformed["fee"], 15)
        self.assertEqual(transformed["merchant_notes"], "Urgent order")
        self.assertEqual(transformed["deeply"]["nested"]["tag"], "beta")

    def test_missing_source_field_never_fabricates_value(self):
        # Incoming payload does not contain 'amount'
        payload = {
            "payment_id": "P101",
            "status": "failed"
        }
        approved_mappings = [{
            "source_field": "amount",
            "target_field": "price",
            "target_type": "integer"
        }]

        transformed, applied, was_transformed = transform_response(payload, approved_mappings)
        self.assertFalse(was_transformed)
        self.assertEqual(len(applied), 0)
        self.assertNotIn("price", transformed)
        self.assertEqual(transformed, payload)

    def test_safe_type_coercion(self):
        # Float 500.0 to integer 500
        payload = {"amount": 500.0}
        approved_mappings = [{
            "source_field": "amount",
            "target_field": "price",
            "target_type": "integer"
        }]

        transformed, applied, was_transformed = transform_response(payload, approved_mappings)
        self.assertTrue(was_transformed)
        self.assertEqual(transformed["price"], 500)
        self.assertIsInstance(transformed["price"], int)

    def test_unsafe_overwrite_protection(self):
        # Both amount and price exist in incoming payload
        payload = {
            "payment_id": "P101",
            "price": 250, # existing real price
            "amount": 500
        }
        approved_mappings = [{
            "source_field": "amount",
            "target_field": "price",
            "target_type": "integer"
        }]

        # Engine should detect target already exists and NOT clobber price
        transformed, applied, was_transformed = transform_response(payload, approved_mappings)
        self.assertFalse(was_transformed)
        self.assertEqual(transformed["price"], 250)
        self.assertEqual(transformed["amount"], 500)

if __name__ == "__main__":
    unittest.main()
