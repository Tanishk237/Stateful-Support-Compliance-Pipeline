"""Extraction node for complaint emails."""

import json
import re
from typing import Any, Dict, Optional

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, USE_LLM
from prompts import build_extraction_prompt
from state.workflow_state import WorkflowState

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on environment
    OpenAI = None


def extract_information(state: WorkflowState) -> WorkflowState:
    """Extract structured complaint information from the raw email text."""
    state.ensure_request_id()
    email_content = state.raw_email or ""
    prompt = build_extraction_prompt(email_content)

    try:
        extracted_payload = _extract_with_llm(prompt)
        extraction_source = "llm"
    except ValueError as exc:
        extracted_payload = _extract_with_fallback(email_content)
        extraction_source = f"fallback (LLM parse error: {exc})"
    except Exception as exc:
        extracted_payload = _extract_with_fallback(email_content)
        extraction_source = f"fallback ({type(exc).__name__}: {exc})"

    normalized_payload = _normalize_payload(extracted_payload)
    if extraction_source == "llm":
        fallback_payload = _normalize_payload(_extract_with_fallback(email_content))
        filled_fields = _fill_missing_from_fallback(normalized_payload, fallback_payload)
        if filled_fields:
            extraction_source = f"llm + fallback_fill({', '.join(filled_fields)})"
    normalized_payload["_extraction_source"] = extraction_source
    state.extracted_information = normalized_payload
    state.missing_fields = [
        field
        for field in ["customer_name", "account_id"]
        if not normalized_payload.get(field)
    ]
    state.record_event("extract", "completed", f"Structured complaint information extracted using {extraction_source}")
    return state


def _extract_with_llm(prompt: str) -> Dict[str, Any]:
    """Call the NVIDIA-backed chat completion API and parse the JSON response."""
    if not USE_LLM:
        raise RuntimeError("LLM extraction is disabled; using deterministic fallback")
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")

    client = OpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
    )
    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        top_p=0.95,
        max_tokens=512,
        response_format={"type": "json_object"},
    )

    if not completion.choices or not completion.choices[0].message:
        raise ValueError("The model response was empty")
    raw_response = (completion.choices[0].message.content or "").strip()
    return _parse_json_payload(raw_response)


def _extract_with_fallback(email_content: str) -> Dict[str, Any]:
    """Provide deterministic extraction when the LLM is unavailable."""
    lower_email = email_content.lower()
    customer_name = ""
    account_id = ""
    claimed_amount: Optional[float] = None
    expected_amount: Optional[float] = None
    issue_type = "other"

    name_match = re.search(r"\bmy name is ([a-z][a-z .'-]*?)(?:\.|,|$)", lower_email)
    if name_match:
        customer_name = name_match.group(1).strip().title()

    account_match = re.search(r"\b(?:account|acct)(?:\s+id)?\s*([a-z0-9-]{2,})\b", email_content, re.IGNORECASE)
    if account_match:
        candidate = account_match.group(1).strip()
        if candidate.lower() not in {"because", "help", "issue", "billing"} and (
            re.search(r"\d", candidate) or candidate.lower().startswith(("acc", "acct"))
        ):
            account_id = candidate.upper()
    else:
        account_match = re.search(r"\b(acc\d{4})\b", lower_email)
        if account_match:
            account_id = account_match.group(1).upper()

    cleaned_email = re.sub(r"\b(?:account|acct)(?:\s+id)?\s*[a-z0-9-]+\b", "", email_content, flags=re.IGNORECASE)
    cleaned_email = re.sub(r"\b(acc\d{4})\b", "", cleaned_email, flags=re.IGNORECASE)
    amounts = [float(value) for value in re.findall(r"\$?(\d+(?:\.\d+)?)", cleaned_email)]
    if amounts:
        claimed_amount = amounts[0]
    if len(amounts) >= 2:
        expected_amount = amounts[1]

    if any(keyword in lower_email for keyword in ["duplicate", "wrong charge", "overcharged", "charged twice", "billing"]):
        issue_type = "billing_error"

    if "expected" in lower_email and expected_amount is None and len(amounts) >= 1:
        expected_amount = amounts[0]

    return {
        "customer_name": customer_name,
        "account_id": account_id,
        "claimed_amount": claimed_amount,
        "expected_amount": expected_amount,
        "issue_type": issue_type,
    }


def _parse_json_payload(raw_response: str) -> Dict[str, Any]:
    """Parse JSON from the model output, handling code fences and plain text."""
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not json_match:
            raise ValueError("The model response was not valid JSON") from None
        try:
            payload = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            raise ValueError("The model response was not valid JSON") from None

    if not isinstance(payload, dict):
        raise ValueError("The model response was not a JSON object")
    return payload


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize keys and convert values to the expected types."""
    key_aliases = {
        "name": "customer_name",
        "customer": "customer_name",
        "account": "account_id",
        "account_number": "account_id",
        "acct_id": "account_id",
        "billed_amount": "claimed_amount",
        "charged_amount": "claimed_amount",
        "amount_charged": "claimed_amount",
        "disputed_amount": "claimed_amount",
        "invoice_amount": "claimed_amount",
        "expected_bill": "expected_amount",
        "expected_charge": "expected_amount",
        "expected_billing_amount": "expected_amount",
        "correct_amount": "expected_amount",
        "issue": "issue_type",
        "complaint_type": "issue_type",
    }
    normalized: Dict[str, Any] = {
        "customer_name": "",
        "account_id": "",
        "claimed_amount": None,
        "expected_amount": None,
        "issue_type": "other",
    }

    for key, value in payload.items():
        normalized_key = str(key).strip().lower().replace(" ", "_")
        normalized_key = key_aliases.get(normalized_key, normalized_key)
        if normalized_key in normalized:
            if normalized_key in {"claimed_amount", "expected_amount"} and value is not None:
                normalized[normalized_key] = _parse_amount(value)
            elif normalized_key in {"customer_name", "account_id", "issue_type"}:
                normalized[normalized_key] = "" if value is None else str(value).strip()

    normalized["account_id"] = normalized["account_id"].upper()

    return normalized


def _fill_missing_from_fallback(payload: Dict[str, Any], fallback_payload: Dict[str, Any]) -> list[str]:
    """Fill fields the LLM missed when deterministic extraction found them."""
    filled_fields: list[str] = []
    for field in ["customer_name", "account_id", "claimed_amount", "expected_amount", "issue_type"]:
        value = payload.get(field)
        fallback_value = fallback_payload.get(field)
        if value in (None, "") and fallback_value not in (None, ""):
            payload[field] = fallback_value
            filled_fields.append(field)
    return filled_fields


def _parse_amount(value: Any) -> Optional[float]:
    """Parse numeric and currency-like amount values into floats."""
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None

    amount_text = str(value).strip()
    amount_match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?", amount_text)
    if not amount_match:
        return None
    try:
        return float(amount_match.group(0).replace(",", ""))
    except ValueError:
        return None
