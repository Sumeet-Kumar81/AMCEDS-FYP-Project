from fastapi.testclient import TestClient
from app.main import app


def test_health_shape():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["api"] == "ok"


def test_report_requires_description():
    r = TestClient(app).post("/reports", json={"channel": "web"})
    assert r.status_code == 422
