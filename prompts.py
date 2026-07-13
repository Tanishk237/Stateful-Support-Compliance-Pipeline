"""Prompt templates for the support compliance workflow."""

from typing import Any, Dict, Iterable, Optional


def build_extraction_prompt(email_content: str) -> str:
    """Create the extraction prompt for a complaint email."""
    return f"""
You are extracting structured billing complaint information from a customer email.

Return ONLY valid JSON. Do not include markdown, commentary, reasoning, or code fences.
The JSON object must use exactly these keys:
- customer_name: string
- account_id: string
- claimed_amount: number or null
- expected_amount: number or null
- issue_type: string, one of billing_error, duplicate_charge, overcharge, refund_request, plan_change, other

If a field is missing, use an empty string for text fields and null for numeric fields.
If the email says "billed", "charged", "was charged", or "invoice amount", map that amount to claimed_amount.
If the email says "expected", "should be", "correct amount", or "supposed to be", map that amount to expected_amount.

Email content:
{email_content}
""".strip()


def build_clarification_prompt(missing_field: str, missing_fields: Iterable[str]) -> str:
    """Create the clarification prompt for missing required fields."""
    missing_list = ", ".join(missing_fields)
    return f"""
The previous extraction was missing required information.
Please ask the user to provide the missing field: {missing_field}.
Missing fields currently: {missing_list}
""".strip()


def build_response_prompt(
    customer_name: str,
    summary: str,
    request_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Create the customer response prompt."""
    details = details or {}
    return f"""
You are writing a customer support response.
Request ID: {request_id}
Customer name: {customer_name}
Summary: {summary}
Account ID: {details.get('account_id', '')}
Issue type: {details.get('issue_type', '')}
Claimed amount: {details.get('claimed_amount', '')}
Expected amount: {details.get('expected_amount', '')}
Verified difference: {details.get('difference', '')}
Verification status: {details.get('verification_status', '')}
Compliance status: {details.get('compliance_status', '')}

Write a polite, concise, request-specific response.
Mention the request id.
Do not mention internal compliance checks.
Do not promise a refund unless the details explicitly say one was approved.
""".strip()
