"""Logging helpers for the workflow."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from state.workflow_state import WorkflowState


LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Create and return a configured logger for the given name."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        logger.addHandler(handler)

    return logger


def write_run_log(state: WorkflowState, log_path: Optional[str] = None) -> Path:
    """Write a human-readable execution log for the workflow state."""
    state.ensure_request_id()
    if log_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = str(LOG_DIR / f"run_{timestamp}.log")

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "Execution Summary",
        "=================",
        f"timestamp={datetime.now().isoformat()}",
        f"request_id={state.request_id}",
        f"route={state.route}",
        f"retry_count={state.retry_count}",
        f"validation_status={state.validation_status}",
        f"verification_status={state.verification_status}",
        f"compliance_status={state.compliance_status}",
        "",
        "Execution History",
        "-----------------",
    ]

    for entry in state.execution_history:
        step = entry.get("step", "unknown")
        status = entry.get("status", "unknown")
        details = entry.get("details", "")
        lines.append(f"- {step}: {status}" + (f" | {details}" if details else ""))

    lines.extend([
        "",
        "Final Output",
        "-----------",
        state.final_output or "<empty>",
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def log_run_summary(state: WorkflowState, logger: Optional[logging.Logger] = None) -> Path:
    """Log a workflow summary and persist it to disk."""
    active_logger = logger or get_logger("workflow")
    active_logger.info("route=%s retry_count=%s", state.route, state.retry_count)
    return write_run_log(state)
