import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.verify import verify_business_claim
from models import ExtractedInformation
from state.workflow_state import WorkflowState


def test_verify_business_claim_for_existing_account_and_matching_bill():
    state = WorkflowState(
        extracted_information=ExtractedInformation(
            account_id="ACC1023", customer_name="Alice Johnson",
            claimed_amount=120.0, expected_amount=100.0
        )
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "verified"
    assert updated_state.business_verification.account_found is True
    assert updated_state.business_verification.identity_match is True
    assert updated_state.business_verification.claimed_amount_match is True
    assert updated_state.business_verification.expected_amount_match is True
    assert updated_state.business_verification.account_active is True
    assert updated_state.business_verification.calculated_discrepancy == 20.0
    assert updated_state.business_verification.recorded_discrepancy == 20.0
    assert updated_state.business_verification.reason_codes == ["VERIFIED"]
    assert updated_state.business_verification.billing_match is True
    assert updated_state.business_verification.difference == 0.0


def test_verify_business_claim_for_missing_account():
    state = WorkflowState(
        extracted_information=ExtractedInformation(
            account_id="ACC9999", customer_name="Ghost User",
            claimed_amount=50.0, expected_amount=30.0
        )
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "not_found"
    assert updated_state.business_verification.account_found is False
    assert updated_state.business_verification.reason_codes == ["ACCOUNT_NOT_FOUND"]


def test_verify_business_claim_for_bill_mismatch():
    state = WorkflowState(
        extracted_information=ExtractedInformation(
            account_id="ACC1023", customer_name="Alice Johnson",
            claimed_amount=90.0, expected_amount=100.0
        )
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "mismatch"
    assert updated_state.business_verification.billing_match is False
    assert updated_state.business_verification.difference == 30.0
    assert "CLAIMED_AMOUNT_MISMATCH" in updated_state.business_verification.reason_codes
    assert "DISCREPANCY_MISMATCH" in updated_state.business_verification.reason_codes


def test_verify_business_claim_reports_identity_mismatch():
    state = WorkflowState(
        extracted_information=ExtractedInformation(
            account_id="ACC1023", customer_name="Someone Else",
            claimed_amount=120.0, expected_amount=100.0
        )
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "mismatch"
    assert updated_state.business_verification.identity_match is False
    assert updated_state.business_verification.reason_codes == ["IDENTITY_MISMATCH"]


def test_verify_business_claim_checks_account_status(monkeypatch):
    from mock_db import CUSTOMER_RECORDS

    monkeypatch.setitem(CUSTOMER_RECORDS["ACC2045"], "status", "suspended")
    state = WorkflowState(
        extracted_information=ExtractedInformation(
            account_id="ACC2045", customer_name="Ben Carter",
            claimed_amount=80.0, expected_amount=60.0
        )
    )

    updated_state = verify_business_claim(state)

    assert updated_state.verification_status == "mismatch"
    assert updated_state.business_verification.account_status == "suspended"
    assert updated_state.business_verification.account_active is False
    assert updated_state.business_verification.reason_codes == ["ACCOUNT_INACTIVE"]
