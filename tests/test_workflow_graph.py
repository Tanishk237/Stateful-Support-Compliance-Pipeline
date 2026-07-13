import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph.workflow import build_workflow_graph
from state.workflow_state import WorkflowState


def test_workflow_graph_routes_valid_request_to_response():
    workflow = build_workflow_graph()
    state = WorkflowState(
        raw_email="Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge.",
    )

    result = workflow.invoke(state)
    final_state = result if isinstance(result, WorkflowState) else WorkflowState(**result)

    assert final_state.route == "response"
    assert final_state.final_output != ""


def test_workflow_graph_routes_invalid_request_to_escalation():
    workflow = build_workflow_graph()
    state = WorkflowState(
        raw_email="Hello, I need help with my account because I believe there is a billing issue.",
    )

    result = workflow.invoke(state)
    final_state = result if isinstance(result, WorkflowState) else WorkflowState(**result)

    assert final_state.route == "escalate"
    assert final_state.final_output != ""
