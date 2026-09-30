"""Business verification node against the mock billing database."""

from models import BusinessVerification
from mock_db import find_account, verify_amount, verify_customer, verify_expected_amount
from state.workflow_state import WorkflowState


def verify_business_claim(state: WorkflowState) -> WorkflowState:
    """Verify the customer claim against the mock billing database."""
    payload = state.extracted_information
    account_id = payload.account_id.strip()
    customer_name = payload.customer_name.strip()
    claimed_amount = payload.claimed_amount
    expected_amount = payload.expected_amount

    account = find_account(account_id) if account_id else None
    account_found = account is not None

    if not account_found:
        state.verification_status = "not_found"
        state.business_verification = BusinessVerification(reason_codes=["ACCOUNT_NOT_FOUND"])
    else:
        identity_match = verify_customer(account_id, customer_name)
        claimed_amount_match = (
            verify_amount(account_id, claimed_amount) if claimed_amount is not None else False
        )
        expected_amount_match = (
            verify_expected_amount(account_id, expected_amount)
            if expected_amount is not None
            else False
        )
        account_status = str(account.get("status", "unknown"))
        account_active = account_status.casefold() == "active"

        actual_bill = float(account["actual_bill"])
        stored_expected_bill = float(account["expected_bill"])
        difference = (
            round(actual_bill - float(claimed_amount), 2)
            if claimed_amount is not None
            else None
        )
        calculated_discrepancy = (
            round(float(claimed_amount) - float(expected_amount), 2)
            if claimed_amount is not None and expected_amount is not None
            else None
        )
        recorded_discrepancy = round(actual_bill - stored_expected_bill, 2)
        discrepancy_match = (
            calculated_discrepancy == recorded_discrepancy
            if calculated_discrepancy is not None
            else False
        )

        reason_codes = []
        if not identity_match:
            reason_codes.append("IDENTITY_MISMATCH")
        if not account_active:
            reason_codes.append("ACCOUNT_INACTIVE")
        if not claimed_amount_match:
            reason_codes.append("CLAIMED_AMOUNT_MISMATCH")
        if not expected_amount_match:
            reason_codes.append("EXPECTED_AMOUNT_MISMATCH")
        if not discrepancy_match:
            reason_codes.append("DISCREPANCY_MISMATCH")

        billing_match = claimed_amount_match and expected_amount_match and discrepancy_match
        verified = identity_match and account_active and billing_match
        if verified:
            reason_codes.append("VERIFIED")

        state.business_verification = BusinessVerification(
            account_found=True,
            identity_match=identity_match,
            claimed_amount_match=claimed_amount_match,
            expected_amount_match=expected_amount_match,
            account_status=account_status,
            account_active=account_active,
            calculated_discrepancy=calculated_discrepancy,
            recorded_discrepancy=recorded_discrepancy,
            discrepancy_match=discrepancy_match,
            billing_match=billing_match,
            difference=difference,
            reason_codes=reason_codes,
        )

        state.verification_status = "verified" if verified else "mismatch"

    reasons = ", ".join(state.business_verification.reason_codes)
    state.record_event(
        "verify",
        state.verification_status,
        f"Business verification completed: {reasons}",
    )
    return state
