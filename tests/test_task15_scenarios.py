import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph.workflow import build_workflow_graph
from nodes.clarify import clarify_missing_information
from nodes.compliance import evaluate_compliance
from nodes.extract import extract_information
from nodes.validate import validate_extraction
from nodes.verify import verify_business_claim
from state.workflow_state import WorkflowState


def test_happy_path_routes_to_response():
    workflow = build_workflow_graph()
    state = WorkflowState(
        raw_email="Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge.",
    )

    result = workflow.invoke(state)
    final_state = result if isinstance(result, WorkflowState) else WorkflowState(**result)

    assert final_state.route == "response"
    assert final_state.validation_status == "passed"
    assert final_state.verification_status == "verified"
    assert final_state.compliance_status == "safe"
    assert final_state.final_output != ""


def test_missing_account_triggers_clarification():
    state = WorkflowState(
        raw_email="Hello, my name is Bob. I was billed $80 and expected $60 for a wrong charge.",
    )

    updated_state = validate_extraction(extract_information(state))

    assert updated_state.validation_status == "clarification"
    assert "account_id" in updated_state.missing_fields


def test_missing_amount_triggers_clarification():
    state = WorkflowState(
        raw_email="Hello, my name is Bob. My account ACC1023 has a billing issue.",
    )

    updated_state = validate_extraction(extract_information(state))

    assert updated_state.validation_status == "clarification"
    assert "claimed_amount" in updated_state.missing_fields
    assert "expected_amount" in updated_state.missing_fields


def test_retry_limit_escalates():
    state = WorkflowState(
        raw_email="Hello, I need help with my account because I believe there is a billing issue.",
        retry_count=3,
        missing_fields=["account_id"],
        validation_status="clarification",
    )

    updated_state = clarify_missing_information(state)

    assert updated_state.route == "escalate"
    assert updated_state.retry_count == 3


def test_credit_card_is_flagged_as_high_risk():
    state = WorkflowState(raw_email="My card number is 4111 1111 1111 1111 and I need help.")

    updated_state = evaluate_compliance(state)

    assert updated_state.compliance_status == "high"
    assert "credit_card" in updated_state.extracted_information["compliance_details"]["pii_found"]


def test_wrong_account_fails_business_verification():
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


def test_invalid_json_falls_back_to_deterministic_extraction():
    state = WorkflowState(
        raw_email="Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100.",
    )

    with patch("nodes.extract._extract_with_llm", side_effect=ValueError("The model response was not valid JSON")):
        extracted_state = extract_information(state)

    validated_state = validate_extraction(extracted_state)

    assert validated_state.validation_status == "passed"
    assert validated_state.extracted_information["claimed_amount"] == 120.0
    assert validated_state.extracted_information["expected_amount"] == 100.0
    assert "LLM parse error" in validated_state.extracted_information["_extraction_source"]


def test_complete_end_to_end_workflow_for_valid_request():
    workflow = build_workflow_graph()
    state = WorkflowState(
        raw_email="Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge.",
    )

    result = workflow.invoke(state)
    final_state = result if isinstance(result, WorkflowState) else WorkflowState(**result)

    assert final_state.route == "response"
    assert final_state.final_output != ""
    assert "Alice" in final_state.final_output or "billing" in final_state.final_output.lower()
