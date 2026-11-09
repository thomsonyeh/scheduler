import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DIAMOND = {
    "name": "diamond",
    "tasks": [
        {"name": "a", "command": "x"},
        {"name": "b", "depends_on": ["a"]},
        {"name": "c", "depends_on": ["a"]},
        {"name": "d", "depends_on": ["b", "c"]},
    ],
}


@pytest.fixture
def client():
    settings = Settings(database_url="sqlite://", run_orchestrator=False)
    with TestClient(create_app(settings)) as c:
        yield c


def test_create_get_list(client):
    r = client.post("/api/workflows", json=DIAMOND)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["total_tasks"] == 4
    assert body["task_counts"]["PENDING"] == 4
    assert [t["name"] for t in body["tasks"]] == ["a", "b", "c", "d"]
    assert body["created_at"].endswith("Z") or "+00:00" in body["created_at"]

    r = client.get(f"/api/workflows/{body['id']}")
    assert r.status_code == 200
    assert r.json()["tasks"][3]["depends_on"] == ["b", "c"]

    r = client.get("/api/workflows")
    assert [w["id"] for w in r.json()] == [body["id"]]
    assert client.get("/api/workflows", params={"status": "RUNNING"}).json() == []


def test_rejects_cycle(client):
    r = client.post(
        "/api/workflows",
        json={
            "name": "bad",
            "tasks": [{"name": "a", "depends_on": ["b"]}, {"name": "b", "depends_on": ["a"]}],
        },
    )
    assert r.status_code == 422
    assert "dependency cycle" in r.json()["detail"][0]["msg"]


def test_rejects_empty_workflow(client):
    assert client.post("/api/workflows", json={"name": "x", "tasks": []}).status_code == 422


def test_not_found(client):
    assert client.get("/api/workflows/nope").status_code == 404
    assert client.post("/api/workflows/nope/cancel").status_code == 404


def test_cancel(client):
    wf_id = client.post("/api/workflows", json=DIAMOND).json()["id"]
    r = client.post(f"/api/workflows/{wf_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    assert r.json()["task_counts"]["CANCELLED"] == 4
