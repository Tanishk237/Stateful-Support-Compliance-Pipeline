"""Live demo contracts: real node order, resumability, failures, and assets."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import create_app
from graph.workflow import build_workflow_graph
from persistence import SQLiteStore
from service import ComplaintService

EMAIL = "Hello, my name is Alice Johnson. My account ACC1023 was billed $120 but I expected $100 for a duplicate charge."


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("nodes.extract.USE_LLM", False)
    monkeypatch.setattr("nodes.escalation.ESCALATION_DIR", tmp_path)
    return TestClient(create_app(SQLiteStore(str(tmp_path / "stream.db"))))


def events(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return [json.loads(frame[6:]) for frame in response.text.strip().split("\n\n")]


def test_stream_emits_real_order_and_persists_final_state(client):
    output = events(client.post("/complaints/stream", json={"email": EMAIL}))
    assert output[0]["type"] == "request_started"
    expected = ["compliance", "extract", "validate", "verify", "respond"]
    assert [e["step"] for e in output if e["type"] == "step_started"] == expected
    assert [e["step"] for e in output if e["type"] == "step_completed"] == expected
    assert [e["type"] for e in output[1:-1]] == ["step_started", "step_completed"] * 5
    assert all(e["duration_ms"] >= 0 for e in output if e["type"] == "step_completed")
    assert output[-1]["type"] == "complete"
    saved = output[-1]["state"]
    assert saved["route"] == "respond"
    assert client.get(f'/complaints/{saved["request_id"]}').json() == saved


def test_stream_clarification_resumes_at_validation(client):
    output = events(client.post("/complaints/stream", json={"email": EMAIL.replace("My account ACC1023 was", "I was")}))
    state = output[-1]["state"]
    assert state["route"] == "clarify"
    resumed = events(client.post(f'/complaints/{state["request_id"]}/clarification/stream', json={"answers": {"account_id": "ACC1023"}}))
    assert [e["step"] for e in resumed if e["type"] == "step_started"] == ["validate", "verify", "respond"]
    assert resumed[-1]["state"]["route"] == "respond"
    assert resumed[-1]["state"]["request_id"] == state["request_id"]
    assert sum(e["step"] == "extract" for e in resumed[-1]["state"]["execution_history"]) == 1


@pytest.mark.parametrize("email,route,steps", [
    (EMAIL + " My SSN is 123-45-6789.", "compliance_escalation", ["compliance", "compliance_escalation"]),
    (EMAIL.replace("Alice Johnson", "Morgan Reed"), "billing_review", ["compliance", "extract", "validate", "verify", "billing_review"]),
])
def test_stream_alternate_routes(client, email, route, steps):
    output = events(client.post("/complaints/stream", json={"email": email}))
    assert [e["step"] for e in output if e["type"] == "step_started"] == steps
    assert output[-1]["state"]["route"] == route
    if route == "compliance_escalation":
        assert "123-45-6789" not in output[-1]["state"]["redacted_email"]
        assert output[-1]["state"]["extraction_source"] == "pending"


def test_stream_validation_errors_happen_before_headers(client):
    assert client.post("/complaints/stream", json={"email": "  "}).status_code == 422
    assert client.post("/complaints/unknown/clarification/stream", json={"answers": {}}).status_code == 404
    created = client.post("/complaints", json={"email": EMAIL}).json()
    assert client.post(f'/complaints/{created["request_id"]}/clarification/stream', json={"answers": {}}).status_code == 409


def test_node_start_is_emitted_before_handler_finishes(monkeypatch):
    """Prove live start events are not a history reconstructed after completion."""
    import threading

    entered = threading.Event()
    release = threading.Event()
    original = __import__("graph.workflow", fromlist=["evaluate_compliance"]).evaluate_compliance

    def controlled_node(state):
        entered.set()
        assert release.wait(timeout=5)
        return original(state)

    monkeypatch.setattr("graph.workflow.evaluate_compliance", controlled_node)
    monkeypatch.setattr("nodes.extract.USE_LLM", False)
    stream = build_workflow_graph(emit_events=True).stream(ComplaintService.new_state(EMAIL), stream_mode="custom")
    try:
        first = next(stream)
        assert first == {"type": "step_started", "step": "compliance"}
        assert entered.wait(timeout=1)
        assert not release.is_set()
    finally:
        release.set()
        stream.close()


def test_stream_failure_is_an_error_not_a_false_completion(client, monkeypatch):
    def fail(_state):
        raise RuntimeError("sensitive-provider-detail")

    monkeypatch.setattr("graph.workflow.extract_information", fail)
    response = client.post("/complaints/stream", json={"email": EMAIL})
    output = events(response)
    assert output[-1]["type"] == "error"
    assert "sensitive-provider-detail" not in response.text
    assert not any(e["type"] == "complete" for e in output)
    saved = client.get(f'/complaints/{output[0]["request_id"]}').json()
    assert saved["compliance_status"] == "safe"
    assert saved["extraction_source"] == "pending"


def test_frontend_and_config_are_served_without_secrets(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Watch the graph think." in response.text
    for asset in ["app.js", "graph.js", "speech.js", "styles.css", "workflow-sculpture.jpg", "microphone.svg", "space-grotesk.ttf"]:
        assert client.get(f"/assets/{asset}").status_code == 200
    assert set(client.get("/demo-config").json()) == {"llm_enabled"}
