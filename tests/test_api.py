import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import create_app
from persistence import SQLiteStore


def test_api_creates_reads_and_resumes_a_complaint(tmp_path):
    store = SQLiteStore(str(tmp_path / "api.db"))
    client = TestClient(create_app(store))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "connected"}

    created = client.post(
        "/complaints",
        json={
            "email": (
                "Hello, my name is Alice Johnson. I was billed $120 but expected "
                "$100 for a billing issue."
            )
        },
    )
    assert created.status_code == 201
    paused = created.json()
    request_id = paused["request_id"]
    assert paused["route"] == "clarify"
    assert paused["missing_fields"] == ["account_id"]

    clarified = client.post(
        f"/complaints/{request_id}/clarification",
        json={"answers": {"account_id": "ACC1023"}},
    )
    assert clarified.status_code == 200
    assert clarified.json()["route"] == "respond"

    fetched = client.get(f"/complaints/{request_id}")
    assert fetched.status_code == 200
    assert fetched.json()["request_id"] == request_id


def test_api_returns_not_found_for_unknown_complaint(tmp_path):
    store = SQLiteStore(str(tmp_path / "api.db"))
    client = TestClient(create_app(store))

    response = client.get("/complaints/REQ-UNKNOWN")

    assert response.status_code == 404
