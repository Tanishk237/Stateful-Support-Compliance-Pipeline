import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.verify import verify_business_claim
from state.workflow_state import WorkflowState


def test_verify_business_claim_for_existing_account_and_matching_bill():
    state = WorkflowState(
        extracted_information={
            "account_id": "ACC1023",
            "customer_name": "Alice Johnson",
            "claimed_amount": 120.0,
        }
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "verified"
    assert updated_state.extracted_information["account_found"] is True
    assert updated_state.extracted_information["billing_match"] is True
    assert updated_state.extracted_information["difference"] == 0.0


def test_verify_business_claim_for_missing_account():
    state = WorkflowState(
        extracted_information={
            "account_id": "ACC9999",
            "customer_name": "Ghost User",
            "claimed_amount": 50.0,
        }
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "not_found"
    assert updated_state.extracted_information["account_found"] is False


def test_verify_business_claim_for_bill_mismatch():
    state = WorkflowState(
        extracted_information={
            "account_id": "ACC1023",
            "customer_name": "Alice Johnson",
            "claimed_amount": 90.0,
        }
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "mismatch"
    assert updated_state.extracted_information["billing_match"] is False
    assert updated_state.extracted_information["difference"] == 30.0
