import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import EscalationTicket
from persistence import SQLiteStore
from state.workflow_state import WorkflowState


def test_sqlite_store_persists_state_history_and_ticket(tmp_path):
    database_path = tmp_path / "workflow.db"
    store = SQLiteStore(str(database_path))
    state = WorkflowState(
        request_id="REQ-TEST-1",
        raw_email="Billing complaint",
        route="billing_review",
        escalation_ticket=EscalationTicket(
            ticket_id="T-1000",
            reason="Manual review needed",
            department="billing",
            summary="Amount mismatch",
        ),
        execution_history=[
            {"step": "validate", "status": "passed"},
            {"step": "verify", "status": "mismatch", "details": "AMOUNT_MISMATCH"},
        ],
    )

    store.save_state(state)
    restored = store.get_state("REQ-TEST-1")

    assert restored is not None
    assert restored.route == "billing_review"
    assert restored.execution_history == state.execution_history
    assert restored.escalation_ticket.ticket_id == "T-1000"

    with sqlite3.connect(database_path) as connection:
        history_count = connection.execute(
            "SELECT COUNT(*) FROM execution_history"
        ).fetchone()[0]
        ticket_count = connection.execute(
            "SELECT COUNT(*) FROM escalation_tickets"
        ).fetchone()[0]

    assert history_count == 2
    assert ticket_count == 1


def test_sqlite_store_returns_none_for_unknown_request(tmp_path):
    store = SQLiteStore(str(tmp_path / "workflow.db"))

    assert store.get_state("missing") is None
    assert store.healthcheck() is True
