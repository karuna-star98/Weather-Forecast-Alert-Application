"""API tests - skipped automatically if FastAPI is not installed."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402


def test_health_and_snapshot():
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
        r = c.get("/snapshot", params={"city": "Delhi", "mode": "simulate"})
        assert r.status_code == 200 and "risk" in r.json()
        loc = c.post("/locations", params={"city": "Mumbai"}).json()["location"]["id"]
        assert len(c.get("/forecast/daily", params={"location_id": loc}).json()) >= 1
        assert "alerts" in c.get("/alerts", params={"location_id": loc}).json()
        assert c.get("/forecast/hourly", params={"location_id": 9999}).status_code == 404
