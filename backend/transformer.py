"""
Safe JSON Response Transformation Engine for SHIM.
Applies approved mappings, validates types, and preserves unrelated fields.
Never fabricates missing financial data or silently discards valid fields.
"""
from typing import Dict, Any, List, Optional, Tuple
import copy
import logging

logger = logging.getLogger("shim.transformer")

def get_nested_value(data: Any, path: str) -> Tuple[bool, Any]:
    """Retrieve value from a nested dict/list using dot path."""
    if not path:
        return False, None
    parts = path.split(".")
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return False, None
    return True, curr

def set_nested_value(data: Dict[str, Any], path: str, value: Any) -> None:
    """Set value in nested dict creating intermediate objects as necessary."""
    parts = path.split(".")
    curr = data
    for part in parts[:-1]:
        if part not in curr or not isinstance(curr[part], dict):
            curr[part] = {}
        curr = curr[part]
    curr[parts[-1]] = value

def delete_nested_key(data: Dict[str, Any], path: str) -> None:
    """Safely delete key from nested dict if present."""
    parts = path.split(".")
    curr = data
    for part in parts[:-1]:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return
    if isinstance(curr, dict) and parts[-1] in curr:
        del curr[parts[-1]]

def coerce_type(value: Any, target_type: str) -> Tuple[bool, Any]:
    """Safely coerces value to expected target type without inventing data."""
    if value is None:
        return True, None

    try:
        if target_type == "integer":
            if isinstance(value, bool):
                return False, None
            if isinstance(value, (int, float)):
                return True, int(value)
            if isinstance(value, str) and value.strip().replace("-", "").isdigit():
                return True, int(value.strip())
            return False, None

        elif target_type == "float":
            if isinstance(value, bool):
                return False, None
            if isinstance(value, (int, float)):
                return True, float(value)
            if isinstance(value, str):
                return True, float(value.strip())
            return False, None

        elif target_type == "string":
            if isinstance(value, (int, float, bool, str)):
                return True, str(value)
            return False, None

        elif target_type == "boolean":
            if isinstance(value, bool):
                return True, value
            if isinstance(value, str):
                if value.lower() in ["true", "1", "yes"]:
                    return True, True
                if value.lower() in ["false", "0", "no"]:
                    return True, False
            return False, None

        return True, value
    except Exception:
        return False, None

def transform_response(
    payload: Dict[str, Any],
    approved_mappings: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
    """
    Applies approved mappings to incoming JSON response.
    Returns (transformed_payload, applied_mappings, was_transformed).
    """
    if not approved_mappings or not isinstance(payload, dict):
        return payload, [], False

    # Deep copy to prevent side-effects on original payload
    transformed = copy.deepcopy(payload)
    applied = []
    was_transformed = False

    for mapping in approved_mappings:
        source_field = mapping["source_field"]
        target_field = mapping["target_field"]
        target_type = mapping.get("target_type", "unknown")

        found, source_val = get_nested_value(transformed, source_field)
        if not found:
            # Source field missing from this particular response; do not invent data
            continue

        # Prevent unsafe overwrite: if target_field already exists with a non-null value, do not blindly overwrite
        target_exists, existing_target_val = get_nested_value(transformed, target_field)
        if target_exists and existing_target_val is not None:
            logger.warning(f"Unsafe overwrite avoided: {target_field} already exists with data.")
            continue

        # Coerce type safely if needed
        valid_type, coerced_val = coerce_type(source_val, target_type)
        if not valid_type:
            logger.warning(f"Type mismatch: could not coerce {source_val} to {target_type}")
            continue

        # Write to target path
        set_nested_value(transformed, target_field, coerced_val)

        # Remove source field if it's different from target
        if source_field != target_field:
            delete_nested_key(transformed, source_field)

        was_transformed = True
        applied.append({
            "source_field": source_field,
            "target_field": target_field,
            "original_value": source_val,
            "transformed_value": coerced_val
        })

    return transformed, applied, was_transformed
