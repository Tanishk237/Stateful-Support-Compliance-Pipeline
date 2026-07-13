import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prompts import build_clarification_prompt, build_extraction_prompt, build_response_prompt


def test_prompt_templates_are_parameterized_and_render_expected_content():
    extraction = build_extraction_prompt("Please review my duplicate charge")
    clarification = build_clarification_prompt("customer_name", ["customer_name", "account_id"])
    response = build_response_prompt("Alice", "We reviewed your billing issue")

    assert "Please review my duplicate charge" in extraction
    assert "customer_name" in clarification
    assert "account_id" in clarification
    assert "Alice" in response
    assert "We reviewed your billing issue" in response
