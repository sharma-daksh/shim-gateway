import unittest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from mapping_engine import IntelligentMappingEngine, evaluate_type_compatibility

class TestPhase4MappingEngine(unittest.TestCase):
    def setUp(self):
        self.engine = IntelligentMappingEngine(fallback_mode=True)

    def test_similar_and_synonymous_fields(self):
        # price (removed) vs amount (added)
        removed = [{"path": "price", "type": "integer"}]
        added = [{"path": "amount", "type": "integer"}]

        suggestions = self.engine.suggest_mappings(removed, added)
        self.assertEqual(len(suggestions), 1)
        top = suggestions[0]
        self.assertEqual(top["source_field"], "amount")
        self.assertEqual(top["target_field"], "price")
        self.assertGreaterEqual(top["confidence"], 0.85)
        self.assertIn("Semantic match", top["explanation"])

    def test_unrelated_fields_low_score(self):
        removed = [{"path": "price", "type": "integer"}]
        added = [{"path": "support_email", "type": "string"}]

        suggestions = self.engine.suggest_mappings(removed, added)
        self.assertEqual(len(suggestions), 1)
        self.assertLess(suggestions[0]["confidence"], 0.50)

    def test_type_incompatibility_rejection(self):
        # target expects integer, source is complex object -> should be filtered out
        removed = [{"path": "price", "type": "integer"}]
        added = [{"path": "cost_breakdown", "type": "object"}]

        suggestions = self.engine.suggest_mappings(removed, added)
        # Incompatible complex types are discarded from suggestions
        self.assertEqual(len(suggestions), 0)

    def test_nested_fields_depth_penalty(self):
        removed = [{"path": "customer.address.zip", "type": "string"}]
        added_same_depth = [{"path": "customer.address.postal_code", "type": "string"}]
        added_different_depth = [{"path": "postal_code", "type": "string"}]

        s_same = self.engine.suggest_mappings(removed, added_same_depth)[0]
        s_diff = self.engine.suggest_mappings(removed, added_different_depth)[0]

        # Sibling match at the exact same depth level should rank higher
        self.assertGreater(s_same["confidence"], s_diff["confidence"])

    def test_multiple_candidates_ranking(self):
        removed = [{"path": "price", "type": "integer"}]
        added = [
            {"path": "notes", "type": "string"},
            {"path": "amount", "type": "integer"},
            {"path": "currency", "type": "string"}
        ]

        suggestions = self.engine.suggest_mappings(removed, added)
        self.assertEqual(len(suggestions), 3)
        # Top ranked candidate must be amount
        self.assertEqual(suggestions[0]["source_field"], "amount")
        self.assertEqual(suggestions[0]["target_field"], "price")

    def test_ambiguous_mappings_flagged(self):
        # Two very similar fields: 'total_amount' and 'gross_amount'
        removed = [{"path": "amount", "type": "float"}]
        added = [
            {"path": "total_amount", "type": "float"},
            {"path": "gross_amount", "type": "float"}
        ]

        suggestions = self.engine.suggest_mappings(removed, added)
        self.assertEqual(len(suggestions), 2)
        # Both should be marked as ambiguous due to close confidence
        self.assertTrue(suggestions[0].get("ambiguous", False))
        self.assertTrue(suggestions[1].get("ambiguous", False))
        self.assertIn("AMBIGUOUS", suggestions[0]["explanation"])

    def test_safe_fallback_mode_operational(self):
        # Verify fallback mode generates valid scores without external model downloads
        score = self.engine.compute_semantic_similarity("payment_id", "transaction_id")
        self.assertGreater(score, 0.80)

if __name__ == "__main__":
    unittest.main()
