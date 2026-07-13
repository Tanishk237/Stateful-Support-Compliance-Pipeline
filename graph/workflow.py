"""Workflow graph definition for the support compliance pipeline."""

from typing import Any, Dict, TypedDict

from langgraph.graph import END, StateGraph

from nodes.clarify import clarify_missing_information
from nodes.compliance import evaluate_compliance
from nodes.escalation import create_escalation_ticket
from nodes.extract import extract_information
from nodes.response import generate_customer_response
from nodes.validate import validate_extraction
from nodes.verify import verify_business_claim
from state.workflow_state import WorkflowState


class WorkflowStateDict(TypedDict, total=False):
    state: WorkflowState


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

    workflow.set_entry_point("extract")
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

    workflow.add_conditional_edges(
        "clarify",
        _route_after_clarify,
        {
            "extract": "extract",
            "escalate": "escalate",
        },
    )

    workflow.add_edge("verify", "compliance")
    workflow.add_conditional_edges(
        "compliance",
        _route_after_compliance,
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


def _route_after_clarify(state: WorkflowState) -> str:
    """Decide whether to loop back to extraction or escalate."""
    if state.route == "retry":
        return "extract"
    return "escalate"


def _route_after_compliance(state: WorkflowState) -> str:
    """Decide whether to generate a response or escalate."""
    if (
        state.compliance_status == "safe"
        and state.validation_status == "passed"
        and state.verification_status == "verified"
    ):
        return "response"
    return "escalate"
