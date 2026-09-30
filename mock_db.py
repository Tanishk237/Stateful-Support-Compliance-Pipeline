"""Mock billing database used by the verification node."""

from typing import Dict, Optional


CUSTOMER_RECORDS: Dict[str, Dict[str, object]] = {
    "ACC1023": {
        "account_id": "ACC1023",
        "customer_name": "Alice Johnson",
        "actual_bill": 120.0,
        "expected_bill": 100.0,
        "plan": "Premium",
        "status": "active",
    },
    "ACC2045": {
        "account_id": "ACC2045",
        "customer_name": "Ben Carter",
        "actual_bill": 80.0,
        "expected_bill": 60.0,
        "plan": "Basic",
        "status": "active",
    },
}


def find_account(account_id: str) -> Optional[Dict[str, object]]:
    """Return the account record for a given account id, if present."""
    return CUSTOMER_RECORDS.get(account_id)


def verify_customer(account_id: str, customer_name: str) -> bool:
    """Verify that the supplied customer name matches the stored account."""
    account = find_account(account_id)
    if not account:
        return False
    stored_name = str(account.get("customer_name", "")).strip().casefold()
    return stored_name == customer_name.strip().casefold()


def verify_amount(account_id: str, claimed_amount: float) -> bool:
    """Verify that the claimed amount matches the stored bill amount."""
    account = find_account(account_id)
    if not account:
        return False
    return _amounts_match(account.get("actual_bill"), claimed_amount)


def verify_expected_amount(account_id: str, expected_amount: float) -> bool:
    """Verify that the expected amount matches the stored expected bill."""
    account = find_account(account_id)
    if not account:
        return False
    return _amounts_match(account.get("expected_bill"), expected_amount)


def _amounts_match(first: object, second: object) -> bool:
    """Compare currency values at cent precision."""
    try:
        return round(float(first), 2) == round(float(second), 2)
    except (TypeError, ValueError):
        return False
