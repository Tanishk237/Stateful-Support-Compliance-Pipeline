"""Central workflow state for the support compliance pipeline."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowState(BaseModel):
    """Mutable state container shared by every node in the workflow."""

    request_id: str = ""
    raw_email: str = ""
    conversation_history: List[str] = Field(default_factory=list)
    retry_count: int = 0
    missing_fields: List[str] = Field(default_factory=list)
    extracted_information: Dict[str, Any] = Field(default_factory=dict)
    validation_status: str = "pending"
    verification_status: str = "pending"
    compliance_status: str = "pending"
    route: str = "pending"
    final_output: str = ""
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)

    def record_event(self, step: str, status: str, details: Optional[str] = None) -> None:
        """Append a step result to the execution history."""
        entry: Dict[str, Any] = {"step": step, "status": status}
        if details is not None:
            entry["details"] = details
        self.execution_history.append(entry)

    def ensure_request_id(self) -> str:
        """Assign a request id if one has not been provided."""
        if not self.request_id:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            suffix = uuid4().hex[:6].upper()
            self.request_id = f"REQ-{timestamp}-{suffix}"
        return self.request_id
