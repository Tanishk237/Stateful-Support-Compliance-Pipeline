"""Validation node for extracted complaint data."""

from typing import Any, Dict, List

from state.workflow_state import WorkflowState


REQUIRED_FIELDS = ["customer_name", "account_id", "claimed_amount", "expected_amount", "issue_type"]


def validate_extraction(state: WorkflowState) -> WorkflowState:
    """Validate extracted complaint information and update the workflow state."""
    payload = state.extracted_information or {}
    missing_fields: List[str] = []

    if payload.get("__parse_error__") is True:
        state.validation_status = "failed"
        state.missing_fields = REQUIRED_FIELDS.copy()
        state.record_event("validate", "failed", "Extraction output could not be parsed as JSON")
        return state

    for field in REQUIRED_FIELDS:
        value = payload.get(field)
        if value in (None, ""):
            missing_fields.append(field)
            continue

        if field in {"claimed_amount", "expected_amount"} and not isinstance(value, (int, float)):
            missing_fields.append(field)

    if missing_fields:
        state.validation_status = "clarification"
        state.missing_fields = missing_fields
    else:
        state.validation_status = "passed"
        state.missing_fields = []

    state.record_event("validate", state.validation_status, "Validation completed")
    return state
