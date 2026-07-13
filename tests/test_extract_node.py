import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.extract import extract_information
from nodes.extract import _normalize_payload
from state.workflow_state import WorkflowState


def test_extract_information_from_normal_billing_email():
    state = WorkflowState(raw_email="Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge.")

    updated_state = extract_information(state)

    assert updated_state.extracted_information["customer_name"] == "Alice Johnson"
    assert updated_state.extracted_information["account_id"] == "ACC1023"
    assert updated_state.extracted_information["claimed_amount"] == 120.0
    assert updated_state.extracted_information["expected_amount"] == 100.0
    assert updated_state.extracted_information["issue_type"] == "billing_error"


def test_extract_information_when_account_is_missing():
    state = WorkflowState(raw_email="Hello, my name is Bob. I was billed $80 and expected $60 for a wrong charge.")

    updated_state = extract_information(state)

    assert updated_state.extracted_information["customer_name"] == "Bob"
    assert updated_state.extracted_information["account_id"] == ""
    assert updated_state.extracted_information["claimed_amount"] == 80.0
    assert updated_state.extracted_information["expected_amount"] == 60.0


def test_extract_information_when_amount_is_missing():
    state = WorkflowState(raw_email="Hello, I need help with my account because I believe there is a billing issue.")

    updated_state = extract_information(state)

    assert updated_state.extracted_information["customer_name"] == ""
    assert updated_state.extracted_information["account_id"] == ""
    assert updated_state.extracted_information["claimed_amount"] is None
    assert updated_state.extracted_information["expected_amount"] is None


def test_extract_information_from_random_email():
    state = WorkflowState(raw_email="Hi team, the weather is lovely today and I hope you are well.")

    updated_state = extract_information(state)

    assert updated_state.extracted_information["issue_type"] == "other"
    assert updated_state.extracted_information["customer_name"] == ""


def test_normalize_payload_accepts_llm_amount_strings_and_aliases():
    payload = {
        "name": "Alice Johnson",
        "account_number": "acc1023",
        "billed_amount": "$1,200.50",
        "expected_bill": "USD 1,000.25",
        "complaint_type": "duplicate_charge",
    }

    normalized = _normalize_payload(payload)

    assert normalized["customer_name"] == "Alice Johnson"
    assert normalized["account_id"] == "ACC1023"
    assert normalized["claimed_amount"] == 1200.50
    assert normalized["expected_amount"] == 1000.25
    assert normalized["issue_type"] == "duplicate_charge"


def test_extract_fills_missing_llm_amounts_from_fallback(monkeypatch):
    def fake_llm(_prompt):
        return {
            "customer_name": "Tanishk",
            "account_id": "ACC1023",
            "claimed_amount": None,
            "expected_amount": None,
            "issue_type": "billing_error",
        }

    monkeypatch.setattr("nodes.extract._extract_with_llm", fake_llm)
    state = WorkflowState(
        raw_email="Hello, my name is Tanishk. My account ACC1023 was billed $120 but I expected $400."
    )

    updated_state = extract_information(state)

    assert updated_state.extracted_information["claimed_amount"] == 120.0
    assert updated_state.extracted_information["expected_amount"] == 400.0
    assert "fallback_fill" in updated_state.extracted_information["_extraction_source"]
