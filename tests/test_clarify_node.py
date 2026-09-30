import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.clarify import apply_clarification_answers, clarify_missing_information
from state.workflow_state import WorkflowState


def test_clarify_node_with_one_missing_field():
    state = WorkflowState(
        missing_fields=["account_id"],
        conversation_history=["Previous attempt: missing account id"],
    )

    updated_state = clarify_missing_information(state)

    assert updated_state.retry_count == 1
    assert "account_id" in updated_state.conversation_history[-1]
    assert updated_state.validation_status == "awaiting_clarification"
    assert updated_state.route == "clarify"
    assert updated_state.clarification_question


def test_clarify_node_with_two_missing_fields():
    state = WorkflowState(
        missing_fields=["account_id", "claimed_amount"],
        conversation_history=["Initial request"],
    )

    updated_state = clarify_missing_information(state)

    assert updated_state.retry_count == 1
    assert "account_id" in updated_state.conversation_history[-1]
    assert "claimed_amount" in updated_state.conversation_history[-1]


def test_clarify_node_retry_exceeded():
    state = WorkflowState(
        missing_fields=["account_id"],
        retry_count=3,
        conversation_history=["Initial request"],
    )

    updated_state = clarify_missing_information(state)

    assert updated_state.retry_count == 3
    assert updated_state.validation_status == "clarification"
    assert updated_state.route == "billing_review"


def test_clarification_answers_are_merged_for_resume():
    state = WorkflowState(missing_fields=["account_id", "claimed_amount"], route="clarify")

    updated_state = apply_clarification_answers(
        state, {"account_id": "acc1023", "claimed_amount": "120"}
    )

    assert updated_state.extracted_information.account_id == "ACC1023"
    assert updated_state.extracted_information.claimed_amount == 120.0
    assert updated_state.resume_from_clarification is True
