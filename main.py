"""Command-line entry point for the Support & Compliance Pipeline."""

import argparse
import re
from pathlib import Path
from typing import Any, Dict, Optional

from config import LLM_MODEL, USE_LLM
from logger import write_run_log
from nodes.clarify import clarify_missing_information
from nodes.compliance import evaluate_compliance
from nodes.escalation import create_escalation_ticket
from nodes.extract import extract_information
from nodes.response import generate_customer_response
from nodes.validate import validate_extraction
from nodes.verify import verify_business_claim
from state.workflow_state import WorkflowState


DEMO_EMAILS: Dict[str, str] = {
    "happy": "Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge.",
    "missing_account": "Hello, my name is Bob. I was billed $80 and expected $60 for a wrong charge.",
    "missing_amount": "Hello, my name is Alice Johnson. My account ACC1023 has a billing issue.",
    "credit_card": "Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100. My card number is 4111 1111 1111 1111.",
    "wrong_account": "Hello, my name is Ghost User. My account ACC9999 was billed $50 but I expected $30 for a billing issue.",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Support & Compliance Pipeline from the command line."
    )
    parser.add_argument("--email", help="Complaint email text to process.")
    parser.add_argument("--file", help="Path to a text file containing the complaint email.")
    parser.add_argument("--demo", choices=sorted(DEMO_EMAILS), help="Run a built-in demo scenario.")
    parser.add_argument("--auto", action="store_true", help="Run the LangGraph workflow without interactive clarification.")
    parser.add_argument("--json", action="store_true", help="Print the final WorkflowState as JSON.")
    parser.add_argument("--no-log", action="store_true", help="Do not write a run log under logs/.")
    args = parser.parse_args()

    email = _load_email(args.email, args.file, args.demo)
    _warn_about_shell_amount_expansion(email, args.email is not None)
    state = WorkflowState(raw_email=email)
    state.ensure_request_id()

    print("\nSupport & Compliance Pipeline")
    print("===================================")
    print(f"Request ID: {state.request_id}")
    print(f"LLM mode: {'enabled' if USE_LLM else 'disabled'}" + (f" ({LLM_MODEL})" if USE_LLM else ""))
    print("Processing your billing complaint...\n")

    if args.auto:
        state = _run_graph(state)
    else:
        state = run_interactive_workflow(state)

    if not args.no_log:
        log_path = write_run_log(state)
        print(f"\nRun log: {log_path}")

    if args.json:
        print("\nFinal state JSON:")
        print(_state_to_json(state))
    else:
        _print_human_summary(state)


def run_interactive_workflow(state: WorkflowState) -> WorkflowState:
    """Run the workflow with CLI clarification when extracted fields are missing."""
    _step("Extracting structured information")
    state = extract_information(state)
    _print_extraction_indicator(state)

    while True:
        _step("Validating required fields")
        state = validate_extraction(state)

        if state.validation_status == "passed":
            break
        if state.validation_status == "failed":
            _step("Validation failed; creating escalation ticket")
            return create_escalation_ticket(state)

        state = clarify_missing_information(state)
        if state.route == "escalate":
            _step("Retry limit reached; creating escalation ticket")
            return create_escalation_ticket(state)

        if not _collect_missing_fields(state):
            _step("Clarification input unavailable; creating escalation ticket")
            return create_escalation_ticket(state)

    _step("Verifying account and billing details")
    state = verify_business_claim(state)

    _step("Checking compliance and PII risk")
    state = evaluate_compliance(state)

    if (
        state.compliance_status == "safe"
        and state.validation_status == "passed"
        and state.verification_status == "verified"
    ):
        _step("Generating customer response")
        state = generate_customer_response(state)
        if state.route == "response":
            return state

    _step("Creating internal escalation ticket")
    return create_escalation_ticket(state)


def _run_graph(state: WorkflowState) -> WorkflowState:
    try:
        from graph.workflow import build_workflow_graph
    except ModuleNotFoundError as exc:
        if exc.name == "langgraph":
            raise SystemExit(
                "LangGraph is required for --auto mode. Install dependencies with: "
                "pip install -r requirements.txt"
            ) from exc
        raise

    workflow = build_workflow_graph()
    result = workflow.invoke(state)
    if isinstance(result, WorkflowState):
        return result
    return WorkflowState(**result)


def _load_email(email: Optional[str], file_path: Optional[str], demo: Optional[str]) -> str:
    if email:
        return email.strip()
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    if demo:
        return DEMO_EMAILS[demo]

    print("Paste the customer billing complaint email below.")
    print("Press Enter on an empty line when you are done.\n")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _collect_missing_fields(state: WorkflowState) -> bool:
    print("\nI need a little more information before this can continue.")
    print(f"Missing fields: {', '.join(state.missing_fields)}")

    for field in list(state.missing_fields):
        try:
            value = input(f"Enter {field.replace('_', ' ')}: ").strip()
        except EOFError:
            state.record_event("clarify", "input_unavailable", "No interactive input was available")
            return False
        state.extracted_information[field] = _coerce_field_value(field, value)
    return True


def _coerce_field_value(field: str, value: str) -> Any:
    if field in {"claimed_amount", "expected_amount"}:
        try:
            return float(value)
        except ValueError:
            return None
    if field == "account_id":
        return value.upper()
    return value


def _warn_about_shell_amount_expansion(email: str, from_inline_arg: bool) -> None:
    if not from_inline_arg:
        return
    lower_email = email.lower()
    has_amount_cues = any(keyword in lower_email for keyword in ["billed", "charged", "expected", "amount"])
    email_without_account_ids = re.sub(r"\b(?:acc|acct)[a-z0-9-]*\b", "", email, flags=re.IGNORECASE)
    has_amount_numbers = bool(re.search(r"\d+(?:\.\d+)?", email_without_account_ids))
    if has_amount_cues and not has_amount_numbers:
        print(
            "Warning: no numeric amounts reached the CLI. If your --email text contains dollar amounts, "
            "wrap it in single quotes or escape dollar signs, e.g. '$120' or \\$120."
        )


def _print_human_summary(state: WorkflowState) -> None:
    print("\nWorkflow Summary")
    print("----------------")
    print(f"Route: {state.route}")
    print(f"Validation: {state.validation_status}")
    print(f"Verification: {state.verification_status}")
    print(f"Compliance: {state.compliance_status}")
    print(f"Retries: {state.retry_count}/3")
    if state.extracted_information:
        print(f"Extraction: {state.extracted_information.get('_extraction_source', 'unknown')}")

    print("\nFinal Output")
    print("------------")
    print(state.final_output or "<no final output>")

    print("\nExecution History")
    print("-----------------")
    for entry in state.execution_history:
        details = f" - {entry['details']}" if entry.get("details") else ""
        print(f"{entry.get('step', 'unknown')}: {entry.get('status', 'unknown')}{details}")


def _state_to_json(state: WorkflowState) -> str:
    if hasattr(state, "model_dump_json"):
        return state.model_dump_json(indent=2)
    return state.json(indent=2)


def _print_extraction_indicator(state: WorkflowState) -> None:
    source = state.extracted_information.get("_extraction_source", "unknown")
    claimed_amount = state.extracted_information.get("claimed_amount")
    expected_amount = state.extracted_information.get("expected_amount")
    print(f"  Extraction engine: {source}")
    print(f"  Extracted amounts: claimed={claimed_amount}, expected={expected_amount}")


def _step(message: str) -> None:
    print(f"> {message}...")


if __name__ == "__main__":
    main()
