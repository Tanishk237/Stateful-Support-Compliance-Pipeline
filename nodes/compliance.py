"""Compliance node for PII and policy checks."""

from pii import classify_risk, detect_pii
from state.workflow_state import WorkflowState


def evaluate_compliance(state: WorkflowState) -> WorkflowState:
    """Scan the raw email for PII and update the workflow state."""
    email_text = state.raw_email or ""
    pii_found = detect_pii(email_text)
    risk_level = classify_risk(pii_found)

    state.compliance_status = risk_level
    state.extracted_information.setdefault("compliance", risk_level)
    state.extracted_information["compliance_details"] = {
        "risk_level": risk_level,
        "pii_found": pii_found,
    }
    state.record_event("compliance", risk_level, "Compliance evaluation completed")
    return state
