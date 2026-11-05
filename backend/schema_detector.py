"""
Schema detection, recursive comparison, and versioning engine for SHIM.
"""
from typing import Dict, Any, List, Optional, Tuple, Set
import hashlib
import json
import time

def infer_field_type(value: Any) -> str:
    """Infer semantic and structural type of a value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    return "unknown"

def extract_schema(data: Any, current_path: str = "") -> Dict[str, Any]:
    """
    Recursively extracts the structural schema of any JSON payload.
    Captures paths, types, and array item signatures.
    """
    field_type = infer_field_type(data)
    
    if field_type == "object":
        properties = {}
        for k, v in data.items():
            child_path = f"{current_path}.{k}" if current_path else k
            properties[k] = extract_schema(v, child_path)
        return {
            "type": "object",
            "path": current_path or "$",
            "properties": properties
        }
    elif field_type == "array":
        if not data:
            return {
                "type": "array",
                "path": current_path or "$",
                "items": {"type": "any"}
            }
        # Sample items to deduce element schema
        first_item = data[0]
        item_path = f"{current_path}[]" if current_path else "[]"
        return {
            "type": "array",
            "path": current_path or "$",
            "items": extract_schema(first_item, item_path)
        }
    else:
        return {
            "type": field_type,
            "path": current_path or "$"
        }

def flatten_schema(schema: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """
    Flattens a hierarchical schema into a mapping of {field_path: field_type}.
    e.g. {'payment_id': 'string', 'price': 'integer', 'card.brand': 'string'}
    """
    flat = {}
    stype = schema.get("type")
    
    if stype == "object":
        for prop_name, prop_schema in schema.get("properties", {}).items():
            full_path = f"{prefix}.{prop_name}" if prefix else prop_name
            if prop_schema.get("type") == "object":
                flat.update(flatten_schema(prop_schema, full_path))
            elif prop_schema.get("type") == "array":
                flat[f"{full_path}[]"] = f"array[{prop_schema.get('items', {}).get('type', 'any')}]"
                if prop_schema.get("items", {}).get("type") == "object":
                    flat.update(flatten_schema(prop_schema.get("items", {}), f"{full_path}[]"))
            else:
                flat[full_path] = prop_schema.get("type", "unknown")
    elif stype == "array":
        full_path = f"{prefix}[]" if prefix else "[]"
        item_schema = schema.get("items", {})
        flat[full_path] = f"array[{item_schema.get('type', 'any')}]"
        if item_schema.get("type") == "object":
            flat.update(flatten_schema(item_schema, full_path))
    else:
        flat[prefix or "$"] = stype
        
    return flat

def compute_schema_hash(schema: Dict[str, Any]) -> str:
    """Generate deterministic SHA-256 hash representing structural schema."""
    flat = flatten_schema(schema)
    canonical = json.dumps(sorted(flat.items()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

def compare_schemas(
    old_schema: Dict[str, Any],
    new_schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compares two schemas recursively and identifies:
    - added_fields: list of {path, type}
    - removed_fields: list of {path, type}
    - type_changes: list of {path, old_type, new_type}
    - potential_renames: list of {old_field, new_field, old_type, new_type, confidence}
    - has_changed: boolean
    """
    old_flat = flatten_schema(old_schema)
    new_flat = flatten_schema(new_schema)

    added_fields = []
    removed_fields = []
    type_changes = []
    potential_renames = []

    # Detect removed fields or type changes
    for path, otype in old_flat.items():
        if path not in new_flat:
            removed_fields.append({"path": path, "type": otype})
        else:
            ntype = new_flat[path]
            if otype != ntype:
                type_changes.append({
                    "path": path,
                    "old_type": otype,
                    "new_type": ntype
                })

    # Detect added fields
    for path, ntype in new_flat.items():
        if path not in old_flat:
            added_fields.append({"path": path, "type": ntype})

    # Detect potential renames (heuristic pairing by depth and type compatibility)
    for rem in removed_fields:
        r_name = rem["path"].split(".")[-1]
        r_depth = rem["path"].count(".")
        for add in added_fields:
            a_name = add["path"].split(".")[-1]
            a_depth = add["path"].count(".")
            # If at the same nesting level and compatible types
            if r_depth == a_depth:
                type_compat = (rem["type"] == add["type"]) or \
                    ({rem["type"], add["type"]}.issubset({"integer", "float"}))
                if type_compat:
                    potential_renames.append({
                        "old_field": rem["path"],
                        "new_field": add["path"],
                        "old_type": rem["type"],
                        "new_type": add["type"],
                        "same_depth": True
                    })

    has_changed = bool(added_fields or removed_fields or type_changes)

    return {
        "has_changed": has_changed,
        "added_fields": added_fields,
        "removed_fields": removed_fields,
        "type_changes": type_changes,
        "potential_renames": potential_renames,
        "old_hash": compute_schema_hash(old_schema),
        "new_hash": compute_schema_hash(new_schema)
    }

class SchemaVersionRegistry:
    """In-memory or persistent store for endpoint baseline schemas and versions."""
    def __init__(self):
        # endpoint_key -> list of versions
        self._endpoints: Dict[str, List[Dict[str, Any]]] = {}

    def get_baseline(self, endpoint_key: str) -> Optional[Dict[str, Any]]:
        history = self._endpoints.get(endpoint_key, [])
        return history[0]["schema"] if history else None

    def get_latest(self, endpoint_key: str) -> Optional[Dict[str, Any]]:
        history = self._endpoints.get(endpoint_key, [])
        return history[-1]["schema"] if history else None

    def register_response(self, endpoint_key: str, data: Any) -> Tuple[bool, Dict[str, Any]]:
        """
        Processes a response for an endpoint.
        Returns (is_new_version, diff_or_info)
        """
        current_schema = extract_schema(data)
        current_hash = compute_schema_hash(current_schema)
        timestamp = time.time()

        if endpoint_key not in self._endpoints:
            # First time seeing this endpoint: store as baseline v1
            record = {
                "version": 1,
                "version_tag": f"v1-{current_hash}",
                "schema_hash": current_hash,
                "schema": current_schema,
                "timestamp": timestamp,
                "is_baseline": True
            }
            self._endpoints[endpoint_key] = [record]
            return False, {"status": "baseline_established", "version": 1, "schema_hash": current_hash}

        latest_record = self._endpoints[endpoint_key][-1]
        if latest_record["schema_hash"] == current_hash:
            # Structure has not changed (ordinary value change or identical schema)
            return False, {"status": "unchanged", "version": latest_record["version"], "schema_hash": current_hash}

        # Structure has changed!
        diff = compare_schemas(latest_record["schema"], current_schema)
        new_version_num = len(self._endpoints[endpoint_key]) + 1
        new_record = {
            "version": new_version_num,
            "version_tag": f"v{new_version_num}-{current_hash}",
            "schema_hash": current_hash,
            "schema": current_schema,
            "timestamp": timestamp,
            "is_baseline": False,
            "diff_from_previous": diff
        }
        self._endpoints[endpoint_key].append(new_record)
        return True, {
            "status": "schema_change_detected",
            "version": new_version_num,
            "diff": diff,
            "schema_hash": current_hash
        }
