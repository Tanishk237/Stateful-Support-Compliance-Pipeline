"""Clarification node for missing required information."""

from typing import List

from prompts import build_clarification_prompt
from state.workflow_state import WorkflowState


def clarify_missing_information(state: WorkflowState) -> WorkflowState:
    """Create a clarification request for the missing fields and update retry state."""
    missing_fields = list(state.missing_fields or [])
    if not missing_fields:
        state.validation_status = "passed"
        state.route = "response"
        state.record_event("clarify", "completed", "No clarification required")
        return state

    if state.retry_count < 3:
        state.retry_count += 1
        state.validation_status = "clarification"
        state.route = "retry"
    else:
        state.validation_status = "clarification"
        state.route = "escalate"

    clarification_message = build_clarification_prompt(missing_fields[0], missing_fields)
    state.conversation_history.append(clarification_message)
    state.record_event("clarify", "requested", clarification_message)
    return state
