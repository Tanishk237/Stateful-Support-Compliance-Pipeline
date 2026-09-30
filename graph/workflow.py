"""Workflow graph definition for the support compliance pipeline."""

from time import perf_counter

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from nodes.clarify import apply_clarification_answers, clarify_missing_information
from nodes.compliance import evaluate_compliance
from nodes.escalation import create_escalation_ticket
from nodes.extract import extract_information
from nodes.response import generate_customer_response
from nodes.validate import validate_extraction
from nodes.verify import verify_business_claim
from state.workflow_state import WorkflowState


def _tracked_node(name, handler):
    """Emit real node boundaries without changing the underlying business logic."""
    def run(state):
        writer = get_stream_writer()
        started = perf_counter()
        writer({"type": "step_started", "step": name})
        result = handler(state)
        writer({
            "type": "step_completed",
            "step": name,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "state": result.model_dump(),
        })
        return result

    return run


def build_workflow_graph(emit_events=False):
    """Create and return the LangGraph workflow for the billing complaint pipeline."""
    workflow = StateGraph(WorkflowState)

    nodes = {
        "compliance": evaluate_compliance,
        "extract": extract_information,
        "validate": validate_extraction,
        "clarify": clarify_missing_information,
        "verify": verify_business_claim,
        "respond": generate_customer_response,
        "billing_review": create_escalation_ticket,
        "compliance_escalation": create_escalation_ticket,
    }
    for name, handler in nodes.items():
        workflow.add_node(name, _tracked_node(name, handler) if emit_events else handler)

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
            "compliance_escalation": "compliance_escalation",
        },
    )
    workflow.add_edge("extract", "validate")

    workflow.add_conditional_edges(
        "validate",
        _route_after_validation,
        {
            "clarify": "clarify",
            "verify": "verify",
            "billing_review": "billing_review",
        },
    )

    # Clarification pauses instead of repeatedly re-extracting the same email.
    workflow.add_conditional_edges(
        "clarify",
        _route_after_clarify,
        {"pause": END, "billing_review": "billing_review"},
    )

    workflow.add_conditional_edges(
        "verify",
        _route_after_verification,
        {
            "respond": "respond",
            "billing_review": "billing_review",
        },
    )

    workflow.add_edge("respond", END)
    workflow.add_edge("billing_review", END)
    workflow.add_edge("compliance_escalation", END)

    return workflow.compile()


def _route_after_validation(state: WorkflowState) -> str:
    """Decide whether to clarify or continue with verification."""
    if state.validation_status == "failed":
        return "billing_review"
    if state.validation_status == "clarification":
        return "clarify"
    return "verify"


def resume_workflow(state: WorkflowState, answers: dict) -> WorkflowState:
    """Merge a clarification answer and continue the compiled workflow."""
    apply_clarification_answers(state, answers)
    workflow = build_workflow_graph()
    result = workflow.invoke(state)
    return result if isinstance(result, WorkflowState) else WorkflowState(**result)


def run_workflow(state: WorkflowState) -> WorkflowState:
    """Run a state until it reaches a final route or pauses for clarification."""
    result = build_workflow_graph().invoke(state)
    return result if isinstance(result, WorkflowState) else WorkflowState(**result)


def _route_at_entry(state: WorkflowState) -> str:
    """Skip extraction when a validated clarification answer is being resumed."""
    return "validate" if state.resume_from_clarification else "compliance"


def _route_after_clarify(state: WorkflowState) -> str:
    """Pause for an answer unless the clarification limit was already reached."""
    return "billing_review" if state.route == "billing_review" else "pause"


def _route_after_compliance_precheck(state: WorkflowState) -> str:
    """Only safe emails may continue to extraction."""
    if state.compliance_status == "safe":
        return "extract"
    return "compliance_escalation"


def _route_after_verification(state: WorkflowState) -> str:
    """Generate a response only for safe, valid, verified complaints."""
    if (
        state.compliance_status == "safe"
        and state.validation_status == "passed"
        and state.verification_status == "verified"
    ):
        return "respond"
    return "billing_review"
