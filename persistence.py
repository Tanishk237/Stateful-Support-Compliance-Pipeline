"""Small SQLite persistence layer for workflow runs."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH
from state.workflow_state import WorkflowState


class SQLiteStore:
    """Persist workflow state, execution steps, and escalation tickets."""

    def __init__(self, database_path: Optional[str] = None) -> None:
        self.path = Path(database_path or DATABASE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        """Create the three small tables used by the demo."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_states (
                    request_id TEXT PRIMARY KEY,
                    route TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS execution_history (
                    request_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    step TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    PRIMARY KEY (request_id, step_number),
                    FOREIGN KEY (request_id) REFERENCES workflow_states(request_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS escalation_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    route TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    department TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    ticket_path TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES workflow_states(request_id)
                );
                """
            )

    def save_state(self, state: WorkflowState) -> None:
        """Upsert a complete workflow snapshot and its related records."""
        request_id = state.ensure_request_id()
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_states (
                    request_id, route, state_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    route = excluded.route,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (request_id, state.route, state.model_dump_json(), now, now),
            )

            connection.execute(
                "DELETE FROM execution_history WHERE request_id = ?",
                (request_id,),
            )
            connection.executemany(
                """
                INSERT INTO execution_history (
                    request_id, step_number, step, status, details
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        request_id,
                        index,
                        str(event.get("step", "unknown")),
                        str(event.get("status", "unknown")),
                        str(event.get("details", "")),
                    )
                    for index, event in enumerate(state.execution_history)
                ],
            )

            ticket = state.escalation_ticket
            if ticket.ticket_id:
                connection.execute(
                    """
                    INSERT INTO escalation_tickets (
                        ticket_id, request_id, route, reason, priority,
                        department, summary, ticket_path, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticket_id) DO UPDATE SET
                        route = excluded.route,
                        reason = excluded.reason,
                        priority = excluded.priority,
                        department = excluded.department,
                        summary = excluded.summary,
                        ticket_path = excluded.ticket_path
                    """,
                    (
                        ticket.ticket_id,
                        request_id,
                        state.route,
                        ticket.reason,
                        ticket.priority,
                        ticket.department,
                        ticket.summary,
                        ticket.ticket_path,
                        now,
                    ),
                )

    def get_state(self, request_id: str) -> Optional[WorkflowState]:
        """Load one workflow state by request id."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM workflow_states WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkflowState.model_validate_json(row["state_json"])

    def healthcheck(self) -> bool:
        """Return whether SQLite can answer a simple query."""
        with self._connect() as connection:
            return connection.execute("SELECT 1").fetchone()[0] == 1

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
