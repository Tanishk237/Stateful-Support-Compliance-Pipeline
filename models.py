from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExtractedInformation(BaseModel):
    """Structured information extracted from a complaint email."""

    model_config = ConfigDict(extra="forbid")

    customer_name: str = ""
    account_id: str = ""
    claimed_amount: Optional[float] = None
    expected_amount: Optional[float] = None
    issue_type: Literal[
        "billing_error",
        "duplicate_charge",
        "overcharge",
        "refund_request",
        "plan_change",
        "other",
    ] = "other"


class CustomerResponse(BaseModel):
    """Response returned to the customer."""

    subject: str = ""
    body: str = ""


class EscalationTicket(BaseModel):
    """Internal escalation ticket payload."""

    ticket_id: str = ""
    reason: str = ""
    priority: str = "medium"
    department: str = "billing"
    summary: str = ""
    ticket_path: str = ""


class BusinessVerification(BaseModel):
    """Business verification outcome for the complaint."""

    account_found: bool = False
    billing_match: bool = False
    difference: Optional[float] = None


class ComplianceResult(BaseModel):
    """Compliance and PII scan result."""

    is_safe: bool = True
    risk_level: str = "low"
    pii_found: List[str] = Field(default_factory=list)


__all__ = [
    "BusinessVerification",
    "ComplianceResult",
    "CustomerResponse",
    "EscalationTicket",
    "ExtractedInformation",
]
