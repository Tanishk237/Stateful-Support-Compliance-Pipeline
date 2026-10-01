"""Application service shared by the API and visual demo."""

import json
import logging
from typing import Any, Dict, Optional

from graph.workflow import build_workflow_graph, resume_workflow, run_workflow
from nodes.clarify import apply_clarification_answers
from persistence import SQLiteStore
from state.workflow_state import WorkflowState


class ComplaintService:
    """Run and persist billing complaint workflows."""

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self.store = store or SQLiteStore()

    def create_complaint(self, email: str) -> WorkflowState:
        """Start a new complaint and persist its latest state."""
        state = run_workflow(self.new_state(email))
        self.store.save_state(state)
        return state

    @staticmethod
    def new_state(email: str) -> WorkflowState:
        """Validate input before a normal or streaming response starts."""
        if not email.strip():
            raise ValueError("Complaint email cannot be empty")

        state = WorkflowState(raw_email=email.strip())
        state.ensure_request_id()
        return state

    def clarification_state(self, request_id: str, answers: Dict[str, Any]) -> WorkflowState:
        """Prepare a saved request for streaming from validation."""
        state = self.get_complaint(request_id)
        return apply_clarification_answers(state, answers)

    def stream(self, state: WorkflowState):
        """Stream SSE node events and persist each completed checkpoint.

        The same compiled graph powers both API styles. A completion event means
        the final state is saved; an error event never includes exception secrets.
        """
        def frame(event):
            return "data: " + json.dumps(event, allow_nan=False) + "\n\n"

        try:
            self.store.save_state(state)
            yield frame({"type": "request_started", "request_id": state.request_id})
            for event in build_workflow_graph(emit_events=True).stream(
                state, stream_mode="custom"
            ):
                if event["type"] == "step_completed":
                    state = WorkflowState.model_validate(event["state"])
                    self.store.save_state(state)
                yield frame(event)
            yield frame({"type": "complete", "state": state.model_dump()})
        except Exception:
            logging.getLogger(__name__).exception("Workflow stream failed: %s", state.request_id)
            yield frame({"type": "error", "request_id": state.request_id,
                         "message": "Processing stopped. Reopen this request to inspect its last saved step, or start a new run."})

    def submit_clarification(
        self, request_id: str, answers: Dict[str, Any]
    ) -> WorkflowState:
        """Resume a complaint that is waiting for customer clarification."""
        state = self.get_complaint(request_id)
        if state.route != "clarify":
            raise ValueError("Complaint is not waiting for clarification")

        state = resume_workflow(state, answers)
        self.store.save_state(state)
        return state

    def get_complaint(self, request_id: str) -> WorkflowState:
        """Return a saved complaint or raise a clear lookup error."""
        state = self.store.get_state(request_id)
        if state is None:
            raise KeyError(request_id)
        return state
