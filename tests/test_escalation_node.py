import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes import escalation
from nodes.escalation import create_escalation_ticket
from models import ComplianceResult, ExtractedInformation
from state.workflow_state import WorkflowState


def test_escalation_ticket_for_unverified_account(tmp_path, monkeypatch):
    monkeypatch.setattr(escalation, "ESCALATION_DIR", tmp_path)
    state = WorkflowState(
        extracted_information=ExtractedInformation(
            customer_name="Alice", account_id="ACC9999", issue_type="billing_error"
        ),
        verification_status="not_found",
        compliance_status="safe",
    )

    updated_state = create_escalation_ticket(state)

    assert updated_state.final_output != ""
    assert "T-" in updated_state.final_output
    assert updated_state.request_id.startswith("REQ-")
    assert updated_state.request_id in updated_state.final_output
    ticket_path = updated_state.escalation_ticket.ticket_path
    assert str(tmp_path) in ticket_path
    assert updated_state.request_id in Path(ticket_path).read_text()
    assert "billing" in updated_state.final_output.lower() or "issue" in updated_state.final_output.lower()
    assert updated_state.route == "billing_review"


def test_escalation_ticket_for_compliance_violation():
    state = WorkflowState(
        extracted_information=ExtractedInformation(
            customer_name="Bob", account_id="ACC1023", issue_type="billing_error"
        ),
        compliance_result=ComplianceResult(is_safe=False, risk_level="high", pii_found=["credit_card"]),
        verification_status="verified",
        compliance_status="high",
    )

    updated_state = create_escalation_ticket(state)

    assert updated_state.final_output != ""
    assert "T-" in updated_state.final_output
    assert "high" in updated_state.final_output.lower() or "pii" in updated_state.final_output.lower()
    assert updated_state.route == "compliance_escalation"


def test_escalation_ticket_for_retry_exceeded():
    state = WorkflowState(
        raw_email="Missing all required fields",
        extracted_information=ExtractedInformation(issue_type="billing_error"),
        retry_count=3,
        validation_status="clarification",
    )

    updated_state = create_escalation_ticket(state)

    assert updated_state.final_output != ""
    assert "T-" in updated_state.final_output
    assert "retry" in updated_state.final_output.lower() or "clarification" in updated_state.final_output.lower()
