"""Escalation node for non-compliant or unverifiable requests."""

import random
import string
from datetime import datetime
from pathlib import Path

from state.workflow_state import WorkflowState


ESCALATION_DIR = Path(__file__).resolve().parents[1] / "escalation_tickets"
ESCALATION_DIR.mkdir(exist_ok=True)


def create_escalation_ticket(state: WorkflowState) -> WorkflowState:
    """Create an internal escalation ticket for requests that cannot be automatically handled."""
    request_id = state.ensure_request_id()
    payload = state.extracted_information or {}
    ticket_id = _generate_ticket_id()
    created_at = datetime.now()
    priority = _determine_priority(state)
    department = _determine_department(state)
    reason = _build_reason(state)
    summary = _build_summary(state)

    ticket_text = f"""
INTERNAL ESCALATION TICKET
=========================
Ticket ID: {ticket_id}
Request ID: {request_id}
Date: {created_at.strftime('%Y-%m-%d %H:%M:%S')}
Customer: {payload.get('customer_name', 'Unknown')}
Account: {payload.get('account_id', 'Unknown')}
Priority: {priority}
Department: {department}

Reason:
{reason}

Summary:
{summary}

Execution History:
{_format_execution_history(state)}
""".strip()

    ticket_path = _write_ticket_file(ticket_id, created_at, ticket_text)
    payload["escalation_ticket_path"] = str(ticket_path)
    state.extracted_information = payload
    state.final_output = ticket_text
    state.route = "escalate"
    state.record_event("escalation", "ticket_created", f"Escalation ticket {ticket_id} saved to {ticket_path}")
    return state


def _generate_ticket_id() -> str:
    """Generate a unique ticket ID."""
    random_suffix = "".join(random.choices(string.digits, k=4))
    return f"T-{random_suffix}"


def _write_ticket_file(ticket_id: str, created_at: datetime, ticket_text: str) -> Path:
    """Persist an escalation ticket in the dedicated ticket folder."""
    timestamp = created_at.strftime("%Y%m%d_%H%M%S")
    ticket_path = ESCALATION_DIR / f"{timestamp}_{ticket_id}.txt"
    ticket_path.write_text(ticket_text + "\n", encoding="utf-8")
    return ticket_path


def _determine_priority(state: WorkflowState) -> str:
    """Determine the priority based on the workflow state."""
    if state.compliance_status in ("critical", "high"):
        return "high"
    if state.verification_status == "mismatch":
        return "medium"
    if state.retry_count >= 3:
        return "medium"
    return "low"


def _determine_department(state: WorkflowState) -> str:
    """Determine the appropriate department for the ticket."""
    if state.compliance_status in ("critical", "high"):
        return "compliance"
    if state.verification_status == "not_found":
        return "billing"
    if state.verification_status == "mismatch":
        return "billing"
    return "support"


def _build_reason(state: WorkflowState) -> str:
    """Build a concise reason for escalation."""
    if state.compliance_status in ("critical", "high"):
        pii_found = state.extracted_information.get("compliance_details", {}).get("pii_found", [])
        return f"Sensitive information detected in customer email: {', '.join(pii_found)}"
    if state.verification_status == "not_found":
        return "Account not found in the system."
    if state.verification_status == "mismatch":
        return "Billing amount mismatch detected between claim and records."
    if state.retry_count >= 3:
        return "Clarification retry limit exceeded; customer failed to provide required information."
    if state.validation_status == "clarification":
        missing = ", ".join(state.missing_fields or ["unknown fields"])
        return f"Required information missing: {missing}"
    return "Request requires manual review and escalation."


def _build_summary(state: WorkflowState) -> str:
    """Build a summary of the complaint and current state."""
    payload = state.extracted_information or {}
    lines = [
        f"Issue Type: {payload.get('issue_type', 'unspecified')}",
        f"Claimed Amount: ${payload.get('claimed_amount', 'N/A')}",
        f"Expected Amount: ${payload.get('expected_amount', 'N/A')}",
        f"Verification Status: {state.verification_status}",
        f"Compliance Status: {state.compliance_status}",
        f"Retry Count: {state.retry_count}/3",
    ]
    return "\n".join(lines)


def _format_execution_history(state: WorkflowState) -> str:
    """Format the execution history for the ticket."""
    if not state.execution_history:
        return "No execution history available."
    lines = []
    for entry in state.execution_history:
        step = entry.get("step", "unknown")
        status = entry.get("status", "unknown")
        lines.append(f"- {step}: {status}")
    return "\n".join(lines)
