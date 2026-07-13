import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.validate import validate_extraction
from state.workflow_state import WorkflowState


def test_validate_extraction_passes_for_valid_payload():
    state = WorkflowState(
        raw_email="Billing issue",
        extracted_information={
            "customer_name": "Alice",
            "account_id": "ACC1023",
            "claimed_amount": 120.0,
            "expected_amount": 100.0,
            "issue_type": "billing_error",
        },
    )

    updated_state = validate_extraction(state)

    assert updated_state.validation_status == "passed"
    assert updated_state.missing_fields == []


def test_validate_extraction_requests_clarification_for_missing_values():
    state = WorkflowState(
        raw_email="Billing issue",
        extracted_information={
            "customer_name": "",
            "account_id": "ACC1023",
            "claimed_amount": 120.0,
            "expected_amount": 100.0,
            "issue_type": "billing_error",
        },
    )

    updated_state = validate_extraction(state)

    assert updated_state.validation_status == "clarification"
    assert "customer_name" in updated_state.missing_fields


def test_validate_extraction_handles_malformed_payload_shape():
    state = WorkflowState(
        raw_email="Billing issue",
        extracted_information={
            "customer_name": "Alice",
            "account_id": "ACC1023",
            "claimed_amount": "not-a-number",
            "expected_amount": 100.0,
            "issue_type": "billing_error",
        },
    )

    updated_state = validate_extraction(state)

    assert updated_state.validation_status == "clarification"
    assert "claimed_amount" in updated_state.missing_fields
