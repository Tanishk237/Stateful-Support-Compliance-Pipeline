import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from state.workflow_state import WorkflowState


def test_workflow_state_has_sensible_defaults_and_mutable_lists():
    state = WorkflowState(raw_email="I was billed twice")

    assert state.request_id == ""
    assert state.raw_email == "I was billed twice"
    assert state.retry_count == 0
    assert state.missing_fields == []
    assert state.extracted_information == {}
    assert state.validation_status == "pending"
    assert state.verification_status == "pending"
    assert state.compliance_status == "pending"
    assert state.route == "pending"
    assert state.final_output == ""
    assert state.execution_history == []

    state.retry_count += 1
    state.missing_fields.append("customer_name")
    state.extracted_information["customer_name"] = "Alice"
    state.execution_history.append({"step": "extract", "status": "done"})

    assert state.retry_count == 1
    assert state.missing_fields == ["customer_name"]
    assert state.extracted_information["customer_name"] == "Alice"
    assert state.execution_history[-1]["step"] == "extract"


def test_workflow_state_assigns_request_id_once():
    state = WorkflowState(raw_email="I was billed twice")

    request_id = state.ensure_request_id()

    assert request_id.startswith("REQ-")
    assert state.request_id == request_id
    assert state.ensure_request_id() == request_id
