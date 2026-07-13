import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mock_db import find_account, verify_amount, verify_customer


def test_mock_database_lookup_account():
    account = find_account("ACC1023")

    assert account is not None
    assert account["account_id"] == "ACC1023"
    assert account["customer_name"] == "Alice Johnson"
    assert account["status"] == "active"

    assert verify_customer("ACC1023", "Alice Johnson") is True
    assert verify_customer("ACC1023", "Bob Smith") is False

    assert verify_amount("ACC1023", 120.0) is True
    assert verify_amount("ACC1023", 90.0) is False
