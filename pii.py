"""PII detection utilities using regex."""

import re
from typing import Dict, List, Tuple


PII_PATTERNS: Dict[str, Tuple[str, str]] = {
    "credit_card": (r"\b(?:\d[ -]?){13,19}\b", "high"),
    "pan": (r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", "high"),
    "aadhaar": (r"(?<!\d)\d{4}(?:[ -]\d{4}){2}(?![ -]?\d{4})(?!\d)", "high"),
    "passport": (r"\b[A-Z][0-9]{7}\b", "high"),
    "phone": (r"(?:\+?\d[\d -]{8,}\d)", "high"),
    "email": (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "medium"),
}


def detect_pii(text: str) -> List[str]:
    """Return the list of sensitive data categories detected in the supplied text."""
    found: List[str] = []
    credit_card_spans = [
        match.span()
        for match in re.finditer(PII_PATTERNS["credit_card"][0], text, re.IGNORECASE)
    ]

    for pii_type, (pattern, _) in PII_PATTERNS.items():
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if pii_type in {"aadhaar", "phone"} and credit_card_spans:
            matches = [
                match
                for match in matches
                if not any(_spans_overlap(match.span(), card_span) for card_span in credit_card_spans)
            ]
        if matches:
            found.append(pii_type)
    return found


def _spans_overlap(left: Tuple[int, int], right: Tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def classify_risk(pii_found: List[str]) -> str:
    """Classify the compliance risk based on the detected PII categories."""
    if not pii_found:
        return "safe"
    if any(pii_type in pii_found for pii_type in {"aadhaar", "passport"}) and not any(
        pii_type in pii_found for pii_type in {"credit_card", "pan", "phone"}
    ):
        return "critical"
    return "high"
