"""Central workflow state for the support compliance pipeline."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from models import (
    BusinessVerification,
    ComplianceResult,
    CustomerResponse,
    EscalationTicket,
    ExtractedInformation,
)


WorkflowRoute = Literal[
    "pending",
    "respond",
    "clarify",
    "billing_review",
    "compliance_escalation",
]


class WorkflowState(BaseModel):
    """Mutable state container shared by every node in the workflow."""

    request_id: str = ""
    raw_email: str = ""
    redacted_email: str = ""
    conversation_history: List[str] = Field(default_factory=list)
    retry_count: int = 0
    missing_fields: List[str] = Field(default_factory=list)
    extracted_information: ExtractedInformation = Field(default_factory=ExtractedInformation)
    business_verification: BusinessVerification = Field(default_factory=BusinessVerification)
    compliance_result: ComplianceResult = Field(
        default_factory=lambda: ComplianceResult(is_safe=False, risk_level="pending")
    )
    customer_response: CustomerResponse = Field(default_factory=CustomerResponse)
    escalation_ticket: EscalationTicket = Field(default_factory=EscalationTicket)
    extraction_source: str = "pending"
    extraction_prompt_version: str = ""
    extraction_error: str = ""
    clarification_question: str = ""
    resume_from_clarification: bool = False
    validation_status: str = "pending"
    verification_status: str = "pending"
    compliance_status: str = "pending"
    route: WorkflowRoute = "pending"
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
