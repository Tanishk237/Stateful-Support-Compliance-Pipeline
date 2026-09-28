"""Clarification helpers for missing required information."""

from typing import Any, Dict

from prompts import build_clarification_prompt
from state.workflow_state import WorkflowState


def clarify_missing_information(state: WorkflowState) -> WorkflowState:
    """Return one customer-facing question and pause the workflow for an answer."""
    missing_fields = list(state.missing_fields or [])
    if not missing_fields:
        state.validation_status = "passed"
        state.route = "response"
        state.clarification_question = ""
        state.record_event("clarify", "completed", "No clarification required")
        return state

    if state.retry_count < 3:
        state.retry_count += 1
        state.validation_status = "awaiting_clarification"
        state.route = "clarification"
    else:
        state.validation_status = "clarification"
        state.route = "escalate"

    clarification_message = build_clarification_prompt(missing_fields[0], missing_fields)
    state.clarification_question = clarification_message
    state.final_output = clarification_message
    state.conversation_history.append(f"Support: {clarification_message}")
    state.record_event("clarify", "requested", clarification_message)
    return state


def apply_clarification_answers(state: WorkflowState, answers: Dict[str, Any]) -> WorkflowState:
    """Merge a customer's answers for currently missing fields and prepare validation.

    The caller supplies only the fields requested in ``state.missing_fields``.
    This keeps the resume contract simple for a CLI, web form, or API later.
    """
    if state.route != "clarification":
        raise ValueError("The workflow is not waiting for clarification")

    accepted_fields = []
    for field in state.missing_fields:
        value = answers.get(field)
        if value in (None, ""):
            continue
        setattr(state.extracted_information, field, _coerce_answer(field, value))
        accepted_fields.append(field)

    state.clarification_question = ""
    state.final_output = ""
    state.resume_from_clarification = True
    state.route = "pending"
    state.validation_status = "pending"
    state.record_event(
        "clarify",
        "answered",
        f"Customer supplied: {', '.join(accepted_fields) or 'no usable fields'}",
    )
    return state


def _coerce_answer(field: str, value: Any) -> Any:
    """Coerce form or CLI values into the extraction model's field types."""
    if field in {"claimed_amount", "expected_amount"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if field == "account_id":
        return str(value).strip().upper()
    return str(value).strip()
