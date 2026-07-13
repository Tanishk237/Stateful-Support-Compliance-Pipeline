import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.compliance import evaluate_compliance
from state.workflow_state import WorkflowState


def test_compliance_for_normal_email():
    state = WorkflowState(raw_email="Hello, I need help with a billing issue for my account.")

    updated_state = evaluate_compliance(state)

    assert updated_state.compliance_status == "safe"
    assert updated_state.extracted_information["compliance"] == "safe"


def test_compliance_for_credit_card():
    state = WorkflowState(raw_email="My card number is 4111 1111 1111 1111 and I need help.")

    updated_state = evaluate_compliance(state)

    assert updated_state.compliance_status == "high"
    assert "credit_card" in updated_state.extracted_information["compliance_details"]["pii_found"]


def test_compliance_for_pan():
    state = WorkflowState(raw_email="My PAN is ABCDE1234F and I want to dispute the charge.")

    updated_state = evaluate_compliance(state)

    assert updated_state.compliance_status == "high"
    assert "pan" in updated_state.extracted_information["compliance_details"]["pii_found"]


def test_compliance_for_phone():
    state = WorkflowState(raw_email="Please call me at +91 98765 43210 regarding this issue.")

    updated_state = evaluate_compliance(state)

    assert updated_state.compliance_status == "high"
    assert "phone" in updated_state.extracted_information["compliance_details"]["pii_found"]
