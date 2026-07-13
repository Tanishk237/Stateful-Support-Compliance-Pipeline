"""Mock billing database used by the verification node."""

from typing import Dict, Optional


CUSTOMER_RECORDS: Dict[str, Dict[str, object]] = {
    "ACC1023": {
        "account_id": "ACC1023",
        "customer_name": "Alice Johnson",
        "actual_bill": 120.0,
        "plan": "Premium",
        "status": "active",
    },
    "ACC2045": {
        "account_id": "ACC2045",
        "customer_name": "Ben Carter",
        "actual_bill": 80.0,
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
    return account.get("customer_name") == customer_name


def verify_amount(account_id: str, claimed_amount: float) -> bool:
    """Verify that the claimed amount matches the stored bill amount."""
    account = find_account(account_id)
    if not account:
        return False
    return float(account.get("actual_bill", 0.0)) == float(claimed_amount)
