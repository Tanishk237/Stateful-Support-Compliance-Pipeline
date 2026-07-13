import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import (
    BusinessVerification,
    ComplianceResult,
    CustomerResponse,
    EscalationTicket,
    ExtractedInformation,
)


def test_all_data_models_can_be_instantiated():
    extracted = ExtractedInformation(
        customer_name="Alice",
        account_id="ACC-001",
        claimed_amount=120.0,
        expected_amount=100.0,
        issue_type="billing_error",
    )
    response = CustomerResponse(subject="Billing issue", body="We are reviewing your concern.")
    ticket = EscalationTicket(
        ticket_id="T-1001",
        reason="Potential billing mismatch",
        priority="high",
        department="billing",
        summary="Customer reports duplicate charge",
    )
    verification = BusinessVerification(account_found=True, billing_match=False, difference=20.0)
    compliance = ComplianceResult(is_safe=False, risk_level="high", pii_found=["email"])

    assert extracted.customer_name == "Alice"
    assert response.subject == "Billing issue"
    assert ticket.department == "billing"
    assert verification.difference == 20.0
    assert compliance.pii_found == ["email"]
