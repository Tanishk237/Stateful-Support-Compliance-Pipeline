"""Compliance node for PII and policy checks."""

from models import ComplianceResult
from pii import classify_risk, detect_pii, redact_pii
from state.workflow_state import WorkflowState


def evaluate_compliance(state: WorkflowState) -> WorkflowState:
    """Scan and redact the email before any external model can receive it."""
    email_text = state.raw_email or ""
    pii_found = detect_pii(email_text)
    risk_level = classify_risk(pii_found)

    state.compliance_result = ComplianceResult(
        is_safe=risk_level == "safe",
        risk_level=risk_level,
        pii_found=pii_found,
    )
    state.compliance_status = risk_level
    state.redacted_email = redact_pii(email_text)
    state.record_event("compliance", risk_level, "Compliance evaluation completed")
    return state
