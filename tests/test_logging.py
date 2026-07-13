import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from logger import get_logger, log_run_summary, write_run_log
from state.workflow_state import WorkflowState


def test_logger_writes_run_log_with_summary_and_history(tmp_path):
    state = WorkflowState(raw_email="Test email", route="response", retry_count=2)
    state.execution_history = [
        {"step": "extract", "status": "completed"},
        {"step": "validate", "status": "passed"},
    ]

    log_path = tmp_path / "run.log"
    write_run_log(state, str(log_path))

    assert log_path.exists()
    content = log_path.read_text()
    assert "Execution Summary" in content
    assert "extract" in content
    assert "response" in content
    assert "retry_count=2" in content
    assert "request_id=REQ-" in content


def test_get_logger_returns_logger_instance():
    logger = get_logger("test")
    assert logger.name == "test"
