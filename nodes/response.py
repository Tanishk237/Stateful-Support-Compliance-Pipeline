"""Response generation node for compliant requests."""

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, USE_LLM
from prompts import build_response_prompt
from state.workflow_state import WorkflowState

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on environment
    OpenAI = None

def generate_customer_response(state: WorkflowState) -> WorkflowState:
    """Generate a professional customer response only when the request is safe and verified."""
    request_id = state.ensure_request_id()
    payload = state.extracted_information or {}
    is_safe = state.compliance_status == "safe"
    is_verified = state.verification_status == "verified"
    is_validated = state.validation_status == "passed"

    if not (is_safe and is_validated and is_verified):
        state.route = "escalate"
        state.final_output = ""
        state.record_event("response", "skipped", "Request is not safe, validated, or verified")
        return state

    customer_name = str(payload.get("customer_name", "")).strip()
    issue_summary = _build_issue_summary(payload)
    prompt = build_response_prompt(
        customer_name,
        issue_summary,
        request_id=request_id,
        details={
            **payload,
            "verification_status": state.verification_status,
            "compliance_status": state.compliance_status,
        },
    )

    try:
        response_text = _generate_with_llm(prompt)
        response_source = "llm"
    except Exception as exc:
        response_text = _generate_fallback_response(request_id, customer_name, payload, issue_summary)
        response_source = f"fallback ({type(exc).__name__}: {exc})"

    state.final_output = response_text
    state.route = "response"
    state.record_event("response", "generated", f"Customer response email generated using {response_source}")
    return state


def _generate_with_llm(prompt: str) -> str:
    """Call the NVIDIA-backed chat completion API to generate a response."""
    if not USE_LLM:
        raise RuntimeError("LLM response generation is disabled; using deterministic fallback")
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
        temperature=0.7,
        top_p=0.95,
        max_tokens=512,
    )

    if completion.choices and completion.choices[0].message:
        response_text = (completion.choices[0].message.content or "").strip()
        if response_text:
            return response_text
    raise RuntimeError("The model response was empty")


def _build_issue_summary(payload: dict) -> str:
    issue_type = str(payload.get("issue_type", "billing")).replace("_", " ")
    account_id = payload.get("account_id", "your account")
    claimed_amount = payload.get("claimed_amount")
    expected_amount = payload.get("expected_amount")
    difference = payload.get("difference")

    amount_part = ""
    if claimed_amount is not None and expected_amount is not None:
        amount_part = f" You reported a billed amount of ${claimed_amount} and an expected amount of ${expected_amount}."
    if difference is not None:
        amount_part += f" Our records show a difference of ${difference} against the claimed amount."

    return f"Your {issue_type} for account {account_id} has been reviewed.{amount_part}"


def _generate_fallback_response(request_id: str, customer_name: str, payload: dict, issue_summary: str) -> str:
    """Provide a deterministic professional response when the LLM is unavailable."""
    name_part = f"Dear {customer_name}," if customer_name else "Dear Valued Customer,"
    account_id = payload.get("account_id", "your account")
    issue_type = str(payload.get("issue_type", "billing issue")).replace("_", " ")
    return f"""{name_part}

Thank you for bringing this matter to our attention. Your request ID is {request_id}.

{issue_summary}

We verified the information for account {account_id} and confirmed that your {issue_type} can be handled by our support workflow. Our team is taking the next steps to resolve the billing concern.

You can expect a full resolution within 3-5 business days. If you have any questions in the meantime, please do not hesitate to contact us.

We appreciate your patience and understanding.

Best regards,
Customer Support Team""".strip()
