import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.response import generate_customer_response
from state.workflow_state import WorkflowState


def test_generate_response_for_safe_validated_verified_request():
    state = WorkflowState(
        extracted_information={
            "customer_name": "Alice Johnson",
            "account_id": "ACC1023",
            "claimed_amount": 120.0,
            "expected_amount": 100.0,
            "issue_type": "billing_error",
            "account_found": True,
            "billing_match": True,
            "difference": 0.0,
            "compliance": "safe",
        },
        compliance_status="safe",
        verification_status="verified",
        validation_status="passed",
    )

    updated_state = generate_customer_response(state)

    assert updated_state.final_output != ""
    assert updated_state.route == "response"
    assert updated_state.request_id.startswith("REQ-")
    assert updated_state.request_id in updated_state.final_output
    assert "Alice" in updated_state.final_output or "billing" in updated_state.final_output.lower()


def test_generate_response_only_when_safe_and_verified():
    state = WorkflowState(
        extracted_information={
            "customer_name": "Bob",
            "account_id": "ACC2045",
            "compliance": "high",
        },
        compliance_status="high",
        verification_status="not_found",
        validation_status="passed",
    )

    updated_state = generate_customer_response(state)

    assert updated_state.route == "escalate"
    assert updated_state.final_output == ""
