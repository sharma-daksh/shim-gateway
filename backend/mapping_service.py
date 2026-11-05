"""
Mapping Approval and Validation Service for SHIM.
Enforces validation rules, status lifecycles, and project access controls.
"""
from typing import Dict, Any, List, Optional, Tuple
import uuid
import time
from database import (
    get_project,
    upsert_mapping,
    update_mapping_status,
    get_approved_mappings,
    get_mappings_for_project,
    get_connection,
    DB_PATH
)
from mapping_engine import evaluate_type_compatibility

VALID_STATUSES = {"PENDING", "APPROVED", "REJECTED", "DISABLED"}

def validate_mapping_candidate(
    source_field: str,
    target_field: str,
    source_type: str,
    target_type: str
) -> Tuple[bool, str]:
    """
    Validates whether a mapping rule can be legally approved.
    Rejects incompatible types and empty field specifications.
    """
    if not source_field or not target_field:
        return False, "Source and target fields cannot be empty."

    if source_field == target_field:
        return False, "Source field cannot be identical to target field."

    type_score, reason = evaluate_type_compatibility(source_type, target_type)
    if type_score <= 0.0:
        return False, f"Type incompatibility: {reason}"

    return True, "Valid mapping specification"

def approve_mapping_request(
    mapping_id: str,
    project_id: str,
    user_id: str,
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Validates and transitions a mapping to APPROVED status.
    Verifies project access and rule validity before allowing approval.
    """
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM field_mappings WHERE id = ?", (mapping_id,)).fetchone()
    if not row:
        return False, "Mapping not found"

    mapping = dict(row)
    if mapping["project_id"] != project_id:
        return False, "Access denied: mapping does not belong to this project"

    # Validate before approving
    is_valid, reason = validate_mapping_candidate(
        mapping["source_field"],
        mapping["target_field"],
        mapping["source_type"],
        mapping["target_type"]
    )
    if not is_valid:
        return False, f"Approval rejected: {reason}"

    success = update_mapping_status(mapping_id, "APPROVED", approved_by=user_id, db_path=db_path)
    return success, "Mapping approved successfully"

def reject_mapping_request(
    mapping_id: str,
    project_id: str,
    user_id: str,
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM field_mappings WHERE id = ?", (mapping_id,)).fetchone()
    if not row:
        return False, "Mapping not found"
    if row["project_id"] != project_id:
        return False, "Access denied"

    success = update_mapping_status(mapping_id, "REJECTED", approved_by=user_id, db_path=db_path)
    return success, "Mapping rejected"

def disable_mapping_request(
    mapping_id: str,
    project_id: str,
    user_id: str,
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM field_mappings WHERE id = ?", (mapping_id,)).fetchone()
    if not row:
        return False, "Mapping not found"
    if row["project_id"] != project_id:
        return False, "Access denied"

    success = update_mapping_status(mapping_id, "DISABLED", approved_by=user_id, db_path=db_path)
    return success, "Mapping disabled"
