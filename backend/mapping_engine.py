"""
Intelligent Field Mapping Engine for SHIM.
Combines semantic embeddings, structural context, and type compatibility.
Includes safe fallback when heavy embedding models are unavailable.
"""
import math
import re
from typing import Dict, Any, List, Optional, Tuple

# Domain-specific synonym priors for standard web APIs
API_SYNONYM_CLUSTERS = [
    {
        "price", "amount", "cost", "total", "fee", "charge", "value", 
        "subtotal", "gross_amount", "net_amount", "total_amount", "order_total", "payment_amount"
    },
    {"payment_id", "transaction_id", "txn_id", "order_id", "charge_id", "id", "reference_id"},
    {"status", "state", "result", "outcome", "condition"},
    {"customer_id", "user_id", "client_id", "account_id", "member_id"},
    {"currency", "curr", "currency_code"},
    {"postal_code", "zip", "zip_code", "zipcode", "postcode"},
    {"created_at", "timestamp", "creation_date", "date_created", "time"},
    {"updated_at", "modified_at", "last_updated"},
    {"email", "email_address", "mail", "contact_email", "user_email"},
    {"phone", "phone_number", "telephone", "mobile", "contact_phone"}
]

def tokenize_field_name(name: str) -> List[str]:
    """Split snake_case, camelCase, kebab-case, and dot paths into lower tokens."""
    leaf = name.split(".")[-1].replace("[]", "")
    parts = re.findall(r'[A-Za-z]+|\d+', leaf)
    tokens = []
    for p in parts:
        s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', p).lower()
        tokens.extend(s.split('_'))
    return [t for t in tokens if t]

def get_char_ngram_vector(text: str, n: int = 3) -> Dict[str, float]:
    """Generate subword character n-gram bag of features for fallback embedding."""
    clean = f"^{text.lower()}$"
    vec = {}
    for i in range(len(clean) - n + 1):
        gram = clean[i:i+n]
        vec[gram] = vec.get(gram, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm > 0:
        for k in vec:
            vec[k] /= norm
    return vec

def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse feature vectors."""
    dot = sum(v1[k] * v2[k] for k in v1 if k in v2)
    return max(0.0, min(1.0, dot))

def evaluate_type_compatibility(source_type: str, target_type: str) -> Tuple[float, str]:
    """
    Evaluates whether two data types can be safely converted without data loss.
    Returns (score, reason).
    """
    if source_type == target_type:
        return 1.0, "Exact type match"

    numeric = {"integer", "float"}
    if {source_type, target_type}.issubset(numeric):
        return 0.95, "Compatible numeric types"

    if (source_type in numeric and target_type == "string") or (source_type == "string" and target_type in numeric):
        return 0.70, "Coercible string-numeric conversion"

    if "object" in (source_type, target_type) or "array" in (source_type, target_type):
        return 0.0, f"Incompatible complex type: {source_type} vs {target_type}"

    return 0.40, f"Uncertain type conversion: {source_type} to {target_type}"

class IntelligentMappingEngine:
    """
    Intelligent field matching engine.
    Uses semantic subword vectors + synonym clusters + structural depth & type validation.
    """
    def __init__(self, fallback_mode: bool = True):
        self.fallback_mode = fallback_mode

    def compute_semantic_similarity(self, field_a: str, field_b: str) -> float:
        """Computes semantic similarity score [0.0, 1.0] between two field names."""
        leaf_a = field_a.split(".")[-1].replace("[]", "").lower()
        leaf_b = field_b.split(".")[-1].replace("[]", "").lower()

        if leaf_a == leaf_b:
            return 1.0

        # Check domain-specific synonym priors
        for cluster in API_SYNONYM_CLUSTERS:
            if leaf_a in cluster and leaf_b in cluster:
                return 0.94
            # Also check if any constituent token is in the cluster
            tokens_a = set(tokenize_field_name(leaf_a))
            tokens_b = set(tokenize_field_name(leaf_b))
            if tokens_a & cluster and tokens_b & cluster:
                return 0.91

        # Token intersection
        tokens_a = set(tokenize_field_name(leaf_a))
        tokens_b = set(tokenize_field_name(leaf_b))
        if tokens_a and tokens_b:
            jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
            if jaccard > 0:
                return round(0.60 + (jaccard * 0.35), 3)

        # Subword character n-gram embedding cosine similarity
        v_a = get_char_ngram_vector(leaf_a)
        v_b = get_char_ngram_vector(leaf_b)
        subword_sim = cosine_similarity(v_a, v_b)

        return round(subword_sim, 3)

    def suggest_mappings(
        self,
        removed_fields: List[Dict[str, str]], # target expected by application
        added_fields: List[Dict[str, str]]    # source present in new response
    ) -> List[Dict[str, Any]]:
        """
        Suggests field mappings from added (new API) -> removed (expected by app).
        Returns candidates with confidence scores and explanations.
        """
        suggestions = []

        for target in removed_fields:
            target_path = target["path"]
            target_type = target["type"]
            target_depth = target_path.count(".")

            candidates = []
            for source in added_fields:
                source_path = source["path"]
                source_type = source["type"]
                source_depth = source_path.count(".")

                # 1. Semantic score
                sem_score = self.compute_semantic_similarity(source_path, target_path)

                # 2. Structural depth penalty
                depth_diff = abs(source_depth - target_depth)
                structural_penalty = 0.15 * depth_diff
                struct_score = max(0.0, 1.0 - structural_penalty)

                # 3. Type compatibility
                type_score, type_reason = evaluate_type_compatibility(source_type, target_type)

                # If types are completely incompatible (e.g. object to int), reject candidate
                if type_score <= 0.0:
                    continue

                # Composite confidence: 55% semantic, 25% type, 20% structural
                raw_confidence = (0.55 * sem_score) + (0.25 * type_score) + (0.20 * struct_score)
                confidence = round(max(0.0, min(1.0, raw_confidence)), 3)

                explanation = (
                    f"Semantic match: {sem_score:.2f} ('{source_path}' -> '{target_path}'). "
                    f"Type compatibility: {type_reason} ({source_type} -> {target_type}). "
                    f"Depth difference: {depth_diff}."
                )

                candidates.append({
                    "source_field": source_path,
                    "target_field": target_path,
                    "source_type": source_type,
                    "target_type": target_type,
                    "similarity_score": sem_score,
                    "confidence": confidence,
                    "explanation": explanation
                })

            candidates.sort(key=lambda c: c["confidence"], reverse=True)

            # Detect ambiguity if top candidates are close
            if len(candidates) >= 2:
                top_diff = abs(candidates[0]["confidence"] - candidates[1]["confidence"])
                if top_diff < 0.10 and candidates[0]["confidence"] > 0.5:
                    candidates[0]["ambiguous"] = True
                    candidates[1]["ambiguous"] = True
                    candidates[0]["explanation"] += " [AMBIGUOUS: Close alternative candidate found]"
                    candidates[1]["explanation"] += " [AMBIGUOUS: Close alternative candidate found]"

            suggestions.extend(candidates)

        return suggestions
