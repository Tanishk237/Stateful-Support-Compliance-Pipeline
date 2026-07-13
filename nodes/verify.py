"""Verification node against the mock billing database."""

from typing import Dict, Any

from mock_db import find_account, verify_amount, verify_customer
from state.workflow_state import WorkflowState


def verify_business_claim(state: WorkflowState) -> WorkflowState:
    """Verify the customer claim against the mock billing database."""
    payload = state.extracted_information or {}
    account_id = str(payload.get("account_id", "")).strip()
    customer_name = str(payload.get("customer_name", "")).strip()
    claimed_amount = payload.get("claimed_amount")

    account = find_account(account_id) if account_id else None
    account_found = account is not None

    if not account_found:
        state.verification_status = "not_found"
        payload["account_found"] = False
        payload["billing_match"] = False
        payload["difference"] = None
    else:
        customer_match = verify_customer(account_id, customer_name)
        amount_match = verify_amount(account_id, claimed_amount) if claimed_amount is not None else False

        payload["account_found"] = True
        payload["billing_match"] = customer_match and amount_match
        if account_found and claimed_amount is not None:
            difference = float(account["actual_bill"]) - float(claimed_amount)
            payload["difference"] = round(difference, 2)
        else:
            payload["difference"] = None

        if customer_match and amount_match:
            state.verification_status = "verified"
        else:
            state.verification_status = "mismatch"

    state.extracted_information = payload
    state.record_event("verify", state.verification_status, "Business claim verification completed")
    return state
