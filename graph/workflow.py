"""Workflow graph definition for the support compliance pipeline."""

from langgraph.graph import END, StateGraph

from nodes.clarify import apply_clarification_answers, clarify_missing_information
from nodes.compliance import evaluate_compliance
from nodes.escalation import create_escalation_ticket
from nodes.extract import extract_information
from nodes.response import generate_customer_response
from nodes.validate import validate_extraction
from nodes.verify import verify_business_claim
from state.workflow_state import WorkflowState


def build_workflow_graph():
    """Create and return the LangGraph workflow for the billing complaint pipeline."""
    workflow = StateGraph(WorkflowState)

    workflow.add_node("extract", extract_information)
    workflow.add_node("validate", validate_extraction)
    workflow.add_node("clarify", clarify_missing_information)
    workflow.add_node("verify", verify_business_claim)
    workflow.add_node("compliance", evaluate_compliance)
    workflow.add_node("response", generate_customer_response)
    workflow.add_node("escalate", create_escalation_ticket)

    # A normal request starts with compliance. A resumed request already passed
    # that check, so it continues from validation with the merged customer answer.
    workflow.set_conditional_entry_point(
        _route_at_entry,
        {
            "compliance": "compliance",
            "validate": "validate",
        },
    )
    workflow.add_conditional_edges(
        "compliance",
        _route_after_compliance_precheck,
        {
            "extract": "extract",
            "escalate": "escalate",
        },
    )
    workflow.add_edge("extract", "validate")

    workflow.add_conditional_edges(
        "validate",
        _route_after_validation,
        {
            "clarify": "clarify",
            "verify": "verify",
            "escalate": "escalate",
        },
    )

    # Clarification pauses instead of repeatedly re-extracting the same email.
    workflow.add_conditional_edges(
        "clarify",
        _route_after_clarify,
        {"pause": END, "escalate": "escalate"},
    )

    workflow.add_conditional_edges(
        "verify",
        _route_after_verification,
        {
            "response": "response",
            "escalate": "escalate",
        },
    )

    workflow.add_edge("response", END)
    workflow.add_edge("escalate", END)

    return workflow.compile()


def _route_after_validation(state: WorkflowState) -> str:
    """Decide whether to clarify or continue with verification."""
    if state.validation_status == "failed":
        return "escalate"
    if state.validation_status == "clarification":
        return "clarify"
    return "verify"


def resume_workflow(state: WorkflowState, answers: dict) -> WorkflowState:
    """Merge a clarification answer and continue the compiled workflow."""
    apply_clarification_answers(state, answers)
    workflow = build_workflow_graph()
    result = workflow.invoke(state)
    return result if isinstance(result, WorkflowState) else WorkflowState(**result)


def _route_at_entry(state: WorkflowState) -> str:
    """Skip extraction when a validated clarification answer is being resumed."""
    return "validate" if state.resume_from_clarification else "compliance"


def _route_after_clarify(state: WorkflowState) -> str:
    """Pause for an answer unless the clarification limit was already reached."""
    return "escalate" if state.route == "escalate" else "pause"


def _route_after_compliance_precheck(state: WorkflowState) -> str:
    """Only safe emails may continue to extraction."""
    if state.compliance_status == "safe":
        return "extract"
    return "escalate"


def _route_after_verification(state: WorkflowState) -> str:
    """Generate a response only for safe, valid, verified complaints."""
    if (
        state.compliance_status == "safe"
        and state.validation_status == "passed"
        and state.verification_status == "verified"
    ):
        return "response"
    return "escalate"
